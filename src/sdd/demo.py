"""Reproduce T02-T09 control fixture or explicit control replay. Default: dry-run."""
import argparse
from dataclasses import replace
import json
import hashlib
from pathlib import Path
import subprocess
import time
import tomllib

from src.sonification.controls import single_dimension_baseline
from src.sonification.protocol import OrganismControlSender, OrganismVoicingFrame
from .fixture_source import control_fixture
from .replay_source import ReplaySource
from .session_recorder import SessionRecorder
from .session_runtime import SessionRuntime
from .session_types import FrameEnvelope


class DryClient:
    def __init__(self):
        self.messages = []

    def send_message(self, address, values):
        self.messages.append((address, values))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('config/sdd_v1.toml'))
    parser.add_argument('--output', type=Path, required=True, help='new recording directory')
    parser.add_argument('--send', action='store_true', help='actually send to running v2 receiver')
    parser.add_argument('--replay', type=Path, help='control replay; raw never substituted')
    parser.add_argument('--allow-live-recording', action='store_true',
                        help='explicitly allow copying recordings with real EEG provenance')
    parser.add_argument('--dropout', nargs=2, type=float, metavar=('START', 'END'))
    args = parser.parse_args(argv)
    config = tomllib.loads(args.config.read_text(encoding='utf-8'))
    settings, mapping = config['session'], config['mapping']
    client = None if args.send else DryClient()
    sender = OrganismControlSender(**config['transport'], client=client)
    virtual = [0.0]
    clock = time.monotonic if args.send else lambda: virtual[0]
    origin = clock()
    replay = ReplaySource(args.replay, mode='control', clock=clock) if args.replay else None
    session_id = args.output.name
    original_source = replay.metadata['source'] if replay else {}
    real_eeg = original_source.get('real_eeg', original_source.get('mode') == 'live')
    source = dict(mode='replay' if replay else 'fixture', kind='control', real_eeg=real_eeg,
                  replay_mode='control' if replay else None,
                  original_metadata=replay.metadata if replay else None,
                  dropout=args.dropout)
    version = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain'], text=True)
    snapshot_paths = [args.config, Path('config/eeg_organism_v2.scd'),
                      Path('sound/eeg_harmonics_manual_config.scd')]
    config['snapshots'] = {str(p): p.read_text(encoding='utf-8') for p in snapshot_paths}
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
              for base in ('src/sdd', 'src/sonification', 'sound')
              for p in Path(base).glob('*') if p.suffix in ('.py', '.scd')}
    with SessionRecorder(args.output, session_id=session_id, config=config,
                         code_version=dict(head=version, worktree=dirty, sha256=hashes), source=source,
                         seed=replay.metadata['seed'] if replay else settings['seed'],
                         monotonic_origin=origin, wall_origin=time.time(),
                         allow_live_recording=args.allow_live_recording) as recorder:
        runtime = SessionRuntime(sender, session_id=session_id,
                                 participant_id=settings['participant_id'],
                                 rate=settings['control_hz'], max_age=settings['max_age_seconds'],
                                 clock=clock, recorder=recorder,
                                 mapping=lambda frame: single_dimension_baseline(frame,
                                     field=mapping['field'], fixed=mapping['fixed']))
        fixtures = list(control_fixture(session_id=session_id,
            participant_id=settings['participant_id'], duration=settings['duration'],
            rate=settings['control_hz'], field=mapping['field'], levels=mapping['levels'],
            fixed=mapping['fixed'], dropout=[args.dropout] if args.dropout else (), origin=origin))
        index = 0
        duration = max((row['t'] for row in replay.rows), default=0)+1/settings['control_hz'] if replay else settings['duration']
        sender.send_voicing(OrganismVoicingFrame.from_active(mapping['frequencies_hz'], mapping['weights']))
        try:
            while clock()-origin < duration-1e-8:
                now = clock()
                due = []
                if replay:
                    for row in replay.poll():
                        if row['kind'] == 'frame':
                            original = FrameEnvelope(**row['data'])
                            age = original.received_at-original.sampled_at
                            due.append(replace(original, session_id=session_id, mode='replay',
                                               sampled_at=replay.started+row['t']-age, received_at=now))
                        else:
                            recorder.write('event', now, {**row['data'], 'at': now,
                                'session_id': session_id, 'original_t': row['t']})
                else:
                    while index < len(fixtures) and fixtures[index].sampled_at <= now+1e-8:
                        due.append(fixtures[index])
                        index += 1
                if due:
                    frame = replace(due[-1], received_at=now)
                    runtime.offer(frame)
                runtime.tick()
                if args.send:
                    time.sleep(0.01)
                else:
                    virtual[0] += 1/settings['control_hz']
        except KeyboardInterrupt:
            runtime.stop('keyboard_interrupt')
        finally:
            runtime.stop('completed')
            sender.close()
    print(json.dumps(dict(source=source['mode'], real_eeg=real_eeg, sent=args.send,
                          frames=sender.frame_count, output=str(args.output))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
