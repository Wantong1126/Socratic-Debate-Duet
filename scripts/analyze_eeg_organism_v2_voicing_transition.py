"""Objective safety metrics for the persistent voice-bank NRT render."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import wave

import numpy as np
from scipy.io import wavfile


def analyze(path: Path) -> dict[str, float | int | bool]:
    rate, raw = wavfile.read(path)
    if raw.dtype == np.int32:
        audio = raw.astype(np.float64) / (2**31)
    elif raw.dtype == np.int16:
        audio = raw.astype(np.float64) / (2**15)
    else:
        audio = raw.astype(np.float64)
    if audio.ndim == 1:
        audio = audio[:, None]
    peak = float(np.max(np.abs(audio)))
    duration = len(audio) / float(rate)
    # Short windows straddling the two bank transitions catch discontinuity
    # spikes without making a subjective sound-quality claim.
    transition_peaks = []
    transition_steps = []
    for at_seconds in (4.01, 9.01):
        start = max(0, int((at_seconds - 0.05) * rate))
        stop = min(len(audio), int((at_seconds + 0.05) * rate))
        window = audio[start:stop]
        transition_peaks.append(float(np.max(np.abs(window))))
        transition_steps.append(float(np.max(np.abs(np.diff(window, axis=0)))))
    with wave.open(str(path), "rb") as recording:
        sample_width = recording.getsampwidth()
    return {
        "sample_rate": int(rate),
        "channels": int(audio.shape[1]),
        "sample_width_bytes": sample_width,
        "frames": int(len(audio)),
        "duration_seconds": duration,
        "finite": bool(np.isfinite(audio).all()),
        "peak": peak,
        "peak_dbfs": 20.0 * math.log10(peak + 1e-30),
        "transition_peak": max(transition_peaks),
        "transition_max_sample_step": max(transition_steps),
        "clipped": peak >= 0.999,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path("recordings/eeg_organism_v2_voicing/g_lydian_transition.wav"),
    )
    args = parser.parse_args(argv)
    print(json.dumps(analyze(args.path), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
