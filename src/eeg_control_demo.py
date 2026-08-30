"""Stream six EEG channels as calibrated controls to Tidal or SuperCollider."""

import argparse
from collections import deque
from functools import partial
import time

import numpy as np

from .eeg_control_features import (CHANNELS, DESCRIPTORS, EEGControlFeatureEngine,
                                   control_names)
from .eeg_preprocessing import EEGFilterConfig, StreamingEEGPreprocessor
from .organism_osc import (DEFAULT_CONFIG_PATH, OrganismOscSender,
                           load_sonification_config)
from .tidal_osc import TidalControlOscSender

DEFAULT_CONTROL_HZ = 2.0
MAX_CONTROL_HZ = 4.0
CONTROLS_PER_FRAME = 18


class RateLimitedControlTransmitter:
    """Keep only the newest frame and send without deadline catch-up bursts."""

    def __init__(self, sender, control_hz=DEFAULT_CONTROL_HZ, clock=time.monotonic):
        if not 0 < control_hz <= MAX_CONTROL_HZ:
            raise ValueError(f"control_hz must be in (0, {MAX_CONTROL_HZ:g}]")
        self.sender = sender
        self.control_hz = float(control_hz)
        self.interval = 1.0 / self.control_hz
        self.clock = clock
        self.next_deadline = None
        self.latest = None
        self.frames_sent = 0
        self.first_sent_at = None
        self.first_packet_count = 0

    def offer(self, controls):
        if tuple(controls) != control_names():
            raise ValueError("A control frame must contain the 18 canonical EEG controls in order.")
        values = {name: float(value) for name, value in controls.items()}
        if not all(np.isfinite(value) and 0.0 <= value <= 1.0 for value in values.values()):
            raise ValueError("All control values must be finite and within [0,1].")
        self.latest = values

    def maybe_send(self, now=None):
        if self.latest is None:
            return False
        now = self.clock() if now is None else float(now)
        if self.next_deadline is not None and now < self.next_deadline:
            return False
        self.sender.send(self.latest)
        self.frames_sent += 1
        completed_at = self.clock()
        if self.first_sent_at is None:
            self.first_sent_at = completed_at
            self.first_packet_count = self.sender.packet_count
        # Base the next deadline on completion, not the old schedule. A late
        # iteration therefore drops missed frames and can never catch up in a burst.
        self.next_deadline = completed_at + self.interval
        return True

    def seconds_until_deadline(self):
        if self.next_deadline is None:
            return 0.0
        return max(0.0, self.next_deadline - self.clock())

    def rate_snapshot(self):
        if self.frames_sent < 2 or self.first_sent_at is None:
            return 0.0, 0.0
        elapsed = max(self.clock() - self.first_sent_at, np.finfo(float).eps)
        return ((self.frames_sent - 1) / elapsed,
                (self.sender.packet_count - self.first_packet_count) / elapsed)

    @property
    def total_controls_sent(self):
        return self.sender.packet_count

    @property
    def total_packets_sent(self):
        return self.sender.packet_count


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
                 smoothing_seconds=0.5, diagnostics=True,
                 control_hz=DEFAULT_CONTROL_HZ, clock=time.monotonic):
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
        self.transmitter = RateLimitedControlTransmitter(sender, control_hz, clock)
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
        frame_rate, message_rate = self.transmitter.rate_snapshot()
        print(" | ".join(groups) +
              f" | RATE frames/sec={frame_rate:.2f} OSC messages/sec={message_rate:.2f} "
              f"total OSC packets sent={self.transmitter.total_packets_sent}")

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
        last_frame = None
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
                self.transmitter.offer(frame.normalized)
            self.frames.append(frame)
            last_frame = frame
            if timestamps is not None and row_index < len(timestamps):
                self.frame_times.append(float(timestamps[row_index]))
            else:
                self.frame_times.append(self.total_samples / self.sample_rate)
        # One large LSL chunk may contain several descriptor frames. Only the
        # newest is retained, and at most one bounded transmission occurs here.
        self.transmitter.maybe_send()
        if self.diagnostics and last_frame is not None:
            self._print_status(last_frame)


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


