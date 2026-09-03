# Harmonic instrument preset auditions

These three files are direct `scsynth` non-realtime renders from the same continuous SynthDef used by the manual instrument. Each is 56 seconds, 48 kHz, stereo, and 24-bit PCM. No live EEG, LSL, OSC control frame, FieldTrip buffer, or Redis process was involved.

The character descriptions below are design targets, not claims that Codex listened to or selected a preferred preset.

| File | Intended character | Fundamental | Base groups | Group trims | Roll-off |
|---|---|---:|---|---|---:|
| `01_warm_organic.wav` | Warm, deep, soft, grounded | 65.41 Hz | 1.00 / 0.72 / 0.30 / 0.10 | 1.00 / 0.94 / 0.80 / 0.70 | 0.56 |
| `02_air_glass.wav` | Bright, spacious, glassy but restrained | 82.41 Hz | 0.82 / 0.88 / 0.60 / 0.34 | 0.92 / 1.00 / 1.02 / 0.94 | 0.38 |
| `03_dark_mineral.wav` | Dark, weighty, subtly metallic, low-mid controlled | 58.27 Hz | 1.00 / 0.48 / 0.32 / 0.16 | 1.00 / 0.82 / 1.08 / 0.96 | 0.50 |

| Preset | Width | Saturation | Delay mix | Reverb mix / time / damping |
|---|---:|---:|---:|---|
| `warm_organic` | 0.58 | 1.35 | 0.018 | 0.30 / 6.4 s / 0.72 |
| `air_glass` | 0.84 | 1.12 | 0.040 | 0.34 / 7.2 s / 0.60 |
| `dark_mineral` | 0.66 | 1.50 | 0.085 | 0.27 / 5.7 s / 0.48 |

All use 12 exact harmonics and a fixed, feedback-free 23/31 ms stereo delay. Full parameters, including pan positions, loudness calibration, smoothing, energy curve, room, early/tail levels, trim, limiter, attack, and release, are centralized in `sound/eeg_harmonics_manual_config.scd`.

## Identical timeline

```text
00-04  preset base full mix
04-07  master low
07-10  master high
10-14  master low
14-18  warm redistribution
18-22  bright redistribution
22-26  warm redistribution
26-30  group 1 solo
30-34  group 2 solo
34-38  group 3 solo
38-42  group 4 solo
42-48  preset base full mix
48-56  release and reverb tail
```

## Objective render QA

The A-weighted figures are engineering proxies only, not listening judgments.

| Preset | Peak | Master high-low | Low return error | Warm/bright level spread | Solo-group level spread | Solo-group centroid range |
|---|---:|---:|---:|---:|---:|---:|
| `warm_organic` | -5.82 dBFS | 13.99 dB | 0.07 dB | 0.30 dB | 0.44 dB | 108-714 Hz |
| `air_glass` | -11.66 dBFS | 14.92 dB | 1.26 dB | 0.45 dB | 0.25 dB | 137-860 Hz |
| `dark_mineral` | -5.17 dBFS | 12.51 dB | 0.04 dB | 0.55 dB | 0.55 dB | 94-630 Hz |

No file reaches the limiter ceiling or clips. Warm-to-bright centroid ratios are 4.88, 4.81, and 5.55 respectively while the proxy level remains within 0.55 dB. Base-mix return differs from the opening by at most 0.18 dB.
