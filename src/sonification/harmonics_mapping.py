"""Pure normalized EEG-band to harmonic-group calculations."""

from __future__ import annotations

import math
from typing import Mapping

from .harmonics_protocol import HarmonicsControlFrame, clamp_unit


EEG_BAND_ORDER = ("delta", "theta", "alpha", "beta")
HARMONIC_GROUP_ORDER = ("group1", "group2", "group3", "group4")

# Canonical direct routing inspired by the published EEGsynth Harmonics principle:
# progressively faster EEG bands address progressively higher harmonic groups.
DEFAULT_BAND_TO_GROUP_ROUTING = {
    "group1": {"delta": 1.0},
    "group2": {"theta": 1.0},
    "group3": {"alpha": 1.0},
    "group4": {"beta": 1.0},
}


def _validated_bands(band_controls: Mapping[str, float]) -> dict[str, float]:
    expected = set(EEG_BAND_ORDER)
    supplied = set(band_controls)
    if supplied != expected:
        missing = sorted(expected - supplied)
        extra = sorted(supplied - expected)
        raise ValueError(
            f"Expected exactly {EEG_BAND_ORDER}; missing={missing}, extra={extra}"
        )
    return {
        band: clamp_unit(band_controls[band], name=band)
        for band in EEG_BAND_ORDER
    }


def _validated_routing(
    routing: Mapping[str, Mapping[str, float]],
) -> dict[str, dict[str, float]]:
    if set(routing) != set(HARMONIC_GROUP_ORDER):
        raise ValueError(f"Routing must define exactly {HARMONIC_GROUP_ORDER}")
    validated: dict[str, dict[str, float]] = {}
    for group in HARMONIC_GROUP_ORDER:
        weights = routing[group]
        if not weights or not set(weights).issubset(EEG_BAND_ORDER):
            raise ValueError(f"{group} routing contains no valid EEG bands")
        validated[group] = {}
        for band, weight in weights.items():
            converted = float(weight)
            if not math.isfinite(converted) or converted < 0:
                raise ValueError(f"Routing weight {group}/{band} must be finite and >= 0")
            validated[group][band] = converted
    return validated


def band_controls_to_group_amplitudes(
    band_controls: Mapping[str, float],
    *,
    routing: Mapping[str, Mapping[str, float]] = DEFAULT_BAND_TO_GROUP_ROUTING,
) -> dict[str, float]:
    """Route four bands, then L2-normalize their harmonic energy distribution.

    Absolute signal presence is intentionally excluded; it belongs to the separate
    ``master_energy`` control. A zero band vector remains silence rather than being
    replaced by an arbitrary spectrum.
    """
    bands = _validated_bands(band_controls)
    routes = _validated_routing(routing)
    raw = {
        group: sum(bands[band] * weight for band, weight in routes[group].items())
        for group in HARMONIC_GROUP_ORDER
    }
    norm = math.sqrt(sum(value * value for value in raw.values()))
    if norm <= 1e-12:
        return {group: 0.0 for group in HARMONIC_GROUP_ORDER}
    return {group: value / norm for group, value in raw.items()}


def band_controls_to_harmonics_frame(
    band_controls: Mapping[str, float],
    master_energy: float,
    *,
    routing: Mapping[str, Mapping[str, float]] = DEFAULT_BAND_TO_GROUP_ROUTING,
) -> HarmonicsControlFrame:
    """Build one validated frame with independent loudness and timbre controls."""
    groups = band_controls_to_group_amplitudes(band_controls, routing=routing)
    return HarmonicsControlFrame(
        master_energy=clamp_unit(master_energy, name="master_energy"),
        **groups,
    )
