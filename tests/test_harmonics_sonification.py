import json
import math
from pathlib import Path
import subprocess
import sys
import unittest

from src.sonification.harmonics_mapping import (
    band_controls_to_group_amplitudes,
    band_controls_to_harmonics_frame,
)
from src.sonification.harmonics_protocol import (
    HARMONICS_FRAME_ADDRESS,
    HARMONICS_PARAMETER_ORDER,
    HarmonicsControlFrame,
    HarmonicsOscSender,
    clamp_unit,
)
from src.sonification.harmonics_synthetic_demo import iter_sweep, synthetic_frame_at


ROOT = Path(__file__).resolve().parents[1]


class RecordingClient:
    def __init__(self):
        self.messages = []

    def send_message(self, address, values):
        self.messages.append((address, tuple(values)))


class HarmonicsSonificationTests(unittest.TestCase):
    def test_protocol_has_one_strict_ordered_bounded_packet(self):
        frame = HarmonicsControlFrame.from_mapping({
            "group4": 2,
            "group2": 0.4,
            "master_energy": -1,
            "group1": 0.2,
            "group3": 0.6,
        })
        self.assertEqual(HARMONICS_PARAMETER_ORDER, (
            "master_energy", "group1", "group2", "group3", "group4"
        ))
        self.assertEqual(frame.as_osc_values(), (0.0, 0.2, 0.4, 0.6, 1.0))
        client = RecordingClient()
        sender = HarmonicsOscSender(client=client)
        sender.send(frame)
        self.assertEqual(client.messages, [
            (HARMONICS_FRAME_ADDRESS, (0.0, 0.2, 0.4, 0.6, 1.0))
        ])
        self.assertEqual(sender.packet_count, 1)

    def test_protocol_rejects_missing_extra_and_nonfinite_values(self):
        with self.assertRaises(ValueError):
            HarmonicsControlFrame.from_mapping({"master_energy": 1})
        with self.assertRaises(ValueError):
            HarmonicsControlFrame.from_values([1, 2])
        for invalid in (math.nan, math.inf, -math.inf, "not-a-number"):
            with self.assertRaises(ValueError):
                clamp_unit(invalid)

    def test_direct_band_mapping_is_pure_l2_normalized_and_energy_independent(self):
        bands = {"delta": 0.8, "theta": 0.4, "alpha": 0.2, "beta": 0.1}
        original = bands.copy()
        groups = band_controls_to_group_amplitudes(bands)
        self.assertEqual(bands, original)
        self.assertAlmostEqual(sum(value * value for value in groups.values()), 1.0)
        low = band_controls_to_harmonics_frame(bands, 0.1)
        high = band_controls_to_harmonics_frame(bands, 0.9)
        self.assertEqual(low.as_osc_values()[1:], high.as_osc_values()[1:])
        self.assertEqual((low.master_energy, high.master_energy), (0.1, 0.9))

    def test_zero_band_vector_remains_zero(self):
        groups = band_controls_to_group_amplitudes({
            "delta": 0, "theta": 0, "alpha": 0, "beta": 0
        })
        self.assertEqual(groups, {
            "group1": 0.0, "group2": 0.0, "group3": 0.0, "group4": 0.0
        })

    def test_synthetic_sweeps_are_deterministic_bounded_and_separated(self):
        for name in ("master", "brightness", "groups"):
            first = list(iter_sweep(name, duration=4, rate=4))
            repeated = list(iter_sweep(name, duration=4, rate=4))
            self.assertEqual(first, repeated)
            self.assertEqual(len(first), 17)
            self.assertTrue(all(
                0 <= value <= 1
                for _, frame in first
                for value in frame.as_osc_values()
            ))
        master_start = synthetic_frame_at(0, sweep="master")
        master_mid = synthetic_frame_at(8, sweep="master")
        self.assertGreater(master_mid.master_energy, master_start.master_energy)
        self.assertEqual(master_mid.as_osc_values()[1:], master_start.as_osc_values()[1:])
        bright_start = synthetic_frame_at(0, sweep="brightness")
        bright_mid = synthetic_frame_at(8, sweep="brightness")
        self.assertGreater(bright_start.group1, bright_start.group4)
        self.assertGreater(bright_mid.group4, bright_mid.group1)

    def test_cli_defaults_to_fast_dry_run_without_changing_old_entry_points(self):
        result = subprocess.run(
            [sys.executable, "-m", "src.sonification.harmonics_synthetic_demo",
             "--sweep", "master", "--duration", "0.5", "--rate", "2"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(rows), 2)
        self.assertEqual(tuple(key for key in rows[0] if key != "seconds"),
                         HARMONICS_PARAMETER_ORDER)
        self.assertTrue((ROOT / "src" / "eeg_control_demo.py").exists())
        self.assertTrue((ROOT / "scripts" / "start_eeg_organism.ps1").exists())

    def test_new_package_does_not_import_forbidden_runtime_or_duplicate_acquisition(self):
        package = ROOT / "src" / "sonification"
        source = "\n".join(
            path.read_text(encoding="utf-8") for path in package.glob("*.py")
        ).lower()
        for forbidden in ("import eegsynth", "import fieldtrip", "import redis", "pylsl"):
            self.assertNotIn(forbidden, source)
        architecture = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
        for stage in (
            "LSL / acquisition", "EEG preprocessing", "Feature extraction",
            "Normalization / mapping", "OSC protocol", "SuperCollider instrument",
        ):
            self.assertIn(stage, architecture)


if __name__ == "__main__":
    unittest.main()
