import threading
import time
import unittest

import numpy as np
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

from src.eeg_control_demo import ControlSession
from src.eeg_control_features import EEGControlFeatureEngine
from src.tidal_osc import TidalControlOscSender


RATE = 250.0


def tones(seconds=2.0):
    t = np.arange(round(seconds * RATE)) / RATE
    return np.column_stack([(i + 1) * np.sin(2 * np.pi * (4 + 2 * i) * t + i * 0.13) for i in range(6)])


class NullSender:
    def __init__(self):
        self.last_values = {}
        self.packet_count = 0
        self.host, self.port = "none", 0

    def send(self, controls):
        self.last_values = dict(controls)
        self.packet_count += len(controls)


class EEGControlTests(unittest.TestCase):
    def test_channels_are_separate_finite_normalized_and_not_averaged(self):
        eeg = tones()
        engine = EEGControlFeatureEngine(RATE, baseline_seconds=1)
        frame = engine.update(eeg)
        self.assertTrue(all(np.isfinite(list(frame.raw.values()))))
        self.assertTrue(all(0 <= value <= 1 for value in frame.normalized.values()))
        energies = [frame.raw[f"{name}_energy"] for name in ("f3", "f4", "c3", "c4", "p3", "p4")]
        self.assertTrue(all(a < b for a, b in zip(energies, energies[1:])))
        changed = eeg.copy(); changed[:, 0] *= 3
        other = EEGControlFeatureEngine(RATE, baseline_seconds=1).update(changed)
        self.assertGreater(other.raw["f3_energy"], frame.raw["f3_energy"] * 2.5)
        self.assertAlmostEqual(other.raw["f4_energy"], frame.raw["f4_energy"], places=10)

    def test_expected_energy_centroid_entropy_and_mobility_response(self):
        t = np.arange(round(2 * RATE)) / RATE
        base = np.column_stack([np.sin(2 * np.pi * 6 * t)] * 6)
        reference = EEGControlFeatureEngine(RATE).update(base)
        changed = base.copy()
        changed[:, 0] *= 2
        changed[:, 1] = np.sin(2 * np.pi * 24 * t)
        changed[:, 2] = sum(np.sin(2 * np.pi * f * t + f) for f in (4, 9, 15, 23, 31)) / np.sqrt(5)
        response = EEGControlFeatureEngine(RATE).update(changed)
        self.assertGreater(response.raw["f3_energy"], reference.raw["f3_energy"] * 1.8)
        self.assertGreater(response.raw["f4_centroid"], reference.raw["f4_centroid"] * 2)
        self.assertGreater(response.raw["f4_mobility"], reference.raw["f4_mobility"] * 2)
        self.assertGreater(response.raw["c3_entropy"], reference.raw["c3_entropy"])

    def test_pair_asymmetry_similarity_and_positive_delayed_second_signal_lag(self):
        t = np.arange(round(2 * RATE)) / RATE
        signal = np.sin(2 * np.pi * 7 * t) * (1 + 0.3 * np.sin(2 * np.pi * 0.8 * t))
        delay = round(0.04 * RATE)
        delayed = np.concatenate((np.zeros(delay), signal[:-delay]))
        eeg = tones()
        eeg[:, 0], eeg[:, 1] = 2 * signal, delayed
        frame = EEGControlFeatureEngine(RATE).update(eeg)
        self.assertGreater(frame.raw["f3_f4_asymmetry"], 0)
        self.assertGreater(frame.raw["f3_f4_similarity"], -0.2)
        self.assertAlmostEqual(frame.raw["f3_f4_lag"], 0.04, delta=1 / RATE)

    def test_actual_udp_ctrl_packet_encoding(self):
        received = []
        dispatcher = Dispatcher()
        dispatcher.map("/ctrl", lambda address, *args: received.append((address, args)))
        server = ThreadingOSCUDPServer(("127.0.0.1", 0), dispatcher)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            sender = TidalControlOscSender("127.0.0.1", server.server_address[1])
            sender.send({"f3_energy": 0.25, "p3_p4_lag": 0.75})
            deadline = time.monotonic() + 2
            while len(received) < 2 and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual({item[1][0] for item in received}, {"f3_energy", "p3_p4_lag"})
            self.assertTrue(all(item[0] == "/ctrl" and isinstance(item[1][1], float) for item in received))
            sender.close()
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)

    def test_configurable_feature_and_packet_rate(self):
        eeg = tones(5.0)
        slow = ControlSession(RATE, 2.0, 2.0, NullSender()); slow.add_chunk(eeg)
        fast = ControlSession(RATE, 4.0, 2.0, NullSender()); fast.add_chunk(eeg)
        self.assertGreater(len(fast.frames), len(slow.frames))
        self.assertAlmostEqual(len(fast.frames) / len(slow.frames), 2.0, delta=0.35)
        self.assertEqual(fast.sender.packet_count, len(fast.frames) * len(fast.frames[-1].normalized))


if __name__ == "__main__":
    unittest.main()
