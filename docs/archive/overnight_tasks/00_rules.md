# Shared overnight rules

- First inspect the repository, `git status`, relevant diffs, dependencies, and
  every applicable `AGENTS.md`.
- Preserve all existing tracked and untracked user work. Do not commit, stash,
  reset, delete, or broadly reorganize the repository.
- Reuse the current Python 3.12 environment, `src/sonification` package, v2 OSC
  protocol, persistent SuperCollider architecture, watchdog, and stop behavior.
- Do not create a competing acquisition, protocol, or sound pipeline.
- Do not connect real EEG/LSL. Do not implement six-channel or two-debater
  behavior, EOG/EMG, drums, Tidal, arrangement, or large-scale structure.
- Complete only the current numbered task. Do not read or implement future task
  files early.
- Keep mappings documented as artistic choices, not mental-state inference.
- Never claim that sound was heard. Mark subjective checks `PENDING HUMAN LISTENING`.
- After each task run focused tests, the relevant full suite, compile/static
  checks, and `git diff --check`.
- At queue start, create one timestamped `reports/overnight/<timestamp>/progress.md`.
  Append: task, evidence, files changed, commands/tests, result, pending human
  checks, and unresolved issue. Do not rewrite earlier checkpoints.
- Preserve working public commands unless the task explicitly extends them.
- No per-frame Synth, Group, Buffer, or Routine creation.
- If a task fails validation after reasonable repair attempts, stop the queue.

## Accepted starting state

- v2 synthetic descriptor and band sweeps now run at approximately 4 Hz with
  monotonic pacing, holds, loop support, and no catch-up burst.
- OSC address, nine-field order, receiver indexing, persistent Synth update,
  watchdog silence, and stop path have passed automated checks.
- Energy and all four harmonic groups respond in live human testing.
- Beta uses exact partials 24/36/48 from 65.41 Hz and is clearly audible, but
  its high state is subjectively too piercing.
- Real EEG, real spectral entropy/novelty, dynamic pitches, six channels, and
  two debaters are not yet connected.

