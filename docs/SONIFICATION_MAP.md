# Phase 1B: sustained EEG harmonic organism

Phase 1B keeps the successful Phase 1 transport and lifecycle engineering but replaces its sound design. One debater is now a sustained atmospheric harmonic body. This is not yet the ambient-techno composition: there is no rhythm layer, EOG/EMG, second debater, relationship mapping, Tidal structure or raw-window synthesis.

## Why Phase 1 sounded like noise and pulses

The listening failure followed directly from the old sources:

- F cells mixed an always-on `PinkNoise` air source with random `LFNoise` drift.
- C cells used `Impulse` and `Decay2` to retrigger resonators continuously. Raising mobility accelerated those audible note-like attacks.
- P cells used `Dust` to trigger Brown/Pink-noise grains and sent them through tails.
- Filtering those different sources into similarly dark resonances made F, C and P converge perceptually.
- Energy, centroid and mobility all affected combinations of level, filtering, articulation or space, so their identities were not orthogonal.

Phase 1B removes those sources completely. The production engine contains no noise bed, Dust, audible Impulse trigger, sequence, random note, grain event or fixed pulse.

## Architecture and stable nodes

```text
synthetic scene or real six-channel EEG
  -> existing Python filtering/features/calibration
  -> one /eeg/organism/frame packet at 4 Hz
  -> six persistent harmonic cells in one Group
  -> one private stereo bus
  -> one fixed-space mixer, master gain and limiter
  -> stereo output summed alongside SuperDirt
```

The frame protocol and canonical order are unchanged:

```text
F3 energy, centroid, mobility, F4 energy, centroid, mobility,
C3 energy, centroid, mobility, C4 energy, centroid, mobility,
P3 energy, centroid, mobility, P4 energy, centroid, mobility
```

One frame is exactly 18 finite 0..1 floats in one `/eeg/organism/frame` packet. Configuration is sent once on `/eeg/organism/config`. Audition modes send a six-value `/eeg/organism/audition` mask that multiplies existing cell outputs; it creates or frees no nodes.

Stable expected tree: **one Group + six cell Synths + one mixer Synth = eight server nodes**. The bus is routing, not a node. Frame, config and audition callbacks use `.set` only.

## One harmonic source, three register families

Every source is a deterministic bank of four sine partials derived from the same configurable D2 fundamental, `tonal.fundamental_hz = 73.42` Hz. The assignments are artistic orchestration choices, not neurological claims.

| EEG cells | Role | Default harmonics | Frequencies at 73.42 Hz |
|---|---|---:|---:|
| P3/P4 | low foundation/body | 1, 2, 3, 4 | 73, 147, 220, 294 Hz |
| C3/C4 | middle resonance | 3, 4, 5, 6 | 220, 294, 367, 441 Hz |
| F3/F4 | upper air/shimmer | 6, 8, 10, 12 | 441, 587, 734, 881 Hz |

Odd/even partners have the same exact frequencies. They differ only in modest pan, oscillator starting phase and modulation phase; stereo does not introduce a second pitch. Each of the six incoming EEG channels still controls its own cell independently—there is no averaging.

## Orthogonal descriptor formulas

### Energy: presence only

For normalized energy `E`:

```text
level_dB = energy.minimum_db + E * (energy.maximum_db - energy.minimum_db)
amplitude = 10 ^ (level_dB / 20)
```

Defaults are -36 to -16 dB, a 20 dB span. Phase 1's 0.012..0.085 linear range was about 17 dB, so the cell-level modulation span is approximately 18% wider—close to the requested 15% increase. `energy.lag_seconds = 0.35` smooths it. Energy does not alter frequency, partial weights, motion rate, reverb or note duration.

Tune after listening:

- More/less energy contrast: lower/raise `energy.minimum_db` or raise/lower `energy.maximum_db`.
- Faster/slower response: lower/raise `energy.lag_seconds`.
- Do not use `master.level` to tune energy contrast; it changes the whole organism.

### Spectral centroid: brightness only

The cell always uses the same four frequencies. Centroid `C` only tilts their weights:

```text
tilt = centroid.tilt_min + C * (centroid.tilt_max - centroid.tilt_min)
blend = (tilt + 1) / 2
dark weights   = [1.00, 0.72, 0.30, 0.10]
bright weights = [0.28, 0.58, 0.86, 1.00]
weights = dark * (1 - blend) + bright * blend
normalized weights = weights / sqrt(sum(weights ^ 2))
```

Defaults sweep tilt from -0.85 to +0.85. Euclidean normalization keeps oscillator-bank RMS comparatively stable. A final configurable high-end correction is:

```text
compensation = 10 ^ ((C * centroid.high_compensation_db) / 20)
```

The default is -1 dB at maximum brightness. Centroid never changes pitch, event rate, duration, motion rate or reverb.

Tune after listening:

- Stronger/weaker dark-to-bright contrast: widen/narrow `centroid.tilt_min` and `centroid.tilt_max` within -1..1.
- If the bright end sounds louder/quieter: make `centroid.high_compensation_db` more negative/positive.
- Faster/slower colour response: lower/raise `centroid.lag_seconds`.