def synthetic_organism_controls(elapsed_seconds, sweep_descriptor="all", sweep_channel="all"):
    """Connection-test frame that can isolate exactly one descriptor and channel.

    Non-selected controls stay at 0.5. Use, for example, ``energy`` and ``F3``
    to prove that only F3 presence changes while every other mapping stays fixed.
    """
    valid_descriptors = (*DESCRIPTORS, "all")
    valid_channels = (*CHANNELS, "all")
    if sweep_descriptor not in valid_descriptors:
        raise ValueError(f"sweep_descriptor must be one of {valid_descriptors}")
    if sweep_channel not in valid_channels:
        raise ValueError(f"sweep_channel must be one of {valid_channels}")
    if sweep_descriptor == "all" and sweep_channel == "all":
        return synthetic_controls(elapsed_seconds)

    controls = {name: 0.5 for name in control_names()}
    channel_indexes = range(1, 7) if sweep_channel == "all" else (CHANNELS.index(sweep_channel) + 1,)
    descriptors = DESCRIPTORS if sweep_descriptor == "all" else (sweep_descriptor,)
    sweep = 0.5 + 0.45 * np.sin(2.0 * np.pi * elapsed_seconds / 8.0)
    for channel_index in channel_indexes:
        for descriptor in descriptors:
            controls[f"eeg{channel_index}_{descriptor}"] = float(np.clip(sweep, 0.05, 0.95))
    return controls


def format_diagnostic(controls):
    groups = []
    for index, label in enumerate(CHANNELS, 1):
        groups.append(f"{label}  E={controls[f'eeg{index}_energy']:.2f} "
                      f"C={controls[f'eeg{index}_centroid']:.2f} "
                      f"M={controls[f'eeg{index}_mobility']:.2f}")
    return " | ".join(groups)


def _run_synthetic(sender, controls_at, control_hz, max_updates=None,
                   clock=time.monotonic, sleeper=time.sleep, stop_event=None,
                   diagnostics=True):
    """Send generated frames at a bounded, non-catching-up rate."""
    transmitter = RateLimitedControlTransmitter(sender, control_hz, clock)
    started = clock()
    updates = 0
    last_printed_second = 0
    while max_updates is None or updates < max_updates:
        if stop_event is not None and stop_event.is_set():
            break
        now = clock()
        controls = controls_at(now - started)
        transmitter.offer(controls)
        if transmitter.maybe_send(now):
            updates += 1
            second = int(clock() - started)
            if diagnostics and second != last_printed_second:
                frame_rate, message_rate = transmitter.rate_snapshot()
                print(format_diagnostic(controls) +
                      f" | RATE frames/sec={frame_rate:.2f} OSC messages/sec={message_rate:.2f} "
                      f"total OSC packets sent={transmitter.total_packets_sent}")
                last_printed_second = second
        if max_updates is not None and updates >= max_updates:
            break
        # A positive sleep occurs after every send. Since maybe_send schedules
        # from completion time, a missed deadline is dropped rather than replayed.
        sleeper(transmitter.seconds_until_deadline())
    return transmitter


def run_synthetic_tidal(sender, control_hz=DEFAULT_CONTROL_HZ, max_updates=None,
                        clock=time.monotonic, sleeper=time.sleep, stop_event=None,
                        diagnostics=True):
    """Preserved Tidal connection test using its existing 18-packet frame."""
    return _run_synthetic(sender, synthetic_controls, control_hz, max_updates,
                          clock, sleeper, stop_event, diagnostics)


def run_synthetic_supercollider(sender, control_hz=MAX_CONTROL_HZ,
                                sweep_descriptor="all", sweep_channel="all",
                                max_updates=None, clock=time.monotonic,
                                sleeper=time.sleep, stop_event=None,
                                diagnostics=True):
    """Send one bounded organism packet per update, optionally as an isolated sweep."""
    controls_at = partial(synthetic_organism_controls,
                          sweep_descriptor=sweep_descriptor,
                          sweep_channel=sweep_channel)
    return _run_synthetic(sender, controls_at, control_hz, max_updates,
                          clock, sleeper, stop_event, diagnostics)


