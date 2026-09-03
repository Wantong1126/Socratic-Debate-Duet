"""Report objective steady-state metrics for organism v2 LOW/HIGH renders."""

from __future__ import annotations

import argparse
from pathlib import Path
import wave

import numpy as np
from scipy.io import wavfile


FIELDS = ("energy", "delta", "theta", "alpha", "beta")
RELEVANT_BANDS_HZ = {
    "energy": (40.0, 4000.0),
    "delta": (50.0, 220.0),
    "theta": (240.0, 420.0),
    "alpha": (430.0, 820.0),
    "beta": (1500.0, 3250.0),
}


def _normalized_audio(path: Path) -> tuple[int, np.ndarray]:
    rate, raw = wavfile.read(path)
    if raw.dtype == np.int32:
        audio = raw.astype(np.float64) / (2**31)
    elif raw.dtype == np.int16:
        audio = raw.astype(np.float64) / (2**15)
    else:
        audio = raw.astype(np.float64)
    if audio.ndim == 1:
        audio = audio[:, None]
    return rate, audio


def metrics(path: Path, band_hz: tuple[float, float]) -> dict[str, float | bool]:
    rate, audio = _normalized_audio(path)
    segment = audio[int(2.0 * rate):int(5.0 * rate)]
    rms = float(np.sqrt(np.mean(np.square(segment))))
    peak = float(np.max(np.abs(audio)))
    window = np.hanning(len(segment))[:, None]
    spectrum = np.fft.rfft(segment * window, axis=0)
    power = np.mean(np.abs(spectrum) ** 2, axis=1)
    frequencies = np.fft.rfftfreq(len(segment), 1.0 / rate)
    audible = (frequencies >= 20) & (frequencies <= 12000)
    total_power = float(np.sum(power[audible])) + 1e-30
    centroid = float(np.sum(frequencies[audible] * power[audible]) / total_power)
    selected = (frequencies >= band_hz[0]) & (frequencies <= band_hz[1])
    relevant_power = float(np.sum(power[selected])) + 1e-30
    return {
        "rms_dbfs": float(20 * np.log10(rms + 1e-30)),
        "spectral_centroid_hz": centroid,
        "relevant_band_db": float(10 * np.log10(relevant_power)),
        "relevant_band_percent": 100 * relevant_power / total_power,
        "peak": peak,
        "clipped": peak >= 0.999,
    }


def analyze_directory(directory: Path) -> dict[str, dict[str, object]]:
    report = {}
    for field in FIELDS:
        low = metrics(directory / f"{field}_low.wav", RELEVANT_BANDS_HZ[field])
        high = metrics(directory / f"{field}_high.wav", RELEVANT_BANDS_HZ[field])
        report[field] = {
            "low": low,
            "high": high,
            "high_minus_low_rms_db": high["rms_dbfs"] - low["rms_dbfs"],
            "high_minus_low_relevant_band_db": (
                high["relevant_band_db"] - low["relevant_band_db"]
            ),
        }
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        default=Path("recordings/eeg_organism_v2_isolated"),
    )
    args = parser.parse_args(argv)
    report = analyze_directory(args.directory)
    for field, result in report.items():
        print(field)
        print(f"  LOW  {result['low']}")
        print(f"  HIGH {result['high']}")
        print(f"  HIGH-LOW RMS dB: {result['high_minus_low_rms_db']:.3f}")
        print(
            "  HIGH-LOW relevant-band dB: "
            f"{result['high_minus_low_relevant_band_db']:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
