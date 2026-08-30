"""Stream six EEG channels as calibrated controls to Tidal or SuperCollider."""

import argparse
from collections import deque
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
ISOLATED_REFERENCE = {"energy": 0.65, "centroid": 0.50, "mobility": 0.25}
ISOLATED_SWEEP_SECONDS = 16.0
FAMILY_STAGE_SECONDS = 6.0


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


def _reference_controls():
    return {
        f"eeg{channel}_{descriptor}": ISOLATED_REFERENCE[descriptor]
        for channel in range(1, 7) for descriptor in DESCRIPTORS
    }


def isolated_audition_mask(channel):
    """Return a strict one-cell mask in canonical F3..P4 order."""
    if channel not in CHANNELS:
        raise ValueError(f"channel must be one of {CHANNELS}")
    selected = CHANNELS.index(channel)
    return tuple(1.0 if index == selected else 0.0 for index in range(6))


def isolated_sweep_value(elapsed_seconds):
    """Deterministic low -> mid -> high -> mid -> low sweep."""
    phase = (float(elapsed_seconds) % ISOLATED_SWEEP_SECONDS) / ISOLATED_SWEEP_SECONDS
    return round(float(0.5 - (0.45 * np.cos(2.0 * np.pi * phase))), 12)


def isolated_sweep_stage(elapsed_seconds):
    value = isolated_sweep_value(elapsed_seconds)
    if value < 0.25:
        return "LOW"
    if value > 0.75:
        return "HIGH"
    return "MID"


def isolated_organism_controls(elapsed_seconds, descriptor, channel):
    """Hold 17 mappings fixed and sweep one descriptor on one audible cell."""
    if descriptor not in DESCRIPTORS:
        raise ValueError(f"descriptor must be one of {DESCRIPTORS}")
    if channel not in CHANNELS:
        raise ValueError(f"channel must be one of {CHANNELS}")
    controls = _reference_controls()
    channel_index = CHANNELS.index(channel) + 1
    controls[f"eeg{channel_index}_{descriptor}"] = isolated_sweep_value(elapsed_seconds)
    return controls


def full_organism_controls(elapsed_seconds):
    """Slow deterministic, offset trajectories for one sustained harmonic body."""
    elapsed = float(elapsed_seconds)
    controls = {}
    ranges = {
        "energy": (0.38, 0.76, 24.0),
        "centroid": (0.24, 0.78, 32.0),
        "mobility": (0.08, 0.62, 19.0),
    }
    descriptor_phase = {"energy": 0.0, "centroid": 1.1, "mobility": 2.3}
    for channel in range(1, 7):
        channel_phase = (channel - 1) * 0.47
        for descriptor in DESCRIPTORS:
            low, high, period = ranges[descriptor]
            unit = 0.5 + 0.5 * np.sin(
                (2.0 * np.pi * elapsed / period) + channel_phase + descriptor_phase[descriptor]
            )
            controls[f"eeg{channel}_{descriptor}"] = float(low + ((high - low) * unit))
    return controls


def family_comparison_controls(elapsed_seconds=0.0):
    """Identical descriptor references for every family comparison stage."""
    del elapsed_seconds
    return _reference_controls()


