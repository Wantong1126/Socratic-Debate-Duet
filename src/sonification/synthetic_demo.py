"""Finite synthetic transport for the versioned organism control frame.

The demo generates controls only. It does not acquire EEG or implement melody,
pitch selection, harmony, channels, or debater-specific behavior.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from typing import Callable, Iterator

from .controls import BAND_FIELDS, DESCRIPTOR_FIELDS
from .protocol import (
    DEFAULT_OSC_HOST,
    DEFAULT_OSC_PORT,
    ORGANISM_PARAMETER_ORDER,
    ORGANISM_STOP_ADDRESS,
    OrganismControlFrame,
    OrganismControlSender,
)


MODES = ("descriptor", "band", "combined", "stop")
SWEEP_FIELDS = DESCRIPTOR_FIELDS + BAND_FIELDS
DEFAULT_RATE_HZ = 4.0
DEFAULT_ISOLATED_DURATION = 20.0
DEFAULT_COMBINED_DURATION = 24.0
ISOLATED_LOW = 0.0
ISOLATED_HIGH = 1.0
ISOLATED_BAND_BASELINE = 0.01
ISOLATED_MASTER_ENERGY = 0.68
BASELINE = {
    "energy": 0.62,
    "centroid": 0.42,
    "mobility": 0.28,
    "spectral_entropy": 0.38,
    "novelty": 0.20,
    "delta": 0.82,
    "theta": 0.58,
    "alpha": 0.32,
    "beta": 0.14,
}


def _smoothstep(value: float) -> float:
    bounded = min(1.0, max(0.0, value))
    return bounded * bounded * (3.0 - (2.0 * bounded))


def _out_and_back(position: float) -> float:
    bounded = min(1.0, max(0.0, position))
    return _smoothstep(1.0 - abs((2.0 * bounded) - 1.0))


def audition_value_at(elapsed: float, *, duration: float = DEFAULT_ISOLATED_DURATION):
    """LOW hold -> rise -> HIGH hold -> fall -> LOW hold, five equal stages."""
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("duration must be finite and positive")
    elapsed = min(duration, max(0.0, float(elapsed)))
    stage_seconds = duration / 5.0
    if elapsed < stage_seconds:
        blend = 0.0
    elif elapsed < stage_seconds * 2:
        blend = _smoothstep((elapsed - stage_seconds) / stage_seconds)
    elif elapsed < stage_seconds * 3:
        blend = 1.0
    elif elapsed < stage_seconds * 4:
        blend = 1.0 - _smoothstep(
            (elapsed - (stage_seconds * 3)) / stage_seconds
        )
    else:
        blend = 0.0
    return ISOLATED_LOW + ((ISOLATED_HIGH - ISOLATED_LOW) * blend)


def isolated_frame_at(
    elapsed: float,
    *,
    field: str,
    duration: float = DEFAULT_ISOLATED_DURATION,
) -> OrganismControlFrame:
    """Audition exactly one descriptor or band with audible endpoint holds."""
    if field not in SWEEP_FIELDS:
        raise ValueError(f"field must be one of {SWEEP_FIELDS}")
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("duration must be finite and positive")
    values = BASELINE.copy()
    value = audition_value_at(elapsed, duration=duration)
    if field in BAND_FIELDS:
        values["energy"] = ISOLATED_MASTER_ENERGY
        for band in BAND_FIELDS:
            values[band] = ISOLATED_BAND_BASELINE
    values[field] = value
    return OrganismControlFrame.from_mapping(values)


def combined_frame_at(
    elapsed: float,
    *,
    duration: float = DEFAULT_COMBINED_DURATION,
) -> OrganismControlFrame:
    """Return a slow, deterministic transport stress/demo frame."""
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("duration must be finite and positive")
    position = min(1.0, max(0.0, float(elapsed) / duration))
    forward = _smoothstep(position)
    round_trip = _out_and_back(position)
    values = {
        "energy": 0.24 + (0.52 * round_trip),
        "centroid": 0.18 + (0.62 * forward),
        "mobility": 0.16 + (0.48 * round_trip),
        "spectral_entropy": 0.72 - (0.38 * forward),
        "novelty": 0.12 + (0.44 * round_trip),
        "delta": 0.90 - (0.72 * forward),
        "theta": 0.62 - (0.24 * forward),
        "alpha": 0.24 + (0.28 * forward),
        "beta": 0.10 + (0.70 * forward),
    }
    return OrganismControlFrame.from_mapping(values)


def frame_at(
    elapsed: float,
    *,
    mode: str,
    field: str | None = None,
    duration: float,
) -> OrganismControlFrame:
    if mode == "descriptor":
        if field not in DESCRIPTOR_FIELDS:
            raise ValueError(f"descriptor field must be one of {DESCRIPTOR_FIELDS}")
        return isolated_frame_at(elapsed, field=field, duration=duration)
    if mode == "band":
        if field not in BAND_FIELDS:
            raise ValueError(f"band field must be one of {BAND_FIELDS}")
        return isolated_frame_at(elapsed, field=field, duration=duration)
    if mode == "combined":
        if field is not None:
            raise ValueError("combined mode does not accept a field")
        return combined_frame_at(elapsed, duration=duration)
    raise ValueError("frame mode must be descriptor, band, or combined")


def iter_frames(
    mode: str,
    *,
    field: str | None = None,
    duration: float = DEFAULT_ISOLATED_DURATION,
    rate: float = DEFAULT_RATE_HZ,
) -> Iterator[tuple[float, OrganismControlFrame]]:
    if not math.isfinite(rate) or not 0 < rate <= 20:
        raise ValueError("rate must be finite and in (0, 20]")
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("duration must be finite and positive")
    frame_count = int(round(duration * rate))
    for index in range(frame_count + 1):
        elapsed = min(duration, index / rate)
        yield elapsed, frame_at(
            elapsed,
            mode=mode,
            field=field,
            duration=duration,
        )


def _diagnostic_line(
    frame: OrganismControlFrame,
    *,
    sequence: int,
    elapsed: float,
    interval: float | None,
    effective_hz: float,
    skipped_deadlines: int,
) -> str:
    row = {
        "sequence": int(sequence),
        "elapsed_seconds": round(float(elapsed), 3),
        "interval_seconds": (
            None if interval is None else round(float(interval), 4)
        ),
        "effective_send_hz": round(float(effective_hz), 3),
        "skipped_deadlines": int(skipped_deadlines),
        **frame.as_mapping(),
    }
    return json.dumps(row, separators=(",", ":"))


def run_transport(
    mode: str,
    *,
    field: str | None = None,
    duration: float = DEFAULT_ISOLATED_DURATION,
    rate: float = DEFAULT_RATE_HZ,
    sender: OrganismControlSender | None = None,
    dry_run: bool = False,
    loop: bool = False,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    printer: Callable[[str], None] = print,
) -> int:
    """Send on monotonic deadlines, dropping stale frames instead of catching up."""
    if not dry_run and sender is None:
        raise ValueError("sender is required unless dry_run is true")
    if loop and dry_run:
        raise ValueError("--loop requires real-time transport; omit --dry-run")
    if not math.isfinite(rate) or not 0 < rate <= 20:
        raise ValueError("rate must be finite and in (0, 20]")
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("duration must be finite and positive")

    interval_seconds = 1.0 / rate
    cycle_steps = max(1, int(round(duration * rate)))
    final_step = cycle_steps
    started = clock()
    previous_report_at = started
    previous_report_elapsed = 0.0
    previous_report_sent = 0
    previous_send_at = None
    sent = 0
    skipped = 0
    sequence = 0

    while loop or sequence <= final_step:
        scheduled_elapsed = sequence * interval_seconds
        if not dry_run:
            deadline = started + scheduled_elapsed
            now = clock()
            lateness = now - deadline
            if lateness >= interval_seconds:
                # Advance to the first deadline that is not already stale. Using
                # ceil rather than floor prevents one immediate catch-up packet.
                missed = max(
                    1,
                    int(math.ceil((lateness / interval_seconds) - 1e-9)),
                )
                sequence += missed
                skipped += missed
                continue
            if now < deadline:
                sleeper(deadline - now)

        cycle_elapsed = (
            (sequence % cycle_steps) * interval_seconds
            if loop
            else min(duration, scheduled_elapsed)
        )
        frame = frame_at(
            cycle_elapsed,
            mode=mode,
            field=field,
            duration=duration,
        )
        if not dry_run:
            sender.send(frame)
            send_at = clock()
        else:
            # Dry-run is intentionally immediate; virtual scheduled time keeps its
            # diagnostics useful without pretending to measure wall-clock sends.
            send_at = started + scheduled_elapsed
        sent += 1

        latest_interval = (
            None if previous_send_at is None else send_at - previous_send_at
        )
        report_due = (
            sequence == 0
            or (scheduled_elapsed - previous_report_elapsed) >= 1.0
        )
        if report_due:
            report_window = send_at - previous_report_at
            if sequence == 0:
                measured_rate = 0.0
            elif dry_run:
                measured_rate = rate
            else:
                measured_rate = (sent - previous_report_sent) / max(
                    report_window, 1e-9
                )
            printer(_diagnostic_line(
                frame,
                sequence=sequence,
                elapsed=send_at - started,
                interval=latest_interval,
                effective_hz=measured_rate,
                skipped_deadlines=skipped,
            ))
            previous_report_at = send_at
            previous_report_elapsed = scheduled_elapsed
            previous_report_sent = sent
        previous_send_at = send_at
        sequence += 1
    return sent


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, default="combined")
    parser.add_argument("--field", choices=SWEEP_FIELDS)
    parser.add_argument(
        "--duration",
        type=float,
        help="override 20 s isolated or 24 s combined one-shot duration",
    )
    parser.add_argument("--rate", type=float, default=DEFAULT_RATE_HZ)
    parser.add_argument(
        "--loop",
        action="store_true",
        help="repeat the complete trajectory until Ctrl+C",
    )
    parser.add_argument("--host", default=DEFAULT_OSC_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_OSC_PORT)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="generate immediately without opening or sending through an OSC socket",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.mode == "descriptor" and args.field not in DESCRIPTOR_FIELDS:
        raise SystemExit(f"--mode descriptor requires --field in {DESCRIPTOR_FIELDS}")
    if args.mode == "band" and args.field not in BAND_FIELDS:
        raise SystemExit(f"--mode band requires --field in {BAND_FIELDS}")
    if args.mode in ("combined", "stop") and args.field is not None:
        raise SystemExit(f"--mode {args.mode} does not accept --field")
    if args.mode == "stop" and args.loop:
        raise SystemExit("--mode stop does not accept --loop")
    if args.loop and args.dry_run:
        raise SystemExit("--loop requires real-time transport; omit --dry-run")

    duration = args.duration
    if duration is None:
        duration = (
            DEFAULT_COMBINED_DURATION
            if args.mode == "combined"
            else DEFAULT_ISOLATED_DURATION
        )

    sender = None
    try:
        if args.mode == "stop":
            if args.dry_run:
                print(json.dumps({"stop_address": ORGANISM_STOP_ADDRESS, "sent": False}))
            else:
                sender = OrganismControlSender(args.host, args.port)
                sender.send_stop()
                print(json.dumps({"stop_address": ORGANISM_STOP_ADDRESS, "sent": True}))
            return 0

        if not args.dry_run:
            sender = OrganismControlSender(args.host, args.port)
        if args.loop:
            print(
                f"LOOP mode: {duration:.1f}s trajectory at {args.rate:.3g} Hz; "
                "press Ctrl+C to stop."
            )
        else:
            shape = (
                "combined control trajectory"
                if args.mode == "combined"
                else "LOW hold -> rise -> HIGH hold -> fall -> LOW hold"
            )
            print(
                f"ONE-SHOT mode: {duration:.1f}s at {args.rate:.3g} Hz; "
                f"{shape}."
            )
        sent = run_transport(
            args.mode,
            field=args.field,
            duration=duration,
            rate=args.rate,
            sender=sender,
            dry_run=args.dry_run,
            loop=args.loop,
        )
        if not args.loop:
            print(f"ONE-SHOT complete: sent {sent} scheduled frames.")
    except KeyboardInterrupt:
        print("Synthetic transport stopped; the SuperCollider watchdog will fade output.")
        return 130
    finally:
        if sender is not None:
            sender.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
