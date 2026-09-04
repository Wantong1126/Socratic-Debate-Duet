"""Manual-only transport for the persistent organism v2 voice banks.

The two voicings are fixed G Lydian audition material.  No descriptor selects,
scores, or changes pitch, and this module does not import the offline voicing
decision engine.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from typing import Callable, Sequence

from .protocol import (
    DEFAULT_OSC_HOST,
    DEFAULT_OSC_PORT,
    OrganismControlFrame,
    OrganismControlSender,
    OrganismVoicingFrame,
)


MANUAL_BED_FRAME = OrganismControlFrame(
    energy=0.68,
    centroid=0.5,
    mobility=0.5,
    spectral_entropy=0.5,
    novelty=0.5,
    delta=0.72,
    theta=0.55,
    alpha=0.34,
    beta=0.16,
)

# Contrasting register, cardinality, and interval spacing; every pitch class is
# in G Lydian. The values are static manual test fixtures, not mapped features.
MANUAL_VOICINGS = (
    (
        "grounded_g_lydian",
        OrganismVoicingFrame.from_active(
            (97.998859, 146.832384, 220.0),       # G2, D3, A3
            (0.48, 0.32, 0.20),
        ),
    ),
    (
        "open_bright_g_lydian",
        OrganismVoicingFrame.from_active(
            (138.591315, 184.997211, 277.182631, 369.994423),  # C#3 F#3 C#4 F#4
            (0.34, 0.28, 0.22, 0.16),
        ),
    ),
)


def run_manual_demo(
    *,
    sender: OrganismControlSender,
    hold_seconds: float = 6.0,
    changes: int = 4,
    rate: float = 4.0,
    dry_run: bool = False,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    printer: Callable[[str], None] = print,
) -> int:
    """Alternate fixed voicings while refreshing one unchanged manual frame."""
    if not math.isfinite(hold_seconds) or hold_seconds <= 0:
        raise ValueError("hold_seconds must be finite and positive")
    if changes < 1:
        raise ValueError("changes must be positive")
    if not math.isfinite(rate) or not 0 < rate <= 20:
        raise ValueError("rate must be finite and in (0, 20]")

    interval = 1.0 / rate
    duration = hold_seconds * changes
    start = clock()
    final_step = max(1, int(round(duration * rate)))
    sequence = 0
    current_voicing_index = -1
    sent_frames = 0
    last_report_elapsed = -1.0

    while sequence <= final_step:
        scheduled_elapsed = min(duration, sequence * interval)
        if not dry_run:
            deadline = start + scheduled_elapsed
            now = clock()
            lateness = now - deadline
            if lateness >= interval:
                sequence += max(
                    1, int(math.ceil((lateness / interval) - 1e-9))
                )
                continue
            if now < deadline:
                sleeper(deadline - now)
        voicing_index = min(
            changes - 1, int(scheduled_elapsed / hold_seconds)
        ) % 2
        if voicing_index != current_voicing_index:
            label, voicing = MANUAL_VOICINGS[voicing_index]
            sender.send_voicing(voicing)
            current_voicing_index = voicing_index
            printer(json.dumps({
                "event": "voicing",
                "label": label,
                "frequencies_hz": voicing.frequencies_hz,
                "weights": voicing.weights,
                "elapsed_seconds": round(scheduled_elapsed, 3),
            }))

        sender.send(MANUAL_BED_FRAME)
        sent_frames += 1
        if sequence == 0 or scheduled_elapsed - last_report_elapsed >= 1.0:
            printer(json.dumps({
                "event": "frame",
                "sequence": sequence,
                "elapsed_seconds": round(scheduled_elapsed, 3),
                "send_rate_hz": rate,
                **MANUAL_BED_FRAME.as_mapping(),
            }))
            last_report_elapsed = scheduled_elapsed
        sequence += 1
    return sent_frames


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_OSC_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_OSC_PORT)
    parser.add_argument("--hold", type=float, default=6.0)
    parser.add_argument("--changes", type=int, default=4)
    parser.add_argument("--rate", type=float, default=4.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser


class _DryRunClient:
    def send_message(self, address, values):
        del address, values


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = _DryRunClient() if args.dry_run else None
    sender = OrganismControlSender(args.host, args.port, client=client)
    duration = args.hold * args.changes
    print(
        f"MANUAL VOICING {'DRY-RUN' if args.dry_run else 'SEND'}: "
        f"{args.changes} holds x {args.hold:.3g}s = {duration:.3g}s at "
        f"{args.rate:.3g} frame/s."
    )
    try:
        sent = run_manual_demo(
            sender=sender,
            hold_seconds=args.hold,
            changes=args.changes,
            rate=args.rate,
            dry_run=args.dry_run,
        )
        print(
            f"MANUAL VOICING complete: {sent} frame packets, "
            f"{sender.voicing_count} voicing packets."
        )
    except KeyboardInterrupt:
        print("Manual voicing transport stopped; watchdog will fade the instrument.")
        return 130
    finally:
        sender.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
