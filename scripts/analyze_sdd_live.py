"""Measure the saved bounded soak; never infer human listening from a WAV."""
import json
from pathlib import Path
import re
import warnings

import numpy as np
from scipy.io import wavfile


def main():
    root = Path('reports/sdd_v1')
    data = (root/'soak.log').read_bytes()
    text = data.decode('utf-16' if data.startswith(b'\xff\xfe') else 'utf-8')
    trees = [line for line in text.splitlines()
             if 'SDD_TREE' in line and '1000, 1, 1001' in line]
    assert len(trees) == 30
    assert 'SDD_INVALID_RESULT count=1200 timedOut=true' in text
    assert 'SDD_LIVE_COMPLETE' in text and 'ERROR:' not in text
    disconnect = float(re.search(r'SDD_DISCONNECT t=([0-9.]+)', text)[1])
    stop = float(re.search(r'SDD_STOP t=([0-9.]+)', text)[1])
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', wavfile.WavFileWarning)
        rate, audio = wavfile.read(root/'live.wav')
    def peak(start, end):
        return float(np.max(np.abs(audio[int(start*rate):int(end*rate)])))
    result = dict(duration=len(audio)/rate, rate=rate,
                  peak=float(np.max(np.abs(audio))), finite=bool(np.isfinite(audio).all()),
                  stable_queries=len(trees), disconnect_at=disconnect,
                  disconnect_tail_peak=peak(disconnect+3, disconnect+3.8),
                  stop_at=stop, stop_tail_peak=peak(stop+3, stop+3.8))
    assert result['finite'] and result['peak'] < 0.999
    assert result['disconnect_tail_peak'] < 1e-6 and result['stop_tail_peak'] == 0
    (root/'soak_metrics.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
