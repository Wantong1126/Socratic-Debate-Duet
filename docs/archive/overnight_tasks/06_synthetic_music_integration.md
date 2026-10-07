# Task 06 — synthetic descriptors to the melodic layer

Connect the tested offline voicing engine to the tested persistent voice bank,
still using synthetic controls only.

- Continue descriptor/harmonic frames at about 4 Hz.
- Send a voicing message only when the music-decision layer chooses a change;
  never choose/send new notes every EEG frame.
- Bands continue to control harmonic coloration. The other descriptors use only
  the documented mappings from Task 04.
- Add CLI scenarios: calm-stable, bright-stable, tense-stable, active-novel, and
  a combined continuous demonstration.
- Print compact lines showing descriptors, selected notes, hold time, and reason.
- Support one-shot and `--loop`, with clean Ctrl+C and watchdog behavior.
- Preserve bounded values, stable nodes, click-free changes, and safe gain.

Add protocol, cadence, reproducibility, node-stability, stop, and duration tests.
Generate one offline/NRT reference render per scenario when practical. Do not
connect real EEG. Mark all musical judgments `PENDING HUMAN LISTENING` and return
to the dispatcher.

