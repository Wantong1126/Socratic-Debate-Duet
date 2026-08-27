"""Shared, per-channel EEG validation and preprocessing."""

from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, iirnotch, sosfilt, sosfiltfilt, tf2sos


@dataclass(frozen=True)
class EEGFilterConfig:
    highpass_hz: float | None = 0.5
    highpass_order: int = 4
    lowpass_hz: float | None = 45.0
    lowpass_order: int = 4
    notch_hz: float | None = 50.0
    notch_q: float = 30.0


def validate_eeg(eeg, channels=6, minimum_samples=2):
    data = np.asarray(eeg, dtype=np.float64)
    if data.ndim != 2 or data.shape[1] != channels or data.shape[0] < minimum_samples:
        raise ValueError(f"Expected EEG data shaped (at least {minimum_samples} samples, {channels} channels).")
    if not np.all(np.isfinite(data)):
        raise ValueError("EEG input contains non-finite samples.")
    return data


def preprocess_eeg(eeg, sample_rate, config=EEGFilterConfig(), *, zero_phase=True):
    """Filter all columns independently using one shared SOS pipeline.

    Offline reports use zero-phase filtering.  The legacy live feature path can
    request only centering with all cutoffs set to ``None``; this preserves its
    established theta/alpha/beta behaviour while sharing validation and DC
    handling rather than maintaining a second implementation.
    """
    data = validate_eeg(eeg)
    sample_rate = float(sample_rate)
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    nyquist = sample_rate / 2.0
    sections = []
    for cutoff, order, kind in (
        (config.highpass_hz, config.highpass_order, "highpass"),
        (config.lowpass_hz, config.lowpass_order, "lowpass"),
    ):
        if cutoff is None:
            continue
        if not 0 < cutoff < nyquist or order < 1:
            raise ValueError(f"Invalid {kind} cutoff/order for {sample_rate:g} Hz data.")
        sections.append(butter(order, cutoff, btype=kind, fs=sample_rate, output="sos"))
    if config.notch_hz is not None:
        if not 0 < config.notch_hz < nyquist or config.notch_q <= 0:
            raise ValueError("Invalid notch frequency/Q for this sample rate.")
        b, a = iirnotch(config.notch_hz, config.notch_q, fs=sample_rate)
        sections.append(tf2sos(b, a))

    cleaned = data - np.mean(data, axis=0, keepdims=True)
    if not sections:
        return cleaned
    sos = np.vstack(sections)
    if not zero_phase:
        raise ValueError("Only completed-window zero-phase EEG filtering is currently supported.")
    try:
        return sosfiltfilt(sos, cleaned, axis=0)
    except ValueError as exc:
        raise ValueError("EEG window is too short for the configured zero-phase filters.") from exc


def _filter_sections(sample_rate, config):
    """Design an HP -> LP -> notch SOS cascade."""
    sample_rate = float(sample_rate)
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    nyquist = sample_rate / 2.0
    sections = []
    for cutoff, order, kind in ((config.highpass_hz, config.highpass_order, "highpass"),
                                (config.lowpass_hz, config.lowpass_order, "lowpass")):
        if cutoff is None:
            continue
        if not 0 < cutoff < nyquist or order < 1:
            raise ValueError(f"Invalid {kind} cutoff/order for {sample_rate:g} Hz data.")
        sections.append(butter(order, cutoff, btype=kind, fs=sample_rate, output="sos"))
    if config.notch_hz is not None:
        if not 0 < config.notch_hz < nyquist or config.notch_q <= 0:
            raise ValueError("Invalid notch frequency/Q for this sample rate.")
        b, a = iirnotch(config.notch_hz, config.notch_q, fs=sample_rate)
        sections.append(tf2sos(b, a))
    return np.vstack(sections) if sections else np.empty((0, 6))


class StreamingEEGPreprocessor:
    """Causal, stateful per-channel SOS filtering for live EEG chunks."""

    def __init__(self, sample_rate, config=EEGFilterConfig(), channels=6):
        self.channels = int(channels)
        self.sos = _filter_sections(sample_rate, config)
        self.zi = np.zeros((len(self.sos), 2, self.channels), dtype=float)

    def process(self, chunk):
        data = validate_eeg(chunk, channels=self.channels, minimum_samples=1)
        if not len(self.sos):
            return data.copy()
        cleaned, self.zi = sosfilt(self.sos, data, axis=0, zi=self.zi)
        if not np.all(np.isfinite(cleaned)):
            raise ValueError("EEG filtering produced non-finite samples.")
        return cleaned
