# Overnight progress — 2026-09-04 01:43:35 Asia/Shanghai

Queue root: `overnight files/codex_tasks/overnight/`

The requested `codex_tasks/overnight/` path did not exist. The queue root above
was the sole repository match and contains `00_rules.md` plus tasks 01–07.

## Queue start

- Baseline commit: `bd4055d connect to complete synthetic control frame`.
- Initial worktree: only the supplied `overnight files/codex_tasks/overnight/`
  directory was untracked.
- Environment: Python 3.12.3; python-osc 1.10.2; NumPy 2.5.2; SciPy 1.18.0;
  pylsl 1.18.2; sclang at `D:\OpenBCI\supercollider\sclang.exe`.
- Applicable `AGENTS.md`: none found.
- Safety: no commit, stash, reset, deletion, real EEG/LSL connection, or future
  task content read at queue start.

## Task 01 — Beta softening

- Status: `CODE/RENDER/TEST PASS`; `PENDING HUMAN LISTENING` (non-blocking).
- Scope review: changes are confined to the v2 beta/group-4 palette, its named profiles, isolated render/analyzer tooling, tests, and documentation. OSC frame ordering, Python mapping, pitch set, receiver callback lifecycle, and the other three harmonic groups remain unchanged.
- Profiles preserved: `softened` is the default; `original_24_36_48` keeps the prior 24/36/48 beta partial palette for direct comparison.
- Central controls: `betaCeilingHz`, `betaUpperPartialTiltDb`, and `betaTrim`; the documented single human tuning knob is `betaUpperPartialTiltDb`.
- Generated 48 kHz/24-bit stereo comparisons:
  - `recordings/eeg_organism_v2_beta_profiles/original_24_36_48_beta_low.wav`
  - `recordings/eeg_organism_v2_beta_profiles/original_24_36_48_beta_high.wav`
  - `recordings/eeg_organism_v2_beta_profiles/softened_beta_low.wav`
  - `recordings/eeg_organism_v2_beta_profiles/softened_beta_high.wav`
- Objective high-state comparison (softened versus original): RMS `-0.43 dB`, spectral centroid `-209.99 Hz`, 1.5–4 kHz RMS `-0.54 dB`, A-weight proxy `-0.57 dB`. Files are finite, stereo, 48 kHz/24-bit, and show no clipping. The softened high centroid remains above the alpha reference, retaining the intended brightness ordering.
- Regression evidence: original-profile render hashes match the prior beta reference renders; the two low-state renders are identical.
- Focused test: `.venv\Scripts\python.exe -m unittest tests.test_beta_softening -v` — 3/3 passed.
- Relevant full suite: `.venv\Scripts\python.exe -m unittest discover -s tests -v` — 62/62 passed.
- Static/diff checks: analyzer `py_compile` passed; `git diff --check` passed (line-ending warnings only).
- Human morning check: compare original and softened HIGH files at matched monitor level and decide whether to adjust only `betaUpperPartialTiltDb`; no claim of listening is made here.

## Task 02 — Real spectral entropy feature

- Status: `CODE/TEST PASS`; no listening check applies because the feature is deliberately disconnected from OSC and sound.
- Files changed: added `src/sonification/features.py`, `tests/test_spectral_entropy.py`, and `docs/ORGANISM_V2_SPECTRAL_ENTROPY.md`; exported `spectral_entropy` from `src/sonification/__init__.py`.
- Implementation evidence: the stateless, single-channel pure function uses a two-second Welch segment with 50% overlap, includes only 0.5–45 Hz PSD bins, normalizes them to probabilities, applies normalized Shannon entropy, and returns a finite `[0,1]` value.
- Defined invalid behavior: non-numeric/non-1D/non-finite input, windows under two seconds, flatlines, invalid sample rates, inadequate Nyquist range, and zero valid band power return deterministic `0.0`.
- Representative deterministic results: 10 Hz sine `0.192800`; seeded broadband noise `0.968503`; dense 1–44 Hz tones `0.995500`. Scaling from `1e-12` through `1e120` preserves the result to 12 decimal places; a bin-aligned 70 Hz component is excluded by the analysis band.
- Boundary review: no acquisition, OSC, SuperCollider, feature-to-music mapping, or real EEG connection was added.
- Focused test: `.venv\Scripts\python.exe -m unittest tests.test_spectral_entropy -v` — 5/5 passed.
- Relevant full suite: `.venv\Scripts\python.exe -m unittest discover -s tests -v` — 67/67 passed.
- Static/diff checks: `py_compile` passed for implementation and test; `git diff --check` passed (line-ending warnings only).
- Pending/unresolved: none.

