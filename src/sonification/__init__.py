"""Focused building blocks for the candidate harmonic sonification path.

This package does not acquire EEG or start a live pipeline. Existing acquisition,
preprocessing, feature extraction, and SuperCollider entry points remain in place.
"""

from .harmonics_mapping import (
    EEG_BAND_ORDER,
    band_controls_to_group_amplitudes,
    band_controls_to_harmonics_frame,
)
from .harmonics_protocol import (
    HARMONICS_FRAME_ADDRESS,
    HARMONICS_PARAMETER_ORDER,
    HarmonicsControlFrame,
)

__all__ = (
    "EEG_BAND_ORDER",
    "HARMONICS_FRAME_ADDRESS",
    "HARMONICS_PARAMETER_ORDER",
    "HarmonicsControlFrame",
    "band_controls_to_group_amplitudes",
    "band_controls_to_harmonics_frame",
)
