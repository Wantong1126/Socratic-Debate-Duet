import math
import unittest

from src.sonification.features import NOVELTY_FEATURE_ORDER, NoveltyEstimator


BASELINE = {
    "energy": 0.2,
    "centroid": 0.2,
    "mobility": 0.2,
    "spectral_entropy": 0.2,
    "delta": 0.2,
    "theta": 0.2,
    "alpha": 0.2,
    "beta": 0.2,
}
CHANGED = {name: 0.8 for name in NOVELTY_FEATURE_ORDER}


def update(estimator, values):
    return estimator.update(
        values["energy"],
        values["centroid"],
        values["mobility"],
        values["spectral_entropy"],
        {name: values[name] for name in ("delta", "theta", "alpha", "beta")},
    )


class NoveltyEstimatorTests(unittest.TestCase):
    def test_defaults_use_eight_seconds_of_prior_frames_at_four_hz(self):
        estimator = NoveltyEstimator()
        self.assertEqual(estimator.history_capacity, 32)
        warmup = [update(estimator, BASELINE) for _ in range(32)]
        self.assertEqual(warmup, [0.0] * 32)
        self.assertTrue(estimator.is_warm)

    def test_stable_repetition_stays_low(self):
        estimator = NoveltyEstimator()
        output = [update(estimator, BASELINE) for _ in range(80)]
        self.assertEqual(output, [0.0] * 80)

    def test_abrupt_multidimensional_change_peaks_then_new_state_settles(self):
        estimator = NoveltyEstimator()
        for _ in range(estimator.history_capacity):
            update(estimator, BASELINE)

        first_change = update(estimator, CHANGED)
        continued = [update(estimator, CHANGED) for _ in range(40)]

        self.assertGreater(first_change, 0.99)
        self.assertLess(continued[-1], 0.01)
        self.assertGreater(first_change, continued[-1])

    def test_zero_mad_uses_finite_floor_and_caps_one_dimension(self):
        estimator = NoveltyEstimator()
        for _ in range(estimator.history_capacity):
            update(estimator, BASELINE)
        changed = BASELINE.copy()
        changed["energy"] = 1.0

        result = update(estimator, changed)

        self.assertTrue(math.isfinite(result))
        self.assertGreater(result, 0.0)
        self.assertLess(result, 0.6)

    def test_estimator_histories_are_independent(self):
        first = NoveltyEstimator()
        second = NoveltyEstimator()
        for _ in range(32):
            update(first, BASELINE)
            update(second, CHANGED)

        self.assertGreater(update(first, CHANGED), 0.99)
        self.assertEqual(update(second, CHANGED), 0.0)
        first.reset()
        self.assertEqual(first.history_length, 0)
        self.assertEqual(second.history_length, 32)

    def test_output_is_finite_clamped_and_reproducible(self):
        sequence = []
        for index in range(96):
            sequence.append({
                name: ((index * (offset + 3)) % 29) / 28.0
                for offset, name in enumerate(NOVELTY_FEATURE_ORDER)
            })
        first = NoveltyEstimator()
        second = NoveltyEstimator()
        first_output = [update(first, values) for values in sequence]
        second_output = [update(second, values) for values in sequence]

        self.assertEqual(first_output, second_output)
        self.assertTrue(all(
            math.isfinite(value) and 0.0 <= value <= 1.0
            for value in first_output
        ))

    def test_invalid_frame_does_not_mutate_history(self):
        estimator = NoveltyEstimator()
        update(estimator, BASELINE)
        invalid = BASELINE.copy()
        invalid["energy"] = math.nan
        with self.assertRaises(ValueError):
            update(estimator, invalid)
        self.assertEqual(estimator.history_length, 1)


if __name__ == "__main__":
    unittest.main()
