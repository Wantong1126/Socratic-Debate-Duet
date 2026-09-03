"""Versioned OSC contract for one candidate organism control frame."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import ClassVar, Mapping, Sequence


ORGANISM_PROTOCOL_VERSION = 2
ORGANISM_FRAME_ADDRESS = "/eeg/organism/v2/frame"
ORGANISM_STOP_ADDRESS = "/eeg/organism/v2/stop"
ORGANISM_PARAMETER_ORDER = (
    "energy",
    "centroid",
    "mobility",
    "spectral_entropy",
    "novelty",
    "delta",
    "theta",
    "alpha",
    "beta",
)
DEFAULT_OSC_HOST = "127.0.0.1"
DEFAULT_OSC_PORT = 57120


def clamp_unit(value: float, *, name: str = "value") -> float:
    """Return a finite float in [0, 1]; non-finite input safely becomes zero."""
    try:
        converted = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(converted):
        return 0.0
    return min(1.0, max(0.0, converted))


def validate_controls(controls: Mapping[str, float]) -> dict[str, float]:
    """Require exactly the v2 fields and return them in protocol order."""
    expected = set(ORGANISM_PARAMETER_ORDER)
    supplied = set(controls)
    if supplied != expected:
        missing = sorted(expected - supplied)
        extra = sorted(supplied - expected)
        raise ValueError(
            f"Expected exactly {ORGANISM_PARAMETER_ORDER}; "
            f"missing={missing}, extra={extra}"
        )
    return {
        name: clamp_unit(controls[name], name=name)
        for name in ORGANISM_PARAMETER_ORDER
    }


@dataclass(frozen=True)
class OrganismControlFrame:
    """One immutable v2 frame, serialized in the declared field order."""

    version: ClassVar[int] = ORGANISM_PROTOCOL_VERSION
    osc_address: ClassVar[str] = ORGANISM_FRAME_ADDRESS

    energy: float
    centroid: float
    mobility: float
    spectral_entropy: float
    novelty: float
    delta: float
    theta: float
    alpha: float
    beta: float

    def __post_init__(self) -> None:
        for name in ORGANISM_PARAMETER_ORDER:
            object.__setattr__(self, name, clamp_unit(getattr(self, name), name=name))

    @classmethod
    def from_mapping(cls, controls: Mapping[str, float]) -> "OrganismControlFrame":
        return cls(**validate_controls(controls))

    @classmethod
    def from_values(cls, values: Sequence[float]) -> "OrganismControlFrame":
        if len(values) != len(ORGANISM_PARAMETER_ORDER):
            raise ValueError(
                f"Expected {len(ORGANISM_PARAMETER_ORDER)} values, got {len(values)}"
            )
        return cls(**dict(zip(ORGANISM_PARAMETER_ORDER, values)))

    def as_mapping(self) -> dict[str, float]:
        return {name: getattr(self, name) for name in ORGANISM_PARAMETER_ORDER}

    def as_osc_values(self) -> tuple[float, ...]:
        return tuple(getattr(self, name) for name in ORGANISM_PARAMETER_ORDER)


class OrganismControlSender:
    """Send atomic v2 frames without owning acquisition or synthesis."""

    def __init__(
        self,
        host: str = DEFAULT_OSC_HOST,
        port: int = DEFAULT_OSC_PORT,
        *,
        frame_address: str = ORGANISM_FRAME_ADDRESS,
        stop_address: str = ORGANISM_STOP_ADDRESS,
        client=None,
    ) -> None:
        try:
            parsed_port = int(port)
        except (TypeError, ValueError) as exc:
            raise ValueError("OSC port must be an integer") from exc
        if not 1 <= parsed_port <= 65535:
            raise ValueError("OSC port must be between 1 and 65535")
        if not str(frame_address).startswith("/"):
            raise ValueError("OSC frame address must start with '/'")
        if not str(stop_address).startswith("/"):
            raise ValueError("OSC stop address must start with '/'")

        self.host = str(host)
        self.port = parsed_port
        self.frame_address = str(frame_address)
        self.stop_address = str(stop_address)
        if client is None:
            from pythonosc.udp_client import SimpleUDPClient

            client = SimpleUDPClient(self.host, self.port)
        self.client = client
        self.frame_count = 0

    def send(
        self,
        frame: OrganismControlFrame | Mapping[str, float] | Sequence[float],
    ) -> OrganismControlFrame:
        if isinstance(frame, OrganismControlFrame):
            validated = frame
        elif isinstance(frame, Mapping):
            validated = OrganismControlFrame.from_mapping(frame)
        else:
            validated = OrganismControlFrame.from_values(frame)
        self.client.send_message(self.frame_address, list(validated.as_osc_values()))
        self.frame_count += 1
        return validated

    def send_stop(self) -> None:
        self.client.send_message(self.stop_address, [])

    def close(self) -> None:
        socket = getattr(self.client, "_sock", None)
        if socket is not None:
            socket.close()
