import math
import unittest

import numpy as np

from src.eeg_control_demo import (run_synthetic_supercollider,
                                  synthetic_organism_controls)
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
    def test_frame_order_is_channel_major_and_documented(self):
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

    def test_frame_requires_exactly_six_independent_channels(self):
        controls = synthetic_organism_controls(1.0, "energy", "F3")
        values = bounded_frame_values(controls)
        changed = [name for name, value in zip(FRAME_ORDER, values) if value != 0.5]
        self.assertEqual(changed, ["eeg1_energy"])
        with self.assertRaises(ValueError):
            bounded_frame_values({name: 0.5 for name in FRAME_ORDER[:-1]})

    def test_every_descriptor_channel_pair_can_be_isolated(self):
        for channel_index, channel in enumerate(CHANNELS, 1):
            for descriptor in DESCRIPTORS:
                controls = synthetic_organism_controls(2.0, descriptor, channel)
                changed = [name for name, value in controls.items() if value != 0.5]
                self.assertEqual(changed, [f"eeg{channel_index}_{descriptor}"])

    def test_config_packet_order_is_complete_and_finite(self):
        config = load_sonification_config()
        values = config_values(config)
        self.assertEqual(len(values), len(CONFIG_PATHS))
        self.assertEqual(len(values), 28)
        self.assertTrue(all(math.isfinite(value) for value in values))
        client = RecordingClient()
        sender = OrganismOscSender.from_config(config, client=client)
        sender.send_config(config)
        self.assertEqual(client.messages, [(config["osc"]["config_address"], values)])

    def test_extended_stream_has_one_packet_per_frame_and_no_catch_up(self):
        clock = FakeClock()
        client = RecordingClient()
        sender = OrganismOscSender(client=client)
        transmitter = run_synthetic_supercollider(
            sender, control_hz=4.0, sweep_descriptor="mobility", sweep_channel="P4",
            max_updates=5000, clock=clock.monotonic, sleeper=clock.sleep,
            diagnostics=False
        )
        self.assertEqual(transmitter.frames_sent, 5000)
        self.assertEqual(sender.packet_count, 5000)
        self.assertEqual(len(client.messages), 5000)
        self.assertTrue(all(address == "/eeg/organism/frame" and len(values) == 18
                            for address, values in client.messages))
        np.testing.assert_allclose(clock.now, (5000 - 1) / 4.0, atol=1e-9)


if __name__ == "__main__":
    unittest.main()
