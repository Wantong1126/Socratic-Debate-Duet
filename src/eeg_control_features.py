"""Continuous, interpretation-free controls from six independent EEG channels."""

from collections import defaultdict, deque
from dataclasses import dataclass

import numpy as np
from scipy.signal import correlate, correlation_lags, hilbert, welch

from .eeg_features import clean_eeg

CHANNELS = ("f3", "f4", "c3", "c4", "p3", "p4")
PAIRS = ((0, 1, "f3_f4"), (2, 3, "c3_c4"), (4, 5, "p3_p4"))
CHANNEL_DESCRIPTORS = ("energy", "energy_slope", "mobility", "centroid", "entropy", "novelty")
PAIR_DESCRIPTORS = ("asymmetry", "similarity", "lag")


@dataclass
class ControlFrame:
    raw: dict[str, float]
    normalized: dict[str, float]
    baseline_progress: float
    quality_warnings: dict[str, list[str]]


def _robust_energy(signal):
    """RMS after winsorising absolute values at the 95th percentile."""
    limit = np.percentile(np.abs(signal), 95.0)
    return float(np.sqrt(np.mean(np.minimum(np.abs(signal), limit) ** 2)))


def _envelope(signal, sample_rate):
    envelope = np.abs(hilbert(signal))
    width = max(1, int(round(0.08 * sample_rate)))
    return np.convolve(envelope, np.ones(width) / width, mode="same")


def _energy_slope(envelope, sample_rate):
    # Median envelope derivative is resistant to isolated transients.
    return float(np.median(np.diff(envelope)) * sample_rate)


def _mobility(signal, sample_rate):
    variance = np.var(signal)
    if variance <= np.finfo(float).eps:
        return 0.0
    return float(np.sqrt(np.var(np.diff(signal) * sample_rate) / variance))


def _spectral_descriptors(signal, sample_rate):
    nperseg = min(len(signal), max(32, int(round(sample_rate))))
    frequencies, power = welch(signal, fs=sample_rate, nperseg=nperseg)
    mask = (frequencies >= 1.0) & (frequencies <= min(45.0, sample_rate / 2))
    frequencies, power = frequencies[mask], power[mask]
    total = float(np.sum(power))
    if total <= np.finfo(float).eps or len(power) < 2:
        return 0.0, 0.0
    probabilities = power / total
    centroid = float(np.sum(frequencies * probabilities) / (sample_rate / 2))
    entropy = float(-np.sum(probabilities * np.log(probabilities + np.finfo(float).eps)) / np.log(len(probabilities)))
    return centroid, entropy


def _safe_correlation(a, b):
    if np.std(a) <= np.finfo(float).eps or np.std(b) <= np.finfo(float).eps:
        return 0.0
    return float(np.clip(np.corrcoef(a, b)[0, 1], -1.0, 1.0))


def _pair_lag(a, b, sample_rate, max_lag_seconds):
    max_samples = max(1, int(round(max_lag_seconds * sample_rate)))
    a = (a - np.mean(a)) / max(np.std(a), np.finfo(float).eps)
    b = (b - np.mean(b)) / max(np.std(b), np.finfo(float).eps)
    values = correlate(b, a, mode="full")
    lags = correlation_lags(len(b), len(a), mode="full")
    keep = np.abs(lags) <= max_samples
    lag_samples = int(lags[keep][np.argmax(values[keep])])
    return lag_samples / sample_rate


def signal_quality(eeg):
    warnings = {}
    for index, name in enumerate(CHANNELS):
        x = eeg[:, index]
        items = []
        if not np.all(np.isfinite(x)):
            items.append("non-finite samples")
        finite = x[np.isfinite(x)]
        if not finite.size or np.ptp(finite) <= 1e-9:
            items.append("flatline")
        if finite.size:
            repeated_extremes = max(np.count_nonzero(finite == np.min(finite)), np.count_nonzero(finite == np.max(finite)))
            if repeated_extremes >= max(3, int(0.01 * finite.size)):
                items.append("repeated extreme values / possible clipping")
        warnings[name] = items
    return warnings


def _repair_nonfinite(eeg):
    repaired = np.asarray(eeg, dtype=float).copy()
    for channel in range(repaired.shape[1]):
        x = repaired[:, channel]
        good = np.isfinite(x)
        if not np.any(good):
            x[:] = 0.0
        elif not np.all(good):
            x[~good] = np.interp(np.flatnonzero(~good), np.flatnonzero(good), x[good])
    return repaired