def run_live(args, sender):
    # Keep synthetic connection testing independent of pylsl and EEG hardware.
    from .window_engine import connect_openbci_lsl

    print("Searching for one 8-channel OpenBCI TimeSeriesRaw EEG stream...")
    inlet, stream, sample_rate = connect_openbci_lsl()
    print(f"Connected: {stream.name()} | 8 channels | {sample_rate:g} Hz")
    session = ControlSession(sample_rate, args.update_rate, args.calibration_seconds,
                             sender, args.window_seconds, args.analysis_low,
                             args.analysis_high, args.smoothing_seconds,
                             control_hz=args.control_hz)
    max_samples = max(1, int(round(sample_rate / args.update_rate)))
    while True:
        chunk, timestamps = inlet.pull_chunk(timeout=1.0, max_samples=max_samples)
        if chunk:
            session.add_chunk(chunk, timestamps)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=(
        "synthetic-tidal", "tidal-live", "synthetic-supercollider",
        "supercollider-live", "stop-supercollider"
    ))
    parser.add_argument("--update-rate", type=float, default=4.0)
    parser.add_argument("--control-hz", type=float,
                        help=f"OSC frames/sec (Tidal default 2; SuperCollider config default 4; maximum {MAX_CONTROL_HZ:g})")
    parser.add_argument("--window-seconds", type=float, default=2.0)
    parser.add_argument("--calibration-seconds", "--baseline-seconds", dest="calibration_seconds", type=float, default=20.0)
    parser.add_argument("--analysis-low", type=float, default=4.0)
    parser.add_argument("--analysis-high", type=float, default=40.0)
    parser.add_argument("--smoothing-seconds", type=float, default=0.5)
    parser.add_argument("--osc-host")
    parser.add_argument("--osc-port", type=int)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--sweep-descriptor", choices=(*DESCRIPTORS, "all"), default="all",
                        help="SuperCollider synthetic mode: vary only this descriptor")
    parser.add_argument("--sweep-channel", choices=(*CHANNELS, "all"), default="all",
                        help="SuperCollider synthetic mode: vary only this channel")
    args = parser.parse_args(argv)
    if "supercollider" in args.mode:
        config = load_sonification_config(args.config)
        args.control_hz = (float(config["stream"]["control_hz"])
                           if args.control_hz is None else args.control_hz)
        args.osc_host = config["osc"]["host"] if args.osc_host is None else args.osc_host
        args.osc_port = int(config["osc"]["port"]) if args.osc_port is None else args.osc_port
    else:
        args.control_hz = DEFAULT_CONTROL_HZ if args.control_hz is None else args.control_hz
        args.osc_host = "127.0.0.1" if args.osc_host is None else args.osc_host
        args.osc_port = 6010 if args.osc_port is None else args.osc_port
    return args


def main(argv=None):
    args = parse_args(argv)
    if min(args.update_rate, args.control_hz, args.window_seconds, args.calibration_seconds) <= 0:
        raise SystemExit("window, update rate, control rate, and calibration duration must be positive")
    if args.control_hz > MAX_CONTROL_HZ:
        print(f"Clamping --control-hz {args.control_hz:g} to safe maximum {MAX_CONTROL_HZ:g}.")
        args.control_hz = MAX_CONTROL_HZ
    is_supercollider = "supercollider" in args.mode
    config = load_sonification_config(args.config) if is_supercollider else None
    if is_supercollider:
        osc = config["osc"]
        sender = OrganismOscSender(
            args.osc_host, args.osc_port,
            frame_address=osc["frame_address"], config_address=osc["config_address"],
            stop_address=osc["stop_address"]
        )
    else:
        sender = TidalControlOscSender(args.osc_host, args.osc_port)
    try:
        if args.mode == "stop-supercollider":
            sender.send_stop()
            print(f"Sent graceful stop to SuperCollider at {sender.host}:{sender.port}.")
        elif args.mode == "synthetic-tidal":
            print("Synthetic Tidal connection test (not EEG validation). Press Ctrl+C to stop.")
            run_synthetic_tidal(sender, args.control_hz)
        elif args.mode == "synthetic-supercollider":
            sender.send_config(config)
            print("Synthetic SuperCollider organism test (not EEG validation). Press Ctrl+C to stop.")
            print(f"Sweep descriptor={args.sweep_descriptor}, channel={args.sweep_channel}")
            run_synthetic_supercollider(sender, args.control_hz, args.sweep_descriptor,
                                        args.sweep_channel)
        else:
            if is_supercollider:
                sender.send_config(config)
            run_live(args, sender)
    except KeyboardInterrupt:
        print(f"\nStopped. Sent {sender.packet_count} OSC packets to {sender.host}:{sender.port}.")
    except RuntimeError as exc:
        raise SystemExit(f"Live LSL stream failed: {exc}") from exc
    finally:
        sender.close()


if __name__ == "__main__":
    main()
