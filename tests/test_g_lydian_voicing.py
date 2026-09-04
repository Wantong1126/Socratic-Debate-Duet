import json
import math
from pathlib import Path
import tempfile
import unittest

from src.sonification.voicing import (
    DEFAULT_VOICING_SEED,
    G_LYDIAN_NAMES,
    G_LYDIAN_PITCH_CLASSES,
    MAX_VOICE_SLOTS,
    MIDI_HIGH,
    TRACE_SCENARIOS,
    GLydianVoicingEngine,
    VoicingControls,
    VoicingDecision,
    generate_trace,
    midi_to_frequency,
    write_standard_traces,
)


ROOT = Path(__file__).resolve().parents[1]
TRACE_DIR = ROOT / "traces" / "organism_v2_g_lydian"


def controls(**changes):
    values = {
        "energy": 0.4,
        "centroid": 0.5,
        "mobility": 0.4,
        "spectral_entropy": 0.4,
        "novelty": 0.2,
    }
    values.update(changes)
    return VoicingControls(**values)


class GLydianVoicingTests(unittest.TestCase):
    def test_decision_is_typed_data_with_exact_pitch_material(self):
        decision = GLydianVoicingEngine(seed=7).decide(controls())
        self.assertIsInstance(decision, VoicingDecision)
        self.assertGreaterEqual(decision.active_voice_count, 2)
        self.assertLessEqual(decision.active_voice_count, MAX_VOICE_SLOTS)
        self.assertEqual(len(set(decision.midi_notes)), len(decision.midi_notes))
        self.assertTrue(all(
            note % 12 in G_LYDIAN_PITCH_CLASSES
            for note in decision.midi_notes
        ))
        self.assertTrue(all(
            name.rstrip("-0123456789") in G_LYDIAN_NAMES
            for name in decision.note_names
        ))
        self.assertEqual(len(decision.frequencies_hz), decision.active_voice_count)
        self.assertEqual(len(decision.weights), decision.active_voice_count)
        self.assertAlmostEqual(sum(decision.weights), 1.0, places=6)
        for midi, frequency in zip(
            decision.midi_notes, decision.frequencies_hz
        ):
            self.assertAlmostEqual(frequency, midi_to_frequency(midi), places=5)
        self.assertTrue(decision.reason)
        self.assertEqual(decision.as_dict()["capacity_slots"], 6)
        self.assertLessEqual(max(decision.midi_notes), MIDI_HIGH)
        self.assertLessEqual(max(decision.frequencies_hz), 500.0)

    def test_controls_are_finite_and_clamped(self):
        bounded = VoicingControls(-1, 2, 0.5, 1.5, -0.5)
        self.assertEqual(
            (bounded.energy, bounded.centroid, bounded.mobility,
             bounded.spectral_entropy, bounded.novelty),
            (0.0, 1.0, 0.5, 1.0, 0.0),
        )
        for invalid in (math.nan, math.inf, -math.inf, "not-a-number"):
            with self.assertRaises(ValueError):
                VoicingControls(invalid, 0, 0, 0, 0)

    def test_centroid_moves_register_and_entropy_controls_tension(self):
        low_register = GLydianVoicingEngine(seed=3).decide(
            controls(centroid=0.0, novelty=0.0)
        )
        high_register = GLydianVoicingEngine(seed=3).decide(
            controls(centroid=1.0, novelty=0.0)
        )
        self.assertGreater(
            sum(high_register.midi_notes) / high_register.active_voice_count,
            sum(low_register.midi_notes) / low_register.active_voice_count + 20,
        )

        consonant = GLydianVoicingEngine(seed=3).decide(
            controls(spectral_entropy=0.0, novelty=0.0)
        )
        tense = GLydianVoicingEngine(seed=3).decide(
            controls(spectral_entropy=1.0, novelty=0.0)
        )
        self.assertGreater(
            tense.scores.interval_tension,
            consonant.scores.interval_tension + 0.3,
        )
        interval_classes = {
            abs(right - left) % 12
            for index, left in enumerate(tense.midi_notes)
            for right in tense.midi_notes[index + 1 :]
        }
        self.assertTrue(interval_classes.intersection({1, 2, 6, 10, 11}))

    def test_density_is_variable_and_energy_has_only_secondary_influence(self):
        low_entropy = GLydianVoicingEngine(seed=5).decide(
            controls(energy=0.0, spectral_entropy=0.0, novelty=0.0)
        )
        high_entropy = GLydianVoicingEngine(seed=5).decide(
            controls(energy=0.0, spectral_entropy=1.0, novelty=0.0)
        )
        low_energy = GLydianVoicingEngine(seed=5).decide(
            controls(energy=0.0, spectral_entropy=0.0, novelty=0.0)
        )
        high_energy = GLydianVoicingEngine(seed=5).decide(
            controls(energy=1.0, spectral_entropy=0.0, novelty=0.0)
        )
        maximum = GLydianVoicingEngine(seed=5).decide(
            controls(energy=1.0, spectral_entropy=1.0, novelty=0.0)
        )
        self.assertGreater(
            high_entropy.active_voice_count, low_entropy.active_voice_count
        )
        self.assertLessEqual(
            high_energy.active_voice_count - low_energy.active_voice_count, 1
        )
        self.assertEqual(maximum.active_voice_count, MAX_VOICE_SLOTS)

    def test_novelty_changes_retention_temperature_and_bounded_motion(self):
        low_engine = GLydianVoicingEngine(seed=DEFAULT_VOICING_SEED)
        high_engine = GLydianVoicingEngine(seed=DEFAULT_VOICING_SEED)
        low = [
            low_engine.decide(controls(novelty=0.02)) for _ in range(24)
        ]
        high = [
            high_engine.decide(controls(novelty=0.98)) for _ in range(24)
        ]
        low_changes = sum(
            left.midi_notes != right.midi_notes
            for left, right in zip(low, low[1:])
        )
        high_changes = sum(
            left.midi_notes != right.midi_notes
            for left, right in zip(high, high[1:])
        )
        self.assertLessEqual(low_changes, 3)
        self.assertGreater(high_changes, low_changes + 10)
        self.assertTrue(all(
            decision.scores.voice_leading_semitones <= 13.0
            for decision in high[1:]
        ))
        self.assertTrue(all(
            decision.midi_notes[-1] - decision.midi_notes[0] <= 38
            for decision in high
        ))

    def test_mobility_alone_shortens_hold_duration(self):
        slow = GLydianVoicingEngine(seed=9).decide(controls(mobility=0.0))
        fast = GLydianVoicingEngine(seed=9).decide(controls(mobility=1.0))
        self.assertEqual(slow.hold_duration_seconds, 12.0)
        self.assertEqual(fast.hold_duration_seconds, 2.0)
        self.assertGreater(slow.hold_duration_seconds, fast.hold_duration_seconds)

    def test_seed_reproduces_sequence(self):
        first = GLydianVoicingEngine(seed=81)
        second = GLydianVoicingEngine(seed=81)
        values = controls(novelty=0.9, spectral_entropy=0.7)
        first_sequence = [first.decide(values) for _ in range(16)]
        second_sequence = [second.decide(values) for _ in range(16)]
        self.assertEqual(first_sequence, second_sequence)

    def test_four_committed_json_traces_match_generator(self):
        expected_names = {
            "calm-stable",
            "bright-stable",
            "tense-stable",
            "active-novel",
        }
        self.assertEqual(set(TRACE_SCENARIOS), expected_names)
        paths = sorted(TRACE_DIR.glob("*.json"))
        self.assertEqual({path.stem for path in paths}, expected_names)
        for path in paths:
            stored = json.loads(path.read_text(encoding="utf-8"))
            expected = generate_trace(
                path.stem,
                TRACE_SCENARIOS[path.stem],
                seed=DEFAULT_VOICING_SEED,
                decision_count=12,
            )
            self.assertEqual(stored, expected)
            self.assertEqual(stored["pitch_material"], list(G_LYDIAN_NAMES))
            self.assertEqual(len(stored["decisions"]), 12)

    def test_trace_writer_uses_four_named_files(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = write_standard_traces(Path(directory), decision_count=2)
            self.assertEqual({path.stem for path in paths}, set(TRACE_SCENARIOS))
            self.assertTrue(all(path.is_file() for path in paths))


if __name__ == "__main__":
    unittest.main()
