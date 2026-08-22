# converting an EEG window into reusable numeric features.the same calculations can later be used by live streaming, recorded sessions and ML evaluation.
import numpy as np
from scipy.signal import welch


FREQUENCY_BANDS = {
    "4_8_hz": (4.0, 8.0),
    "8_13_hz": (8.0, 13.0),
    "13_30_hz": (13.0, 30.0),
}


def clean_eeg(eeg_window):
    """Return the existing per-channel mean-centred EEG representation."""
    eeg_window = np.asarray(eeg_window, dtype=float)
    if eeg_window.ndim != 2 or eeg_window.shape[1] != 6:
        raise ValueError("Expected EEG data shaped (samples, 6 channels).")
    return eeg_window - np.mean(eeg_window, axis=0, keepdims=True)


def relative_band_powers(eeg_window, sample_rate):
    """
    Calculate mean relative power across six EEG channels.

    Parameters
    ----------
    eeg_window:
        NumPy array shaped (samples, 6 channels).
    sample_rate:
        Sampling rate in Hz.

    Returns
    -------
    Dictionary containing the proportion of total 4–30 Hz
    power located in each frequency band.
    """

    if eeg_window.ndim != 2 or eeg_window.shape[1] != 6:
        raise ValueError(
            "Expected EEG data shaped (samples, 6 channels)."
        )

    # Remove the mean of each channel through the shared cleaning path.
    centered = clean_eeg(eeg_window)

    # Use one-second segments with 50% internal overlap.
    segment_samples = min(sample_rate, centered.shape[0])

    frequencies, power_spectrum = welch(
        centered,
        fs=sample_rate,
        axis=0,
        nperseg=segment_samples,
        noverlap=segment_samples // 2,
    )

    total_mask = (
        (frequencies >= 4.0)
        & (frequencies <= 30.0)
    )

    total_power = np.sum(
        power_spectrum[total_mask],
        axis=0,
    )

    # Prevent division by zero.
    total_power = np.maximum(
        total_power,
        np.finfo(float).eps,
    )

    features = {}

    for name, (low_frequency, high_frequency) in (
        FREQUENCY_BANDS.items()
    ):
        if high_frequency == 30.0:
            band_mask = (
                (frequencies >= low_frequency)
                & (frequencies <= high_frequency)
            )
        else:
            band_mask = (
                (frequencies >= low_frequency)
                & (frequencies < high_frequency)
            )

        band_power = np.sum(
            power_spectrum[band_mask],
            axis=0,
        )

        relative_power_per_channel = (
            band_power / total_power
        )

        features[name] = float(
            np.mean(relative_power_per_channel)
        )

    return features
