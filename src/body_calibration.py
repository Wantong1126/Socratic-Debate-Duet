import numpy as np


class BodyCalibrator:
    FEATURE_NAMES = (
        "eog_activity",
        "emg_activity",
    )

    def __init__(
        self,
        duration_seconds=20.0,
        update_interval_seconds=0.25,
    ):
        self.required_updates = int(round(
            duration_seconds / update_interval_seconds
        ))

        self.recorded_values = {
            name: []
            for name in self.FEATURE_NAMES
        }

        self.ranges = None

    @property
    def ready(self):
        return self.ranges is not None

    @property
    def progress(self):
        recorded = len(
            self.recorded_values["eog_activity"]
        )

        return min(
            recorded / self.required_updates,
            1.0,
        )

    def add(self, body_features):
        if self.ready:
            return

        for name in self.FEATURE_NAMES:
            self.recorded_values[name].append(
                float(body_features[name])
            )

        recorded = len(
            self.recorded_values["eog_activity"]
        )

        if recorded >= self.required_updates:
            self._fit()

    def _fit(self):
        self.ranges = {}

        for name in self.FEATURE_NAMES:
            values = np.asarray(
                self.recorded_values[name],
                dtype=float,
            )

            low, high = np.percentile(
                values,
                [5, 95],
            )

            self.ranges[name] = (
                float(low),
                float(high),
            )

    def normalize(self, body_features):
        if not self.ready:
            raise RuntimeError(
                "Calibration has not finished."
            )

        controls = {}

        for name in self.FEATURE_NAMES:
            low, high = self.ranges[name]
            span = high - low

            # A nearly constant signal has no useful range.
            if span <= 1e-9:
                normalized = 0.0
            else:
                normalized = (
                    body_features[name] - low
                ) / span

                normalized = float(
                    np.clip(normalized, 0.0, 1.0)
                )

            control_name = name.replace(
                "_activity",
                "_control",
            )

            controls[control_name] = normalized

        return controls