"""Deterministic synthetic control sweeps for the candidate harmonics protocol.

Default operation prints frames immediately and does not open a socket. Use
``--send`` explicitly for real-time OSC transmission after a compatible receiver
has been approved and installed.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from typing import Iterator

from .harmonics_mapping import band_controls_to_harmonics_frame
from .harmonics_protocol import (
    DEFAULT_OSC_HOST,
    DEFAULT_OSC_PORT,
    HARMONICS_FRAME_ADDRESS,
    HarmonicsControlFrame,
    HarmonicsOscSender,
)


SWEEP_NAMES = ("master", "brightness", "groups")
BASE_BANDS = {"delta": 1.0, "theta": 0.70, "alpha": 0.34, "beta": 0.16}
WARM_BANDS = {"delta": 1.0, "theta": 0.34, "alpha": 0.08, "beta": 0.02}
BRIGHT_BANDS = {"delta": 0.02, "theta": 0.08, "alpha": 0.34, "beta": 1.0}


def _smoothstep(value: float) -> float:
    bounded = min(1.0, max(0.0, value))
    return bounded * bounded * (3.0 - 2.0 * bounded)


def _out_and_back(position: float) -> float:
    triangle = 1.0 - abs((2.0 * min(1.0, max(0.0, position))) - 1.0)
    return _smoothstep(triangle)


def _interpolate(left: dict[str, float], right: dict[str, float], blend: float):
    return {name: left[name] + (right[name] - left[name]) * blend for name in left}


def synthetic_frame_at(
    elapsed: float,
    *,
    sweep: str,
    duration: float = 16.0,
) -> HarmonicsControlFrame:
    """Return a deterministic bounded frame without network or wall-clock access."""
    if sweep not in SWEEP_NAMES:
        raise ValueError(f"sweep must be one of {SWEEP_NAMES}")
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("duration must be finite and positive")
    position = min(1.0, max(0.0, float(elapsed) / duration))

    if sweep == "master":
        master = 0.18 + (0.72 * _out_and_back(position))
        return band_controls_to_harmonics_frame(BASE_BANDS, master)
    if sweep == "brightness":
        bands = _interpolate(WARM_BANDS, BRIGHT_BANDS, _out_and_back(position))
        return band_controls_to_harmonics_frame(bands, 0.66)

    # Sequential continuous crossfades through delta/theta/alpha/beta, which map
    # directly to groups 1/2/3/4. No trigger or note event is generated.
    scaled = position * 3.0
    left_index = min(2, int(scaled))
    blend = _smoothstep(scaled - left_index)
    bands = {name: 0.0 for name in BASE_BANDS}
    band_names = tuple(BASE_BANDS)
    bands[band_names[left_index]] = 1.0 - blend
    bands[band_names[left_index + 1]] = blend
    return band_controls_to_harmonics_frame(bands, 0.66)


def iter_sweep(
    sweep: str,
    *,
    duration: float = 16.0,
    rate: float = 4.0,
) -> Iterator[tuple[float, HarmonicsControlFrame]]:
    if not math.isfinite(rate) or not 0 < rate <= 20:
        raise ValueError("rate must be finite and in (0, 20]")
    count = int(round(duration * rate))
    for index in range(count + 1):
        elapsed = min(duration, index / rate)
        yield elapsed, synthetic_frame_at(elapsed, sweep=sweep, duration=duration)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep", choices=SWEEP_NAMES, default="brightness")
    parser.add_argument("--duration", type=float, default=16.0)
    parser.add_argument("--rate", type=float, default=4.0)
    parser.add_argument("--send", action="store_true",
                        help="explicitly send real-time OSC instead of dry-run output")
    parser.add_argument("--realtime", action="store_true",
                        help="pace dry-run output in real time; --send always does this")
    parser.add_argument("--host", default=DEFAULT_OSC_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_OSC_PORT)
    parser.add_argument("--address", default=HARMONICS_FRAME_ADDRESS)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    frames = iter_sweep(args.sweep, duration=args.duration, rate=args.rate)
    sender = (
        HarmonicsOscSender(args.host, args.port, address=args.address)
        if args.send
        else None
    )
    started = time.monotonic()
    try:
        for elapsed, frame in frames:
            if args.send or args.realtime:
                delay = (started + elapsed) - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
            if sender is not None:
                sender.send(frame)
            else:
                print(json.dumps({"seconds": elapsed, **frame.as_mapping()}, sort_keys=False))
    finally:
        if sender is not None:
            sender.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
