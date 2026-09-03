"""Validation and OSC serialization for the candidate harmonic instrument.

The SuperCollider manual instrument intentionally has no handler for this address
yet. Keeping the protocol here allows synthetic and future live producers to share
one strict packet contract without coupling acquisition to synthesis.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence


HARMONICS_FRAME_ADDRESS = "/eeg/harmonics/frame"
HARMONICS_PARAMETER_ORDER = (
    "master_energy",
    "group1",
    "group2",
    "group3",
    "group4",
)
DEFAULT_OSC_HOST = "127.0.0.1"
DEFAULT_OSC_PORT = 57120


def clamp_unit(value: float, *, name: str = "value") -> float:
    """Convert a finite number to float and clamp it to the closed unit range."""
    try:
        converted = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return min(1.0, max(0.0, converted))


def validate_harmonics_controls(controls: Mapping[str, float]) -> dict[str, float]:
    """Require exactly the canonical controls and return clamped ordered values."""
    expected = set(HARMONICS_PARAMETER_ORDER)
    supplied = set(controls)
    if supplied != expected:
        missing = sorted(expected - supplied)
        extra = sorted(supplied - expected)
        raise ValueError(
            f"Expected exactly {HARMONICS_PARAMETER_ORDER}; "
            f"missing={missing}, extra={extra}"
        )
    return {
        name: clamp_unit(controls[name], name=name)
        for name in HARMONICS_PARAMETER_ORDER
    }


@dataclass(frozen=True)
class HarmonicsControlFrame:
    """One atomic master-plus-four-groups control frame."""

    master_energy: float
    group1: float
    group2: float
    group3: float
    group4: float

    def __post_init__(self) -> None:
        for name in HARMONICS_PARAMETER_ORDER:
            object.__setattr__(self, name, clamp_unit(getattr(self, name), name=name))

    @classmethod
    def from_mapping(cls, controls: Mapping[str, float]) -> "HarmonicsControlFrame":
        return cls(**validate_harmonics_controls(controls))

    @classmethod
    def from_values(cls, values: Sequence[float]) -> "HarmonicsControlFrame":
        if len(values) != len(HARMONICS_PARAMETER_ORDER):
            raise ValueError(
                f"Expected {len(HARMONICS_PARAMETER_ORDER)} values, got {len(values)}"
            )
        return cls(**dict(zip(HARMONICS_PARAMETER_ORDER, values)))

    def as_mapping(self) -> dict[str, float]:
        return {name: getattr(self, name) for name in HARMONICS_PARAMETER_ORDER}

    def as_osc_values(self) -> tuple[float, ...]:
        return tuple(getattr(self, name) for name in HARMONICS_PARAMETER_ORDER)


class HarmonicsOscSender:
    """Send validated frames; construction alone performs no network operation."""

    def __init__(
        self,
        host: str = DEFAULT_OSC_HOST,
        port: int = DEFAULT_OSC_PORT,
        *,
        address: str = HARMONICS_FRAME_ADDRESS,
        client=None,
    ) -> None:
        if not 1 <= int(port) <= 65535:
            raise ValueError("OSC port must be between 1 and 65535")
        if not str(address).startswith("/"):
            raise ValueError("OSC address must start with '/'")
        self.host = str(host)
        self.port = int(port)
        self.address = str(address)
        if client is None:
            from pythonosc.udp_client import SimpleUDPClient

            client = SimpleUDPClient(self.host, self.port)
        self.client = client
        self.packet_count = 0

    def send(self, frame: HarmonicsControlFrame | Mapping[str, float]) -> None:
        validated = (
            frame
            if isinstance(frame, HarmonicsControlFrame)
            else HarmonicsControlFrame.from_mapping(frame)
        )
        self.client.send_message(self.address, list(validated.as_osc_values()))
        self.packet_count += 1

    def close(self) -> None:
        socket = getattr(self.client, "_sock", None)
        if socket is not None:
            socket.close()
