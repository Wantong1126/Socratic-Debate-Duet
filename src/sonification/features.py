"""Pure, stream-independent feature calculations for organism controls.

This module performs no acquisition, OSC, or sound work. Spectral entropy acts
on one already-cleaned channel window; temporal novelty acts on one stream of
already-normalized features and keeps state only inside its estimator instance.
"""

from __future__ import annotations

from collections import deque
import math
from typing import Mapping

import numpy as np
from scipy.signal import welch


SPECTRAL_ENTROPY_LOW_HZ = 0.5
SPECTRAL_ENTROPY_HIGH_HZ = 45.0
SPECTRAL_ENTROPY_WINDOW_SECONDS = 2.0

NOVELTY_BAND_ORDER = ("delta", "theta", "alpha", "beta")
NOVELTY_FEATURE_ORDER = (
    "energy",
    "centroid",
    "mobility",
    "spectral_entropy",
    *NOVELTY_BAND_ORDER,
)
NOVELTY_DEFAULT_UPDATE_RATE_HZ = 4.0
NOVELTY_DEFAULT_HISTORY_SECONDS = 8.0
NOVELTY_DEFAULT_SCALE_FLOOR = 0.05
NOVELTY_DEFAULT_MAX_DIMENSION_DISTANCE = 6.0


def spectral_entropy(cleaned_window, sample_rate: float) -> float:
    """Return normalized Welch spectral entropy for one cleaned EEG channel.

    Only PSD bins from 0.5 through 45 Hz (inclusive) participate.  A two-second
    Welch segment provides 0.5 Hz bin spacing, matching the project's rolling
    EEG window; longer inputs use two-second segments with 50% overlap.

    Invalid input is deliberately deterministic and safe for a future control
    pipeline: non-1D, non-numeric, non-finite, too-short, flatline, invalid-rate,
    and zero-band-power input all return ``0.0``.
    """
    try:
        signal = np.asarray(cleaned_window, dtype=float)
        rate = float(sample_rate)
    except (TypeError, ValueError, OverflowError):
        return 0.0

    if (
        signal.ndim != 1
        or not math.isfinite(rate)
        or rate <= 0.0
        or rate / 2.0 < SPECTRAL_ENTROPY_HIGH_HZ
        or not np.all(np.isfinite(signal))
    ):
        return 0.0

    segment_samples = int(round(SPECTRAL_ENTROPY_WINDOW_SECONDS * rate))
    if segment_samples < 2 or signal.size < segment_samples:
        return 0.0

    centered = signal - np.mean(signal)
    peak = float(np.max(np.abs(centered)))
    if not math.isfinite(peak) or peak == 0.0:
        return 0.0

    # Spectral probabilities are scale-invariant.  Normalizing before Welch
    # additionally avoids overflow/underflow for otherwise valid amplitudes.
    normalized = centered / peak
    frequencies, psd = welch(
        normalized,
        fs=rate,
        nperseg=segment_samples,
        noverlap=segment_samples // 2,
    )
    valid = (
        (frequencies >= SPECTRAL_ENTROPY_LOW_HZ)
        & (frequencies <= SPECTRAL_ENTROPY_HIGH_HZ)
        & np.isfinite(psd)
        & (psd >= 0.0)
    )
    band_psd = psd[valid]
    bin_count = int(band_psd.size)
    if bin_count < 2:
        return 0.0

    total_power = float(np.sum(band_psd))
    if not math.isfinite(total_power) or total_power <= 0.0:
        return 0.0

    probabilities = band_psd / total_power
    nonzero = probabilities > 0.0
    entropy = -float(np.sum(
        probabilities[nonzero] * np.log(probabilities[nonzero])
    )) / math.log(bin_count)
    if not math.isfinite(entropy):
        return 0.0
    return float(np.clip(entropy, 0.0, 1.0))


