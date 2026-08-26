import unittest

import numpy as np

from src.eeg_audification import AudificationConfig, process_eeg, signal_metrics
from src.eeg_audification_demo import synthetic_recording, timestamp_metrics


class EEGAudificationIntegrationTest(unittest.TestCase):
    def test_six_channels_remain_separate_with_valid_durations_and_samples(self):
        seconds = 2.0
        samples, _, sample_rate, _ = synthetic_recording(seconds)
        config = AudificationConfig()
        result = process_eeg(samples[:, :6], sample_rate, config)

        expected_a = round(samples.shape[0] * config.output_rate / config.audification_rate)
        expected_b = round(seconds * config.output_rate)
        self.assertTrue(all(len(x) == expected_a for x in result.audified))
        self.assertTrue(all(len(x) == expected_b for x in result.modulated))

        for collection in (result.normalized.T, result.audified, result.modulated):
            self.assertEqual(len(collection), 6)
            for channel, signal in enumerate(collection):
                self.assertTrue(np.all(np.isfinite(signal)))
                self.assertEqual(signal_metrics(signal)["clipping_count"], 0)
                for other in range(channel):
                    self.assertFalse(np.allclose(signal, collection[other]))

    def test_large_offset_and_slow_ramp_are_removed_but_passband_is_preserved(self):
        seconds, rate = 20.0, 250.0
        t = np.arange(round(seconds * rate)) / rate
        tone = 18.0 * np.sin(2 * np.pi * 10.0 * t)
        base = 30_000.0 + 600.0 * t / 60.0 + tone
        eeg = np.column_stack([base + ch * 1000.0 for ch in range(6)])
        result = process_eeg(eeg, rate)
        middle = result.cleaned[round(rate * 2):-round(rate * 2), 0]
        middle_t = t[round(rate * 2):-round(rate * 2)]
        fitted = np.column_stack((np.sin(2 * np.pi * 10 * middle_t),
                                  np.cos(2 * np.pi * 10 * middle_t)))
        amplitude = np.linalg.norm(np.linalg.lstsq(fitted, middle, rcond=None)[0])
        cleaned_slope = np.polyfit(middle_t / 60.0, middle, 1)[0]
        self.assertLess(abs(np.mean(middle)), 0.1)
        self.assertLess(abs(cleaned_slope), 1.0)
        self.assertAlmostEqual(amplitude, 18.0, delta=1.0)

    def test_50_hz_is_attenuated(self):
        rate, seconds = 250.0, 20.0
        t = np.arange(round(rate * seconds)) / rate
        contamination = 100.0 * np.sin(2 * np.pi * 50 * t)
        eeg = np.column_stack([contamination + np.sin(2 * np.pi * (8 + ch) * t)
                               for ch in range(6)])
        result = process_eeg(eeg, rate)
        basis = np.column_stack((np.sin(2 * np.pi * 50 * t), np.cos(2 * np.pi * 50 * t)))
        residual = np.linalg.norm(np.linalg.lstsq(basis, result.cleaned[:, 0], rcond=None)[0])
        self.assertLess(residual, 2.0)

    def test_filtering_does_not_mix_channels(self):
        rate = 250.0
        t = np.arange(round(4 * rate)) / rate
        original = np.column_stack([np.sin(2 * np.pi * (5 + ch) * t) for ch in range(6)])
        changed = original.copy()
        changed[:, 0] += 100 * np.sin(2 * np.pi * 20 * t)
        first, second = process_eeg(original, rate), process_eeg(changed, rate)
        self.assertFalse(np.allclose(first.cleaned[:, 0], second.cleaned[:, 0]))
        np.testing.assert_allclose(first.cleaned[:, 1:], second.cleaned[:, 1:], atol=1e-12)

    def test_flatline_method_b_is_silence_and_wav_lengths_remain_valid(self):
        rate, seconds = 250.0, 2.0
        t = np.arange(round(rate * seconds)) / rate
        eeg = np.column_stack([np.zeros_like(t)] +
                              [np.sin(2 * np.pi * (5 + ch) * t) for ch in range(1, 6)])
        result = process_eeg(eeg, rate)
        self.assertFalse(result.valid_channels[0])
        self.assertTrue(np.all(result.modulated[0] == 0))
        self.assertTrue(np.all(result.audified[0] == 0))
        self.assertEqual(len(result.audified[0]), round(len(t) * 48_000 / 8_000))
        self.assertEqual(len(result.modulated[0]), round(seconds * 48_000))
        for output in result.audified + result.modulated:
            self.assertTrue(np.all(np.isfinite(output)))
            self.assertEqual(signal_metrics(output)["clipping_count"], 0)

    def test_timestamp_jitter_is_not_counted_as_missing_samples(self):
        intervals = np.tile([0.0038, 0.0042, 0.0040, 0.0041], 100)
        metrics = timestamp_metrics(np.concatenate(([0.0], np.cumsum(intervals))), 250.0)
        self.assertEqual(metrics["missing_samples"], 0)
        self.assertAlmostEqual(metrics["median"], 0.00405, places=6)
        with_gap = intervals.copy()
        with_gap[50] = 0.012
        metrics = timestamp_metrics(np.concatenate(([0.0], np.cumsum(with_gap))), 250.0)
        self.assertEqual(metrics["missing_samples"], 2)


if __name__ == "__main__":
    unittest.main()
