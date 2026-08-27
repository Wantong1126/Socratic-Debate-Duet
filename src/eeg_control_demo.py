"""Stream six EEG channels as 18 calibrated controls to TidalCycles."""

import argparse
from collections import deque
import time

import numpy as np

from .eeg_control_features import CHANNELS, DESCRIPTORS, EEGControlFeatureEngine
from .eeg_preprocessing import EEGFilterConfig, StreamingEEGPreprocessor
from .tidal_osc import TidalControlOscSender


def synthetic_sweep(seconds, sample_rate=250.0):
    """Six distinct continuously varying signals for end-to-end sound checks."""
    count = int(round(seconds * sample_rate))
    t = np.arange(count) / sample_rate
    channels = []
    for index in range(6):
        slow = 0.5 + 0.5 * np.sin(2 * np.pi * t / (7.0 + index) + index)
        frequency = 5.0 + index * 2.0 + (22.0 - index) * slow
        phase = 2 * np.pi * np.cumsum(frequency) / sample_rate
        channels.append((8.0 + 20.0 * slow) * np.sin(phase)
                        + (2.0 + index) * np.sin(2 * np.pi * (35 - index) * t))
    return np.column_stack((np.column_stack(channels), np.zeros((count, 2)))), t


# Retained as an import-compatible alias for earlier validation scripts.
def deterministic_scenarios(seconds, sample_rate=250.0):
    samples, timestamps = synthetic_sweep(seconds, sample_rate)
    return samples, timestamps, None


class ControlSession:
    def __init__(self, sample_rate, update_rate, baseline_seconds, sender,
                 window_seconds=2.0, analysis_low_hz=4.0, analysis_high_hz=40.0,
                 smoothing_seconds=0.5, diagnostics=True):
        self.sample_rate, self.update_rate = float(sample_rate), float(update_rate)
        self.window_samples = int(round(window_seconds * sample_rate))
        self.update_samples = max(1, int(round(sample_rate / update_rate)))
        self.feature_buffer = deque(maxlen=self.window_samples)
        self.quality_buffer = deque(maxlen=self.window_samples)
        self.preprocessor = StreamingEEGPreprocessor(sample_rate)
        analysis_config = EEGFilterConfig(highpass_hz=analysis_low_hz, highpass_order=4,
                                          lowpass_hz=analysis_high_hz, lowpass_order=4,
                                          notch_hz=None)
        self.analysis_filter = StreamingEEGPreprocessor(sample_rate, analysis_config)
        self.engine = EEGControlFeatureEngine(sample_rate, update_rate, baseline_seconds,
                                              analysis_low_hz, analysis_high_hz,
                                              smoothing_seconds)
        self.sender = sender
        self.frames, self.frame_times = [], []
        self.total_samples = self.last_update_sample = 0
        self.diagnostics = diagnostics
        self._last_diagnostic_second = -1
        self.calibration_seconds = float(baseline_seconds)
        self._last_valid = np.zeros(6, dtype=float)

    def _print_status(self, frame):
        elapsed = min(self.calibration_seconds,
                      frame.baseline_progress * self.calibration_seconds)
        if not self.engine.ready or not frame.normalized:
            print(f"CALIBRATING EEG: {elapsed:.1f} / {self.calibration_seconds:.1f} seconds")
            return
        second = int(self.total_samples / self.sample_rate)
        if second == self._last_diagnostic_second:
            return
        self._last_diagnostic_second = second
        groups = []
        for index, label in enumerate(CHANNELS, 1):
            groups.append(f"{label}  E={frame.normalized[f'eeg{index}_energy']:.2f} "
                          f"C={frame.normalized[f'eeg{index}_centroid']:.2f} "
                          f"M={frame.normalized[f'eeg{index}_mobility']:.2f}")
        print(" | ".join(groups))

    def add_chunk(self, chunk, timestamps=None):
        raw = np.asarray(chunk, dtype=float)
        if raw.ndim != 2 or raw.shape[1] < 6:
            raise ValueError("Expected chunks shaped (samples, at least 6 channels).")
        eeg = raw[:, :6]
        repaired = eeg.copy()
        # Causal repair: an invalid sample uses only the last finite value seen
        # on that same channel (or zero before the first valid sample).
        for row in repaired:
            valid = np.isfinite(row)
            row[~valid] = self._last_valid[~valid]
            self._last_valid[valid] = row[valid]
        cleaned = self.preprocessor.process(repaired)
        feature_signal = self.analysis_filter.process(cleaned)
        for row_index, (raw_row, feature_row) in enumerate(zip(eeg, feature_signal)):
            self.quality_buffer.append(raw_row)
            self.feature_buffer.append(feature_row)
            self.total_samples += 1
            if len(self.feature_buffer) < self.window_samples:
                continue
            if self.total_samples - self.last_update_sample < self.update_samples:
                continue
            self.last_update_sample = self.total_samples
            frame = self.engine.update(np.asarray(self.feature_buffer), np.asarray(self.quality_buffer))
            if frame.normalized:
                self.sender.send(frame.normalized)
            self.frames.append(frame)
            if timestamps is not None and row_index < len(timestamps):
                self.frame_times.append(float(timestamps[row_index]))
            else:
                self.frame_times.append(self.total_samples / self.sample_rate)
            if self.diagnostics:
                self._print_status(frame)