class NoveltyEstimator:
    """Estimate normalized change against one stream's recent history.

    The default history contains 32 prior frames (eight seconds at 4 Hz).
    During the initial fill, :meth:`update` returns ``0.0``.  Once warm, every
    feature is compared with its rolling median and scaled by its own MAD.  A
    fixed floor handles a zero MAD, and a per-feature cap prevents any single
    dimension from dominating the aggregate.

    Instances own their history.  Create one estimator for every independent
    channel or stream; there is no module-level mutable state.
    """

    def __init__(
        self,
        *,
        update_rate_hz: float = NOVELTY_DEFAULT_UPDATE_RATE_HZ,
        history_seconds: float = NOVELTY_DEFAULT_HISTORY_SECONDS,
        scale_floor: float = NOVELTY_DEFAULT_SCALE_FLOOR,
        max_dimension_distance: float = NOVELTY_DEFAULT_MAX_DIMENSION_DISTANCE,
    ) -> None:
        update_rate = self._positive_finite(update_rate_hz, "update_rate_hz")
        history_duration = self._positive_finite(
            history_seconds, "history_seconds"
        )
        self.scale_floor = self._positive_finite(scale_floor, "scale_floor")
        self.max_dimension_distance = self._positive_finite(
            max_dimension_distance, "max_dimension_distance"
        )
        self.history_capacity = max(1, int(round(update_rate * history_duration)))
        self._history: deque[tuple[float, ...]] = deque(
            maxlen=self.history_capacity
        )

    @staticmethod
    def _positive_finite(value: float, name: str) -> float:
        try:
            converted = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{name} must be a positive finite number") from exc
        if not math.isfinite(converted) or converted <= 0.0:
            raise ValueError(f"{name} must be a positive finite number")
        return converted

    @staticmethod
    def _normalized(value: float, name: str) -> float:
        try:
            converted = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{name} must be finite and numeric") from exc
        if not math.isfinite(converted):
            raise ValueError(f"{name} must be finite and numeric")
        return min(1.0, max(0.0, converted))

    @classmethod
    def _frame(
        cls,
        energy: float,
        centroid: float,
        mobility: float,
        spectral_entropy: float,
        band_powers: Mapping[str, float],
    ) -> tuple[float, ...]:
        if not isinstance(band_powers, Mapping):
            raise ValueError("band_powers must map delta, theta, alpha, and beta")
        expected = set(NOVELTY_BAND_ORDER)
        supplied = set(band_powers)
        if supplied != expected:
            missing = sorted(expected - supplied)
            extra = sorted(supplied - expected)
            raise ValueError(
                "band_powers must contain exactly delta, theta, alpha, and beta; "
                f"missing={missing}, extra={extra}"
            )

        values = (energy, centroid, mobility, spectral_entropy) + tuple(
            band_powers[name] for name in NOVELTY_BAND_ORDER
        )
        return tuple(
            cls._normalized(value, name)
            for name, value in zip(NOVELTY_FEATURE_ORDER, values)
        )

    @property
    def history_length(self) -> int:
        """Number of valid frames currently held for this estimator."""
        return len(self._history)

    @property
    def is_warm(self) -> bool:
        """Whether a complete prior-history window is available."""
        return len(self._history) == self.history_capacity

    def reset(self) -> None:
        """Discard this estimator's history without affecting other instances."""
        self._history.clear()

    def update(
        self,
        energy: float,
        centroid: float,
        mobility: float,
        spectral_entropy: float,
        band_powers: Mapping[str, float],
    ) -> float:
        """Add one normalized frame and return deterministic novelty in [0, 1].

        The current frame is excluded from the reference statistics: novelty is
        calculated from the existing prior-frame deque, then the current frame
        is appended.  Invalid or non-finite values raise ``ValueError`` before
        state is changed; finite values outside the normalized domain are
        clamped to its nearest endpoint.
        """
        current = self._frame(
            energy, centroid, mobility, spectral_entropy, band_powers
        )

        if not self.is_warm:
            novelty = 0.0
        else:
            history = np.asarray(self._history, dtype=float)
            center = np.median(history, axis=0)
            mad = np.median(np.abs(history - center), axis=0)
            robust_scale = np.maximum(1.4826 * mad, self.scale_floor)
            standardized = np.abs(np.asarray(current) - center) / robust_scale
            bounded = np.minimum(standardized, self.max_dimension_distance)
            aggregate = float(np.mean(bounded))
            novelty = -math.expm1(-aggregate)
            if not math.isfinite(novelty):
                novelty = 0.0
            novelty = min(1.0, max(0.0, novelty))

        self._history.append(current)
        return novelty
