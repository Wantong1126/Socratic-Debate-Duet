"""Eighteen continuous musical controls from six independent EEG channels."""

from dataclasses import dataclass

import numpy as np
from scipy.signal import welch

CHANNELS = ("F3", "F4", "C3", "C4", "P3", "P4")
DESCRIPTORS = ("energy", "centroid", "mobility")


@dataclass
class ControlFrame:
    raw: dict[str, float]
    normalized: dict[str, float]
    baseline_progress: float
    quality_warnings: dict[str, list[str]]


def control_names():
    return tuple(f"eeg{channel}_{descriptor}"
                 for channel in range(1, 7) for descriptor in DESCRIPTORS)


def signal_quality(eeg, saturation_abs=None):
    warnings = {}
    for index, name in enumerate(CHANNELS):
        signal = eeg[:, index]
        items = []
        if not np.all(np.isfinite(signal)):
            items.append("non-finite samples")
        finite = signal[np.isfinite(signal)]
        if not finite.size or np.ptp(finite) <= 1e-9:
            items.append("flatline")
        if (saturation_abs is not None and finite.size
                and np.any(np.abs(finite) >= float(saturation_abs))):
            items.append("saturation")
        warnings[name] = items
    return warnings


def _descriptors(signal, sample_rate, low_hz, high_hz):
    """Welch-integrated bandpower, power centroid, and Hjorth mobility."""
    segment = min(len(signal), int(round(sample_rate)))
    frequencies, psd = welch(signal, fs=sample_rate, nperseg=segment,
                             noverlap=segment // 2)
    mask = (frequencies >= low_hz) & (frequencies <= high_hz)
    frequencies, psd = frequencies[mask], psd[mask]
    energy = float(np.trapezoid(psd, frequencies)) if len(frequencies) > 1 else 0.0
    power_sum = float(np.sum(psd))
    centroid = float(np.sum(frequencies * psd) / power_sum) if power_sum > np.finfo(float).eps else low_hz
    variance = float(np.var(signal))
    mobility = float(np.sqrt(np.var(np.diff(signal)) / variance)) if variance > np.finfo(float).eps else 0.0
    return energy, centroid, mobility


class EEGControlFeatureEngine:
    """Calculate, calibrate, normalize, then lightly smooth exactly 18 controls."""

    def __init__(self, sample_rate=250.0, update_rate=4.0, baseline_seconds=20.0,
                 analysis_low_hz=4.0, analysis_high_hz=40.0,
                 smoothing_seconds=0.5, low_percentile=5.0, high_percentile=95.0,
                 required_quality_channels=(), saturation_abs=None, energy_log_scale=False):
        if min(sample_rate, update_rate, baseline_seconds) <= 0:
            raise ValueError("sample, update, and calibration durations must be positive")
        if not 0 < analysis_low_hz < analysis_high_hz < sample_rate / 2:
            raise ValueError("analysis range must lie between zero and Nyquist")
        self.sample_rate, self.update_rate = float(sample_rate), float(update_rate)
        self.low_hz, self.high_hz = float(analysis_low_hz), float(analysis_high_hz)
        self.required_frames = max(2, int(round(baseline_seconds * update_rate)))
        self.low_percentile, self.high_percentile = low_percentile, high_percentile
        self.calibration = {name: [] for name in control_names()}
        self.bounds = None
        self.smoothed = {}
        self.alpha = 1.0 if smoothing_seconds <= 0 else 1.0 - np.exp(-1.0 / (update_rate * smoothing_seconds))
        self.frames_seen = 0
        self.required_quality_channels = tuple(int(index) for index in required_quality_channels)
        self.saturation_abs = saturation_abs
        self.energy_log_scale = energy_log_scale
        if any(index < 0 or index >= 6 for index in self.required_quality_channels):
            raise ValueError("required quality channel indexes must be in [0, 5]")

    @property
    def ready(self):
        return self.bounds is not None

    @property
    def baseline_progress(self):
        return min(1.0, self.frames_seen / self.required_frames)

    def _fit(self):
        self.bounds = {}
        for name, values in self.calibration.items():
            finite = np.asarray(values, dtype=float)
            finite = finite[np.isfinite(finite)]
            low, high = np.percentile(finite, [self.low_percentile, self.high_percentile]) if finite.size else (0.0, 0.0)
            self.bounds[name] = (float(low), float(high))

    def update(self, feature_window, quality_window=None):
        eeg = np.asarray(feature_window, dtype=float)
        if eeg.ndim != 2 or eeg.shape[1] != 6 or eeg.shape[0] < 32 or not np.all(np.isfinite(eeg)):
            raise ValueError("Expected finite EEG shaped (at least 32 samples, 6 channels).")
        raw = {}
        for index in range(6):
            values = _descriptors(eeg[:, index], self.sample_rate, self.low_hz, self.high_hz)
            for descriptor, value in zip(DESCRIPTORS, values):
                raw[f"eeg{index + 1}_{descriptor}"] = float(value) if np.isfinite(value) else 0.0

        quality = eeg if quality_window is None else np.asarray(quality_window, dtype=float)
        warnings = signal_quality(quality, self.saturation_abs)
        required_valid = all(
            not warnings[CHANNELS[index]] for index in self.required_quality_channels
        )
        if not required_valid:
            return ControlFrame(raw, {}, self.baseline_progress, warnings)

        if not self.ready:
            for name, value in raw.items():
                self.calibration[name].append(value)
            self.frames_seen += 1
            if self.frames_seen >= self.required_frames:
                self._fit()
            normalized = {}
        else:
            normalized = {}
            for name, value in raw.items():
                low, high = self.bounds[name]
                if self.energy_log_scale and name.endswith('_energy'):
                    low, high, value = np.log10(np.maximum([low, high, value], 1e-12))
                scale = max(abs(low), abs(high), 1.0)
                mapped = 0.0 if high - low <= np.finfo(float).eps * scale * 32 else (value - low) / (high - low)
                mapped = float(np.clip(mapped, 0.0, 1.0)) if np.isfinite(mapped) else 0.0
                previous = self.smoothed.get(name, mapped)
                mapped = previous + self.alpha * (mapped - previous)
                self.smoothed[name] = mapped
                normalized[name] = float(np.clip(mapped, 0.0, 1.0))
            self.frames_seen += 1
        return ControlFrame(raw, normalized, self.baseline_progress, warnings)
