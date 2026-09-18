# T10-T12 invitation control

This change turns an explicit button press into a traceable invitation event, a continuous per-participant control envelope, and a separate control stream delivered to the existing participant voice. It makes no argument-quality, reflection, musical-effect, or psychological-effect claim.

## Files changed

- `src/sdd/invitation_input.py`: anonymous event schema and one-event-per-press input.
- `src/sdd/reflection_controller.py`: independent A/B envelopes and termination records.
- `src/sdd/invitation_osc.py`: strict sender-side message validation.
- `src/sdd/invitation_demo.py`: deterministic manual demo with decline and completion.
- `src/sdd/session_runtime.py` and `src/sdd/session_recorder.py`: signal-loss/stop integration and trace records.
- `sound/eeg_organism_v2_receiver.scd` and `sound/eeg_harmonic_field_v2_core.scd`: receiver validation and a neutral control on the existing Synth.
- `config/sdd_v1.toml` and `config/eeg_organism_v2.scd`: envelope durations, rate, and message-age limit.
- `scripts/verify_invitation_runtime.py` and `.scd`: reproducible live receiver validation.
- `tests/test_invitation_control.py`: T10-T12 acceptance coverage.

The existing nine-value sonification frame and the six-frequency plus six-weight voicing message were not reordered or extended.

## Message contract

OSC address: `/sdd/invitation/v1/control`

Six ordered OSC arguments:

1. `target_code`: integer `0` for A or `1` for B.
2. `session_id`: non-empty string.
3. `event_id`: non-empty string.
4. `seq`: nonnegative, strictly increasing integer within the receiver session.
5. `age_seconds`: finite value from `0.0` through configured `0.5` seconds.
6. `invitation_amount`: finite value in `[0.0, 1.0]`.

The current receiver owns one participant voice, A. It rejects B-targeted messages rather than implying that a second voice exists. It binds the first accepted session ID, rejects another session, duplicate or older sequence numbers, stale messages, malformed widths, non-finite values, and out-of-range amounts. Accepted values update `\invitationAmount` on the already-running Synth. They do not allocate a node, refresh the sound-frame watchdog, or trigger a separate sound. The neutral parameter has no audible mapping yet.

## Event and state behavior

Each button press creates exactly one event with `event_id`, `session_id`, enumerated source, anonymous target A/B, `prompt_id`, monotonic time, and optional short prompt text. EEG and audio data never create these events.

Each target has its own `idle -> attack -> hold -> release -> cooldown -> idle` state. Pause follows a smooth release into `paused`; a later explicit invitation may start a new attack. Decline, end, signal loss, and stop also release smoothly. An accepted active event rejects repeated presses, so a repeat does not stack or silently extend it. Termination records use only `completed`, `declined`, `ended`, `paused`, `signal_loss`, or `stopped`. Signal loss suppresses the envelope through its release path and is recorded as transport state, not participant behavior.

Configured values are attack `0.5 s`, hold `1.0 s`, release `0.5 s`, cooldown `0.5 s`, and control sampling `20 Hz`.

## Reproduction and results

Deterministic demo without a receiver:

```powershell
.venv\Scripts\python.exe -m src.sdd.invitation_demo --log reports/sdd_v1/invitation_manual_dry.jsonl
```

Live isolated receiver validation (choose a new run name because evidence is never overwritten):

```powershell
.venv\Scripts\python.exe -m scripts.verify_invitation_runtime --run-name invitation_runtime_final
```

Full test suite:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -q
```

Results on 2026-09-18:

- 112 tests passed.
- Live receiver: 111 valid controls accepted and all 6 injected invalid controls rejected (wrong target, duplicate sequence, stale, malformed, NaN, out of range).
- Invitation traffic continued while the sound-frame watchdog fired, confirming that it did not refresh audio health.
- All 22 active node-tree samples contained exactly one participant Synth; the participant node was absent after stop.
- The manual flow produced two events with `declined` and `completed` terminations, then stopped cleanly.
- Captured audio is 48 kHz stereo, finite, peak `0.03582035`; this checks the runtime artifact only.

Evidence: `invitation_runtime_final.json`, `invitation_runtime_final.log`, `invitation_runtime_final.wav`, `invitation_runtime_final_manual.jsonl`, and `invitation_manual_dry.jsonl` in this report directory.

## Unverified and next decision

Human audition is **PENDING HUMAN LISTENING**. Automated tests and the recording checks do not establish an audible, musical, or psychological effect. Participant B has schema and independent controller state, but there is no B voice in the current runtime and the receiver correctly rejects target B.

The next decision is to audition alternative mappings from `invitation_amount` into the same continuing participant voice, then select an artistic transformation without introducing a separate alert melody.
