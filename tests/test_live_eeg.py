import unittest
from unittest.mock import patch
from pathlib import Path

from src import window_engine
from src.sdd.live_eeg import _unit
from src.eeg_control_features import EEGControlFeatureEngine
from src.eeg_control_demo import ControlSession, synthetic_sweep
import numpy as np


class FakeStream:
    def __init__(self, name="OpenBCI", source_id="board-A", uid="uid-A"):
        self._name, self._source_id, self._uid = name, source_id, uid

    def name(self): return self._name
    def type(self): return "EEG"
    def source_id(self): return self._source_id
    def uid(self): return self._uid
    def hostname(self): return "localhost"
    def channel_count(self): return 8
    def nominal_srate(self): return 250.0
    def as_xml(self):
        channels = "".join(
            f"<channel><label>Ch{i}</label><unit>microvolts</unit></channel>"
            for i in range(1, 9)
        )
        return ("<info><desc><channels>" + channels
                + "</channels><acquisition><prefiltering>none</prefiltering>"
                  "</acquisition></desc></info>")


class LiveEEGTests(unittest.TestCase):
    def test_stream_metadata_includes_units_labels_and_filtering(self):
        metadata = window_engine.describe_lsl_stream(FakeStream())
        self.assertEqual(metadata.channel_labels, tuple(f"Ch{i}" for i in range(1, 9)))
        self.assertEqual(metadata.channel_units, ("microvolts",) * 8)
        self.assertEqual(metadata.prefiltering, "none")
        self.assertEqual(metadata.nominal_srate, 250.0)

    def test_multiple_streams_require_an_explicit_selector(self):
        streams = [FakeStream("first", "one", "u1"), FakeStream("second", "two", "u2")]
        with patch.object(window_engine, "list_openbci_lsl", return_value=streams):
            with self.assertRaisesRegex(RuntimeError, "--stream-name or --source-id"):
                window_engine.connect_openbci_lsl()

    def test_selector_is_applied_before_opening_inlet(self):
        streams = [FakeStream("first", "one", "u1"), FakeStream("second", "two", "u2")]
        sentinel = object()
        with patch.object(window_engine, "list_openbci_lsl", return_value=streams), \
                patch.object(window_engine, "StreamInlet", return_value=sentinel):
            inlet, selected, rate = window_engine.connect_openbci_lsl(source_id="two")
        self.assertIs(inlet, sentinel)
        self.assertEqual(selected.name(), "second")
        self.assertEqual(rate, 250.0)

    def test_only_explicit_microvolt_units_enable_energy(self):
        for value in ("uV", "µV", "microvolt", "microvolts"):
            self.assertEqual(_unit(value), "uV")
        self.assertIsNone(_unit("unknown"))
        self.assertIsNone(_unit("volts"))

    def test_flat_required_channel_cannot_calibrate_or_emit_controls(self):
        engine = EEGControlFeatureEngine(
            250, update_rate=4, baseline_seconds=0.5,
            required_quality_channels=(0,),
        )
        t = np.arange(500) / 250
        valid = np.column_stack([
            np.sin(2*np.pi*(8+index)*t) for index in range(6)
        ])
        flat_f3 = valid.copy()
        flat_f3[:, 0] = 0
        for _ in range(3):
            frame = engine.update(flat_f3, flat_f3)
        self.assertFalse(engine.ready)
        self.assertFalse(frame.normalized)
        for _ in range(2):
            frame = engine.update(valid, valid)
        self.assertTrue(engine.ready)

    def test_saturated_required_channel_cannot_calibrate(self):
        engine = EEGControlFeatureEngine(
            250, update_rate=4, baseline_seconds=0.5,
            required_quality_channels=(0,), saturation_abs=10,
        )
        t = np.arange(500) / 250
        data = np.column_stack([np.sin(2*np.pi*(8+i)*t) for i in range(6)])
        data[10, 0] = 10
        frame = engine.update(data, data)
        self.assertFalse(frame.normalized)
        self.assertIn("saturation", frame.quality_warnings["F3"])
        self.assertEqual(engine.frames_seen, 0)

    def test_existing_window_session_can_feed_adapter_without_legacy_output(self):
        class Sender:
            packet_count = 0
            def send(self, _):
                raise AssertionError("legacy 18-value sender must remain disabled")
        frames = []
        session = ControlSession(
            250, 4, 0.5, Sender(), diagnostics=False, transmit=False,
            required_quality_channels=(0,),
            frame_callback=lambda frame, timestamp: frames.append((frame, timestamp)),
        )
        samples, timestamps = synthetic_sweep(4, 250)
        session.add_chunk(samples, timestamps)
        self.assertTrue(frames)
        self.assertTrue(any(frame.normalized for frame, _ in frames))
        self.assertTrue(all(np.isfinite(timestamp) for _, timestamp in frames))

    def test_live_energy_receiver_uses_current_receiver_without_recording(self):
        harness = Path("scripts/run_live_energy_receiver.scd").read_text(encoding="utf-8")
        self.assertIn("sound/eeg_organism_v2_receiver.scd", harness)
        self.assertIn("LIVE_ENERGY_RECEIVER_READY", harness)
        self.assertNotIn("prepareForRecord", harness)
        self.assertNotIn(".record", harness)


if __name__ == "__main__":
    unittest.main()
