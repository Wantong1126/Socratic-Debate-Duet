"""Focused building blocks for the candidate harmonic sonification path.

This package does not acquire EEG or start a live pipeline. Existing acquisition,
preprocessing, feature extraction, and SuperCollider entry points remain in place.
"""

from .controls import (
    BAND_FIELDS,
    DESCRIPTOR_FIELDS,
    HarmonicInstrumentControls,
    frame_to_instrument_controls,
)
from .features import (
    NOVELTY_FEATURE_ORDER,
    NoveltyEstimator,
    spectral_entropy,
)
from .protocol import (
    ORGANISM_FRAME_ADDRESS,
    ORGANISM_PARAMETER_ORDER,
    ORGANISM_PROTOCOL_VERSION,
    ORGANISM_STOP_ADDRESS,
    ORGANISM_VOICE_CAPACITY,
    ORGANISM_VOICING_ADDRESS,
    ORGANISM_VOICING_PARAMETER_ORDER,
    OrganismControlFrame,
    OrganismControlSender,
    OrganismVoicingFrame,
)

# Compatibility exports for the already documented five-control manual demo.
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
    "BAND_FIELDS",
    "DESCRIPTOR_FIELDS",
    "EEG_BAND_ORDER",
    "HARMONICS_FRAME_ADDRESS",
    "HARMONICS_PARAMETER_ORDER",
    "HarmonicInstrumentControls",
    "HarmonicsControlFrame",
    "ORGANISM_FRAME_ADDRESS",
    "ORGANISM_PARAMETER_ORDER",
    "ORGANISM_PROTOCOL_VERSION",
    "ORGANISM_STOP_ADDRESS",
    "ORGANISM_VOICE_CAPACITY",
    "ORGANISM_VOICING_ADDRESS",
    "ORGANISM_VOICING_PARAMETER_ORDER",
    "NOVELTY_FEATURE_ORDER",
    "NoveltyEstimator",
    "OrganismControlFrame",
    "OrganismControlSender",
    "OrganismVoicingFrame",
    "band_controls_to_group_amplitudes",
    "band_controls_to_harmonics_frame",
    "frame_to_instrument_controls",
    "spectral_entropy",
)
