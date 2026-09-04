from pathlib import Path
import unittest
import wave

from scripts.analyze_eeg_organism_v2_beta_profiles import analyze_directory


ROOT = Path(__file__).resolve().parents[1]


class BetaSofteningTests(unittest.TestCase):
    def test_profiles_are_centralized_and_softened_is_default(self):
        config = (ROOT / "config" / "eeg_organism_v2.scd").read_text(
            encoding="utf-8"
        )
        self.assertIn("betaProfile: \\softened", config)
        self.assertIn("original_24_36_48:", config)
        self.assertIn("betaCeilingHz: 12000.0", config)
        self.assertIn("betaUpperPartialTiltDb: 0.0", config)
        self.assertIn("betaTrim: 1.0", config)
        self.assertIn("softened:", config)
        self.assertIn("betaCeilingHz: 2700.0", config)
        self.assertIn("betaUpperPartialTiltDb: -3.5", config)
        self.assertIn("betaTrim: 0.90", config)

    def test_beta_shaping_is_group_four_only_and_transport_is_unchanged(self):
        core = (ROOT / "sound" / "eeg_harmonic_field_v2_core.scd").read_text(
            encoding="utf-8"
        )
        for token in (
            "betaCeilingHz", "betaUpperPartialTiltDb", "betaTrim",
            "if(groupIndex == 3)", "if(groupIndexes[index] == 3)",
        ):
            self.assertIn(token, core)

        receiver = (ROOT / "sound" / "eeg_organism_v2_receiver.scd").read_text(
            encoding="utf-8"
        )
        callback = receiver.split("OSCdef(\\eegOrganismV2Frame", 1)[1].split(
            "OSCdef(\\eegOrganismV2Stop", 1
        )[0]
        for token in (
            "betaCeilingHz", "betaUpperPartialTiltDb", "betaTrim",
        ):
            self.assertNotIn(token, callback)
        self.assertIn("synth.setn(\\groupAmplitudes", callback)

    def test_matched_beta_renders_are_safe_and_softened_remains_bright(self):
        directory = ROOT / "recordings" / "eeg_organism_v2_beta_profiles"
        files = sorted(directory.glob("*.wav"))
        self.assertEqual(len(files), 4)
        for path in files:
            with wave.open(str(path), "rb") as recording:
                self.assertEqual(recording.getnchannels(), 2)
                self.assertEqual(recording.getframerate(), 48000)
                self.assertEqual(recording.getsampwidth(), 3)

        report = analyze_directory(directory)
        original = report["original_24_36_48"]
        softened = report["softened"]
        for profile in (original, softened):
            for level in ("low", "high"):
                self.assertTrue(profile[level]["finite"])
                self.assertFalse(profile[level]["clipped"])
                self.assertLess(profile[level]["peak"], 0.999)

        self.assertAlmostEqual(
            original["low"]["rms_dbfs"], softened["low"]["rms_dbfs"],
            places=3,
        )
        self.assertLess(
            softened["high"]["spectral_centroid_hz"],
            original["high"]["spectral_centroid_hz"],
        )
        self.assertGreater(
            softened["high"]["spectral_centroid_hz"], 1000.0
        )
        self.assertLess(
            softened["high"]["a_weighted_rms_dbfs"],
            original["high"]["a_weighted_rms_dbfs"],
        )


if __name__ == "__main__":
    unittest.main()