def family_comparison_stage(elapsed_seconds):
    return ("P", "C", "F")[int(float(elapsed_seconds) // FAMILY_STAGE_SECONDS) % 3]


def family_audition_mask(family):
    masks = {
        "P": (0.0, 0.0, 0.0, 0.0, 1.0, 1.0),
        "C": (0.0, 0.0, 1.0, 1.0, 0.0, 0.0),
        "F": (1.0, 1.0, 0.0, 0.0, 0.0, 0.0),
    }
    try:
        return masks[family]
    except KeyError as exc:
        raise ValueError("family must be P, C, or F") from exc


def synthetic_organism_controls(elapsed_seconds, sweep_descriptor="all", sweep_channel="all"):
    """Compatibility entry point for the full scene or a strict isolated sweep."""
    valid_descriptors = (*DESCRIPTORS, "all")
    valid_channels = (*CHANNELS, "all")
    if sweep_descriptor not in valid_descriptors:
        raise ValueError(f"sweep_descriptor must be one of {valid_descriptors}")
    if sweep_channel not in valid_channels:
        raise ValueError(f"sweep_channel must be one of {valid_channels}")
    if sweep_descriptor == "all" and sweep_channel == "all":
        return full_organism_controls(elapsed_seconds)
    if sweep_descriptor == "all" or sweep_channel == "all":
        raise ValueError("An isolated sweep requires exactly one descriptor and one channel")
    return isolated_organism_controls(elapsed_seconds, sweep_descriptor, sweep_channel)


def format_diagnostic(controls):
    groups = []
    for index, label in enumerate(CHANNELS, 1):
        groups.append(f"{label}  E={controls[f'eeg{index}_energy']:.2f} "
                      f"C={controls[f'eeg{index}_centroid']:.2f} "
                      f"M={controls[f'eeg{index}_mobility']:.2f}")
    return " | ".join(groups)


def _run_synthetic(sender, controls_at, control_hz, max_updates=None,
                   clock=time.monotonic, sleeper=time.sleep, stop_event=None,
                   diagnostics=True, stage_at=None, on_stage=None):
    """Send generated frames at a bounded, non-catching-up rate."""
    transmitter = RateLimitedControlTransmitter(sender, control_hz, clock)
    started = clock()
    updates = 0
    last_printed_second = 0
    last_stage = None
    while max_updates is None or updates < max_updates:
        if stop_event is not None and stop_event.is_set():
            break
        now = clock()
        elapsed = now - started
        if stage_at is not None:
            stage = stage_at(elapsed)
            if stage != last_stage:
                if on_stage is not None:
                    on_stage(stage)
                if diagnostics:
                    print(f"AUDITION STAGE: {stage}")
                last_stage = stage
        controls = controls_at(elapsed)
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
    """Send the full scene, or preserve the earlier API for a strict isolated sweep."""
    if sweep_descriptor != "all" or sweep_channel != "all":
        return run_isolated_supercollider(
            sender, control_hz, sweep_descriptor, sweep_channel, max_updates,
            clock, sleeper, stop_event, diagnostics
        )
    sender.send_audition_mask((1.0,) * 6)
    return _run_synthetic(sender, full_organism_controls, control_hz, max_updates,
                          clock, sleeper, stop_event, diagnostics)


def run_isolated_supercollider(sender, control_hz, descriptor, channel,
                               max_updates=None, clock=time.monotonic,
                               sleeper=time.sleep, stop_event=None,
                               diagnostics=True):
    """Mute five cells, hold two descriptors fixed, and sweep exactly one."""
    sender.send_audition_mask(isolated_audition_mask(channel))
    controls_at = lambda elapsed: isolated_organism_controls(elapsed, descriptor, channel)
    return _run_synthetic(
        sender, controls_at, control_hz, max_updates, clock, sleeper, stop_event,
        diagnostics, stage_at=isolated_sweep_stage
    )


def run_family_comparison(sender, control_hz=MAX_CONTROL_HZ, max_updates=None,
                          clock=time.monotonic, sleeper=time.sleep, stop_event=None,
                          diagnostics=True):
    """Cycle P, C, F pairs with identical descriptor values."""
    return _run_synthetic(
        sender, family_comparison_controls, control_hz, max_updates, clock,
        sleeper, stop_event, diagnostics, stage_at=family_comparison_stage,
        on_stage=lambda family: sender.send_audition_mask(family_audition_mask(family))
    )


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
        "isolated-supercollider", "family-supercollider",
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
                        help="Isolated SuperCollider mode: vary exactly this descriptor")
    parser.add_argument("--sweep-channel", choices=(*CHANNELS, "all"), default="all",
                        help="Isolated SuperCollider mode: make exactly this channel audible")
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
            audition_address=osc["audition_address"],
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
            print("Full sustained SuperCollider organism scene (not EEG validation). Press Ctrl+C to stop.")
            run_synthetic_supercollider(sender, args.control_hz)
        elif args.mode == "isolated-supercollider":
            if args.sweep_descriptor == "all" or args.sweep_channel == "all":
                raise SystemExit("isolated-supercollider requires --sweep-descriptor and --sweep-channel")
            sender.send_config(config)
            print(f"Strict isolated sweep: {args.sweep_channel} {args.sweep_descriptor}.")
            run_isolated_supercollider(sender, args.control_hz, args.sweep_descriptor,
                                       args.sweep_channel)
        elif args.mode == "family-supercollider":
            sender.send_config(config)
            print("Family comparison: P foundation -> C resonance -> F air, six seconds each.")
            run_family_comparison(sender, args.control_hz)
        else:
            if is_supercollider:
                sender.send_config(config)
                sender.send_audition_mask((1.0,) * 6)
            run_live(args, sender)
    except KeyboardInterrupt:
        print(f"\nStopped. Sent {sender.packet_count} OSC packets to {sender.host}:{sender.port}.")
    except RuntimeError as exc:
        raise SystemExit(f"Live LSL stream failed: {exc}") from exc
    finally:
        sender.close()


if __name__ == "__main__":
    main()
