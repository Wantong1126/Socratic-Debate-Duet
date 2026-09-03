# Isolated manual-audition renders

These files were rendered at 48 kHz, stereo, 24-bit PCM by `scsynth` in non-realtime mode from the same `eegManualHarmonicField` SynthDef used for manual audition. No live EEG, LSL input, Python control frames, FieldTrip buffer or Redis process was involved.

| File | Demonstration |
|---|---|
| `01_master_energy_loudness_only.wav` | Fixed spectrum; low -> high -> low master energy |
| `02_warm_to_bright_constant_loudness.wav` | Low-group -> high-group -> low-group redistribution |
| `03_group_1_foundation.wav` | Harmonics 1-3 only |
| `04_group_2_body.wav` | Harmonics 4-6 only |
| `05_group_3_presence.wav` | Harmonics 7-9 only |
| `06_group_4_air.wav` | Harmonics 10-12 only |

Automated analysis uses an A-weighted spectral-energy proxy; it is supporting evidence, not a substitute for palette approval by listening.

| Test/plateau | A-weighted proxy | Spectral centroid |
|---|---:|---:|
| Master low (opening) | -46.71 dB | 108.3 Hz |
| Master high | -28.87 dB | 112.3 Hz |
| Master low (return) | -46.35 dB | 114.3 Hz |
| Redistribution warm (opening) | -34.64 dB | 105.1 Hz |
| Redistribution bright | -35.55 dB | 514.0 Hz |
| Redistribution warm (return) | -34.21 dB | 107.6 Hz |
| Group 1 | -34.17 dB | 110.2 Hz |
| Group 2 | -34.63 dB | 377.4 Hz |
| Group 3 | -33.85 dB | 600.2 Hz |
| Group 4 | -35.88 dB | 838.8 Hz |

The warm/bright sweep spans 408.9 Hz of measured centroid while remaining within 1.34 dB across its three plateaus. Isolated group centroids are strictly ordered and their proxy levels span 2.03 dB. The full-file maximum peak is 0.7634 (-2.34 dBFS), below the -1.5 dB safety limiter ceiling.
