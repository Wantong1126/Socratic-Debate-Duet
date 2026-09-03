from pathlib import Path
import unittest
import wave

import numpy as np
from scipy.io import wavfile


ROOT = Path(__file__).resolve().parents[1]
RECORDINGS = ROOT / "recordings" / "eeg_harmonics_manual"
PRESET_RECORDINGS = ROOT / "recordings" / "eeg_harmonic_presets"


def _segment_metrics(filename, start, end, directory=RECORDINGS):
    sample_rate, raw = wavfile.read(directory / filename)
    # scipy left-justifies 24-bit PCM in int32.
    audio = raw.astype(np.float64) / (2**31)
    segment = audio[int(start * sample_rate) : int(end * sample_rate)]
    mono = segment.mean(axis=1)
    window = np.hanning(mono.size)
    spectrum = np.fft.rfft(mono * window)
    frequencies = np.fft.rfftfreq(mono.size, 1 / sample_rate)
    power = np.abs(spectrum) ** 2

    f2 = frequencies**2
    numerator = 12194**2 * f2**2
    denominator = (
        (f2 + 20.6**2)
        * np.sqrt((f2 + 107.7**2) * (f2 + 737.9**2))
        * (f2 + 12194**2)
    )
    response = np.divide(
        numerator,
        denominator,
        out=np.zeros_like(frequencies),
        where=denominator > 0,
    ) * 10 ** (2 / 20)
    a_power = np.sum(power * response**2) / (np.sum(window**2) * window.size)
    a_level = 10 * np.log10(a_power + 1e-30)
    centroid = np.sum(frequencies * power) / np.sum(power)
    return a_level, centroid


def test_manual_engine_is_disconnected_and_has_no_autonomous_articulation():
    core = (ROOT / "sound" / "eeg_harmonic_field_core.scd").read_text()
    manual = (ROOT / "sound" / "eeg_harmonics_manual.scd").read_text()
    executable = core + manual

    assert "OSCdef(" not in executable
    assert "'/eeg/organism/frame'" not in executable
    assert "s.quit" not in executable
    assert manual.count("Synth.tail(") == 1
    for forbidden in (
        "Impulse.",
        "Dust.",
        "LFNoise",
        "LFPulse",
        "Pulse.ar",
        "SinOsc.kr",
        "Demand.",
        "TDuty.",
        "LocalIn.",
        "CombN.",
        "CombL.",
        "CombC.",
    ):
        assert forbidden not in executable


def test_three_centralized_presets_are_available_without_live_mapping():
    config = (ROOT / "sound" / "eeg_harmonics_manual_config.scd").read_text()
    support = (ROOT / "sound" / "eeg_harmonics_preset_support.scd").read_text()
    manual = (ROOT / "sound" / "eeg_harmonics_manual.scd").read_text()

    for name in ("warm_organic", "air_glass", "dark_mineral"):
        assert f"{name}: (" in config
    for parameter in (
        "fundamental", "harmonicCount", "baseGroups", "groupTrims",
        "groupLoudnessComp", "harmonicRollOff", "panPositions",
        "stereoWidth", "saturationDrive", "delayMix", "reverbMix",
        "reverbTime", "reverbDamping", "limiterDb",
    ):
        assert f"{parameter}:" in config
    assert "setPreset" in manual
    assert "groupLoudnessComp" in support


def test_all_six_recordings_are_stereo_48k_24bit_with_headroom():
    files = sorted(RECORDINGS.glob("*.wav"))
    assert len(files) == 6
    for path in files:
        with wave.open(str(path), "rb") as recording:
            assert recording.getnchannels() == 2
            assert recording.getframerate() == 48000
            assert recording.getsampwidth() == 3
            assert recording.getnframes() >= 5 * 48000
        _, raw = wavfile.read(path)
        peak = np.max(np.abs(raw.astype(np.float64) / (2**31)))
        assert 0.01 < peak < 0.85


