"""Verify one immutable Python→SC runtime evidence run; no listening inference."""
import argparse
import json
from pathlib import Path
import warnings

import numpy as np
from scipy.io import wavfile


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_name')
    args = parser.parse_args(argv)
    root = Path('reports/sdd_v1')
    log = (root/f'{args.run_name}.log').read_text(encoding='utf-8', errors='strict')
    session = root/args.run_name
    metadata = json.loads((session/'metadata.json').read_text(encoding='utf-8'))
    rows = [json.loads(line) for line in (session/'records.jsonl').read_text(encoding='utf-8').splitlines()]
    frames = [row for row in rows if row['kind'] == 'frame']
    events = [row['data'] for row in rows if row['kind'] == 'event']
    tree_pairs = [('1000', '1001'), ('1003', '1004'), ('1005', '1006')]
    assert all(f'{group}, 1, {synth}, -1, eegOrganismV2HarmonicField' in log
               for group, synth in tree_pairs)
    assert log.count('WATCHDOG:') >= 3
    assert 'SDD_RUNTIME_COMPLETE' in log
    assert all(token not in log for token in ('ERROR:', 'FAILURE IN SERVER'))
    assert len(frames) == 32 and metadata['source']['dropout'] == [4.0, 8.0]
    assert [event['kind'] for event in events] == ['signal_loss', 'stop']
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', wavfile.WavFileWarning)
        rate, audio = wavfile.read(root/'runtime.wav')
    result = {
        'run': args.run_name,
        'fixture_frames': len(frames),
        'event_kinds': [event['kind'] for event in events],
        'watchdogs': log.count('WATCHDOG:'),
        'node_generations': len(tree_pairs),
        'audio_rate': int(rate),
        'audio_channels': int(audio.shape[1]),
        'audio_duration_seconds': len(audio)/rate,
        'audio_finite': bool(np.isfinite(audio).all()),
        'audio_peak': float(np.max(np.abs(audio))),
        # SuperCollider's missing default user synthdef metadata directory is
        # an environment notice here; this run still instantiated/ran/freed the
        # Synth and has no server ERROR or FAILURE.
        'sc_default_synthdef_metadata_notices': log.count('Could Not Find'),
        'listening': 'PENDING HUMAN LISTENING',
    }
    assert result['audio_finite'] and result['audio_peak'] < 0.999
    output = root/f'{args.run_name}.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