## Task 03 — Real temporal novelty feature

- Status: `CODE/TEST PASS`; no listening check applies because novelty remains disconnected from OSC and sound.
- Files changed: extended `src/sonification/features.py`, extended exports in `src/sonification/__init__.py`, and added `tests/test_novelty.py` plus `docs/ORGANISM_V2_NOVELTY.md`.
- Input contract: eight normalized dimensions in fixed documented order—energy, centroid, mobility, spectral entropy, delta, theta, alpha, beta. Finite out-of-range values clamp; invalid/non-finite frames raise `ValueError` before state mutation.
- Algorithm evidence: each estimator owns a 32-frame deque (about eight seconds at 4 Hz); the current frame is compared against prior history before append. Per-dimension rolling median and `1.4826 * MAD` use a `0.05` floor, distances cap at `6.0`, equal-weight mean distance maps through `1 - exp(-distance)`, and the result clamps to `[0,1]`.
- Warm-up/zero-scale behavior: the first 32 valid frames return `0.0`; exact repetition remains `0.0`; a zero-MAD change stays finite through the scale floor and per-dimension cap.
- Representative deterministic results: an eight-dimensional `0.2 -> 0.8` jump produces `0.997521`; after the new state fills the rolling window it settles to `0.0`. Independent estimator and reset tests confirm no history leakage.
- Boundary review: novelty is explicitly numerical temporal distance, not a psychological label; no acquisition, real EEG/LSL, OSC, SuperCollider, pitch, or musical mapping was added.
- Focused test: `.venv\Scripts\python.exe -m unittest tests.test_novelty tests.test_spectral_entropy -v` — 12/12 passed (7 novelty-specific).
- Relevant full suite: `.venv\Scripts\python.exe -m unittest discover -s tests -v` — 74/74 passed.
- Static/diff checks: `py_compile` passed; `git diff --check` passed (line-ending warnings only).
- Pending/unresolved: none.

## Task 04 — Offline G Lydian voicing decisions

- Status: `CODE/TRACE/TEST PASS`; `PENDING HUMAN LISTENING` for eventual musical judgment (non-blocking). This task produces data/text only.
- Files changed: added `src/sonification/voicing.py`, `tests/test_g_lydian_voicing.py`, `docs/ORGANISM_V2_G_LYDIAN_VOICING.md`, and four JSON traces under `traces/organism_v2_g_lydian/`.
- Pitch/density evidence: every generated MIDI pitch class is one of exactly G, A, B, C#, D, E, F#; decisions use 2–6 of six capacity slots with normalized variable note weights and descriptor-dependent density, not a fixed chord/triad/count.
- Mapping/scoring evidence: centroid targets mean register; spectral entropy targets consonance versus bounded scale tension; novelty sets change probability, common-tone/voice-leading priorities, motion bounds, and seeded selection temperature; mobility alone sets 2–12 second holds; energy has only a secondary density effect and does not enter amplitude weights. Candidate scores expose scale membership, interval consonance/tension, entropy fit, register, spacing, common tones, voice leading, and density.
- Determinism/bounds: seed `20260904` regenerates the committed traces exactly. Candidates remain scale-, register-, spacing-, width-, and novelty-motion-bounded even in the active scenario.
- Trace audit (12 decisions each): calm-stable `2` unique/3 voices/max motion `0.666667 st`; bright-stable `2` unique/3 voices/max `0.333333 st`; tense-stable `2` unique/5 voices/max `0.2 st`; active-novel `11` unique/4–5 voices/max `1.9 st`.
- Boundary review: no OSC, SuperCollider, audio rendering, real EEG/LSL, or runtime sound wiring was added. Descriptor mappings are documented as artistic choices, not mental-state inference.
- Focused test: `.venv\Scripts\python.exe -m unittest tests.test_g_lydian_voicing -v` — 9/9 passed.
- Relevant full suite: `.venv\Scripts\python.exe -m unittest discover -s tests -q` — 83/83 passed.
- Static/diff checks: `compileall` passed for `src` and `tests`; `git diff --check` passed (line-ending warnings only); worker also checked untracked files for whitespace errors.
- Pending/unresolved: musical/aesthetic evaluation remains `PENDING HUMAN LISTENING`; no code/test blocker.

