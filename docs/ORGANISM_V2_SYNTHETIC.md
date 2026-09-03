# Organism v2 synthetic control transport

This phase validates only the module boundary and transport. It does not acquire
EEG and does not select pitch, scale, melody, harmony, channels, or debaters.

## File responsibilities

- `src/sonification/controls.py`: pure mapping from a validated frame to the
  currently permitted Synth controls. `energy` maps to master presence;
  delta/theta/alpha/beta map directly to harmonic groups 1-4.
- `src/sonification/protocol.py`: v2 field order, OSC addresses, finite/clamped
  frame validation, serialization, frame sender, and graceful-stop sender.
- `src/sonification/synthetic_demo.py`: finite isolated descriptor sweeps,
  isolated band sweeps, combined demo, drift-free pacing, deadline dropping,
  loop mode, and once-per-second diagnostics.
- `sound/eeg_organism_v2_receiver.scd`: owns one Group and one persistent Synth,
  receives frames, stores all nine fields, updates only existing nodes, and runs
  the watchdog.
- `config/eeg_organism_v2.scd`: v2-only response times, effects, watchdog, and
  exact harmonic-group assignments. It does not change the manual presets.
- `sound/eeg_harmonic_field_v2_core.scd`: targeted variant of the existing
  continuous additive topology with a higher exact upper bank and post-effect
  watchdog gain.
- `sound/stop_eeg_organism_v2.scd`: local graceful-stop convenience block.
- The existing `harmonics_*.py`, manual `.scd`, legacy organism, and audification
  entry points remain available unchanged.

## Data flow in plain language

The Python demo makes one nine-number snapshot, clamps every number to 0-1, and
sends that snapshot as one OSC packet. SuperCollider stores all nine numbers.
For now it uses only energy as overall presence and the four EEG-band placeholders
as the four harmonic-group controls. The other four descriptors are visible in
`~eegOrganismV2[\lastFrame]` and the post window, but do not control pitch or any
other sound parameter.

If packets stop for two seconds, the receiver's post-effect transport gain fades
to true silence in 0.5 seconds. Sending resumes the same existing Synth. No frame
creates a Synth, Group, Buffer, or Routine.

## Diagnosed causes and response settings

The former default did send 49 packets over 12 seconds at 4 Hz. Its 13 JSON lines
were once-per-second summaries, not individual packets. The old curve had no
holds, however, and the 1.6-second group lag plus 6.4-second reverb obscured its
moving endpoints. Two seconds after transport ended, the watchdog caused another
transition. Its `masterEnergy = 0` target still meant -38 dB rather than silence.

V2 audition settings are now intentionally more legible:

- group `VarLag`: 0.35 s; energy `VarLag`: 0.25 s;
- watchdog timeout/fade: 2.0/0.5 s through a post-effect `transportAlive` gain;
- reverb mix/time/damping: 0.18/3.0 s/0.68;
- saturation drive: 1.25; limiter ceiling: -1.5 dB;
- energy mapping: -40 to -18 dB before saturation and reverb;
- the wet path cannot bypass energy because energy is applied before the effects.

There is one smoothing layer per changing musical control. The separate
`transportAlive` smoothing acts only on connection safety. The Synth ASR is
0.5/2.5 seconds and is used for node start/stop, not per-frame control.

At the inherited 65.41 Hz `warm_organic` fundamental, the exact groups are:

| Control | Harmonics | Frequency range |
|---|---:|---:|
| delta / group 1 | 1, 2, 3 | 65.41-196.23 Hz |
| theta / group 2 | 4, 5, 6 | 261.64-392.46 Hz |
| alpha / group 3 | 7, 9, 12 | 457.87-784.92 Hz |
| beta / group 4 | 24, 36, 48 | 1569.84-3139.68 Hz |

The previous beta group was harmonics 10-12, only 654.10-784.92 Hz. The new
partials remain exact integer members of the same harmonic series; no noise,
detune, rhythm, random source, or new fundamental was added.

## Start and stop

1. Start SuperDirt/scsynth as usual. In the same SuperCollider IDE language
   session, evaluate exactly:

   ```supercollider
   "D:/sdd-sonification/sound/eeg_organism_v2_receiver.scd".load;
   ```

2. From PowerShell in `D:\sdd-sonification`, run a one-shot transport at the
   default four frames per second. Descriptor and band auditions last 20 seconds:
   LOW hold 4 s, rise 4 s, HIGH hold 4 s, fall 4 s, LOW hold 4 s. Each sends 81
   scheduled frames including both endpoints.

   ```powershell
   .\.venv\Scripts\python.exe -m src.sonification.synthetic_demo --mode descriptor --field energy
   .\.venv\Scripts\python.exe -m src.sonification.synthetic_demo --mode band --field delta
   .\.venv\Scripts\python.exe -m src.sonification.synthetic_demo --mode combined --duration 24
   ```

   Replace the descriptor with `energy`, `centroid`, `mobility`,
   `spectral_entropy`, or `novelty`. Replace the band with `delta`, `theta`,
   `alpha`, or `beta`. Add `--loop` to repeat the whole trajectory until Ctrl+C.
   Add `--dry-run` to generate a finite one-shot immediately without opening an
   OSC socket; `--loop` and `--dry-run` cannot be combined.

3. `Ctrl+C` stops Python; the receiver watchdog fades the instrument. To release
   the v2 receiver and its two dedicated nodes gracefully while leaving
   SuperDirt/scsynth running, use either:

   ```powershell
   .\.venv\Scripts\python.exe -m src.sonification.synthetic_demo --mode stop
   ```

   or evaluate in SuperCollider:

   ```supercollider
   "D:/sdd-sonification/sound/stop_eeg_organism_v2.scd".load;
   ```

The CLI explicitly announces ONE-SHOT or LOOP mode. About once per second its JSON
diagnostic includes sequence, actual elapsed time, latest send interval, measured
effective Hz, dropped-deadline count, and all nine ordered values. Late deadlines
are skipped; they are never emitted as a catch-up burst. The OSC contract remains
`/eeg/organism/v2/frame` with exactly nine floats in `protocol.py` order.

The SuperCollider post window reports approximately once per second:

```text
Organism v2 rx count=... interval=...s effectiveHz=... age=...s
energy=... delta=... theta=... alpha=... beta=...
```

It also reports activation, watchdog timeout, exact harmonic groups, stable node
IDs, and graceful release. Centroid, mobility, spectral entropy, and novelty are
stored but remain musically inactive.

## Offline evidence

Run:

```powershell
.\scripts\render_eeg_organism_v2_isolated.ps1
.\.venv\Scripts\python.exe .\scripts\analyze_eeg_organism_v2_isolated.py
```

This creates ten independent 48 kHz/24-bit stereo steady-state WAVs under
`recordings/eeg_organism_v2_isolated`. Objective results are recorded in that
directory's README. These measurements verify timing-independent signal and
spectral behavior; they are not a claim that a person has approved the sound.
