"""Synthetic-only integration of v2 controls and persistent voicing.

Control frames continue at a fixed cadence.  The slower music-decision clock
uses only the mappings documented by :mod:`src.sonification.voicing`, and a
voicing packet is sent only when that clock selects different notes.  This
module acquires no EEG and creates no audio/server objects.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import math
from pathlib import Path
import time
from typing import Callable, Iterator, Sequence

from .protocol import (
    DEFAULT_OSC_HOST,
    DEFAULT_OSC_PORT,
    OrganismControlFrame,
    OrganismControlSender,
    OrganismVoicingFrame,
)
from .voicing import (
    DEFAULT_VOICING_SEED,
    TRACE_SCENARIOS,
    GLydianVoicingEngine,
    VoicingControls,
    VoicingDecision,
)


DEFAULT_RATE_HZ = 4.0
DEFAULT_SCENARIO_DURATION = 16.0
DEFAULT_COMBINED_DURATION = 40.0
COMBINED_SCENARIO = "combined"
SCENARIO_NAMES = tuple(TRACE_SCENARIOS) + (COMBINED_SCENARIO,)

# Direct synthetic band fixtures, not descriptor-derived values.  Their sole
# role remains the four harmonic-group coloration already implemented by v2.
SCENARIO_BANDS = {
    "calm-stable": (0.82, 0.58, 0.28, 0.08),
    "bright-stable": (0.16, 0.30, 0.62, 0.66),
    "tense-stable": (0.30, 0.38, 0.52, 0.56),
    "active-novel": (0.38, 0.48, 0.64, 0.50),
}


@dataclass(frozen=True)
class MusicDecisionEvent:
    """One decision-clock result, whether or not it changes the bank."""

    elapsed_seconds: float
    decision: VoicingDecision
    sent: bool
    voicing: OrganismVoicingFrame


@dataclass(frozen=True)
class MusicTimeline:
    """Deterministic one-shot frame and decision plan."""

    scenario: str
    duration_seconds: float
    rate_hz: float
    frames: tuple[tuple[float, OrganismControlFrame], ...]
    decisions: tuple[MusicDecisionEvent, ...]

    @property
    def sent_voicings(self) -> tuple[MusicDecisionEvent, ...]:
        return tuple(event for event in self.decisions if event.sent)


@dataclass(frozen=True)
class MusicTransportResult:
    frame_count: int
    decision_count: int
    voicing_count: int
    skipped_deadlines: int
    elapsed_seconds: float


def _validate_transport(duration: float, rate: float) -> tuple[float, float]:
    duration = float(duration)
    rate = float(rate)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("duration must be finite and positive")
    if not math.isfinite(rate) or not 0 < rate <= 20:
        raise ValueError("rate must be finite and in (0, 20]")
    return duration, rate


def _smoothstep(value: float) -> float:
    bounded = min(1.0, max(0.0, value))
    return bounded * bounded * (3.0 - (2.0 * bounded))


def _static_frame(name: str) -> OrganismControlFrame:
    if name not in TRACE_SCENARIOS:
        raise ValueError(f"unknown static scenario: {name}")
    controls = TRACE_SCENARIOS[name]
    delta, theta, alpha, beta = SCENARIO_BANDS[name]
    return OrganismControlFrame(
        energy=controls.energy,
        centroid=controls.centroid,
        mobility=controls.mobility,
        spectral_entropy=controls.spectral_entropy,
        novelty=controls.novelty,
        delta=delta,
        theta=theta,
        alpha=alpha,
        beta=beta,
    )


def music_frame_at(
    elapsed: float,
    *,
    scenario: str,
    duration: float,
) -> OrganismControlFrame:
    """Return one static scenario frame or a seamless combined interpolation."""
    duration, _ = _validate_transport(duration, DEFAULT_RATE_HZ)
    elapsed = min(duration, max(0.0, float(elapsed)))
    if scenario != COMBINED_SCENARIO:
        return _static_frame(scenario)

    # Calm -> bright -> tense -> active -> calm makes one-shot endpoints calm
    # and gives --loop a continuous boundary rather than a descriptor jump.
    names = tuple(TRACE_SCENARIOS) + (tuple(TRACE_SCENARIOS)[0],)
    if elapsed >= duration:
        return _static_frame(names[-1])
    scaled = (elapsed / duration) * (len(names) - 1)
    index = min(len(names) - 2, int(math.floor(scaled)))
    blend = _smoothstep(scaled - index)
    left = _static_frame(names[index]).as_osc_values()
    right = _static_frame(names[index + 1]).as_osc_values()
    return OrganismControlFrame.from_values(
        tuple(a + ((b - a) * blend) for a, b in zip(left, right))
    )


def iter_music_frames(
    scenario: str,
    *,
    duration: float,
    rate: float = DEFAULT_RATE_HZ,
) -> Iterator[tuple[float, OrganismControlFrame]]:
    """Yield one-shot frame times without an overshoot or duplicate endpoint."""
    if scenario not in SCENARIO_NAMES:
        raise ValueError(f"scenario must be one of {SCENARIO_NAMES}")
    duration, rate = _validate_transport(duration, rate)
    final_step = int(math.floor((duration * rate) + 1e-9))
    for sequence in range(final_step + 1):
        elapsed = sequence / rate
        yield elapsed, music_frame_at(
            elapsed, scenario=scenario, duration=duration
        )


def _voicing_controls(frame: OrganismControlFrame) -> VoicingControls:
    return VoicingControls(
        energy=frame.energy,
        centroid=frame.centroid,
        mobility=frame.mobility,
        spectral_entropy=frame.spectral_entropy,
        novelty=frame.novelty,
    )


def _decision_event(
    engine: GLydianVoicingEngine,
    frame: OrganismControlFrame,
    *,
    elapsed: float,
    last_sent_notes: tuple[int, ...],
) -> MusicDecisionEvent:
    decision = engine.decide(_voicing_controls(frame))
    voicing = OrganismVoicingFrame.from_active(
        decision.frequencies_hz, decision.weights
    )
    sent = decision.midi_notes != last_sent_notes
    return MusicDecisionEvent(elapsed, decision, sent, voicing)


def build_music_timeline(
    scenario: str,
    *,
    duration: float,
    rate: float = DEFAULT_RATE_HZ,
    seed: int = DEFAULT_VOICING_SEED,
) -> MusicTimeline:
    """Build the exact deterministic plan used by offline reference renders."""
    frames = tuple(iter_music_frames(scenario, duration=duration, rate=rate))
    engine = GLydianVoicingEngine(seed=seed)
    next_decision_at = 0.0
    last_sent_notes: tuple[int, ...] = ()
    decisions: list[MusicDecisionEvent] = []
    for elapsed, frame in frames:
        if elapsed + 1e-9 >= next_decision_at:
            event = _decision_event(
                engine,
                frame,
                elapsed=elapsed,
                last_sent_notes=last_sent_notes,
            )
            decisions.append(event)
            if event.sent:
                last_sent_notes = event.decision.midi_notes
            next_decision_at = elapsed + event.decision.hold_duration_seconds
    return MusicTimeline(
        scenario=scenario,
        duration_seconds=float(duration),
        rate_hz=float(rate),
        frames=frames,
        decisions=tuple(decisions),
    )


def _frame_line(
    scenario: str,
    elapsed: float,
    frame: OrganismControlFrame,
    effective_hz: float,
) -> str:
    return (
        f"FRAME {scenario} t={elapsed:6.2f}s rate={effective_hz:4.2f}Hz "
        f"e={frame.energy:.2f} c={frame.centroid:.2f} "
        f"m={frame.mobility:.2f} h={frame.spectral_entropy:.2f} "
        f"n={frame.novelty:.2f} d={frame.delta:.2f} "
        f"t={frame.theta:.2f} a={frame.alpha:.2f} b={frame.beta:.2f}"
    )


def _decision_line(
    scenario: str,
    event: MusicDecisionEvent,
    frame: OrganismControlFrame,
) -> str:
    notes = "/".join(event.decision.note_names)
    action = "SEND" if event.sent else "HOLD"
    return (
        f"VOICE {scenario} t={event.elapsed_seconds:6.2f}s {action} "
        f"desc[e={frame.energy:.2f},c={frame.centroid:.2f},"
        f"m={frame.mobility:.2f},h={frame.spectral_entropy:.2f},"
        f"n={frame.novelty:.2f}] notes={notes} "
        f"hold={event.decision.hold_duration_seconds:.3f}s; "
        f"{event.decision.reason}"
    )


def run_music_transport(
    scenario: str,
    *,
    duration: float,
    rate: float = DEFAULT_RATE_HZ,
    seed: int = DEFAULT_VOICING_SEED,
    sender: OrganismControlSender,
    dry_run: bool = False,
    loop: bool = False,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    printer: Callable[[str], None] = print,
) -> MusicTransportResult:
    """Send frames on monotonic deadlines and voicings on the decision clock."""
    if scenario not in SCENARIO_NAMES:
        raise ValueError(f"scenario must be one of {SCENARIO_NAMES}")
    duration, rate = _validate_transport(duration, rate)
    if loop and dry_run:
        raise ValueError("looped dry-run would be unbounded")

    interval = 1.0 / rate
    final_step = int(math.floor((duration * rate) + 1e-9))
    engine = GLydianVoicingEngine(seed=seed)
    started = clock()
    previous_send_at: float | None = None
    report_started_at = started
    report_started_frames = 0
    last_report_elapsed = -1.0
    next_decision_at = 0.0
    last_sent_notes: tuple[int, ...] = ()
    sequence = 0
    sent_frames = 0
    decision_count = 0
    sent_voicings = 0
    skipped = 0

    while loop or sequence <= final_step:
        scheduled_elapsed = sequence * interval
        if not loop and scheduled_elapsed > duration + 1e-9:
            break
        if not dry_run:
            deadline = started + scheduled_elapsed
            now = clock()
            lateness = now - deadline
            if lateness >= interval:
                missed = max(
                    1, int(math.ceil((lateness / interval) - 1e-9))
                )
                sequence += missed
                skipped += missed
                continue
            if now < deadline:
                sleeper(deadline - now)
            send_at = clock()
        else:
            send_at = started + scheduled_elapsed

        cycle_elapsed = (
            scheduled_elapsed % duration if loop else scheduled_elapsed
        )
        frame = music_frame_at(
            cycle_elapsed, scenario=scenario, duration=duration
        )
        sender.send(frame)
        sent_frames += 1

        if scheduled_elapsed + 1e-9 >= next_decision_at:
            event = _decision_event(
                engine,
                frame,
                elapsed=scheduled_elapsed,
                last_sent_notes=last_sent_notes,
            )
            decision_count += 1
            if event.sent:
                sender.send_voicing(event.voicing)
                sent_voicings += 1
                last_sent_notes = event.decision.midi_notes
            printer(_decision_line(scenario, event, frame))
            next_decision_at = (
                scheduled_elapsed + event.decision.hold_duration_seconds
            )

        if (
            last_report_elapsed < 0
            or scheduled_elapsed - last_report_elapsed >= 1.0 - 1e-9
        ):
            window = max(0.0, send_at - report_started_at)
            effective_hz = (
                rate
                if dry_run and sent_frames > 1
                else (
                    (sent_frames - report_started_frames) / window
                    if window > 0
                    else 0.0
                )
            )
            printer(_frame_line(scenario, scheduled_elapsed, frame, effective_hz))
            report_started_at = send_at
            report_started_frames = sent_frames
            last_report_elapsed = scheduled_elapsed
        previous_send_at = send_at
        del previous_send_at  # retained as an explicit cadence boundary marker
        sequence += 1

    if not loop and not dry_run:
        remaining = (started + duration) - clock()
        if remaining > 0:
            sleeper(remaining)
    elapsed = duration if not loop else max(0.0, clock() - started)
    return MusicTransportResult(
        frame_count=sent_frames,
        decision_count=decision_count,
        voicing_count=sent_voicings,
        skipped_deadlines=skipped,
        elapsed_seconds=elapsed,
    )


def write_supercollider_plan(
    path: Path,
    *,
    scenario: str,
    duration: float,
    rate: float = DEFAULT_RATE_HZ,
    seed: int = DEFAULT_VOICING_SEED,
) -> Path:
    """Write one auditable SC literal consumed by the generic NRT renderer."""
    timeline = build_music_timeline(
        scenario, duration=duration, rate=rate, seed=seed
    )

    def numbers(values: Sequence[float]) -> str:
        return "[" + ", ".join(f"{float(value):.9g}" for value in values) + "]"

    frame_rows = [
        f"        [{elapsed:.9g}, {numbers(frame.as_osc_values())}]"
        for elapsed, frame in timeline.frames
    ]
    voicing_rows = [
        "        "
        + f"[{event.elapsed_seconds:.9g}, "
        + f"{numbers(event.voicing.frequencies_hz)}, "
        + f"{numbers(event.voicing.weights)}]"
        for event in timeline.sent_voicings
    ]
    text = (
        "(\n"
        f'    scenario: "{scenario}",\n'
        f"    duration: {float(duration):.9g},\n"
        f"    rate: {float(rate):.9g},\n"
        "    frameEvents: [\n"
        + ",\n".join(frame_rows)
        + "\n    ],\n"
        "    voicingEvents: [\n"
        + ",\n".join(voicing_rows)
        + "\n    ]\n"
        ")\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class _DryRunClient:
    def send_message(self, address, values):
        del address, values


def _default_duration(scenario: str) -> float:
    return (
        DEFAULT_COMBINED_DURATION
        if scenario == COMBINED_SCENARIO
        else DEFAULT_SCENARIO_DURATION
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIO_NAMES, default=COMBINED_SCENARIO)
    parser.add_argument("--duration", type=float)
    parser.add_argument("--rate", type=float, default=DEFAULT_RATE_HZ)
    parser.add_argument("--seed", type=int, default=DEFAULT_VOICING_SEED)
    parser.add_argument("--host", default=DEFAULT_OSC_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_OSC_PORT)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write-nrt-plan", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    duration = (
        _default_duration(args.scenario)
        if args.duration is None
        else args.duration
    )
    if args.write_nrt_plan is not None:
        if args.loop:
            parser.error("--write-nrt-plan cannot be combined with --loop")
        path = write_supercollider_plan(
            args.write_nrt_plan,
            scenario=args.scenario,
            duration=duration,
            rate=args.rate,
            seed=args.seed,
        )
        print(path)
        return 0
    if args.loop and args.dry_run:
        parser.error("--loop cannot be combined with --dry-run")

    sender = OrganismControlSender(
        args.host,
        args.port,
        client=_DryRunClient() if args.dry_run else None,
    )
    print(
        f"SYNTHETIC MUSIC {'DRY-RUN' if args.dry_run else 'SEND'}: "
        f"scenario={args.scenario} duration={duration:.3g}s "
        f"rate={args.rate:.3g}Hz loop={args.loop}."
    )
    try:
        result = run_music_transport(
            args.scenario,
            duration=duration,
            rate=args.rate,
            seed=args.seed,
            sender=sender,
            dry_run=args.dry_run,
            loop=args.loop,
        )
        print(
            f"SYNTHETIC MUSIC complete: frames={result.frame_count} "
            f"decisions={result.decision_count} "
            f"voicings={result.voicing_count} "
            f"skipped={result.skipped_deadlines}."
        )
    except KeyboardInterrupt:
        print(
            "Synthetic music transport stopped; no stop packet was sent, "
            "so the existing receiver watchdog will fade the instrument."
        )
        return 130
    finally:
        sender.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
