"""Offline, deterministic G Lydian voicing decisions.

The module returns data only.  It does not send OSC, create audio objects, or
interpret its normalized controls as mental states.  The descriptor mappings
are musical choices for a future integration step.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from itertools import combinations
import json
import math
from pathlib import Path
import random
from typing import Iterable, Sequence


G_LYDIAN_NAMES = ("G", "A", "B", "C#", "D", "E", "F#")
G_LYDIAN_PITCH_CLASSES = (7, 9, 11, 1, 2, 4, 6)
MAX_VOICE_SLOTS = 6
DEFAULT_VOICING_SEED = 20260904
MIDI_LOW = 36
# The persistent harmonic bank accepts fundamentals through B4 (493.88 Hz).
# Keeping candidate generation inside that already-tested range prevents the
# OSC safety clamp from collapsing distinct upper notes onto one frequency.
MIDI_HIGH = 71

_PITCH_CLASS_NAMES = {
    1: "C#",
    2: "D",
    4: "E",
    6: "F#",
    7: "G",
    9: "A",
    11: "B",
}

# Perceptual roughness targets for interval classes.  These values are an
# intentionally simple musical ranking, not a psychoacoustic or clinical model.
_INTERVAL_TENSION = {
    0: 0.00,
    1: 1.00,
    2: 0.62,
    3: 0.20,
    4: 0.12,
    5: 0.18,
    6: 0.90,
    7: 0.05,
    8: 0.25,
    9: 0.16,
    10: 0.70,
    11: 0.92,
}


def _unit(value: float, name: str) -> float:
    try:
        converted = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite and numeric") from exc
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite and numeric")
    return min(1.0, max(0.0, converted))


@dataclass(frozen=True)
class VoicingControls:
    """Normalized descriptor controls used by the offline music decision."""

    energy: float
    centroid: float
    mobility: float
    spectral_entropy: float
    novelty: float

    def __post_init__(self) -> None:
        for name in (
            "energy",
            "centroid",
            "mobility",
            "spectral_entropy",
            "novelty",
        ):
            object.__setattr__(self, name, _unit(getattr(self, name), name))


@dataclass(frozen=True)
class VoicingScores:
    """Named score components retained for audit and later tuning."""

    scale_membership: float
    interval_consonance: float
    interval_tension: float
    entropy_fit: float
    register_fit: float
    spacing: float
    common_tone_retention: float
    voice_leading: float
    voice_leading_semitones: float
    density_fit: float
    total: float


@dataclass(frozen=True)
class VoicingDecision:
    """One data-only decision for at most six persistent voice slots."""

    midi_notes: tuple[int, ...]
    note_names: tuple[str, ...]
    frequencies_hz: tuple[float, ...]
    weights: tuple[float, ...]
    hold_duration_seconds: float
    scores: VoicingScores
    reason: str

    @property
    def active_voice_count(self) -> int:
        return len(self.midi_notes)

    def as_dict(self) -> dict[str, object]:
        result = asdict(self)
        for name in ("midi_notes", "note_names", "frequencies_hz", "weights"):
            result[name] = list(result[name])
        result["active_voice_count"] = self.active_voice_count
        result["capacity_slots"] = MAX_VOICE_SLOTS
        return result


@dataclass(frozen=True)
class _ScoredCandidate:
    notes: tuple[int, ...]
    scores: VoicingScores


def midi_to_name(note: int) -> str:
    """Return an octave-qualified sharp note name for G Lydian material."""
    pitch_class = int(note) % 12
    if pitch_class not in _PITCH_CLASS_NAMES:
        raise ValueError(f"MIDI note {note} is outside G Lydian")
    return f"{_PITCH_CLASS_NAMES[pitch_class]}{int(note) // 12 - 1}"


def midi_to_frequency(note: int) -> float:
    """Convert a MIDI note number to equal-tempered frequency."""
    return 440.0 * (2.0 ** ((int(note) - 69) / 12.0))


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _target_density(controls: VoicingControls) -> int:
    # Entropy is the primary density colour; energy contributes at most about
    # one slot and therefore remains principally available for master presence.
    raw = 2.0 + (3.2 * controls.spectral_entropy) + (0.8 * controls.energy)
    return max(2, min(MAX_VOICE_SLOTS, int(math.floor(raw + 0.5))))


def _target_register(centroid: float) -> float:
    # Mean voicing target from roughly G2/A2 to the upper fourth octave.  This
    # preserves the Task 04 low-to-high mapping inside Task 05's 500 Hz bank.
    return 44.0 + (24.0 * centroid)


def _hold_duration(mobility: float) -> float:
    # Mobility alone controls scheduling: 12 s at rest, 2 s at maximum.
    return round(2.0 + (10.0 * ((1.0 - mobility) ** 1.25)), 3)


def _interval_tension(notes: Sequence[int]) -> float:
    intervals = [
        abs(right - left) % 12
        for index, left in enumerate(notes)
        for right in notes[index + 1 :]
    ]
    return _mean([_INTERVAL_TENSION[interval] for interval in intervals])


def _voice_leading_distance(
    notes: Sequence[int], previous: Sequence[int]
) -> float:
    if not previous:
        return 0.0
    forward = _mean([
        min(abs(note - old) for old in previous) for note in notes
    ])
    backward = _mean([
        min(abs(old - note) for note in notes) for old in previous
    ])
    density_penalty = abs(len(notes) - len(previous)) * 1.5
    return (0.5 * (forward + backward)) + density_penalty


def _maximum_nearest_motion(
    notes: Sequence[int], previous: Sequence[int]
) -> float:
    if not previous:
        return 0.0
    return max(
        max(min(abs(note - old) for old in previous) for note in notes),
        max(min(abs(old - note) for note in notes) for old in previous),
    )


def _spacing_score(notes: Sequence[int], entropy: float) -> float:
    if len(notes) < 2:
        return 1.0
    gaps = [right - left for left, right in zip(notes, notes[1:])]
    ideal_gap = 7.0 - (3.0 * entropy)
    fit = _mean([math.exp(-abs(gap - ideal_gap) / 6.0) for gap in gaps])
    # Seconds are deliberately possible at high entropy, but clustered low
    # entropy voicings are penalized without banning them outright.
    close_pairs = sum(gap <= 2 for gap in gaps) / len(gaps)
    return max(0.0, min(1.0, fit - close_pairs * (1.0 - entropy) * 0.45))


def _score_candidate(
    notes: tuple[int, ...],
    controls: VoicingControls,
    previous: tuple[int, ...],
    target_density: int,
    target_register: float,
) -> VoicingScores:
    scale_membership = sum(
        note % 12 in G_LYDIAN_PITCH_CLASSES for note in notes
    ) / len(notes)
    tension = _interval_tension(notes)
    consonance = 1.0 - tension
    target_tension = 0.08 + (0.72 * controls.spectral_entropy)
    entropy_fit = max(0.0, 1.0 - abs(tension - target_tension) / 0.72)
    register_fit = math.exp(-abs(_mean(notes) - target_register) / 12.0)
    spacing = _spacing_score(notes, controls.spectral_entropy)
    if previous:
        common = len(set(notes).intersection(previous)) / max(len(notes), len(previous))
        distance = _voice_leading_distance(notes, previous)
        voice_leading = math.exp(
            -distance / (2.0 + (8.0 * controls.novelty))
        )
    else:
        common = 1.0
        distance = 0.0
        voice_leading = 1.0
    density_fit = max(
        0.0,
        1.0 - abs(len(notes) - target_density) / MAX_VOICE_SLOTS,
    )

    common_weight = 0.4 + (2.8 * (1.0 - controls.novelty))
    leading_weight = 0.65 + (1.9 * (1.0 - controls.novelty))
    total = (
        1.4 * scale_membership
        + 1.6 * entropy_fit
        + 1.2 * register_fit
        + 0.8 * spacing
        + common_weight * common
        + leading_weight * voice_leading
        + 0.9 * density_fit
    )
    return VoicingScores(
        scale_membership=round(scale_membership, 6),
        interval_consonance=round(consonance, 6),
        interval_tension=round(tension, 6),
        entropy_fit=round(entropy_fit, 6),
        register_fit=round(register_fit, 6),
        spacing=round(spacing, 6),
        common_tone_retention=round(common, 6),
        voice_leading=round(voice_leading, 6),
        voice_leading_semitones=round(distance, 6),
        density_fit=round(density_fit, 6),
        total=round(total, 6),
    )


def _relative_weights(notes: Sequence[int], controls: VoicingControls) -> tuple[float, ...]:
    midpoint = (len(notes) - 1) / 2.0
    tilt = -0.20 + (0.34 * controls.centroid)
    raw = []
    for index, note in enumerate(notes):
        register_weight = math.exp(tilt * (index - midpoint))
        pitch_colour = 1.0 + controls.spectral_entropy * 0.06 * (
            ((note % 12) - 5.5) / 5.5
        )
        raw.append(max(0.05, register_weight * pitch_colour))
    total = sum(raw)
    rounded = [round(value / total, 6) for value in raw]
    # Keep the serialized relative weights exactly normalized after rounding.
    rounded[-1] = round(rounded[-1] + (1.0 - sum(rounded)), 6)
    return tuple(rounded)


class GLydianVoicingEngine:
    """Stateful candidate scorer with reproducible, novelty-bounded choices."""

    def __init__(self, *, seed: int = DEFAULT_VOICING_SEED) -> None:
        self.seed = int(seed)
        self._random = random.Random(self.seed)
        self._previous: tuple[int, ...] = ()

    @property
    def previous_notes(self) -> tuple[int, ...]:
        return self._previous

    def reset(self) -> None:
        self._random.seed(self.seed)
        self._previous = ()

    def _candidate_notes(
        self,
        controls: VoicingControls,
        target_density: int,
        target_register: float,
    ) -> Iterable[tuple[int, ...]]:
        all_scale_notes = [
            note
            for note in range(MIDI_LOW, MIDI_HIGH + 1)
            if note % 12 in G_LYDIAN_PITCH_CLASSES
        ]
        nearest = sorted(
            all_scale_notes,
            key=lambda note: (abs(note - target_register), note),
        )[:14]
        pool = sorted(set(nearest).union(self._previous))
        densities = {
            max(2, target_density - 1),
            target_density,
            min(MAX_VOICE_SLOTS, target_density + 1),
        }
        if self._previous:
            densities.add(len(self._previous))

        for density in sorted(densities):
            for notes in combinations(pool, density):
                gaps = [right - left for left, right in zip(notes, notes[1:])]
                if gaps and (max(gaps) > 16 or notes[-1] - notes[0] > 38):
                    continue
                if abs(_mean(notes) - target_register) > 24:
                    continue
                if self._previous:
                    average_limit = 2.5 + (10.5 * controls.novelty)
                    maximum_limit = 7.0 + (14.0 * controls.novelty)
                    if _voice_leading_distance(notes, self._previous) > average_limit:
                        continue
                    if _maximum_nearest_motion(notes, self._previous) > maximum_limit:
                        continue
                yield notes

    def _select(
        self,
        candidates: list[_ScoredCandidate],
        novelty: float,
        *,
        exclude_previous: bool,
    ) -> _ScoredCandidate:
        ordered = sorted(
            candidates,
            key=lambda candidate: (-candidate.scores.total, candidate.notes),
        )
        if exclude_previous:
            changed = [item for item in ordered if item.notes != self._previous]
            if changed:
                ordered = changed
        if novelty <= 0.15:
            return ordered[0]

        shortlist = ordered[: min(32, len(ordered))]
        temperature = 0.04 + (0.56 * novelty)
        best = shortlist[0].scores.total
        probabilities = [
            math.exp((candidate.scores.total - best) / temperature)
            for candidate in shortlist
        ]
        return self._random.choices(shortlist, weights=probabilities, k=1)[0]

    def decide(self, controls: VoicingControls) -> VoicingDecision:
        """Return one coherent decision and retain it for the next call."""
        if not isinstance(controls, VoicingControls):
            raise TypeError("controls must be a VoicingControls instance")

        target_density = _target_density(controls)
        target_register = _target_register(controls.centroid)
        previous = self._previous

        should_change = not previous
        if previous:
            change_probability = 0.04 + (0.90 * (controls.novelty ** 1.15))
            should_change = self._random.random() < change_probability

        if previous and not should_change:
            notes = previous
            scores = _score_candidate(
                notes, controls, previous, target_density, target_register
            )
        else:
            candidates = [
                _ScoredCandidate(
                    notes=notes,
                    scores=_score_candidate(
                        notes,
                        controls,
                        previous,
                        target_density,
                        target_register,
                    ),
                )
                for notes in self._candidate_notes(
                    controls, target_density, target_register
                )
            ]
            if not candidates:
                raise RuntimeError("no bounded G Lydian voicing candidate exists")
            selected = self._select(
                candidates,
                controls.novelty,
                exclude_previous=bool(previous and should_change),
            )
            notes = selected.notes
            scores = selected.scores

        self._previous = notes
        retention = scores.common_tone_retention if previous else 1.0
        tension_label = (
            "controlled-tension"
            if controls.spectral_entropy >= 0.6
            else "consonant"
        )
        register_label = (
            "low" if target_register < 56 else "mid" if target_register < 68 else "high"
        )
        reason = (
            f"{register_label} register from centroid; {tension_label} interval target "
            f"from entropy; {len(notes)}/{MAX_VOICE_SLOTS} active slots; "
            f"retention={retention:.2f}, motion={scores.voice_leading_semitones:.2f} st; "
            f"hold={_hold_duration(controls.mobility):.3f}s from mobility"
        )
        return VoicingDecision(
            midi_notes=notes,
            note_names=tuple(midi_to_name(note) for note in notes),
            frequencies_hz=tuple(
                round(midi_to_frequency(note), 6) for note in notes
            ),
            weights=_relative_weights(notes, controls),
            hold_duration_seconds=_hold_duration(controls.mobility),
            scores=scores,
            reason=reason,
        )


TRACE_SCENARIOS = {
    "calm-stable": VoicingControls(
        energy=0.30,
        centroid=0.24,
        mobility=0.10,
        spectral_entropy=0.12,
        novelty=0.04,
    ),
    "bright-stable": VoicingControls(
        energy=0.45,
        centroid=0.86,
        mobility=0.18,
        spectral_entropy=0.18,
        novelty=0.05,
    ),
    "tense-stable": VoicingControls(
        energy=0.48,
        centroid=0.50,
        mobility=0.22,
        spectral_entropy=0.88,
        novelty=0.08,
    ),
    "active-novel": VoicingControls(
        energy=0.72,
        centroid=0.66,
        mobility=0.88,
        spectral_entropy=0.64,
        novelty=0.92,
    ),
}


def generate_trace(
    name: str,
    controls: VoicingControls,
    *,
    seed: int = DEFAULT_VOICING_SEED,
    decision_count: int = 12,
) -> dict[str, object]:
    """Generate a deterministic audit trace for one named scenario."""
    if decision_count < 1:
        raise ValueError("decision_count must be positive")
    engine = GLydianVoicingEngine(seed=seed)
    decisions = [engine.decide(controls).as_dict() for _ in range(decision_count)]
    return {
        "scenario": name,
        "seed": seed,
        "pitch_material": list(G_LYDIAN_NAMES),
        "controls": asdict(controls),
        "mapping_status": "artistic mapping; not a mental-state inference",
        "decisions": decisions,
    }


def write_standard_traces(
    output_dir: Path,
    *,
    seed: int = DEFAULT_VOICING_SEED,
    decision_count: int = 12,
) -> tuple[Path, ...]:
    """Write the four required scenario traces and return their paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, controls in TRACE_SCENARIOS.items():
        path = output_dir / f"{name}.json"
        path.write_text(
            json.dumps(
                generate_trace(
                    name,
                    controls,
                    seed=seed,
                    decision_count=decision_count,
                ),
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        paths.append(path)
    return tuple(paths)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write deterministic, data-only G Lydian voicing traces."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("traces/organism_v2_g_lydian"),
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_VOICING_SEED)
    parser.add_argument("--decisions", type=int, default=12)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for path in write_standard_traces(
        args.output_dir,
        seed=args.seed,
        decision_count=args.decisions,
    ):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
