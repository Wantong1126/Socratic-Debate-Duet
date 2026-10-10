"""Single participant audition. Default: the specified human raw replay, no LSL."""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import tomllib
import uuid

import numpy as np

from src.sonification.protocol import OrganismControlSender, OrganismVoicingFrame
from .audition_features import EnergyProcessor, recompute
from .replay_source import RawSampleReplay
from .session_runtime import SessionRuntime
from .session_types import FrameEnvelope
from .session_recorder import SessionRecorder
from .reimagination import (ReimaginationButton as InvitationButton,
    ReimaginationControlMessage as InvitationControlMessage, ReimaginationOscSender as InvitationOscSender,
    ReimaginationEnvelopeController as InvitationEnvelopeController,
    ReimaginationEnvelopeConfig as InvitationEnvelopeConfig, sample_dict)
from .music_mapping import CANDIDATES, MUSIC_ADDRESS, MusicMapping, load_config, music_packet, manual_trajectory, display_parameters

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDITION_OSC_PORT = 57120
DEFAULT_AUDITION_SERVER_PORT = 57130


def find_sclang():
    options = [os.environ.get('SDD_SCLANG'), shutil.which('sclang'),
        r'D:\OpenBCI\supercollider\sclang.exe', r'C:\Program Files\SuperCollider-3.14.1\sclang.exe']
    for p in options:
        if p and Path(p).is_file():
            return str(p)
    raise RuntimeError('sclang not found; set SDD_SCLANG to the existing installation')


def prepare_replay(directory, start, clock=time.monotonic, input_name='f3_energy'):
    source = RawSampleReplay(directory, clock=clock)
    if not 0 <= start < source.relative[-1]:
        raise ValueError('fragment start is outside the recording')
    processor = EnergyProcessor(source.metadata['config'], source.sample_rate, input_name)
    end = int(np.searchsorted(source.relative, start))
    processor.add(source.samples[:end], source.relative[:end])
    if not processor.rows or not processor.rows[-1]['valid']:
        raise ValueError(f'fragment must follow valid personal calibration for {input_name}; choose --start >= 52')
    source.index = end
    source.started = clock()-start
    return source, processor


