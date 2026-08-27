import threading
import time
import unittest

import numpy as np
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

from src.eeg_control_demo import (ControlSession, parse_args, run_synthetic_tidal,
                                  synthetic_controls, synthetic_sweep)
from src.eeg_control_features import EEGControlFeatureEngine, control_names
from src.eeg_preprocessing import StreamingEEGPreprocessor
from src.tidal_osc import TidalControlOscSender

RATE = 250.0


class NullSender:
    def __init__(self):
        self.last_values, self.packet_count = {}, 0
        self.host, self.port = "none", 0

    def send(self, controls):
        self.last_values = dict(controls)
        self.packet_count += len(controls)


class EEGControlTests(unittest.TestCase):
    def test_exact_controls_are_finite_bounded_and_channels_stay_separate(self):
        samples, _ = synthetic_sweep(6.0)
        sender = NullSender()
        session = ControlSession(RATE, 4.0, 1.0, sender, diagnostics=False)
        session.add_chunk(samples)
        frame = session.frames[-1]
        self.assertEqual(tuple(frame.raw), control_names())
        self.assertEqual(tuple(frame.normalized), control_names())
        self.assertTrue(all(np.isfinite(list(frame.raw.values()))))
        self.assertTrue(all(0 <= value <= 1 for value in frame.normalized.values()))
        self.assertEqual(sender.packet_count, 18 * sum(bool(f.normalized) for f in session.frames))
        self.assertGreater(len({round(frame.raw[f"eeg{i}_energy"], 8) for i in range(1, 7)}), 1)

    def test_descriptors_respond_continuously_without_cross_channel_mixing(self):
        t = np.arange(round(2 * RATE)) / RATE
        base = np.column_stack([np.sin(2 * np.pi * 6 * t)] * 6)
        reference = EEGControlFeatureEngine(RATE).update(base)
        changed = base.copy()
        changed[:, 0] *= 2
        changed[:, 1] = np.sin(2 * np.pi * 24 * t)
        response = EEGControlFeatureEngine(RATE).update(changed)
        self.assertGreater(response.raw["eeg1_energy"], reference.raw["eeg1_energy"] * 3.5)
        self.assertGreater(response.raw["eeg2_centroid"], reference.raw["eeg2_centroid"] * 2)
        self.assertGreater(response.raw["eeg2_mobility"], reference.raw["eeg2_mobility"] * 2)
        self.assertAlmostEqual(response.raw["eeg3_energy"], reference.raw["eeg3_energy"], places=12)

    def test_stream_filter_is_causal_stateful_and_chunk_invariant(self):
        samples, _ = synthetic_sweep(3.0)
        eeg = samples[:, :6]
        whole = StreamingEEGPreprocessor(RATE).process(eeg)
        split_filter = StreamingEEGPreprocessor(RATE)
        split = np.vstack([split_filter.process(eeg[:137]), split_filter.process(eeg[137:421]),
                           split_filter.process(eeg[421:])])
        np.testing.assert_allclose(split, whole, atol=1e-12)

    def test_live_session_uses_requested_rate_range_and_never_mixes_ch1(self):
        samples, _ = synthetic_sweep(5.0)
        changed = samples.copy(); changed[:, 0] *= 4.0
        first = ControlSession(RATE, 4.0, 1.0, NullSender(),
                               analysis_low_hz=5.0, analysis_high_hz=35.0,
                               diagnostics=False)
        second = ControlSession(RATE, 4.0, 1.0, NullSender(),
                                analysis_low_hz=5.0, analysis_high_hz=35.0,
                                diagnostics=False)
        first.add_chunk(samples); second.add_chunk(changed)
        self.assertEqual((first.engine.sample_rate, first.engine.low_hz, first.engine.high_hz),
                         (RATE, 5.0, 35.0))
        self.assertGreater(second.frames[-1].raw["eeg1_energy"],
                           first.frames[-1].raw["eeg1_energy"] * 10)
        for channel in range(2, 7):
            for descriptor in ("energy", "centroid", "mobility"):
                key = f"eeg{channel}_{descriptor}"
                self.assertAlmostEqual(first.frames[-1].raw[key],
                                       second.frames[-1].raw[key], places=12)

    def test_calibration_bounds_are_fixed_and_flatline_is_safe(self):
        engine = EEGControlFeatureEngine(RATE, update_rate=4, baseline_seconds=1,
                                         smoothing_seconds=0)
        t = np.arange(round(2 * RATE)) / RATE
        for amplitude in (1, 2, 3, 4):
            eeg = np.column_stack([amplitude * np.sin(2 * np.pi * (6 + i) * t) for i in range(6)])
            frame = engine.update(eeg)
        self.assertTrue(engine.ready)
        bounds = dict(engine.bounds)
        frame = engine.update(np.zeros((len(t), 6)))
        self.assertEqual(bounds, engine.bounds)
        self.assertTrue(all(np.isfinite(list(frame.normalized.values()))))
        self.assertTrue(all(value == 0.0 for value in frame.normalized.values()))

    def test_invalid_samples_are_repaired_causally_and_safely(self):
        samples, _ = synthetic_sweep(5.0)
        samples[510:515, 0] = np.nan
        samples[700, 4] = np.inf
        sender = NullSender()
        session = ControlSession(RATE, 4.0, 1.0, sender, diagnostics=False)
        session.add_chunk(samples)
        self.assertTrue(all(np.isfinite(list(session.frames[-1].raw.values()))))
        self.assertTrue(all(np.isfinite(list(session.frames[-1].normalized.values()))))

    def test_synthetic_connection_controls_change_independently(self):
        first = synthetic_controls(0.0)
        second = synthetic_controls(1.0)
        self.assertEqual(tuple(first), control_names())
        self.assertTrue(all(0 <= value <= 1 and np.isfinite(value) for value in first.values()))
        self.assertTrue(all(first[name] != second[name] for name in control_names()))
        energy_values = [first[f"eeg{i}_energy"] for i in range(1, 7)]
        self.assertGreater(len(set(energy_values)), 3)
        sender = NullSender()
        run_synthetic_tidal(sender, update_rate=1000.0, max_updates=3)
        self.assertEqual(sender.packet_count, 54)

    def test_documented_modes_parse(self):
        self.assertEqual(parse_args(["--mode", "synthetic-tidal"]).mode, "synthetic-tidal")
        args = parse_args(["--mode", "tidal-live", "--calibration-seconds", "20"])
        self.assertEqual((args.mode, args.calibration_seconds), ("tidal-live", 20.0))

    def test_actual_udp_ctrl_packet_encoding(self):
        received = []
        dispatcher = Dispatcher()
        dispatcher.map("/ctrl", lambda address, *args: received.append((address, args)))
        server = ThreadingOSCUDPServer(("127.0.0.1", 0), dispatcher)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            sender = TidalControlOscSender("127.0.0.1", server.server_address[1])
            sender.send({"eeg1_energy": 0.25, "eeg6_mobility": 0.75})
            deadline = time.monotonic() + 2
            while len(received) < 2 and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual({item[1][0] for item in received}, {"eeg1_energy", "eeg6_mobility"})
            self.assertTrue(all(item[0] == "/ctrl" and isinstance(item[1][1], float) for item in received))
            sender.close()
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
