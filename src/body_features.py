# ch7 as continuous EOG activity, using the latest 2 seconds at 0.5–10 Hz.
# ch8 as faster EMG activity, using the latest 250 ms at 20–90 Hz with a 50 Hz notch.

import numpy as np
from scipy.signal import (
    butter,
    filtfilt,
    iirnotch,
    sosfiltfilt,
)


EOG_WINDOW_SECONDS = 2.0
EMG_WINDOW_SECONDS = 0.25


def _rms(signal):
    return float(np.sqrt(np.mean(signal**2)))


def _bandpass(signal, sample_rate, low_hz, high_hz):
    signal = np.asarray(signal, dtype=float)
    signal = signal - np.mean(signal)

    filter_sections = butter(
        4,
        [low_hz, high_hz],
        btype="bandpass",
        fs=sample_rate,
        output="sos",
    )

    return sosfiltfilt(filter_sections, signal)


def extract_body_features(window, sample_rate):
    """
    Extract continuous EOG and EMG activity descriptors.

    Expected channel layout:
    CH1–CH6: EEG
    CH7: EOG
    CH8: EMG
    """

    if window.ndim != 2 or window.shape[1] < 8:
        raise ValueError(
            "Expected data shaped (samples, at least 8 channels)."
        )

    eog_samples = int(
        sample_rate * EOG_WINDOW_SECONDS
    )
    emg_samples = int(
        sample_rate * EMG_WINDOW_SECONDS
    )

    if window.shape[0] < eog_samples:
        raise ValueError(
            "The rolling window is too short for EOG processing."
        )

    # Python column 6 corresponds to hardware CH7.
    eog_signal = window[-eog_samples:, 6]

    # Python column 7 corresponds to hardware CH8.
    emg_signal = window[-emg_samples:, 7]

    eog_filtered = _bandpass(
        eog_signal,
        sample_rate,
        low_hz=0.5,
        high_hz=10.0,
    )

    # Remove 50 Hz electrical interference before
    # measuring 20–90 Hz muscular activity.
    if 50.0 < sample_rate / 2:
        notch_b, notch_a = iirnotch(
            50.0,
            Q=30.0,
            fs=sample_rate,
        )

        emg_signal = filtfilt(
            notch_b,
            notch_a,
            emg_signal,
        )

    emg_filtered = _bandpass(
        emg_signal,
        sample_rate,
        low_hz=20.0,
        high_hz=90.0,
    )

    return {
        "eog_activity": _rms(eog_filtered),
        "emg_activity": _rms(emg_filtered),
    }