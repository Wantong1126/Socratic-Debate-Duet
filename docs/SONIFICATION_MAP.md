# Phase 1 EEG organism

This is a new path beside the successful Tidal MVP and the historical SuperCollider sketches. It does not modify or replace them:

```text
synthetic or real six-channel EEG
        -> Python feature/calibration path
        -> one /eeg/organism/frame packet, about 4 times/second
        -> six persistent SuperCollider cells
        -> one dedicated stereo bus and organism mixer
        -> stereo hardware output
```

## Launch order

1. Start SuperDirt/scsynth in the usual project setup. `BootTidal.hs` remains unchanged. The organism file never boots or reboots the server.
2. In PowerShell, open the engine: `Invoke-Item .\sound\eeg_organism_engine.scd`.
3. In the SuperCollider IDE, evaluate the parenthesized engine block with `Ctrl+Enter`. The post window must say `EEG ORGANISM READY on UDP 57120` and report eight stable nodes.
4. In a second PowerShell window, from `D:\sdd-sonification`, run the full synthetic texture:

   ```powershell
   .\scripts\start_eeg_organism.ps1
   ```

   For real OpenBCI LSL input after its stream is available:

   ```powershell
   .\scripts\start_eeg_organism.ps1 -Mode supercollider-live
   ```

The helper uses `.venv\Scripts\python.exe` when present, otherwise `python`. The direct equivalent is:

```powershell
.\.venv\Scripts\python.exe -m src.eeg_control_demo --mode synthetic-supercollider --config .\config\sonification.toml
```

The existing Tidal command still works independently:

```powershell
.\.venv\Scripts\python.exe -m src.eeg_control_demo --mode synthetic-tidal
```

## What Python does

For live EEG, Python keeps F3, F4, C3, C4, P3 and P4 separate, causally filters them, measures each two-second analysis window, calibrates each channel/descriptor against its own baseline, normalizes it to 0..1 and applies the existing light feature smoothing. Synthetic mode bypasses EEG acquisition and emits known 0..1 test movements.

The SuperCollider sender loads `config/sonification.toml`, sends its tunable values once, then sends one bounded OSC frame per update. It clamps non-finite or out-of-range test values before transmission. SuperCollider clamps all 18 controls again.

## OSC frame

The address is `/eeg/organism/frame`. One packet carries exactly 18 float arguments in channel-major order:

```text
F3 energy, F3 centroid, F3 mobility,
F4 energy, F4 centroid, F4 mobility,
C3 energy, C3 centroid, C3 mobility,
C4 energy, C4 centroid, C4 mobility,
P3 energy, P3 centroid, P3 mobility,
P4 energy, P4 centroid, P4 mobility
```

At the default `stream.control_hz = 4.0`, this is four OSC messages per second—not 72 individual control messages. `/eeg/organism/config` is one 28-value startup packet. `/eeg/organism/stop` requests graceful release.

## The six cells

All cells share `tonal.centre_hz`; they are roles in one texture, not six chord notes.

| Cell | Role | Expected character |
|---|---|---|
| F3 | left shimmer/air | slowly drifting low harmonic body with filtered air |
| F4 | right shimmer/air | a related, oppositely drifting harmonic field |
| C3 | left pulse/articulation | resonant breaths/taps whose rate and edge change |
| C4 | right pulse/articulation | a paired pulse cell with a small rate offset |
| P3 | left grain/noise/tail | filtered noise grains feeding a spatial tail |
| P4 | right grain/noise/tail | an independently triggered partner texture |

Each cell is one continuously running Synth node. Internal impulses or noise grains do not create server nodes. A dedicated Group owns six cell synths followed by one mixer synth. Stable expected server-tree size is **one Group + seven Synths = eight nodes**. The stereo bus is an audio routing allocation, not a node.

## Descriptor map and exact tuning controls

