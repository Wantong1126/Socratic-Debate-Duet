"""Non-musical EEG audification transforms for six independent channels."""

from dataclasses import dataclass
from fractions import Fraction

import numpy as np
from scipy.signal import resample_poly

CHANNEL_LABELS = ("F3", "F4", "C3", "C4", "P3", "P4")
OUTPUT_RATE = 48_000


@dataclass(frozen=True)
class AudificationConfig:
    audification_rate: float = 8_000.0
    output_rate: int = OUTPUT_RATE
    fade_ms: float = 5.0
    carrier_hz: float = 220.0
    am_depth: float = 0.5
    fm_depth_hz: float = 0.0
    robust_percentile: float = 99.5
    robust_target: float = 0.9


@dataclass
class AudificationResult:
    raw: np.ndarray
    cleaned: np.ndarray
    normalized: np.ndarray
    audified: list[np.ndarray]
    modulated: list[np.ndarray]
    input_rate: float
    config: AudificationConfig
    initial_gain: float
    safety_gain: float

    @property
    def normalization_gain(self):
        return self.initial_gain * self.safety_gain


def _validate(eeg, sample_rate, config):
    eeg = np.asarray(eeg, dtype=np.float64)
    if eeg.ndim != 2 or eeg.shape[1] != 6 or eeg.shape[0] < 2:
        raise ValueError("Expected EEG data shaped (at least 2 samples, 6 channels).")
    if not np.all(np.isfinite(eeg)):
        raise ValueError("EEG input contains non-finite samples.")
    if sample_rate <= 0 or config.audification_rate <= 0 or config.output_rate <= 0:
        raise ValueError("All sample rates must be positive.")
    if not 0 <= config.am_depth <= 1:
        raise ValueError("AM depth must be between 0 and 1.")
    if config.fm_depth_hz < 0 or config.fade_ms < 0:
        raise ValueError("FM depth and fade length cannot be negative.")
    return eeg


def _exact_resample(signal, source_rate, output_rate, output_samples):
    ratio = Fraction(output_rate / source_rate).limit_denominator(100_000)
    rendered = resample_poly(signal, ratio.numerator, ratio.denominator)
    if len(rendered) < output_samples:
        rendered = np.pad(rendered, (0, output_samples - len(rendered)), mode="edge")
    return rendered[:output_samples]


def _edge_fade(signal, sample_rate, fade_ms):
    count = min(int(round(fade_ms * sample_rate / 1000.0)), len(signal) // 2)
    if count:
        ramp = np.linspace(0.0, 1.0, count, endpoint=True)
        signal = signal.copy()
        signal[:count] *= ramp
        signal[-count:] *= ramp[::-1]
    return signal


def process_eeg(eeg, sample_rate, config=AudificationConfig()):
    """Create time-compressed and carrier-modulated audio for each channel."""
    raw = _validate(eeg, sample_rate, config).copy()
    cleaned = raw - np.mean(raw, axis=0, keepdims=True)

    robust_level = float(np.percentile(np.abs(cleaned), config.robust_percentile))
    initial_gain = config.robust_target / robust_level if robust_level > 0 else 1.0
    initially_normalized = cleaned * initial_gain
    initial_peak = float(np.max(np.abs(initially_normalized)))
    input_safety_gain = min(1.0, 0.999 / initial_peak) if initial_peak > 0 else 1.0
    normalized = initially_normalized * input_safety_gain

    audified, modulated = [], []
    duration = raw.shape[0] / float(sample_rate)
    compressed_samples = int(round(raw.shape[0] * config.output_rate / config.audification_rate))
    modulation_samples = int(round(duration * config.output_rate))
    source_t = np.arange(raw.shape[0], dtype=float) / float(sample_rate)
    output_t = np.arange(modulation_samples, dtype=float) / config.output_rate

    # Polyphase resampling can overshoot even when its input is below full
    # scale. Render all channels once, then apply one shared final safety gain
    # so channel-to-channel amplitude relationships remain intact.
    preliminary_audified = []
    for channel in range(6):
        shifted = _exact_resample(normalized[:, channel], config.audification_rate,
                                  config.output_rate, compressed_samples)
        preliminary_audified.append(_edge_fade(shifted, config.output_rate, config.fade_ms))

    rendered_peak = max(float(np.max(np.abs(x))) for x in preliminary_audified)
    output_safety_gain = min(1.0, 0.999 / rendered_peak) if rendered_peak > 0 else 1.0
    safety_gain = input_safety_gain * output_safety_gain
    normalized *= output_safety_gain
    audified = [(x * output_safety_gain).astype(np.float32) for x in preliminary_audified]

    for channel in range(6):
        envelope_signal = np.interp(output_t, source_t, normalized[:, channel])
        instantaneous_hz = config.carrier_hz + config.fm_depth_hz * envelope_signal
        phase = 2.0 * np.pi * np.cumsum(instantaneous_hz) / config.output_rate
        amplitude = (1.0 + config.am_depth * envelope_signal) / (1.0 + config.am_depth)
        modulated.append((amplitude * np.sin(phase)).astype(np.float32))

    return AudificationResult(raw, cleaned, normalized, audified, modulated,
                              float(sample_rate), config, initial_gain, safety_gain)


def signal_metrics(signal):
    signal = np.asarray(signal)
    return {
        "peak": float(np.max(np.abs(signal))) if signal.size else 0.0,
        "rms": float(np.sqrt(np.mean(np.square(signal)))) if signal.size else 0.0,
        "clipping_count": int(np.count_nonzero(np.abs(signal) >= 1.0)),
    }
