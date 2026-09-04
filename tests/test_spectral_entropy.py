import unittest

import numpy as np

from src.sonification.features import spectral_entropy


SAMPLE_RATE = 250.0
DURATION_SECONDS = 4.0


class SpectralEntropyTests(unittest.TestCase):
    @staticmethod
    def _time_axis():
        return np.arange(round(SAMPLE_RATE * DURATION_SECONDS)) / SAMPLE_RATE

    def test_sinusoid_is_less_entropic_than_broadband_and_dense_spectrum(self):
        time_axis = self._time_axis()
        sinusoid = np.sin(2.0 * np.pi * 10.0 * time_axis)
        broadband = np.random.default_rng(20260904).standard_normal(time_axis.size)
        dense = sum(
            np.sin(2.0 * np.pi * frequency * time_axis)
            for frequency in np.arange(1.0, 45.0, 1.0)
        )

        sinusoid_entropy = spectral_entropy(sinusoid, SAMPLE_RATE)
        broadband_entropy = spectral_entropy(broadband, SAMPLE_RATE)
        dense_entropy = spectral_entropy(dense, SAMPLE_RATE)

        self.assertLess(sinusoid_entropy, broadband_entropy)
        self.assertLess(sinusoid_entropy, dense_entropy)
        self.assertGreater(broadband_entropy - sinusoid_entropy, 0.4)
        self.assertGreater(dense_entropy - sinusoid_entropy, 0.4)

    def test_amplitude_scaling_barely_changes_entropy(self):
        time_axis = self._time_axis()
        signal = (
            np.sin(2.0 * np.pi * 7.0 * time_axis)
            + 0.4 * np.sin(2.0 * np.pi * 19.0 * time_axis)
            + 0.2 * np.sin(2.0 * np.pi * 37.0 * time_axis)
        )
        reference = spectral_entropy(signal, SAMPLE_RATE)

        for scale in (1e-12, 1e-3, 7.5, 1e120):
            with self.subTest(scale=scale):
                self.assertAlmostEqual(
                    spectral_entropy(signal * scale, SAMPLE_RATE),
                    reference,
                    places=12,
                )

    def test_energy_above_45_hz_is_excluded(self):
        time_axis = self._time_axis()
        in_band = np.sin(2.0 * np.pi * 10.0 * time_axis)
        with_strong_out_of_band_tone = (
            in_band + 1000.0 * np.sin(2.0 * np.pi * 70.0 * time_axis)
        )
        self.assertAlmostEqual(
            spectral_entropy(with_strong_out_of_band_tone, SAMPLE_RATE),
            spectral_entropy(in_band, SAMPLE_RATE),
            places=10,
        )

    def test_invalid_inputs_return_zero_deterministically(self):
        valid_length = round(SAMPLE_RATE * 2.0)
        invalid_cases = (
            (np.zeros(valid_length), SAMPLE_RATE),
            (np.ones(valid_length), SAMPLE_RATE),
            (np.arange(valid_length - 1), SAMPLE_RATE),
            (np.full(valid_length, np.nan), SAMPLE_RATE),
            (np.full(valid_length, np.inf), SAMPLE_RATE),
            (np.column_stack((np.ones(valid_length), np.ones(valid_length))), SAMPLE_RATE),
            (["not-a-number"], SAMPLE_RATE),
            (np.ones(valid_length), 0.0),
            (np.ones(valid_length), np.nan),
            (np.ones(valid_length), 80.0),
        )
        for window, sample_rate in invalid_cases:
            with self.subTest(sample_rate=sample_rate):
                first = spectral_entropy(window, sample_rate)
                second = spectral_entropy(window, sample_rate)
                self.assertEqual(first, 0.0)
                self.assertEqual(second, first)

    def test_result_is_finite_and_clamped(self):
        time_axis = self._time_axis()
        candidates = (
            np.sin(2.0 * np.pi * 0.5 * time_axis),
            np.sin(2.0 * np.pi * 45.0 * time_axis),
            np.random.default_rng(7).standard_normal(time_axis.size),
        )
        for candidate in candidates:
            with self.subTest():
                result = spectral_entropy(candidate, SAMPLE_RATE)
                self.assertTrue(np.isfinite(result))
                self.assertGreaterEqual(result, 0.0)
                self.assertLessEqual(result, 1.0)


if __name__ == "__main__":
    unittest.main()
