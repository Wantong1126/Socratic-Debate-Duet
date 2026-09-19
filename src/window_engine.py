"""Live OpenBCI LSL acquisition and reusable rolling-buffer helpers."""

from collections import deque
from dataclasses import dataclass
import time
import xml.etree.ElementTree as ET

import numpy as np
from pylsl import StreamInlet, resolve_streams

try:
    from .eeg_features import relative_band_powers
    from .body_features import extract_body_features
    from .body_calibration import BodyCalibrator
    from .osc_sender import FeatureOscSender
except ImportError:
    from eeg_features import relative_band_powers
    from body_features import extract_body_features
    from body_calibration import BodyCalibrator
    from osc_sender import FeatureOscSender

WINDOW_SECONDS = 2.0
UPDATE_SECONDS = 0.25
EXPECTED_CHANNELS = 8


@dataclass
class LSLRecording:
    samples: np.ndarray
    timestamps: np.ndarray
    sample_rate: float
    stream_name: str


@dataclass(frozen=True)
class LSLStreamMetadata:
    name: str
    stream_type: str
    source_id: str
    uid: str
    hostname: str
    channel_count: int
    nominal_srate: float
    channel_labels: tuple[str, ...]
    channel_units: tuple[str, ...]
    prefiltering: str


def describe_lsl_stream(stream):
    """Extract only transport and channel metadata reported by the LSL source."""
    labels, units, prefiltering = [], [], "unknown"
    try:
        root = ET.fromstring(stream.as_xml())
        channels = root.find("./desc/channels")
        if channels is not None:
            for channel in channels.findall("channel"):
                labels.append((channel.findtext("label") or "unknown").strip())
                units.append((channel.findtext("unit") or "unknown").strip())
        prefiltering = (
            root.findtext("./desc/acquisition/prefiltering")
            or root.findtext("./desc/prefiltering")
            or "unknown"
        ).strip()
    except (AttributeError, ET.ParseError, TypeError):
        pass
    count = int(stream.channel_count())
    labels.extend("unknown" for _ in range(count-len(labels)))
    units.extend("unknown" for _ in range(count-len(units)))
    return LSLStreamMetadata(
        name=stream.name(), stream_type=stream.type(),
        source_id=stream.source_id(), uid=stream.uid(), hostname=stream.hostname(),
        channel_count=count, nominal_srate=float(stream.nominal_srate()),
        channel_labels=tuple(labels[:count]), channel_units=tuple(units[:count]),
        prefiltering=prefiltering,
    )


def list_openbci_lsl(wait_time=5.0, expected_channels=EXPECTED_CHANNELS):
    """Return every eight-channel EEG candidate; selection is a separate step."""
    return [stream for stream in resolve_streams(wait_time=wait_time)
            if stream.type().upper() == "EEG"
            and stream.channel_count() == expected_channels]


def connect_openbci_lsl(wait_time=5.0, expected_channels=EXPECTED_CHANNELS,
                        stream_name=None, source_id=None):
    """Resolve one explicitly selected eight-channel EEG stream."""
    streams = list_openbci_lsl(wait_time, expected_channels)
    if stream_name is not None:
        streams = [stream for stream in streams if stream.name() == stream_name]
    if source_id is not None:
        streams = [stream for stream in streams if stream.source_id() == source_id]
    if not streams:
        selectors = f" name={stream_name!r} source_id={source_id!r}" if stream_name or source_id else ""
        raise RuntimeError("No matching 8-channel EEG stream found." + selectors
                           + " Start OpenBCI GUI LIVE and enable Networking > LSL > Time Series.")
    if len(streams) > 1:
        choices = "; ".join(
            f"name={s.name()!r}, source_id={s.source_id()!r}, uid={s.uid()!r}"
            for s in streams
        )
        raise RuntimeError("Multiple matching streams found: " + choices
                           + ". Select one with --stream-name or --source-id.")
    stream = streams[0]
    sample_rate = float(stream.nominal_srate())
    if sample_rate <= 0:
        raise RuntimeError("The stream does not report a valid sampling rate.")
    return StreamInlet(stream, max_buflen=10), stream, sample_rate


def record_lsl_seconds(seconds, wait_time=5.0, expected_channels=EXPECTED_CHANNELS,
                       chunk_callback=None):
    """Record a fixed number of samples through the shared LSL chunk path."""
    if seconds <= 0:
        raise ValueError("seconds must be positive")
    inlet, stream, sample_rate = connect_openbci_lsl(wait_time, expected_channels)
    target = int(round(seconds * sample_rate))
    samples, timestamps = [], []
    deadline = time.monotonic() + seconds + max(10.0, wait_time)
    while len(samples) < target:
        if time.monotonic() > deadline:
            raise RuntimeError(f"LSL stream stalled after {len(samples)}/{target} samples.")
        chunk, chunk_times = inlet.pull_chunk(timeout=1.0, max_samples=min(target - len(samples), 1024))
        if chunk:
            if chunk_callback is not None:
                chunk_callback(np.asarray(chunk, dtype=float), np.asarray(chunk_times, dtype=float), sample_rate)
            samples.extend(row[:expected_channels] for row in chunk)
            timestamps.extend(chunk_times)
    return LSLRecording(np.asarray(samples, dtype=float), np.asarray(timestamps, dtype=float), sample_rate, stream.name())


def main():
    print("Searching for one 8-channel EEG stream...")
    try:
        inlet, stream, sample_rate_float = connect_openbci_lsl()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    sample_rate = int(round(sample_rate_float))
    window_samples = int(sample_rate * WINDOW_SECONDS)
    update_samples = int(sample_rate * UPDATE_SECONDS)
    print(f"Connecting to {stream.name()} | {stream.channel_count()} channels | {sample_rate} Hz")
    print(f"Rolling window: {window_samples} samples ({WINDOW_SECONDS:.1f} seconds)")
    print("Waiting for the first complete window...")
    buffer = deque(maxlen=window_samples)
    samples_since_update = 0
    body_calibrator = BodyCalibrator(20.0, UPDATE_SECONDS)
    osc_sender = FeatureOscSender(host="127.0.0.1", port=9000)
    try:
        while True:
            chunk, _ = inlet.pull_chunk(timeout=1.0, max_samples=update_samples)
            if not chunk:
                continue
            for sample in chunk:
                buffer.append(sample[:EXPECTED_CHANNELS])
            samples_since_update += len(chunk)
            if len(buffer) < window_samples or samples_since_update < update_samples:
                continue
            samples_since_update = 0
            window = np.asarray(buffer, dtype=float)
            features = relative_band_powers(window[:, :6], sample_rate)
            body = extract_body_features(window, sample_rate)
            if not body_calibrator.ready:
                body_calibrator.add(body)
                print(f"Calibrating body: {body_calibrator.progress * 100:5.1f}% | EOG_RMS={body['eog_activity']:7.2f} | EMG_RMS={body['emg_activity']:7.2f}")
                continue
            body_controls = body_calibrator.normalize(body)
            osc_sender.send(eeg_features=features, body_controls=body_controls)
            print(f"EEG={features['4_8_hz'] * 100:4.1f}/{features['8_13_hz'] * 100:4.1f}/{features['13_30_hz'] * 100:4.1f}% | EOG raw={body['eog_activity']:7.2f} control={body_controls['eog_control']:.2f} | EMG raw={body['emg_activity']:7.2f} control={body_controls['emg_control']:.2f}")
    except KeyboardInterrupt:
        print("\nWindow engine stopped.")


if __name__ == "__main__":
    main()
