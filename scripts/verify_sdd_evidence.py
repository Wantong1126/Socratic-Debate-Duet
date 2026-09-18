"""Check saved fixture/replay inputs and measured baseline audio, not listening."""
import json
from pathlib import Path
import warnings

import numpy as np
from scipy.io import wavfile


def main():
    root = Path('reports/sdd_v1')
    def rows(name):
        return [json.loads(line) for line in (root/name/'records.jsonl').read_text().splitlines()]
    original = [r['data']['values'] for r in rows('fixture_run') if r['kind'] == 'frame']
    replay = [r['data']['values'] for r in rows('replay_run') if r['kind'] == 'frame']
    assert original == replay and len(original) == 48
    assert len({tuple(values[1:]) for values in original}) == 1
    dropout = rows('dropout_run')
    assert len([r for r in dropout if r['kind'] == 'frame']) == 32
    assert any(r['kind'] == 'event' and r['data']['kind'] == 'signal_loss' for r in dropout)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', wavfile.WavFileWarning)
        rate, audio = wavfile.read(root/'baseline_energy.wav')
    audio = audio.astype(float) / 2**31
    levels = [float(20*np.log10(np.sqrt(np.mean(audio[int(a*rate):int(b*rate)]**2))))
              for a,b in ((2,3.8), (6,7.8), (10,11.8))]
    assert np.isfinite(audio).all() and np.max(np.abs(audio)) < 0.999
    assert np.max(np.abs(audio[-rate:])) == 0
    assert levels[1]-levels[0] > 5 and levels[2]-levels[1] > 5
    result = dict(control_replay_matches=True, frames=48, dropout_frames=32,
                  steady_rms_dbfs=levels, listening='PENDING HUMAN LISTENING')
    (root/'evidence_checks.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
