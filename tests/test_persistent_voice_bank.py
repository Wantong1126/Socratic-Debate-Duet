from pathlib import Path
import math
import unittest
import wave

from scripts.analyze_eeg_organism_v2_voicing_transition import analyze
from src.sonification.manual_voicing_demo import MANUAL_VOICINGS, run_manual_demo
from src.sonification.protocol import (
    ORGANISM_FRAME_ADDRESS,
    ORGANISM_PARAMETER_ORDER,
    ORGANISM_VOICE_CAPACITY,
    ORGANISM_VOICING_ADDRESS,
    ORGANISM_VOICING_PARAMETER_ORDER,
    OrganismControlFrame,
    OrganismControlSender,
    OrganismVoicingFrame,
)


ROOT = Path(__file__).resolve().parents[1]


class RecordingClient:
    def __init__(self):
        self.messages = []

    def send_message(self, address, values):
        self.messages.append((address, tuple(values)))


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class PersistentVoiceBankTests(unittest.TestCase):
    def test_voicing_contract_is_separate_fixed_width_and_frame_is_unchanged(self):
        self.assertEqual(ORGANISM_FRAME_ADDRESS, "/eeg/organism/v2/frame")
        self.assertEqual(len(ORGANISM_PARAMETER_ORDER), 9)
        self.assertEqual(ORGANISM_VOICING_ADDRESS, "/eeg/organism/v2/voicing")
        self.assertEqual(ORGANISM_VOICE_CAPACITY, 6)
        self.assertEqual(len(ORGANISM_VOICING_PARAMETER_ORDER), 12)

        client = RecordingClient()
        sender = OrganismControlSender(client=client)
        control = OrganismControlFrame.from_values([0.5] * 9)
        voicing = OrganismVoicingFrame.from_active((98.0, 146.8), (0.6, 0.4))
        sender.send(control)
        sender.send_voicing(voicing)
        self.assertEqual(client.messages[0], (
            ORGANISM_FRAME_ADDRESS, control.as_osc_values()
        ))
        self.assertEqual(client.messages[1], (
            ORGANISM_VOICING_ADDRESS, voicing.as_osc_values()
        ))
        self.assertEqual((sender.frame_count, sender.voicing_count), (1, 1))

    def test_voicing_is_finite_bounded_padded_and_requires_active_weight(self):
        voicing = OrganismVoicingFrame.from_active(
            (20.0, 700.0), (-1.0, 2.0), inactive_frequency_hz=65.41
        )
        self.assertEqual(voicing.frequencies_hz[:2], (40.0, 500.0))
        self.assertEqual(voicing.weights[:2], (0.0, 1.0))
        self.assertEqual(len(voicing.as_osc_values()), 12)
        self.assertEqual(voicing.weights[2:], (0.0, 0.0, 0.0, 0.0))
        for invalid in (math.nan, math.inf, -math.inf, "bad"):
            with self.assertRaises(ValueError):
                OrganismVoicingFrame.from_active((invalid,), (1.0,))
        with self.assertRaises(ValueError):
            OrganismVoicingFrame.from_active((98.0,), (0.0,))
        with self.assertRaises(ValueError):
            OrganismVoicingFrame.from_active((98.0,) * 7, (1.0,) * 7)

    def test_manual_sender_material_is_static_contrasting_g_lydian(self):
        self.assertEqual(len(MANUAL_VOICINGS), 2)
        first = MANUAL_VOICINGS[0][1]
        second = MANUAL_VOICINGS[1][1]
        self.assertNotEqual(first.frequencies_hz, second.frequencies_hz)
        self.assertNotEqual(
            sum(weight > 0 for weight in first.weights),
            sum(weight > 0 for weight in second.weights),
        )
        self.assertNotIn("voicing import", (
            ROOT / "src" / "sonification" / "manual_voicing_demo.py"
        ).read_text(encoding="utf-8"))

    def test_manual_sender_alternates_without_mapping_or_timing_drift(self):
        client = RecordingClient()
        sender = OrganismControlSender(client=client)
        clock = FakeClock()
        sent = run_manual_demo(
            sender=sender,
            hold_seconds=2.0,
            changes=4,
            rate=4.0,
            clock=clock.monotonic,
            sleeper=clock.sleep,
            printer=lambda line: None,
        )
        self.assertEqual(sent, 33)
        voicings = [
            values for address, values in client.messages
            if address == ORGANISM_VOICING_ADDRESS
        ]
        self.assertEqual(len(voicings), 4)
        self.assertEqual(voicings, [
            MANUAL_VOICINGS[0][1].as_osc_values(),
            MANUAL_VOICINGS[1][1].as_osc_values(),
            MANUAL_VOICINGS[0][1].as_osc_values(),
            MANUAL_VOICINGS[1][1].as_osc_values(),
        ])
        frames = [
            values for address, values in client.messages
            if address == ORGANISM_FRAME_ADDRESS
        ]
        self.assertTrue(all(values == frames[0] for values in frames))
        self.assertEqual(clock.now, 8.0)

    def test_receiver_updates_only_inactive_bank_without_allocating_nodes(self):
        receiver = (
            ROOT / "sound" / "eeg_organism_v2_receiver.scd"
        ).read_text(encoding="utf-8")
        self.assertIn("'/eeg/organism/v2/voicing'", receiver)
        self.assertIn("message.size == 13", receiver)
        self.assertIn("nextBank = 1 - state[\\activeVoicingBank]", receiver)
        self.assertIn("synth.setn(\\voiceFrequenciesA", receiver)
        self.assertIn("synth.setn(\\voiceFrequenciesB", receiver)
        self.assertIn("synth.set(\\voicingBank, nextBank)", receiver)
        callback = receiver.split(
            "OSCdef(\\eegOrganismV2Voicing", 1
        )[1].split("OSCdef(\\eegOrganismV2Stop", 1)[0]
        for constructor in (
            "Synth(", "Synth.new(", "Synth.tail(", "Synth.head(",
            "Group(", "Group.new(", "Group.tail(", "Group.head(",
            "Buffer(", "Buffer.", "Routine(",
        ):
            self.assertNotIn(constructor, callback)
        self.assertEqual(receiver.count("Synth.tail("), 1)
        self.assertEqual(receiver.count("Group.tail("), 1)

    def test_core_has_two_persistent_banks_polyphony_norm_and_crossfade(self):
        config = (ROOT / "config" / "eeg_organism_v2.scd").read_text(
            encoding="utf-8"
        )
        core = (
            ROOT / "sound" / "eeg_harmonic_field_v2_core.scd"
        ).read_text(encoding="utf-8")
        for token in (
            "voiceCapacity: 6", "voicingCrossfade: 1.35",
            "polyphonySafetyTrim: 0.82",
        ):
            self.assertIn(token, config)
        for token in (
            "\\voiceFrequenciesA", "\\voiceFrequenciesB",
            "\\voiceWeightsA", "\\voiceWeightsB",
            "weights.collect(_.squared).sum", "XFade2.ar(sourceA, sourceB",
            "Limiter.ar(", "\\transportAlive",
        ):
            self.assertIn(token, core)
        self.assertNotIn("LFNoise", core)
        self.assertNotIn("Dust", core)
        self.assertNotIn("Impulse", core)

    def test_render_has_one_synth_and_audio_is_safe(self):
        render_source = (
            ROOT / "sound" / "render_eeg_organism_v2_voicing_transition.scd"
        ).read_text(encoding="utf-8")
        self.assertEqual(render_source.count("[\\s_new,"), 1)
        self.assertNotIn("\\s_new", render_source.split("[\\s_new,", 1)[1])
        self.assertGreaterEqual(render_source.count("[\\n_set,"), 3)
        self.assertGreaterEqual(render_source.count("[\\n_setn,"), 1)

        path = (
            ROOT / "recordings" / "eeg_organism_v2_voicing"
            / "g_lydian_transition.wav"
        )
        with wave.open(str(path), "rb") as recording:
            self.assertEqual(recording.getnchannels(), 2)
            self.assertEqual(recording.getframerate(), 48000)
            self.assertEqual(recording.getsampwidth(), 3)
        result = analyze(path)
        self.assertTrue(result["finite"])
        self.assertFalse(result["clipped"])
        self.assertGreater(result["peak"], 0.001)
        self.assertLess(result["peak"], 0.999)
        self.assertLess(result["transition_max_sample_step"], 0.02)
        self.assertAlmostEqual(result["duration_seconds"], 19.0, places=2)


if __name__ == "__main__":
    unittest.main()