| Per-channel descriptor | Audible result | Make it stronger/weaker |
|---|---|---|
| `energy` | presence between a quiet floor and restrained ceiling | raise/lower `depths.presence`; set endpoints with `ranges.presence_min` and `ranges.presence_max` |
| `spectral_centroid` | dark-to-bright filtering and more/fewer upper harmonics or noise edge | raise/lower `depths.brightness`; widen/narrow `ranges.cutoff_min_hz` to `ranges.cutoff_max_hz` |
| `mobility` | slow/smooth to fast/jagged shimmer, pulse or grain activity | raise/lower `depths.movement`; widen/narrow `ranges.movement_min_hz` to `ranges.movement_max_hz` |
| `mobility` (secondary) | more or less spatial tail in P3/P4 | raise/lower `depths.space`; set endpoints with `ranges.room_min` and `ranges.room_max` |

Other ordinary adjustments require only `config/sonification.toml`:

- Overall level: `master.level`. The final safety ceiling is `master.limiter_level`.
- Response speed: `lags.energy_seconds`, `lags.centroid_seconds` and `lags.mobility_seconds`; larger values move more slowly.
- Transition shape for centroid/mobility: `lags.varlag_curve`.
- Stereo placement: `pan.F3` through `pan.P4`, from -1 (left) to +1 (right).
- Pitch scaffold: `tonal.centre_hz`.
- Start/stop fades: `master.attack_seconds` and `master.release_seconds`.
- Missing-input fade: `master.watchdog_fade_seconds`.
- Update rate: `stream.control_hz`, with Python enforcing a maximum of 4 Hz.

Restart the Python sender after a config edit so it resends the configuration. SynthDef code does not need editing.

## Terms in plain language

- `gate` is the on/off control for a cell's lifecycle envelope. Turning it off fades the node according to `master.release_seconds`; `doneAction: 2` then removes that synth.
- `Lag` and `VarLag` glide between incoming values to avoid steps and clicks. `VarLag` also allows a curved transition.
- A `Group` is a server-side folder that gives this engine ownership and execution order for its nodes. Re-evaluating the engine frees the old folder first, preventing orphans.
- A `bus` is the private two-channel cable from the six cells to their mixer. It keeps organism processing separate from SuperDirt and is summed safely into stereo output.
- The `Limiter` is a final ceiling on this organism only. It catches peaks after the mixer; it is not a substitute for conservative listening level.

## Isolated listening checks

Each command holds all non-selected controls at 0.5 and sweeps only one 0.05..0.95 value over eight seconds:

```powershell
.\scripts\start_eeg_organism.ps1 -Descriptor energy -Channel F3
.\scripts\start_eeg_organism.ps1 -Descriptor centroid -Channel C4
.\scripts\start_eeg_organism.ps1 -Descriptor mobility -Channel P4
```

Replace the channel with F3, F4, C3, C4, P3 or P4 to check every cell independently.

- Energy alone: only the chosen cell should become more and less present; timbre and activity should stay broadly fixed.
- Centroid alone: only the chosen cell should sweep clearly dark to bright without becoming a new pitch.
- Mobility alone: F cells move from slow/smooth to active/jagged, C cells from sparse/rounded to rapid/crisp articulation, and P cells from sparse/long grains to active/granular noise with a secondary space change.

These are connection and mapping checks, not physiological validation.

## Post window and watchdog

On start, watch for `EEG ORGANISM READY`, the six cell node IDs and one mixer ID. The IDs must remain unchanged as frames arrive. The engine prints `input active` once, not once per packet. It rejects any frame whose argument count is not exactly 18.

If frames stop for more than two seconds, the post window says `WATCHDOG` and the mixer fades to silence using `master.watchdog_fade_seconds`. The six nodes remain stable and resume on the next valid frame. This silence is expected and is not a server crash.

## Stop

First stop the foreground Python helper with `Ctrl+C`. The watchdog will fade the mixer within two seconds. Then request full graceful node release:

```powershell
.\scripts\stop_eeg_organism.ps1
```

Alternatively, open and evaluate the explicit block in `sound/stop_eeg_organism.scd`. The post window should say `graceful release started`; after `master.release_seconds`, the dedicated group and bus are freed. `hush` is neither required nor used, so the existing Tidal/SuperDirt session is not stopped.
