import math
from pathlib import Path
import re
import unittest

import numpy as np

from src.eeg_control_demo import (
    ISOLATED_REFERENCE,
    family_audition_mask,
    family_comparison_controls,
    full_organism_controls,
    isolated_audition_mask,
    isolated_organism_controls,
    isolated_sweep_stage,
    parse_args,
    run_synthetic_supercollider,
)
from src.eeg_control_features import CHANNELS, DESCRIPTORS, control_names
from src.organism_osc import (CONFIG_PATHS, FRAME_ORDER, OrganismOscSender,
                              bounded_frame_values, config_values,
                              load_sonification_config)


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


class OrganismOscTests(unittest.TestCase):
    def test_phase_1b_modes_parse_with_four_hz_supercollider_default(self):
        for mode in ("synthetic-supercollider", "isolated-supercollider",
                     "family-supercollider", "supercollider-live"):
            args = parse_args(["--mode", mode])
            self.assertEqual((args.mode, args.control_hz, args.osc_port),
                             (mode, 4.0, 57120))

    def test_frame_order_is_channel_major_and_unchanged(self):
        expected = tuple(
            f"eeg{channel}_{descriptor}"
            for channel in range(1, 7)
            for descriptor in ("energy", "centroid", "mobility")
        )
        self.assertEqual(FRAME_ORDER, expected)
        self.assertEqual(FRAME_ORDER, control_names())

    def test_frame_is_finite_clamped_and_sent_as_one_packet(self):
        controls = {name: index / 10 for index, name in enumerate(FRAME_ORDER)}
        controls[FRAME_ORDER[0]] = -3
        controls[FRAME_ORDER[1]] = math.nan
        controls[FRAME_ORDER[2]] = math.inf
        client = RecordingClient()
        sender = OrganismOscSender(client=client)
        sender.send(controls)
        self.assertEqual(sender.packet_count, 1)
        self.assertEqual(len(client.messages), 1)
        address, values = client.messages[0]
        self.assertEqual(address, "/eeg/organism/frame")
        self.assertEqual(len(values), 18)
        self.assertTrue(all(math.isfinite(value) and 0 <= value <= 1 for value in values))
        self.assertEqual(values[:3], (0.0, 0.0, 0.0))
        self.assertEqual(values[-1], 1.0)

    def test_strict_isolation_mutes_five_cells_and_changes_one_mapping(self):
        for channel_index, channel in enumerate(CHANNELS, 1):
            mask = isolated_audition_mask(channel)
            self.assertEqual(sum(mask), 1.0)
            self.assertEqual(mask[channel_index - 1], 1.0)
            for descriptor in DESCRIPTORS:
                low = isolated_organism_controls(0.0, descriptor, channel)
                mid = isolated_organism_controls(4.0, descriptor, channel)
                high = isolated_organism_controls(8.0, descriptor, channel)
                target = f"eeg{channel_index}_{descriptor}"
                self.assertEqual((low[target], mid[target], high[target]), (0.05, 0.5, 0.95))
                changed = [name for name in FRAME_ORDER if low[name] != high[name]]
                self.assertEqual(changed, [target])
                for name in FRAME_ORDER:
                    if name != target:
                        reference_descriptor = name.rsplit("_", 1)[1]
                        self.assertEqual(low[name], ISOLATED_REFERENCE[reference_descriptor])
                        self.assertEqual(high[name], ISOLATED_REFERENCE[reference_descriptor])

    def test_isolated_stages_are_low_mid_high_mid_low(self):
        stages = tuple(isolated_sweep_stage(t) for t in (0, 4, 8, 12, 16))
        self.assertEqual(stages, ("LOW", "MID", "HIGH", "MID", "LOW"))

    def test_audition_mask_is_one_bounded_packet(self):
        client = RecordingClient()
        sender = OrganismOscSender(client=client)
        sender.send_audition_mask((0, -1, math.nan, 0.5, 2, 1))
        self.assertEqual(client.messages, [
            ("/eeg/organism/audition", (0.0, 0.0, 0.0, 0.5, 1.0, 1.0))
        ])
        with self.assertRaises(ValueError):
            sender.send_audition_mask((1, 0))

    def test_family_comparison_uses_identical_descriptors_and_distinct_masks(self):
        controls = family_comparison_controls()
        for descriptor in DESCRIPTORS:
            values = [controls[f"eeg{channel}_{descriptor}"] for channel in range(1, 7)]
            self.assertEqual(values, [ISOLATED_REFERENCE[descriptor]] * 6)
        self.assertEqual(family_audition_mask("P"), (0, 0, 0, 0, 1, 1))
        self.assertEqual(family_audition_mask("C"), (0, 0, 1, 1, 0, 0))
        self.assertEqual(family_audition_mask("F"), (1, 1, 0, 0, 0, 0))

    def test_full_scene_is_deterministic_ordered_finite_and_slowly_changing(self):
        first = full_organism_controls(3.25)
        repeated = full_organism_controls(3.25)
        later = full_organism_controls(9.25)
        self.assertEqual(first, repeated)
        self.assertEqual(tuple(first), FRAME_ORDER)
        self.assertTrue(all(math.isfinite(value) and 0 <= value <= 1
                            for value in first.values()))
        self.assertTrue(all(first[name] != later[name] for name in FRAME_ORDER))

    def test_config_packet_order_is_complete_and_finite(self):
        config = load_sonification_config()
        values = config_values(config)
        self.assertEqual(len(values), len(CONFIG_PATHS))
        self.assertEqual(len(values), 41)
        self.assertTrue(all(math.isfinite(value) for value in values))
        client = RecordingClient()
        sender = OrganismOscSender.from_config(config, client=client)
        sender.send_config(config)
        self.assertEqual(client.messages, [(config["osc"]["config_address"], values)])

    def test_extended_stream_has_one_frame_packet_per_update(self):
        clock = FakeClock()
        client = RecordingClient()
        sender = OrganismOscSender(client=client)
        transmitter = run_synthetic_supercollider(
            sender, control_hz=4.0, max_updates=5000,
            clock=clock.monotonic, sleeper=clock.sleep, diagnostics=False
        )
        frame_messages = [message for message in client.messages
                          if message[0] == "/eeg/organism/frame"]
        self.assertEqual(transmitter.frames_sent, 5000)
        self.assertEqual(len(frame_messages), 5000)
        self.assertEqual(sender.packet_count, 5001)  # one startup mask, then frames
        self.assertTrue(all(len(values) == 18 for _, values in frame_messages))
        np.testing.assert_allclose(clock.now, (5000 - 1) / 4.0, atol=1e-9)

    def test_engine_has_stable_node_count_and_no_autonomous_event_sources(self):
        engine_path = Path(__file__).resolve().parents[1] / "sound" / "eeg_organism_engine.scd"
        source = engine_path.read_text(encoding="utf-8")
        self.assertEqual(source.count("Synth.tail("), 7)
        config_order = source.split("configOrder = [", 1)[1].split("];", 1)[0]
        self.assertEqual(len(re.findall(r"\\[A-Za-z][A-Za-z0-9]*", config_order)),
                         len(CONFIG_PATHS))
        frame_callback = source.split("OSCdef(\\eegOrganismFrame", 1)[1].split(
            "OSCdef(\\eegOrganismAudition", 1
        )[0]
        self.assertNotIn("Synth.", frame_callback)
        for banned in ("PinkNoise", "WhiteNoise", "BrownNoise", "Dust", "Impulse",
                       "Demand", "Dseq"):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
