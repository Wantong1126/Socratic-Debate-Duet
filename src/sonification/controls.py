"""Pure control-domain mapping for the v2 harmonic instrument.

This module has no OSC, clock, EEG acquisition, or SuperCollider dependency.
It deliberately does not choose pitches, scales, melodies, or voices.
"""

from __future__ import annotations

from dataclasses import dataclass

from .protocol import OrganismControlFrame


DESCRIPTOR_FIELDS = (
    "energy",
    "centroid",
    "mobility",
    "spectral_entropy",
    "novelty",
)
BAND_FIELDS = ("delta", "theta", "alpha", "beta")
HARMONIC_GROUP_FIELDS = BAND_FIELDS


@dataclass(frozen=True)
class HarmonicInstrumentControls:
    """The only v2 values currently allowed to affect the instrument."""

    master_energy: float
    group_amplitudes: tuple[float, float, float, float]


def frame_to_instrument_controls(
    frame: OrganismControlFrame,
) -> HarmonicInstrumentControls:
    """Map presence and spectral groups without coupling their domains.

    The persistent SuperCollider Synth performs its own smoothed spectral-energy
    normalization. Centroid, mobility, entropy, and novelty are intentionally not
    represented in the returned instrument update.
    """
    return HarmonicInstrumentControls(
        master_energy=frame.energy,
        group_amplitudes=(frame.delta, frame.theta, frame.alpha, frame.beta),
    )
