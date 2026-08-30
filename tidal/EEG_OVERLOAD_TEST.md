# EEG/Tidal overload isolation

Watch the SuperCollider post window during every stage. Stop each stage with
`hush` before starting the next one. Do not run Python in Tests A or B.

## Test A — baseline (at least 30 seconds)

Evaluate this ordinary one-event-per-cycle pattern:

```haskell
d1 $ s "supermandolin" # n "c3" # sustain 0.65 # gain 0.45
```

Expected: regular sound, with no continuous `late` messages and no
`command FIFO full`. Then evaluate `hush`.

## Test B — six static MVP voices (at least 60 seconds)

In `eeg_live_mvp.tidal`, evaluate Sections 1, 2, 3, and the Section 4 `do`
block. Do not start Python. The `cF` controls remain at their 0.5 defaults.

Expected: six audible static voices, with no continuous `late` messages and no
`command FIFO full`. Then evaluate `hush`.

If this stage fails, the producer is not the cause. Inspect SuperCollider CPU
and node counts and the SuperDirt event lifecycle before changing Python.

## Test C — rate-limited controls (at least two minutes)

Start the six voices as in Test B, then run:

```powershell
.\.venv\Scripts\python.exe -m src.eeg_control_demo --mode synthetic-tidal --control-hz 2
```

Expected Python rate diagnostics after warm-up:

```text
RATE frames/sec=2.00 OSC messages/sec=36.00 total controls sent=...
```

Expected sound: independently changing gain, dark/neutral/bright `djf`, and a
dry/small to wet/large reverb macro. Expected stability: no `command FIFO full`
and no sustained stream of `late` messages.

Stop Python with Ctrl+C, then evaluate `hush`.

If Tests A and B are clean but Test C fails, treat the OSC producer path as the
cause. `BootTidal.hs` currently uses Tidal's standard `mkTidal` scheduling
configuration and does not override output latency. Do not raise latency to
hide a flood. If A and B are clean and only occasional Windows scheduling
`late` messages remain, a separate follow-up may set a documented 0.15–0.20 s
latency after measuring the current runtime configuration.