### Mobility: continuous motion only

Mobility `M` controls deterministic sine amplitude modulation:

```text
rate = rate_min * (rate_max / rate_min) ^ M
depth = depth_min + M * (depth_max - depth_min)
motion = (1 + depth * sin(2*pi*rate*time + fixed_phase))
         / sqrt(1 + depth^2 / 2)
```

Defaults are 0.08..5 Hz and depth 0.05..0.45. The denominator compensates theoretical sine-AM RMS, keeping average loudness reasonably stable. Low mobility is nearly steady, the middle breathes/undulates, and high mobility flutters. Mobility does not retrigger the source, change its harmonic weights or control reverb.

Tune after listening:

- Faster/slower maximum flutter: `mobility.rate_max_hz`.
- Slower/faster minimum breathing: `mobility.rate_min_hz`.
- More/less audible movement: `mobility.depth_min` and `mobility.depth_max`.
- Faster/slower control response: `mobility.lag_seconds`.

## Fixed space and safety

All six cells share one fixed mixer reverb. `reverb.mix`, `reverb.room` and `reverb.damping` do not receive EEG data and remain constant in isolated tests. Change these only to tune the overall space after descriptor validation.

`source.cell_level` is the pre-cell safety scale. `master.level` controls the whole organism, and `master.limiter_level` is the organism's final ceiling. Gate envelopes use `master.attack_seconds` and `master.release_seconds`; `doneAction: 2` frees synths after graceful release. The two-second watchdog uses `master.watchdog_fade_seconds` to fade the mixer but leaves node identities stable for resumed input.

## Sound source, descriptor, mapping and composition

- A **sound source** generates audio. Here it is the sustained harmonic sine bank.
- A **descriptor** is a measured EEG feature: energy, spectral centroid or mobility.
- A **mapping** is the formula connecting one descriptor to one sound property. Phase 1B maps them to amplitude, spectral tilt and continuous AM respectively.
- A **musical composition** organizes sound over larger time: rhythm, sections, tension and arrangement. That later layer is deliberately absent here; the synthetic scene is only an auditionable atmospheric source.

## Launch order

1. Start the existing SuperDirt/scsynth setup. `BootTidal.hs` is unchanged.
2. From PowerShell in `D:\sdd-sonification`, open the engine:

   ```powershell
   Invoke-Item .\sound\eeg_organism_engine.scd
   ```

3. Evaluate the single parenthesized block in the SuperCollider IDE. It never calls `s.boot` or `s.reboot`.
4. Start one Python audition mode below.

The post window should show `EEG ORGANISM PHASE 1B READY`, six fixed cell IDs, one mixer ID and an eight-node total. `input active` prints after the first frame. Node IDs must not change while controls or audition masks update.

## Exact audition commands and expected result

Full deterministic organism:

```powershell
.\scripts\start_eeg_organism.ps1 -Mode synthetic-supercollider
```

Expected: one sustained harmonic body slowly breathing, brightening and moving through offset six-channel trajectories. There should be no autonomous beat, repeated note, random note or constant noise floor.

Strict energy isolation:

```powershell
.\scripts\start_eeg_organism.ps1 -Mode isolated-supercollider -Descriptor energy -Channel P3
```

Expected: P3 alone; the same sustained low harmonic colour and motion while only loudness moves low -> mid -> high -> mid -> low.

Strict centroid isolation:

```powershell
.\scripts\start_eeg_organism.ps1 -Mode isolated-supercollider -Descriptor centroid -Channel C3
```

Expected: C3 alone; unchanged pitch, sustain and motion with a dark/rounded -> open/rich -> dark sweep at approximately stable loudness.

Strict mobility isolation:

```powershell
.\scripts\start_eeg_organism.ps1 -Mode isolated-supercollider -Descriptor mobility -Channel F3
```

Expected: F3 alone; unchanged upper harmonic colour and approximate average loudness, moving from nearly steady through slow undulation to faster flutter and back.

Python prints `AUDITION STAGE: LOW`, `MID` and `HIGH` with no marker sounds. The selected descriptor follows a deterministic 16-second low -> high -> low cycle. Other descriptor references are fixed at energy 0.65, centroid 0.50 and mobility 0.25. A one-hot audition mask completely mutes the five unselected cells.

Family comparison with identical descriptor values:

```powershell
.\scripts\start_eeg_organism.ps1 -Mode family-supercollider
```

Expected: six seconds of the P3/P4 low foundation, then C3/C4 middle resonance, then F3/F4 upper air/shimmer, repeating. Only the mask changes; all families receive energy 0.65, centroid 0.50 and mobility 0.25.

Live EEG:

```powershell
.\scripts\start_eeg_organism.ps1 -Mode supercollider-live
```

The successful Tidal MVP remains independently available with `--mode synthetic-tidal`.

## Stop

Stop foreground Python with `Ctrl+C`, then release the engine:

```powershell
.\scripts\stop_eeg_organism.ps1
```

Alternatively evaluate `sound/stop_eeg_organism.scd`. `hush` is not used and the existing SuperDirt session is not stopped.