def test_master_energy_changes_level_without_material_spectral_change():
    filename = "01_master_energy_loudness_only.wav"
    low_start = _segment_metrics(filename, 1.6, 2.5)
    high = _segment_metrics(filename, 4.8, 5.7)
    low_return = _segment_metrics(filename, 10.3, 11.2)

    assert high[0] - low_start[0] > 15
    assert abs(low_return[0] - low_start[0]) < 1
    assert abs(high[1] - low_start[1]) / low_start[1] < 0.08
    assert abs(low_return[1] - low_start[1]) / low_start[1] < 0.08


def test_redistribution_changes_brightness_at_approximately_constant_loudness():
    filename = "02_warm_to_bright_constant_loudness.wav"
    warm_start = _segment_metrics(filename, 1.6, 2.5)
    bright = _segment_metrics(filename, 4.8, 5.7)
    warm_return = _segment_metrics(filename, 7.5, 8.4)

    levels = [warm_start[0], bright[0], warm_return[0]]
    assert max(levels) - min(levels) < 1.8
    assert bright[1] > warm_start[1] * 3.5
    assert abs(warm_return[1] - warm_start[1]) / warm_start[1] < 0.1


def test_isolated_groups_have_distinct_ordered_spectral_contributions():
    filenames = (
        "03_group_1_foundation.wav",
        "04_group_2_body.wav",
        "05_group_3_presence.wav",
        "06_group_4_air.wav",
    )
    metrics = [_segment_metrics(name, 2.0, 4.5) for name in filenames]
    levels = [item[0] for item in metrics]
    centroids = [item[1] for item in metrics]

    assert max(levels) - min(levels) < 2.5
    assert centroids == sorted(centroids)
    assert all(right - left > 150 for left, right in zip(centroids, centroids[1:]))


def test_preset_auditions_share_format_duration_headroom_and_sequence_behavior():
    files = sorted(PRESET_RECORDINGS.glob("*.wav"))
    assert [path.name for path in files] == [
        "01_warm_organic.wav", "02_air_glass.wav", "03_dark_mineral.wav"
    ]
    frame_counts = []
    for path in files:
        with wave.open(str(path), "rb") as recording:
            assert recording.getnchannels() == 2
            assert recording.getframerate() == 48000
            assert recording.getsampwidth() == 3
            frame_counts.append(recording.getnframes())
        _, raw = wavfile.read(path)
        peak = np.max(np.abs(raw.astype(np.float64) / (2**31)))
        assert 0.01 < peak < 0.85
    assert len(set(frame_counts)) == 1
    assert abs(frame_counts[0] / 48000 - 56) < 0.01

    for path in files:
        filename = path.name
        low_start = _segment_metrics(filename, 5.5, 6.5, PRESET_RECORDINGS)
        high = _segment_metrics(filename, 8.5, 9.5, PRESET_RECORDINGS)
        low_return = _segment_metrics(filename, 12.4, 13.4, PRESET_RECORDINGS)
        assert high[0] - low_start[0] > 10
        assert abs(low_return[0] - low_start[0]) < 1.5

        warm_start = _segment_metrics(filename, 16.5, 17.5, PRESET_RECORDINGS)
        bright = _segment_metrics(filename, 20.5, 21.5, PRESET_RECORDINGS)
        warm_return = _segment_metrics(filename, 24.5, 25.5, PRESET_RECORDINGS)
        levels = [warm_start[0], bright[0], warm_return[0]]
        assert max(levels) - min(levels) < 0.7
        assert bright[1] / warm_start[1] > 4

        groups = [
            _segment_metrics(filename, start, start + 1, PRESET_RECORDINGS)
            for start in (28.5, 32.5, 36.5, 40.5)
        ]
        group_levels = [item[0] for item in groups]
        group_centroids = [item[1] for item in groups]
        assert max(group_levels) - min(group_levels) < 0.7
        assert group_centroids == sorted(group_centroids)

        base = _segment_metrics(filename, 2.2, 3.5, PRESET_RECORDINGS)
        base_return = _segment_metrics(filename, 44.5, 47.0, PRESET_RECORDINGS)
        assert abs(base_return[0] - base[0]) < 0.3


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            suite.addTest(unittest.FunctionTestCase(value, description=name))
    return suite