## Task 05 — Manual persistent multi-voice instrument

- Status: `CODE/RENDER/TEST PASS`; transition/timbre quality is `PENDING HUMAN LISTENING` (non-blocking).
- Files changed: extended `config/eeg_organism_v2.scd`, `sound/eeg_harmonic_field_v2_core.scd`, `sound/eeg_organism_v2_receiver.scd`, `src/sonification/protocol.py`, and package exports; added `src/sonification/manual_voicing_demo.py`, SC NRT render source, render/analyzer scripts, focused tests, documentation, evidence README, and `recordings/eeg_organism_v2_voicing/g_lydian_transition.wav`.
- Protocol boundary: the existing `/eeg/organism/v2/frame` remains exactly nine values. A separate `/eeg/organism/v2/voicing` packet contains six frequencies followed by six weights, with finite/bounded validation, inactive-slot padding, and at least one active weight.
- Persistence evidence: one Synth contains fixed A/B banks of six slots. The receiver populates only the inactive bank using `setn`, flips one bank selector with `set`, rejects updates during the 1.35-second transition instead of queuing them, and creates no Synth/Group/Buffer/Routine in the voicing callback. The live tree remains one dedicated Group plus one Synth.
- Synthesis/safety: each slot shares the four exact harmonic groups and band controls; four local wavetables are constructed with the Synth rather than per update. `VarLag` plus equal-power `XFade2` avoids audible-bank frequency glides; L2 voice normalization, `0.82` safety trim, sanitize, limiter, and final bound protect changing polyphony. Watchdog and stop attenuate/release the entire Synth and never call `s.quit`.
- Documented adaptation: to remain within default running scsynth graph limits, partials are compiled into four local exact-harmonic wavetables and each group uses the amplitude-weighted mean of its former per-partial pan positions.
- Manual fixtures: the sender alternates G2–D3–A3 and C#3–F#3–C#4–F#4 while refreshing one unchanged synthetic bed frame at 4 Hz; it does not import or invoke the Task 04 decision engine.
- Independent NRT rerender: sclang/scsynth completed without `ERROR`, `FAILURE`, or GraphDef exception. Score contains exactly one `/s_new`; changes use only `/n_setn` and `/n_set`.
- WAV evidence: 48 kHz, stereo, 24-bit PCM, `19.001333 s`, finite, peak `0.0576684` (`-24.781 dBFS`), transition max step `0.00447774`, no clipping; SHA-256 `4C74447FD518DBCA154FE8174849FCDCA1FE124FDFA903034016406D94CD2B7E`.
- Focused test: `.venv\Scripts\python.exe -m unittest tests.test_persistent_voice_bank -v` — 7/7 passed.
- Relevant full suite: `.venv\Scripts\python.exe -m unittest discover -s tests -q` — 90/90 passed.
- Static/diff checks: Python `py_compile`, PowerShell parser, receiver sclang parse, and `git diff --check` passed (line-ending warnings only). Render temporary archive was removed; user processes were not stopped.
- Pending/unresolved: morning listening must assess transition smoothness and timbral continuity; no automated/code blocker.
