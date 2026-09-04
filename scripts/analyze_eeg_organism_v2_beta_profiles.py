"""Measure matched organism v2 beta profile renders without judging timbre."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile


PROFILES = ("original_24_36_48", "softened")
LEVELS = ("low", "high")
BETA_ANALYSIS_BAND_HZ = (1500.0, 4000.0)


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


def _dbfs(value: float) -> float:
    return float(20 * np.log10(value + 1e-30))


def _a_weighting_amplitude(frequencies: np.ndarray) -> np.ndarray:
    """Return IEC-style A-weighting amplitudes for an FFT frequency grid."""

    frequencies = frequencies.astype(np.float64)
    squared = frequencies**2
    numerator = (12194.0**2) * (squared**2)
    denominator = (
        (squared + 20.6**2)
        * np.sqrt((squared + 107.7**2) * (squared + 737.9**2))
        * (squared + 12194.0**2)
    )
    ratio = np.divide(
        numerator,
        denominator,
        out=np.zeros_like(numerator),
        where=denominator > 0,
    )
    return ratio * (10 ** (2.0 / 20.0))


def metrics(path: Path) -> dict[str, float | bool]:
    rate, audio = _normalized_audio(path)
    segment = audio[int(2.0 * rate):int(5.0 * rate)]
    finite = bool(np.all(np.isfinite(audio)))
    rms = float(np.sqrt(np.mean(np.square(segment))))
    peak = float(np.max(np.abs(audio)))

    windowed = segment * np.hanning(len(segment))[:, None]
    spectrum = np.fft.rfft(windowed, axis=0)
    power = np.mean(np.abs(spectrum) ** 2, axis=1)
    frequencies = np.fft.rfftfreq(len(segment), 1.0 / rate)
    audible = (frequencies >= 20.0) & (frequencies <= 12000.0)
    total_power = float(np.sum(power[audible])) + 1e-30
    centroid = float(
        np.sum(frequencies[audible] * power[audible]) / total_power
    )
    selected = (
        (frequencies >= BETA_ANALYSIS_BAND_HZ[0])
        & (frequencies <= BETA_ANALYSIS_BAND_HZ[1])
    )
    selected_power = float(np.sum(power[selected]))

    unwindowed_spectrum = np.fft.rfft(segment, axis=0)
    weighted_spectrum = (
        unwindowed_spectrum
        * _a_weighting_amplitude(frequencies)[:, None]
    )
    weighted_audio = np.fft.irfft(
        weighted_spectrum, n=len(segment), axis=0
    )
    weighted_rms = float(np.sqrt(np.mean(np.square(weighted_audio))))

    beta_spectrum = unwindowed_spectrum.copy()
    beta_spectrum[~selected, :] = 0
    beta_audio = np.fft.irfft(beta_spectrum, n=len(segment), axis=0)
    beta_rms = float(np.sqrt(np.mean(np.square(beta_audio))))

    return {
        "finite": finite,
        "rms_dbfs": _dbfs(rms),
        "peak": peak,
        "clipped": peak >= 0.999,
        "spectral_centroid_hz": centroid,
        "band_1_5_4khz_percent": 100.0 * selected_power / total_power,
        "band_1_5_4khz_rms_dbfs": _dbfs(beta_rms),
        "a_weighted_rms_dbfs": _dbfs(weighted_rms),
    }


def analyze_directory(directory: Path) -> dict[str, dict[str, object]]:
    report: dict[str, dict[str, object]] = {}
    for profile in PROFILES:
        levels = {
            level: metrics(directory / f"{profile}_beta_{level}.wav")
            for level in LEVELS
        }
        low = levels["low"]
        high = levels["high"]
        levels["high_minus_low_rms_db"] = (
            high["rms_dbfs"] - low["rms_dbfs"]
        )
        levels["high_minus_low_a_weighted_db"] = (
            high["a_weighted_rms_dbfs"] - low["a_weighted_rms_dbfs"]
        )
        report[profile] = levels
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        default=Path("recordings/eeg_organism_v2_beta_profiles"),
    )
    args = parser.parse_args(argv)
    print(json.dumps(analyze_directory(args.directory), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
