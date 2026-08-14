from collections import deque

import numpy as np
from pylsl import StreamInlet, resolve_streams

from eeg_features import relative_band_powers

WINDOW_SECONDS = 2.0
UPDATE_SECONDS = 0.25
EXPECTED_CHANNELS = 8


print("Searching for one 8-channel EEG stream...")

streams = [
    stream
    for stream in resolve_streams(wait_time=5.0)
    if stream.type() == "EEG"
    and stream.channel_count() == EXPECTED_CHANNELS
]

if len(streams) == 0:
    raise SystemExit(
        "No 8-channel EEG stream found. "
        "Start the LSL Time Series output in OpenBCI GUI."
    )

if len(streams) > 1:
    print("Multiple matching streams found:")

    for stream in streams:
        print(f"  - {stream.name()}")

    raise SystemExit(
        "Leave exactly one OpenBCI EEG output running, then try again."
    )

stream = streams[0]
sample_rate = int(round(stream.nominal_srate()))

if sample_rate <= 0:
    raise SystemExit("The stream does not report a valid sampling rate.")

window_samples = int(sample_rate * WINDOW_SECONDS)
update_samples = int(sample_rate * UPDATE_SECONDS)

print(
    f"Connecting to {stream.name()} | "
    f"{stream.channel_count()} channels | "
    f"{sample_rate} Hz"
)
print(
    f"Rolling window: {window_samples} samples "
    f"({WINDOW_SECONDS:.1f} seconds)"
)
print("Waiting for the first complete window...")

inlet = StreamInlet(stream, max_buflen=10)
buffer = deque(maxlen=window_samples)
samples_since_update = 0

try:
    while True:
        chunk, timestamps = inlet.pull_chunk(
            timeout=1.0,
            max_samples=update_samples,
        )

        if not chunk:
            continue

        for sample in chunk:
            buffer.append(sample[:EXPECTED_CHANNELS])

        samples_since_update += len(chunk)

        if len(buffer) < window_samples:
            continue

        if samples_since_update < update_samples:
            continue

        samples_since_update = 0

        window = np.asarray(buffer, dtype=float)

        # Planned montage:
        # columns 0–5 = EEG, column 6 = EOG, column 7 = EMG
        eeg_window = window[:, :6]

        # Diagnostic only: remove each channel's mean and calculate RMS.
        features = relative_band_powers(
            eeg_window,
            sample_rate,
        )

        low = features["4_8_hz"] * 100
        middle = features["8_13_hz"] * 100
        high = features["13_30_hz"] * 100

        print(
            f"t={timestamps[-1]:.3f} | "
            f"4–8 Hz={low:5.1f}% | "
            f"8–13 Hz={middle:5.1f}% | "
            f"13–30 Hz={high:5.1f}% | "
            f"sum={low + middle + high:5.1f}%"
        )

except KeyboardInterrupt:
    print("\nWindow engine stopped.")