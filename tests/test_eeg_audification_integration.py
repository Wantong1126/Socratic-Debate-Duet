import unittest

import numpy as np

from src.eeg_audification import AudificationConfig, process_eeg, signal_metrics
from src.eeg_audification_demo import synthetic_recording


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


if __name__ == "__main__":
    unittest.main()
