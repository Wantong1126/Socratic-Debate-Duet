"""Bounded OSC transport and configuration for the EEG organism engine."""

from __future__ import annotations

import math
from pathlib import Path
import time
import tomllib
from typing import Mapping

from pythonosc.udp_client import SimpleUDPClient

from .eeg_control_features import CHANNELS, control_names

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "sonification.toml"
FRAME_ORDER = control_names()

# This order is part of the Python -> SuperCollider configuration protocol.
# Integer path elements index TOML arrays. Keep it in sync with configOrder in
# sound/eeg_organism_engine.scd. The 18-value EEG frame protocol is unchanged.
CONFIG_PATHS = (
    ("energy", "minimum_db"),
    ("energy", "maximum_db"),
    ("energy", "lag_seconds"),
    ("centroid", "tilt_min"),
    ("centroid", "tilt_max"),
    ("centroid", "high_compensation_db"),
    ("centroid", "lag_seconds"),
    ("mobility", "rate_min_hz"),
    ("mobility", "rate_max_hz"),
    ("mobility", "depth_min"),
    ("mobility", "depth_max"),
    ("mobility", "lag_seconds"),
    ("smoothing", "varlag_curve"),
    ("tonal", "fundamental_hz"),
    *(("harmonics", family, index) for family in ("P", "C", "F") for index in range(4)),
    ("source", "cell_level"),
    ("reverb", "mix"),
    ("reverb", "room"),
    ("reverb", "damping"),
    ("master", "level"),
    ("master", "limiter_level"),
    ("master", "attack_seconds"),
    ("master", "release_seconds"),
    ("master", "watchdog_fade_seconds"),
    *(("pan", channel) for channel in CHANNELS),
)


def load_sonification_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict:
    """Read the human-editable TOML configuration with Python 3.12 tomllib."""
    with Path(path).open("rb") as handle:
        return tomllib.load(handle)


def _finite_float(value, *, fallback=0.0) -> float:
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return float(fallback)
    return converted if math.isfinite(converted) else float(fallback)


def bounded_frame_values(controls: Mapping[str, float]) -> tuple[float, ...]:
    """Return all 18 controls in canonical order, finite and clamped to [0, 1]."""
    if set(controls) != set(FRAME_ORDER):
        missing = sorted(set(FRAME_ORDER) - set(controls))
        extra = sorted(set(controls) - set(FRAME_ORDER))
        raise ValueError(f"Expected exactly the 18 canonical controls; missing={missing}, extra={extra}")
    return tuple(min(1.0, max(0.0, _finite_float(controls[name]))) for name in FRAME_ORDER)


def config_values(config: Mapping) -> tuple[float, ...]:
    """Flatten tunable values into the documented SuperCollider config order."""
    values = []
    for path in CONFIG_PATHS:
        try:
            raw = config
            for component in path:
                raw = raw[component]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"Missing config value at {path}") from exc
        value = _finite_float(raw, fallback=math.nan)
        if not math.isfinite(value):
            raise ValueError(f"Config value at {path} must be finite")
        values.append(value)
    return tuple(values)


class OrganismOscSender:
    """Send one 18-float OSC packet per EEG control frame."""

    def __init__(self, host="127.0.0.1", port=57120, *, frame_address="/eeg/organism/frame",
                 config_address="/eeg/organism/config",
                 audition_address="/eeg/organism/audition",
                 stop_address="/eeg/organism/stop", client=None):
        self.host = str(host)
        self.port = int(port)
        self.frame_address = str(frame_address)
        self.config_address = str(config_address)
        self.audition_address = str(audition_address)
        self.stop_address = str(stop_address)
        self.client = client or SimpleUDPClient(self.host, self.port)
        self.packet_count = 0
        self.last_values = {}
        self.started_at = time.monotonic()

    @classmethod
    def from_config(cls, config: Mapping, client=None):
        osc = config["osc"]
        return cls(osc["host"], osc["port"], frame_address=osc["frame_address"],
                   config_address=osc["config_address"], audition_address=osc["audition_address"],
                   stop_address=osc["stop_address"],
                   client=client)

    def send(self, controls: Mapping[str, float]):
        values = bounded_frame_values(controls)
        self.client.send_message(self.frame_address, list(values))
        self.last_values = dict(zip(FRAME_ORDER, values))
        self.packet_count += 1

    def send_config(self, config: Mapping):
        self.client.send_message(self.config_address, list(config_values(config)))
        self.packet_count += 1

    def send_audition_mask(self, enabled):
        """Enable/mute the six persistent cells without changing node identity."""
        values = tuple(min(1.0, max(0.0, _finite_float(value))) for value in enabled)
        if len(values) != len(CHANNELS):
            raise ValueError("An audition mask must contain exactly six values")
        self.client.send_message(self.audition_address, list(values))
        self.packet_count += 1

    def send_stop(self):
        self.client.send_message(self.stop_address, [])
        self.packet_count += 1

    @property
    def packet_rate(self):
        elapsed = time.monotonic() - self.started_at
        return self.packet_count / elapsed if elapsed > 0 else 0.0

    def close(self):
        socket = getattr(self.client, "_sock", None)
        if socket is not None:
            socket.close()