class EEGControlFeatureEngine:
    """Extract and robustly normalise control frames at a configurable rate.

    Normalisation uses each control's own rolling median and MAD, mapped by a
    smooth tanh into [0, 1]. No thresholded states or cross-channel averaging
    are used. The 80 ms envelope smoother has approximately 40 ms latency.
    """

    def __init__(self, sample_rate=250.0, update_rate=4.0, baseline_seconds=20.0,
                 max_lag_seconds=0.1):
        if min(sample_rate, update_rate, baseline_seconds) <= 0:
            raise ValueError("sample, update, and baseline rates must be positive")
        self.sample_rate = float(sample_rate)
        self.update_rate = float(update_rate)
        self.baseline_frames = max(2, int(round(baseline_seconds * update_rate)))
        self.max_lag_seconds = float(max_lag_seconds)
        self.history = defaultdict(lambda: deque(maxlen=self.baseline_frames))
        self.frames_seen = 0

    @property
    def baseline_progress(self):
        return min(1.0, self.frames_seen / self.baseline_frames)

    def _normalize(self, key, value):
        history = np.asarray(self.history[key], dtype=float)
        if history.size < 4:
            normalized = 0.5
        else:
            median = float(np.median(history))
            mad = float(np.median(np.abs(history - median)))
            if key.endswith("_energy"):
                minimum_scale = max(abs(median) * 0.02, 1e-9)
            elif key.endswith("_energy_slope"):
                minimum_scale = 0.01
            elif key.endswith("_mobility"):
                minimum_scale = max(abs(median) * 0.02, 0.1)
            elif key.endswith("_centroid"):
                minimum_scale = 0.005
            elif key.endswith("_entropy"):
                minimum_scale = 0.01
            elif key.endswith("_novelty"):
                minimum_scale = 0.25
            elif key.endswith("_asymmetry"):
                minimum_scale = 0.01
            elif key.endswith("_similarity"):
                minimum_scale = 0.02
            else:  # bounded pair lag
                minimum_scale = 1.0 / self.sample_rate
            scale = max(1.4826 * mad, minimum_scale)
            normalized = 0.5 + 0.5 * np.tanh((value - median) / (3.0 * scale))
        self.history[key].append(float(value))
        return float(np.clip(normalized, 0.0, 1.0))

    def update(self, eeg_window):
        eeg = np.asarray(eeg_window, dtype=float)
        if eeg.ndim != 2 or eeg.shape[1] != 6 or eeg.shape[0] < 32:
            raise ValueError("Expected EEG shaped (at least 32 samples, 6 channels).")
        warnings = signal_quality(eeg)
        cleaned = clean_eeg(_repair_nonfinite(eeg))
        raw, energies, envelopes = {}, [], []
        for index, channel in enumerate(CHANNELS):
            signal = cleaned[:, index]
            envelope = _envelope(signal, self.sample_rate)
            energy = _robust_energy(signal)
            mobility = _mobility(signal, self.sample_rate)
            centroid, entropy = _spectral_descriptors(signal, self.sample_rate)
            previous_energy = np.asarray(self.history[f"{channel}_energy"], dtype=float)
            if previous_energy.size < 4:
                novelty = 0.0
            else:
                median = np.median(previous_energy)
                mad = np.median(np.abs(previous_energy - median))
                novelty = abs(energy - median) / max(1.4826 * mad, abs(median) * 0.01, 1e-9)
            raw.update({
                f"{channel}_energy": energy,
                f"{channel}_energy_slope": _energy_slope(envelope, self.sample_rate),
                f"{channel}_mobility": mobility,
                f"{channel}_centroid": centroid,
                f"{channel}_entropy": entropy,
                f"{channel}_novelty": float(novelty),
            })
            energies.append(energy)
            envelopes.append(envelope)

        for left, right, pair in PAIRS:
            denominator = energies[left] + energies[right]
            asymmetry = (energies[left] - energies[right]) / max(denominator, np.finfo(float).eps)
            waveform_similarity = _safe_correlation(cleaned[:, left], cleaned[:, right])
            envelope_similarity = _safe_correlation(envelopes[left], envelopes[right])
            raw[f"{pair}_asymmetry"] = float(asymmetry)
            raw[f"{pair}_similarity"] = float((waveform_similarity + envelope_similarity) / 2.0)
            raw[f"{pair}_lag"] = _pair_lag(cleaned[:, left], cleaned[:, right], self.sample_rate, self.max_lag_seconds)

        normalized = {key: self._normalize(key, value) for key, value in raw.items()}
        self.frames_seen += 1
        return ControlFrame(raw, normalized, self.baseline_progress, warnings)
