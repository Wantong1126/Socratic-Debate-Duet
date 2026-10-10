# Posterior alpha to brightness — implementation check

## What changed

- `src/sdd/audition_features.py` now accepts `f3_energy` (unchanged default)
  or `posterior_alpha`. The latter calculates the mean of P3 and P4 absolute
  8–13 Hz Welch power from the current causal window, in uV².
- P3 and P4 each retain their own quality warning. Both must be valid before a
  posterior-alpha value can calibrate or drive sound. A missing, saturated,
  flat, non-finite, or degenerate-range window has no valid amount.
- The alpha input has its own 5th–95th percentile calibration range and the
  existing 0.5 s smoothing. F3's energy bounds are never consulted.
- `mapping_audition` exposes `--input posterior_alpha`; it accepts that input
  only with the existing `brightness` candidate. No note, chord, colour,
  reimagination, frame, voicing, or receiver contract changed.
- `--alpha-check-output PATH` is an explicit live-recording mode. It stores
  raw 8-channel chunks, six open/closed condition markers, alpha/quality rows,
  amount, and the actual four brightness-group controls.

## Processing timing

The result is computed from a causal 2.0 s window at 4 Hz after the existing
30 s settling and 20 s alpha calibration. Each saved music-control record has
the measured send-time minus feature-time latency and declares the 2.0 s
analysis support plus 0.5 s EMA smoothing. These operations are not EOG or
EMG removal.

## Checks run on 2026-10-11

- `python -m unittest tests.test_mapping_audition -q`: 13 tests passed.
- A known 10 Hz P3/P4 signal test produced a calibrated posterior-alpha amount
  above 0.9 and changed only the existing four brightness-group controls.
- Bad P3/P4 input produced no valid control. Marker transitions left the same
  brightness mapping unchanged.
- Raw replay recalculation of
  `obci_eeg1_20260919_194100` completed: 276 valid posterior-alpha windows,
  calibration bounds 4.7380–86.1911 uV², and no P3/P4 saturation reported.
  This is an unlabeled resting recording; it does not establish an eyes-open /
  eyes-closed association.

## Still required

Wear the electrodes and run the recorded three-round check. Follow each
printed 20-second eyes-open / eyes-closed prompt. Review per-condition alpha
distributions, valid-window counts, and brightness ranges after the run. If
the three rounds do not show a repeatable difference, report that no
association was established; do not stretch the calibration or force the
brightness range.
