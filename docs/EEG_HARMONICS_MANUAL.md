# Disconnected EEGsynth-inspired Harmonics instrument

This is a manual-palette candidate for one continuous additive harmonic field. It preserves the project's LSL -> Python -> OSC -> persistent SuperCollider architecture, but deliberately does not connect the six EEG channels. `eeg_organism_engine.scd`, its OSC addresses, Python transport, and historical recordings remain intact.

## Attribution and adaptation boundary

The high-level musical principle is adapted from Stephen Whitmarsh and EEGsynth:

- [EEG harmonics and rat intracellular recordings (2019)](https://www.eegsynth.org/?p=1986) describes normalizing and smoothing delta, theta, alpha, and beta values and using them to control different harmonic overtones.
- [Confinement diary #1: updating Harmonics patch (2020)](https://www.eegsynth.org/?p=2066) describes EEG-band-to-harmonic mapping, reverb, and reassignment of controls among harmonics.
- The official [EEGsynth repository](https://github.com/eegsynth/eegsynth) provides the referenced spectral extraction, normalization, smoothing, and routing modules.

No EEGsynth runtime, FieldTrip buffer, or Redis service is imported. The sine-bank oscillator, exact group boundaries, perceptual normalization, preset values, saturation, stereo image, delay, GVerb, and audition score are original SuperCollider design choices. They do not reproduce or claim to reproduce the Verbos Harmonic Oscillator hardware timbre.

## One persistent Synth

`sound/eeg_harmonic_field_core.scd` defines one SynthDef containing 8 or 12 exact integer harmonics of one fundamental. `sound/eeg_harmonics_manual.scd` creates exactly one dedicated Group and one persistent Synth. Preset switching sends only control updates to that Synth; it does not free or recreate the node.

There are no note triggers, impulses, random UGens, noise sources, detuning, LFOs, moving pans, feedback delay, sequencers, or autonomous routines. The only routines are finite manual demonstrations invoked by the user.

## Synthesis path

1. Four smoothed group amplitudes address harmonics 1-3, 4-6, 7-9, and 10-12. In eight-harmonic mode they address pairs.
2. Each preset's group trim and `harmonicRollOff` shape the partial vector.
3. That entire vector is L2-normalized in an approximate perceptual domain. Capped inverse A-weighting and a fixed per-group loudness calibration reduce post-effect group differences.
4. Fixed partial pan positions and `stereoWidth` create width without pitch beating or moving pan.
5. An optional fixed 23/31 ms cross-channel delay has no feedback and no modulation.
6. `masterEnergy` is applied after spectral construction, on a preset-defined dB curve. It cannot change group weights, frequencies, width, or effect parameters.
7. Restrained symmetric `tanh` saturation catches additive peaks.
8. Fixed GVerb parameters add space. A final limiter provides a safety ceiling.

All audible defaults and all audition timing values are centralized in `sound/eeg_harmonics_manual_config.scd`; the DSP file contains topology, mathematical constants, and safety bounds only.

## Manual controls

After the existing scsynth/SuperDirt server is running, evaluate `sound/eeg_harmonics_manual.scd` once.

```supercollider
~eegHarmonicsManual[\setPreset].value(\warm_organic);
~eegHarmonicsManual[\setPreset].value(\air_glass);
~eegHarmonicsManual[\setPreset].value(\dark_mineral);

~eegHarmonicsManual[\sweepMaster].value;
~eegHarmonicsManual[\sweepBrightness].value;
~eegHarmonicsManual[\sweepGroups].value;
~eegHarmonicsManual[\auditionGroup].value(1); // 1..4
~eegHarmonicsManual[\setGroups].value(1, 0.7, 0.3, 0.1);
~eegHarmonicsManual[\setEnergy].value(0.66);
~eegHarmonicsManual[\stop].value;
```

Preset switching is smoothed and retains the same Synth node. Select a preset before judging its palette; switching fundamental while sound is active necessarily produces a smoothed pitch transition.

## Comparable preset renders

```powershell
.\scripts\render_eeg_harmonic_presets.ps1
```

This writes three equal-duration, 48 kHz, stereo, 24-bit PCM WAV files under `recordings/eeg_harmonic_presets`. Each uses the same timeline: base mix; master low/high/low; warm/bright/warm redistribution; groups 1/2/3/4; base mix return. The README in that directory lists parameters, intended character, and objective QA measurements.

The earlier six isolated prototype renders and their legacy renderer remain available under `recordings/eeg_harmonics_manual`.

## Approval gate

No mapping from F3, F4, C3, C4, P3, or P4 has been added. The manual instrument has no `/eeg/organism/frame` handler. Live integration remains a later explicit step after palette approval.