def synthetic_controls(elapsed_seconds):
    """Connection-test controls; these are not presented as simulated EEG."""
    controls = {}
    periods = {"energy": 8.0, "centroid": 11.0, "mobility": 6.0}
    descriptor_phase = {"energy": 0.0, "centroid": 1.7, "mobility": 3.1}
    for channel in range(1, 7):
        channel_phase = (channel - 1) * 2.0 * np.pi / 6.0
        for descriptor in DESCRIPTORS:
            angle = 2.0 * np.pi * elapsed_seconds / periods[descriptor]
            value = 0.5 + 0.45 * np.sin(angle + channel_phase + descriptor_phase[descriptor])
            controls[f"eeg{channel}_{descriptor}"] = float(np.clip(value, 0.05, 0.95))
    return controls


def format_diagnostic(controls):
    groups = []
    for index, label in enumerate(CHANNELS, 1):
        groups.append(f"{label}  E={controls[f'eeg{index}_energy']:.2f} "
                      f"C={controls[f'eeg{index}_centroid']:.2f} "
                      f"M={controls[f'eeg{index}_mobility']:.2f}")
    return " | ".join(groups)


def run_synthetic_tidal(sender, update_rate=4.0, max_updates=None):
    """Continuously send phase-offset connection-test sweeps until interrupted."""
    interval = 1.0 / update_rate
    started = next_deadline = time.monotonic()
    updates = 0
    last_printed_second = -1
    while max_updates is None or updates < max_updates:
        now = time.monotonic()
        controls = synthetic_controls(now - started)
        sender.send(controls)
        second = int(now - started)
        if second != last_printed_second:
            print(format_diagnostic(controls))
            last_printed_second = second
        updates += 1
        next_deadline += interval
        time.sleep(max(0.0, next_deadline - time.monotonic()))


def run_tidal_live(args, sender):
    # Keep synthetic connection testing independent of pylsl and EEG hardware.
    from .window_engine import connect_openbci_lsl

    print("Searching for one 8-channel OpenBCI TimeSeriesRaw EEG stream...")
    inlet, stream, sample_rate = connect_openbci_lsl()
    print(f"Connected: {stream.name()} | 8 channels | {sample_rate:g} Hz")
    session = ControlSession(sample_rate, args.update_rate, args.calibration_seconds,
                             sender, args.window_seconds, args.analysis_low,
                             args.analysis_high, args.smoothing_seconds)
    max_samples = max(1, int(round(sample_rate / args.update_rate)))
    while True:
        chunk, timestamps = inlet.pull_chunk(timeout=1.0, max_samples=max_samples)
        if chunk:
            session.add_chunk(chunk, timestamps)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("synthetic-tidal", "tidal-live"))
    parser.add_argument("--update-rate", type=float, default=4.0)
    parser.add_argument("--window-seconds", type=float, default=2.0)
    parser.add_argument("--calibration-seconds", "--baseline-seconds", dest="calibration_seconds", type=float, default=20.0)
    parser.add_argument("--analysis-low", type=float, default=4.0)
    parser.add_argument("--analysis-high", type=float, default=40.0)
    parser.add_argument("--smoothing-seconds", type=float, default=0.5)
    parser.add_argument("--osc-host", default="127.0.0.1")
    parser.add_argument("--osc-port", type=int, default=6010)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if min(args.update_rate, args.window_seconds, args.calibration_seconds) <= 0:
        raise SystemExit("window, update rate, and calibration duration must be positive")
    sender = TidalControlOscSender(args.osc_host, args.osc_port)
    try:
        if args.mode == "synthetic-tidal":
            print("Synthetic Tidal connection test (not EEG validation). Press Ctrl+C to stop.")
            run_synthetic_tidal(sender, args.update_rate)
        else:
            run_tidal_live(args, sender)
    except KeyboardInterrupt:
        print(f"\nStopped. Sent {sender.packet_count} OSC packets to {sender.host}:{sender.port}.")
    except RuntimeError as exc:
        raise SystemExit(f"Live LSL stream failed: {exc}") from exc
    finally:
        sender.close()


if __name__ == "__main__":
    main()