def _udp_port_available(port):
    """Check whether a localhost UDP port can be used by a new receiver."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(('127.0.0.1', port))
    except OSError:
        return False
    return True


def receiver_port_candidates():
    """Yield isolated OSC/scsynth port pairs, preferring the documented defaults."""
    # Keep each pair in its own small block.  This permits a fresh audition to
    # run even when an interrupted older SuperCollider process still owns the
    # default 57120/57130 pair.
    for offset in range(64):
        osc_port = DEFAULT_AUDITION_OSC_PORT + offset * 20
        server_port = DEFAULT_AUDITION_SERVER_PORT + offset * 20
        if _udp_port_available(osc_port) and _udp_port_available(server_port):
            yield osc_port, server_port


def _terminate_receiver(process):
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def start_receiver(log_path):
    candidates = iter(receiver_port_candidates())
    for attempt in range(1, 65):
        try:
            osc_port, server_port = next(candidates)
        except StopIteration as exc:
            raise RuntimeError('no free UDP port pair available for SuperCollider audition') from exc
        log = log_path.open('w' if attempt == 1 else 'a', encoding='utf-8')
        log.write(f'RECEIVER_START attempt={attempt} osc_port={osc_port} server_port={server_port}\n')
        log.flush()
        environment = dict(os.environ, SDD_AUDITION_OSC_PORT=str(osc_port),
            SDD_AUDITION_SERVER_PORT=str(server_port))
        process = subprocess.Popen([find_sclang(), '-D', 'scripts/run_mapping_audition.scd'],
            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=environment,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        deadline = time.monotonic()+40
        while True:
            output = log_path.read_text(encoding='utf-8', errors='replace')
            if 'MAPPING_AUDITION_READY' in output:
                return process, log, osc_port, server_port
            # A different local process may bind one of the ports after the
            # availability check.  Retry on a fresh pair instead of making the
            # operator find and kill an unrelated receiver.
            port_conflict = ('Could not open UDP port' in output
                or 'Could not bind to requested port' in output)
            if port_conflict:
                _terminate_receiver(process)
                log.close()
                break
            if process.poll() is not None or time.monotonic() > deadline:
                _terminate_receiver(process)
                log.close()
                raise RuntimeError(f'receiver did not start; see {log_path}')
            time.sleep(.1)
    raise RuntimeError(f'receiver could not reserve an isolated UDP port pair; see {log_path}')


def keypress():
    if os.name == 'nt':
        import msvcrt
        return msvcrt.getwch().lower() if msvcrt.kbhit() else None
    return None


class EyesOpenClosedCheck:
    """Condition markers only; they never change a feature or music value."""
    phases = ('eyes_open', 'eyes_closed') * 3

    def __init__(self, seconds=20.0):
        self.seconds, self.index, self.started = float(seconds), -1, None

    @property
    def current(self):
        return None if self.index < 0 or self.index >= len(self.phases) else self.phases[self.index]

    @property
    def complete(self):
        return self.index >= len(self.phases)

    def advance(self, now, ready):
        """Return newly entered markers. Start only after valid alpha exists."""
        markers = []
        if self.started is None:
            if not ready:
                return markers
            self.started, self.index = now, 0
            return [(self.current, now)]
        while not self.complete and now - self.started >= (self.index + 1) * self.seconds:
            self.index += 1
            if not self.complete:
                markers.append((self.current, self.started + self.index * self.seconds))
        return markers


def run(args, config):
    # Validate ownership and raw data before opening any sound device.
    if args.input == 'posterior_alpha' and (args.candidate != 'brightness' or args.mode == 'manual'):
        raise ValueError('posterior_alpha is available only for replay/live and routes only to the approved brightness candidate')
    if args.alpha_check_output and (args.mode != 'live' or args.input != 'posterior_alpha' or args.candidate != 'brightness'):
        raise ValueError('--alpha-check-output requires --mode live --input posterior_alpha --candidate brightness')
    mapping = MusicMapping(args.candidate, config, invitation=args.invitation, diagnostic=args.diagnostic)
    source = processor = inlet = None
    if args.mode == 'replay':
        source, processor = prepare_replay(args.session, args.start, input_name=args.input)
        if args.start+args.duration > source.relative[-1]:
            raise ValueError('requested fragment extends past the actual raw recording')
        print('SOURCE replay raw recomputation: ' + str(args.session), flush=True)
        print(json.dumps(source.audit), flush=True)
    elif args.mode == 'live':
        if not args.confirm_live_hardware or not args.stream_name:
            raise ValueError('live requires --stream-name and --confirm-live-hardware; GUI Raw/uV montage must match config/live_eeg.toml')
        from src.window_engine import connect_openbci_lsl, describe_lsl_stream
        from .live_eeg import _unit
        inlet, info, rate = connect_openbci_lsl(5, stream_name=args.stream_name)
        metadata = describe_lsl_stream(info)
        if metadata.channel_count != 8:
            raise ValueError('live audition requires exactly eight channels')
        if any(u.lower() != 'unknown' and _unit(u) != 'uV' for u in metadata.channel_units):
            raise ValueError('live metadata units conflict with confirmed uV configuration')
        processor = EnergyProcessor(tomllib.loads((ROOT/'config/live_eeg.toml').read_text(encoding='utf-8')), rate, args.input)
        correction = inlet.time_correction(timeout=2)
        print('SOURCE live '+json.dumps(asdict(metadata))+'; 30s settling + 2s window + 20s baseline; input='+args.input, flush=True)
    else:
        print('SOURCE manual; keyboard amount or deterministic low-middle-high-low trajectory', flush=True)
    directory = ROOT/config['output_directory']/time.strftime('session_%Y%m%d_%H%M%S')
    directory.mkdir(parents=True, exist_ok=False)
    session_config = dict(config, mode=args.mode, candidate=args.candidate, input=args.input,
        input_session=str(args.session), fragment_start=args.start, reimagination=args.invitation)
    (directory/'config.json').write_text(json.dumps(session_config, indent=2), encoding='utf-8')
    process, receiver_log, osc_port, server_port = start_receiver(directory/'receiver.log')
    session_config['receiver_transport'] = dict(host='127.0.0.1', osc_port=osc_port,
        server_port=server_port)
    (directory/'config.json').write_text(json.dumps(session_config, indent=2), encoding='utf-8')
    print(f'RECEIVER control UDP {osc_port}; SuperCollider server UDP {server_port}', flush=True)
    sender = OrganismControlSender(port=osc_port)
    sid = 'audition-'+uuid.uuid4().hex[:12]
    alpha_check = EyesOpenClosedCheck() if args.alpha_check_output else None
    recorder = None
    alpha_check_alpha_rows, alpha_check_music_rows = [], []
    if alpha_check:
        recorder = SessionRecorder(args.alpha_check_output, session_id=sid, config=session_config,
            code_version={'entry': 'src.sdd.mapping_audition', 'input': 'posterior_alpha'},
            source={'mode': 'live', 'real_eeg': True, 'stream_name': args.stream_name}, seed=None,
            monotonic_origin=time.monotonic(), wall_origin=time.time(), allow_live_recording=True)
        print('ALPHA CHECK: after calibration, follow each prompt for 20 seconds: OPEN, CLOSED, repeated three times. Markers only label conditions; they do not control sound.', flush=True)
    controller = InvitationEnvelopeController(InvitationEnvelopeConfig(**config['reimagination']))
    runtime = SessionRuntime(sender, session_id=sid, invitation_controller=controller,
        rate=config['control_hz'])
    invitation_sender = InvitationOscSender(client=sender.client)
    button = InvitationButton(session_id=sid, source=args.reimagination_source, target='A',
        prompt_id='question_weighing_criterion', clock=lambda: now)
    frame_seq = music_seq = invitation_seq = 0
    previous_voicing = None
    voicing_at = -1e9
    last_feature = last_feature_at = None
    last_row_count = len(processor.rows) if processor else 0
    started = time.monotonic()
    action_started = started
    actions = json.loads(args.actions.read_text(encoding='utf-8')) if args.actions else []
    action_index = 0
    if source:
        source.started = started-args.start
    paused, ended, manual_amount = False, False, None
    paused_since = None
    last_print, next_manual, last_event, term_index = -1e9, started, None, 0
    pending_candidate = None
    recorded_feature_count = 0

    def record_feature_rows():
        """Persist each alpha result, including invalid windows, only when opted in."""
        nonlocal recorded_feature_count
        if not recorder:
            return
        for row in processor.rows[recorded_feature_count:]:
            data = {key: value for key, value in row.items() if key not in ('t',)}
            for key, value in list(data.items()):
                if isinstance(value, float) and not np.isfinite(value):
                    data[key] = None
            data['condition'] = alpha_check.current
            recorder.write('posterior_alpha', time.monotonic(), data, live=True)
            alpha_check_alpha_rows.append((alpha_check.index, alpha_check.current, data))
        recorded_feature_count = len(processor.rows)

    def save_alpha_check_summary():
        if not recorder:
            return
        rounds = []
        for index, condition in enumerate(EyesOpenClosedCheck.phases):
            alpha = [row for phase, _, row in alpha_check_alpha_rows if phase == index]
            music = [row for phase, _, row in alpha_check_music_rows if phase == index]
            valid = [row for row in alpha if row['valid']]
            amounts = [row['amount'] for row in valid]
            powers = [row['raw_posterior_alpha_uv2'] for row in valid]
            groups = {f'musicGroup{i}': [row['controls'][f'musicGroup{i}'] for row in music] for i in range(1, 5)}
            span = lambda values: None if not values else [float(min(values)), float(np.median(values)), float(max(values))]
            rounds.append({'round': index // 2 + 1, 'condition': condition,
                'windows_total': len(alpha), 'windows_valid': len(valid),
                'posterior_alpha_uv2_min_median_max': span(powers),
                'amount_min_median_max': span(amounts),
                'brightness_groups_min_max': {name: None if not values else [float(min(values)), float(max(values))] for name, values in groups.items()}})
        output = Path(args.alpha_check_output)/'alpha_check_summary.json'
        output.write_text(json.dumps({'input': 'posterior_alpha', 'unit': 'uV^2',
            'protocol': 'eyes_open_20s, eyes_closed_20s, repeated three times; markers do not control sound',
            'rounds': rounds}, indent=2), encoding='utf-8')
        for row in rounds:
            print('ALPHA SUMMARY round={round} condition={condition} valid={windows_valid}/{windows_total} alpha={posterior_alpha_uv2_min_median_max} amount={amount_min_median_max} brightness={brightness_groups_min_max}'.format(**row), flush=True)
    print('KEYS 1 level | 2 melody | 3 brightness | 4 sound colour | 5 harmony', flush=True)
    print('SPACE pause/resume | R repeat/reset | V enable/disable reimagination | I reimagine | E end | D decline | Q stop | +/- manual amount | T trajectory', flush=True)
    print('Reimagination '+('enabled' if args.invitation else 'disabled; restart with --reimagination on a compatible candidate or press V'), flush=True)
    try:
        with (directory/'controls.jsonl').open('w', encoding='utf-8') as log:
            def write(kind, data):
                log.write(json.dumps(dict(kind=kind, data=data), allow_nan=False)+'\n')
                log.flush()
            while True:
                now = time.monotonic()
                if process.poll() is not None:
                    raise RuntimeError('SuperCollider exited during audition')
                key = keypress()
                if action_index < len(actions) and now-action_started >= actions[action_index]['at']:
                    key = actions[action_index]['key']
                    print('SCRIPTED_KEY '+repr(key), flush=True)
                    action_index += 1
                if key == 'q':
                    break
                if key == 'v':
                    sample = controller.advance('A', now)
                    if sample.invitation_amount > 0 or sample.phase in ('attack', 'hold', 'release'):
                        print('End the current reimagination with E and wait for release before toggling.', flush=True)
                    else:
                        try:
                            MusicMapping(mapping.candidate, config, invitation=not args.invitation, diagnostic=args.diagnostic)
                        except ValueError as exc:
                            print(exc, flush=True)
                        else:
                            args.invitation = not args.invitation
                            mapping.invitation = args.invitation
                            print('Reimagination '+('enabled' if args.invitation else 'disabled'), flush=True)
                if key and key in '12345':
                    candidate = CANDIDATES[int(key)-1]
                    try:
                        MusicMapping(candidate, config, invitation=args.invitation, diagnostic=args.diagnostic)
                    except ValueError as exc:
                        print(exc, flush=True)
                    else:
                        pending_candidate = candidate
                        key = 'r'
                if key == 'r':
                    # Pause transport during causal pre-roll; no packet catch-up.
                    controller.pause('A', now)
                    if source:
                        source, processor = prepare_replay(args.session, args.start, input_name=args.input)
                    elif processor:
                        processor = EnergyProcessor(processor.config, processor.sample_rate, args.input)
                        inlet.flush()
                    started = time.monotonic()
                    if source:
                        source.started = started-args.start
                    now = started
                    paused = ended = False
                    paused_since = None
                    last_feature = last_feature_at = None
                    last_row_count = len(processor.rows) if processor else 0
                    recorded_feature_count = 0
                    mapping = MusicMapping(pending_candidate or mapping.candidate, config,
                        invitation=args.invitation, diagnostic=args.diagnostic)
                    pending_candidate = None
                    previous_voicing = None
                    print('RESTART reset filters/window/calibration/smoothing; candidate='+mapping.candidate, flush=True)
                if key == ' ':
                    paused = not paused
                    if paused:
                        paused_since = now
                        controller.pause('A', now)
                        if source:
                            source.pause()
                    else:
                        started += now-paused_since
                        if source:
                            source.resume()
                        if inlet:
                            inlet.flush()
                            processor = EnergyProcessor(processor.config, processor.sample_rate, args.input)
                            last_row_count = 0
                            recorded_feature_count = 0
                    print('PAUSED' if paused else 'RESUMED', flush=True)
                if key in ('+', '-') and args.mode == 'manual':
                    manual_amount = min(1, max(0, (.5 if manual_amount is None else manual_amount)+(.1 if key == '+' else -.1)))
                if key == 't':
                    manual_amount = None
                if key == 'i' and args.invitation and not paused and not ended:
                    event = button.press()
                    accepted = controller.invite(event)
                    write('reimagination_event', dict(event.to_dict(), accepted=accepted))
                    if accepted:
                        last_event = event
                    print(f'BUTTON PRESSED source={event.source} target=A accepted={accepted}', flush=True)
                if key in ('e', 'd'):
                    (controller.end if key == 'e' else controller.decline)('A', now)
                elapsed = now-started
                if not paused and not ended:
                    if source:
                        samples, original, relative = source.poll_samples()
                        processor.add(samples, relative)
                        if len(processor.rows) > last_row_count:
                            last_feature = processor.rows[-1]
                            last_feature_at = source.started+last_feature['t']
                            last_row_count = len(processor.rows)
                        elapsed = now-source.started-args.start
                    elif inlet:
                        from pylsl import local_clock
                        samples, stamps = inlet.pull_chunk(timeout=0, max_samples=256)
                        if samples:
                            age = local_clock()-(float(stamps[-1])+correction)
                            if not np.isfinite(age) or not 0 <= age <= .5:
                                processor = EnergyProcessor(processor.config, processor.sample_rate, args.input)
                                last_row_count = 0
                                recorded_feature_count = 0
                                last_feature = last_feature_at = None
                            else:
                                data, stamp = np.asarray(samples), np.asarray(stamps)
                                if recorder:
                                    recorder.raw(at=now, sampled_at=stamp.tolist(), samples=data.tolist(), sample_rate=rate,
                                        channels=['F3','F4','C3','C4','P3','P4','vertical_EOG','jaw_EMG'], units=['uV']*8,
                                        mode='live', participant_id='A')
                                processor.add(data, stamp)
                                record_feature_rows()
                                if len(processor.rows) > last_row_count:
                                    last_feature = processor.rows[-1]
                                    last_feature_at = now-max(0, local_clock()-(last_feature['t']+correction))
                                    last_row_count = len(processor.rows)
                    elif now >= next_manual:
                        last_feature = dict(valid=True, amount=manual_trajectory(elapsed, args.duration) if manual_amount is None else manual_amount)
                        last_feature_at = now
                        next_manual = now+1/config['control_hz']
                    # poll_samples and causal processing take time. Received-at
                    # must be sampled afterwards, not before the last due sample.
                    now = time.monotonic()
                    elapsed = now-source.started-args.start if source else now-started
                    healthy = last_feature is not None and last_feature['valid'] and 0 <= now-last_feature_at <= .5
                    if healthy:
                        if last_feature_at > runtime.last_sampled:
                            runtime.offer(FrameEnvelope(sid, 'A', frame_seq, last_feature_at, now,
                                'fixture' if args.mode == 'manual' else args.mode, tuple(config['fixed_frame'])))
                            frame_seq += 1
                        result = mapping.update(last_feature['amount'], elapsed)
                        sender.client.send_message(MUSIC_ADDRESS, music_packet(sid, music_seq, result['controls']))
                        if recorder:
                            recorder.write('music_control', now, {
                                'input': 'posterior_alpha', 'amount': last_feature['amount'],
                                'controls': result['controls'], 'candidate': result['candidate'],
                                'processing_latency_seconds': max(0.0, now-last_feature_at),
                                'processing_support_seconds': last_feature.get('processing_support_seconds'),
                            }, live=True)
                            alpha_check_music_rows.append((alpha_check.index, alpha_check.current, dict(
                                controls=result['controls'])))
                        music_seq += 1
                        voicing = (tuple(result['frequencies_hz']), tuple(result['note_weights']))
                        if voicing != previous_voicing and now-voicing_at >= 1.5:
                            sender.send_voicing(OrganismVoicingFrame.from_active(*voicing))
                            previous_voicing, voicing_at = voicing, now
                            write('voicing_applied', dict(at=elapsed, frequencies_hz=voicing[0], weights=voicing[1]))
                            print(f'VOICING applied_at={elapsed:.2f}s Hz={voicing[0]} note_weights={voicing[1]} crossfade_s=1.35', flush=True)
                        if now-last_print >= .5:
                            write('music', dict(result, source=args.mode, raw_feature=last_feature,
                                sampled_at_playback=last_feature_at, sent_at=now))
                            feature_text = ''
                            if args.input == 'posterior_alpha':
                                feature_text = (f" posterior_alpha_uv2={last_feature.get('raw_posterior_alpha_uv2')}"
                                    f" P3={last_feature.get('alpha_p3_uv2')} P4={last_feature.get('alpha_p4_uv2')}"
                                    f" quality={last_feature.get('quality')}")
                            print(f'{args.mode} {mapping.candidate} input={args.input} amount={result["amount"]:.3f} state={result["state"]} t={elapsed:.2f}s parameters={display_parameters(result)}{feature_text}', flush=True)
                            last_print = now
                    else:
                        runtime.latest = None
                    if alpha_check:
                        for condition, marker_at in alpha_check.advance(now, healthy):
                            recorder.write('task_marker', now, {'condition': condition, 'scheduled_at_monotonic': marker_at}, live=True)
                            print('ALPHA CHECK MARKER '+condition.upper()+'; keep this condition for 20 seconds.', flush=True)
                        if alpha_check.complete:
                            print('ALPHA CHECK COMPLETE; stopping after six recorded conditions.', flush=True)
                            break
                    if elapsed >= args.duration and (args.mode != 'live' or args.once):
                        if args.once:
                            break
                        ended = True
                        controller.end('A', now)
                        print('FRAGMENT COMPLETE; R repeat, 1–8 switch/repeat, Q stop', flush=True)
                runtime.tick()
                now = time.monotonic()
                sample = controller.advance('A', now)
                if last_event:
                    invitation_sender.send(InvitationControlMessage(sid, last_event.event_id, 'A', invitation_seq,
                        now, sample.invitation_amount), now=now)
                    invitation_seq += 1
                    write('reimagination_control', sample_dict(sample))
                    if invitation_seq % 10 == 0:
                        print(f'REIMAGINATION source={sample.source} target=A phase={sample.phase} amount={sample.invitation_amount:.3f} upper_shift_semitones={sample.invitation_amount*config["reimagination_semitones"]:.3f}', flush=True)
                for termination in controller.terminations[term_index:]:
                    write('reimagination_termination', asdict(termination))
                    print('REIMAGINATION '+termination.reason, flush=True)
                term_index = len(controller.terminations)
                time.sleep(.05)
    finally:
        runtime.stop('stopped')
        if inlet:
            inlet.close_stream()
        if recorder:
            save_alpha_check_summary()
            recorder.close()
        sender.close()
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
        controller.advance('A', time.monotonic())
        (directory/'terminations.json').write_text(json.dumps([asdict(v) for v in controller.terminations], indent=2), encoding='utf-8')
        receiver_log.close()
    if process.returncode != 0:
        raise RuntimeError(f'receiver exit {process.returncode}; inspect {directory}')
    print('STOPPED; logs='+str(directory), flush=True)


def main(argv=None):
    os.chdir(ROOT)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='config/mapping_audition.json')
    parser.add_argument('--mode', choices=('manual', 'replay', 'live'), default='replay')
    parser.add_argument('--candidate', choices=CANDIDATES, default='colour')
    parser.add_argument('--input', choices=EnergyProcessor.INPUTS, default='f3_energy',
        help='f3_energy (existing) or posterior_alpha (P3/P4 absolute 8-13 Hz power)')
    parser.add_argument('--session', type=Path)
    parser.add_argument('--start', type=float)
    parser.add_argument('--duration', type=float)
    parser.add_argument('--reimagination', '--invitation', dest='invitation', action='store_true')
    parser.add_argument('--reimagination-source', choices=('audience','peer_A','peer_B','operator'), default='operator')
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--actions', type=Path, help='explicit scripted keyboard actions for reproducible diagnostics')
    parser.add_argument('--inspect', action='store_true')
    parser.add_argument('--render-all', action='store_true')
    parser.add_argument('--stream-name')
    parser.add_argument('--confirm-live-hardware', action='store_true')
    parser.add_argument('--alpha-check-output', type=Path,
        help='explicitly save a live 3x open/closed-eyes posterior-alpha check here')
    args = parser.parse_args(argv)
    config = load_config(args.config)
    args.session = args.session or Path(config['session'])
    args.start = config['fragment_start_seconds'] if args.start is None else args.start
    args.duration = config['fragment_seconds'] if args.duration is None else args.duration
    if not np.isfinite([args.start, args.duration]).all() or args.start < 0 or args.duration <= 0:
        parser.error('start/duration must be finite, start >= 0 and duration > 0')
    config = dict(config, fragment_start_seconds=args.start,
        fragment_seconds=args.duration, session=str(args.session))
    if args.render_all and args.input != 'f3_energy':
        parser.error('--render-all currently renders the established F3 trace only; use replay for posterior_alpha')
    if args.inspect or args.render_all:
        source, rows, audit = recompute(args.session, args.input)
        output = ROOT/config['output_directory']
        output.mkdir(parents=True, exist_ok=True)
        audit_name = 'raw_audit.json' if args.input == 'f3_energy' else f'{args.input}_raw_audit.json'
        (output/audit_name).write_text(json.dumps(audit, indent=2), encoding='utf-8')
        print(json.dumps(audit, indent=2))
        if args.render_all:
            from .mapping_render import render_all
            render_all(config, rows, output, args.session)
    else:
        run(args, config)


if __name__ == '__main__':
    main()
