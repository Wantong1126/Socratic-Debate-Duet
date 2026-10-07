"""Reproducible NRT scores through the same harmonic SynthDef as the receiver."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
from scipy.io import wavfile
from .music_mapping import CANDIDATES, MUSIC_FIELDS, MusicMapping, manual_trajectory
from .reimagination import (ReimaginationButton as InvitationButton,
    ReimaginationEnvelopeConfig as InvitationEnvelopeConfig,
    ReimaginationEnvelopeController as InvitationEnvelopeController, sample_dict)


def make_trace(candidate, config, rows, *, source='manual', comparison=None):
    invitation = comparison in ('reimagination_only', 'combined')
    mapping = MusicMapping(candidate, config, invitation=invitation)
    controller = InvitationEnvelopeController(InvitationEnvelopeConfig(**config['reimagination']))
    event = None
    trace, events = [], []
    duration, start = config['fragment_seconds'], config['fragment_start_seconds']
    times = np.asarray([r['t'] for r in rows])
    for step in range(round(duration*20)+1):
        t = step/20
        if source == 'manual':
            amount, valid, raw = manual_trajectory(t, duration), True, None
        else:
            index = int(np.searchsorted(times, start+t, side='right'))-1
            if index < 0:
                raise ValueError('fragment precedes raw feature calculation')
            raw = rows[index]
            amount, valid = raw['amount'], raw['valid'] and 0 <= start+t-raw['t'] <= .5
        if comparison == 'reimagination_only':
            amount = .5
        if invitation and event is None and t >= 7:
            button = InvitationButton(session_id='render-'+source, source='operator', target='A',
                prompt_id='question_weighing_criterion', clock=lambda: t,
                id_factory=lambda: 'explicit-render-button-1')
            event = button.press()
            controller.invite(event)
            events.append(event.to_dict())
        if not valid:
            controller.signal_loss('A', t)
        sample = controller.advance('A', t)
        result = mapping.update(amount, t)
        trace.append(dict(result, t=t, valid=bool(valid), source=source,
            source_playhead_seconds=start+t if source == 'replay' else None,
            feature_relative_seconds=raw['t'] if raw is not None else None,
            raw_energy_uv2=None if raw is None else raw['raw_energy_uv2'],
            reimagination=sample_dict(sample)))
    return dict(candidate=candidate, source=source, comparison=comparison, config=config,
        reimagination_events=events, terminations=[asdict(v) for v in controller.terminations], frames=trace)


def sc_atom(value):
    if isinstance(value, str):
        return json.dumps(value.replace('\\', '/'), ensure_ascii=True)
    if isinstance(value, (list, tuple)):
        return '['+', '.join(sc_atom(v) for v in value)+']'
    return repr(float(value)) if isinstance(value, (np.floating, float)) else str(value)


def score_for(trace):
    c = trace['config']
    score = [[.01, ['s_new', 'mappingRender', 1000, 0, 0,
        'masterEnergy', c['fixed_frame'][0], 'transportAlive', 1, 'musicEnabled', 1]]]
    score += [[.02, ['n_setn', 1000, 'groupAmplitudes', 4, *c['fixed_frame'][5:]]]]
    previous, bank, voicing_at = None, 1, -1e9
    for row in trace['frames']:
        t = .04+row['t']
        controls = row['controls']
        message = ['n_set', 1000, 'transportAlive', int(row['valid']),
            'invitationAmount', row['reimagination']['reimagination_amount']]
        names = {'musicReverbMix': 'reverbMix', 'musicReverbTime': 'reverbTime'}
        for name in MUSIC_FIELDS:
            if not name.startswith('musicGroup') and name != 'musicTempo':
                message += [names.get(name, name), controls[name]]
        score.append([t, message])
        score.append([t, ['n_setn', 1000, 'musicGroups', 4, *[controls[f'musicGroup{i+1}'] for i in range(4)]]])
        voicing = (row['frequencies_hz'], row['note_weights'])
        if voicing != previous and row['t']-voicing_at >= 1.5:
            bank = 1-bank
            suffix = 'A' if bank == 0 else 'B'
            score += [[t, ['n_setn', 1000, 'voiceFrequencies'+suffix, 6, *voicing[0], *([65.41]*(6-len(voicing[0])))]],
                [t, ['n_setn', 1000, 'voiceWeights'+suffix, 6, *voicing[1], *([0]*(6-len(voicing[1])))]] ,
                [t, ['n_set', 1000, 'voicingBank', bank]]]
            previous, voicing_at = voicing, row['t']
    stop = c['fragment_seconds']+.1
    score += [[stop, ['n_set', 1000, 'transportAlive', 0]],
        [stop+.6, ['n_set', 1000, 'gate', 0]], [stop+3.3, ['c_set', 0, 0]]]
    return score, stop+3.3


def render_all(config, rows, output, session):
    from .mapping_audition import find_sclang, ROOT
    traces = {}
    for source in ('manual', 'replay'):
        for candidate in CANDIDATES:
            traces[source+'_'+candidate] = make_trace(candidate, config, rows, source=source)
    for comparison in ('physiology_only', 'reimagination_only', 'combined'):
        traces['compare_'+comparison] = make_trace('colour', config, rows, source='replay', comparison=comparison)
    jobs, manifest = [], {}
    for name, trace in traces.items():
        trace['input_session'] = str(session) if trace['source'] == 'replay' else None
        (output/(name+'.json')).write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding='utf-8')
        score, duration = score_for(trace)
        jobs.append([str(output/(name+'.wav')), duration, score])
        manifest[name] = dict(source=trace['source'], input_session=trace['input_session'],
            candidate=trace['candidate'], comparison=trace['comparison'], seconds=duration,
            input_sha256=hashlib.sha256(json.dumps([r['amount'] for r in trace['frames']]).encode()).hexdigest(),
            node_allocations=sum(row[1][0] == 's_new' for row in score),
            human_audition='pending')
    script = '''(
var root, library, config, preset, definition, jobs, runJob, index, options;
root = ROOT;
thisProcess.interpreter.executeFile(root +/+ "sound/eeg_harmonic_field_v2_core.scd");
library = thisProcess.interpreter.executeFile(root +/+ "sound/eeg_harmonics_manual_config.scd");
config = thisProcess.interpreter.executeFile(root +/+ "config/eeg_organism_v2.scd");
preset = library[\\presets][config[\\basePreset]].copy;
config[\\synthOverrides].keysValuesDo { |key,value| preset[key]=value };
preset[\\harmonicGroups] = config[\\harmonicGroups];
preset[\\voiceCapacity] = config[\\voiceCapacity];
preset[\\auditionColours] = true;
config[\\betaProfiles][config[\\betaProfile]].keysValuesDo { |key,value| preset[key]=value };
definition = ~makeEegOrganismV2HarmonicFieldSynthDef.value(\\mappingRender, preset);
jobs = JOBS;
options = ServerOptions.new;
options.numOutputBusChannels=2; options.numInputBusChannels=0;
options.sampleRate=48000; options.memSize=262144; options.numWireBufs=1024;
index=0;
runJob = {
    var job, score;
    if(index >= jobs.size) { "ALL_MAPPING_RENDERS_COMPLETE".postln; 0.exit } {
    job=jobs[index];
    score = [[0.0, [\\d_recv, definition.asBytes]]] ++ job[2];
    Score(score).recordNRT(oscFilePath: job[0]++".osc", outputFilePath: job[0],
        sampleRate:48000, headerFormat:"WAV", sampleFormat:"int24", options:options,
        duration:job[1], action:{ ("RENDERED "++job[0]).postln; index=index+1; runJob.value });
    };
};
runJob.value;
)
'''.replace('ROOT', sc_atom(str(ROOT))).replace('JOBS', sc_atom(jobs))
    script_path = output/'render_batch.scd'
    script_path.write_text(script, encoding='utf-8')
    with (output/'render.log').open('w', encoding='utf-8') as log:
        proc = subprocess.run([find_sclang(), '-D', str(script_path)], cwd=ROOT,
            stdout=log, stderr=subprocess.STDOUT, timeout=600,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    render_log = (output/'render.log').read_text(encoding='utf-8',errors='replace')
    if proc.returncode or 'ALL_MAPPING_RENDERS_COMPLETE' not in render_log or 'ERROR:' in render_log:
        raise RuntimeError('NRT rendering failed; inspect '+str(output/'render.log'))
    for name, record in manifest.items():
        rate, audio = wavfile.read(output/(name+'.wav'))
        audio = audio.astype(float)/(2**31)
        peak = float(abs(audio).max())
        active = audio[int(rate*2):int(rate*config['fragment_seconds'])]
        record.update(sample_rate=rate, channels=audio.shape[1], peak=peak,
            rms_dbfs=float(20*np.log10(np.sqrt(np.mean(active**2))+1e-12)),
            tail_peak=float(abs(audio[-int(rate*.3):]).max()),
            finite=bool(np.isfinite(audio).all()),
            wav_sha256=hashlib.sha256((output/(name+'.wav')).read_bytes()).hexdigest())
        if peak >= .85 or record['rms_dbfs'] < -80 or not record['finite'] or record['tail_peak'] > 1e-4:
            raise RuntimeError('audio safety/silence/tail check failed: '+name)
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('RENDERED '+str(len(manifest))+' comparisons; '+str(output/'manifest.json'), flush=True)
