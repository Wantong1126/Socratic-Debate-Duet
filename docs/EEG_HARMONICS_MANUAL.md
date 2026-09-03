# Disconnected EEGsynth-inspired Harmonics palette

This is a manual-audition prototype for one continuous additive harmonic field. It preserves the project's LSL -> Python -> OSC -> persistent SuperCollider architecture, but deliberately does **not** connect the six EEG channels. The historical production engine, OSC addresses, Python transport, configuration and Tidal files remain unchanged.

## Attribution and adaptation boundary

The musical principle is adapted, with attribution, from Stephen Whitmarsh and the EEGsynth project:

- [EEG harmonics and rat intracellular recordings (2019)](https://www.eegsynth.org/?p=1986) describes decomposing EEG into delta, theta, alpha and beta, normalizing and smoothing those bands, and using each band to control different harmonic overtones.
- [Confinement diary #1: updating Harmonics patch (2020)](https://www.eegsynth.org/?p=2066) summarizes the patch as mapping EEG frequency bands to harmonics added on one oscillator, with reverb, and discusses switching mappings only at low levels to reduce clicks.
- The official [EEGsynth repository](https://github.com/eegsynth/eegsynth) and its `spectral` module compute configurable band magnitudes from detrended, Hann-tapered FFT windows. The official `patches/akusmata` configuration normalizes delta/theta/alpha/beta, smooths them with the slew limiter and sends them as separate hardware control channels to a Verbos Harmonic Oscillator.

Only this high-level musical relationship is adapted: **four independently smoothed control values redistribute energy among harmonic overtones of one fundamental**. No EEGsynth Python is copied or executed, and this project does not import its runtime, FieldTrip buffer or Redis.

The following are independent design work, not exact EEGsynth reproduction:

- SuperCollider sine-bank implementation of the hardware harmonic oscillator;
- selectable 8/12-partial grouping and the exact group boundaries;
- `1/sqrt(harmonic)` base voicing;
- inverse A-weighting approximation, perceptual L2 normalization and measured fixed group trims;
- dB master-energy law, smoothing times and saturation;
- fixed alternating stereo placement;
- GVerb settings, output trim, limiter and all audition trajectories.

The articles and official patch do not prescribe these DSP formulas, a fundamental pitch, stereo image, saturation, loudness compensation or reverb algorithm. This prototype should therefore be described as **EEGsynth Harmonics-inspired**, not a port or reproduction.

## Synthesis components

1. **One fundamental and one continuous field.** Twelve phase-stable sine partials use exact integer multiples of the configurable fundamental (73.42 Hz / D2 by default). `harmonicCount` selects 8 or 12. There are no envelopes retriggering notes, clocks, impulses, random UGens, LFOs, detuning or delayed voice copies.
2. **Four independent groups.** In 12-partial mode the groups are harmonics 1-3, 4-6, 7-9 and 10-12. In 8-partial mode they are 1-2, 3-4, 5-6 and 7-8. Each amplitude is independently exposed as `group1` through `group4`.
3. **Approximate constant perceived loudness.** Group values first scale a gentle `1/sqrt(n)` voicing. Their perceptual-domain vector is divided by its Euclidean norm before synthesis, so moving energy between groups does not simply add gain. A capped inverse A-weighting approximation compensates part of the ear's reduced low-frequency sensitivity. Small fixed trims (0.95, 1.10, 0.80 and 1.18) compensate measured group differences after saturation and reverb. It is an engineering approximation, not a psychoacoustic guarantee; listening approval remains the deciding test.
4. **Master energy.** `masterEnergy` is applied only after the normalized spectrum and maps 0..1 to -38..-15 dB. It cannot change fundamental, harmonic ratios, group weights, stereo position or reverb settings.
5. **Smoothing.** Curved `VarLag` smoothing (1.25 seconds for groups, 0.9 seconds for master energy by default) prevents clicks and abrupt spectral switching.
6. **Restrained saturation and safety.** A low-drive symmetric `tanh` stage catches additive peaks. A final -1.5 dB limiter is a safety ceiling, not a loudness effect.
7. **Stereo width without flutter.** Each exact harmonic has one fixed pan location. Width scales those positions toward or away from centre. There is no pitch offset, chorus, phase modulation or moving pan.
8. **Reverb.** Fixed GVerb settings add a diffuse stereo room. Reverb is not assigned to master energy or any harmonic group.

## Manual audition

Start the existing SuperDirt/scsynth setup, open `sound/eeg_harmonics_manual.scd`, and evaluate its single block. It never boots or reboots the server. It creates one dedicated group and one persistent synth, registers no live EEG OSC endpoint, and coexists with the existing server.

Run one demonstration at a time in the SuperCollider IDE:

```supercollider
~eegHarmonicsManual[\sweepMaster].value;      // loudness only
~eegHarmonicsManual[\sweepBrightness].value;  // warm -> bright -> warm
~eegHarmonicsManual[\sweepGroups].value;      // groups 1, 2, 3, 4
~eegHarmonicsManual[\auditionGroup].value(1); // isolate any group, 1..4
~eegHarmonicsManual[\setGroups].value(1, 0.7, 0.34, 0.16);
~eegHarmonicsManual[\setEnergy].value(0.72);
```

Edit `sound/eeg_harmonics_manual_config.scd` for the fundamental, 8/12-partial choice, group levels, smoothing, width, saturation, space and trim. Re-evaluate the manual file after editing. Stop gracefully with:

```supercollider
~eegHarmonicsManual[\stop].value;
```

## Offline isolated recordings

The renderer uses scsynth non-realtime mode and the exact same SynthDef/config as manual audition. It neither uses an audio input device nor starts the live EEG pipeline:

```powershell
.\scripts\render_eeg_harmonics_manual.ps1
```

If `sclang` is not on `PATH`, pass `-SclangPath`. Six 48 kHz, stereo, 24-bit WAV files are written to `recordings/eeg_harmonics_manual`: master-energy sweep, warm/bright redistribution sweep, and one isolated recording for each group.

## Approval gate

No mapping from F3, F4, C3, C4, P3 or P4 has been added. The prototype has no `/eeg/organism/frame` handler. Any live mapping requires a separate, explicit palette approval and a later integration step.
