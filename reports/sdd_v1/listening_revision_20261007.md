# Listening feedback and implemented revision — 2026-10-07

## Human observations on the September menu

| Old candidate | User observation | Decision |
| --- | --- | --- |
| 1 level | Quieter/darker; loudness versus brightness unclear | Retain as gain-only comparison; explain perceptual overlap |
| 2 pitch | B appears/disappears, pleasing; asks for harmony relation | Retain an upper melodic line, now over complete Abmaj7 |
| 3 timbre | Sudden increase in apparent loudness/brightness | Rename brightness, slower smoothing; add separate colour candidate |
| 4 reverb / 5 delay | Both feel like muffled pulsing, little distinction | Retire both from active menu |
| 6 harmony | Too similar to option 2; wants bolder harmony beyond G Lydian | Four distinct chords starting at Abmaj7 |
| 7 rhythm | Some irregular pulses, too similar to 4/5 | Retire; do not add unrelated random behavior |
| 8 note weights | Contrast inadequate | Retire from active menu |

These are actual user listening observations, not inferred physiological or psychological states. New revisions have not yet been heard or approved by the user.

## Event naming and compatibility

The explicit request to rethink the weighing metric is now **reimagination**. `ReimaginationEvent` is the actual immutable event class; current CLI/logs use reimagination terminology and `reimagination_event/control/termination`. `src/sdd/reimagination.py` exposes the current API. Sources, anonymous target A/B, unique event, monotonic time, decline/end/pause, finite bounded envelope and real termination reasons retain their semantics.

The new endpoint is `/sdd/reimagination/v1/control` with the established six values: target code, session_id, event_id, seq, age_seconds, amount. The receiver shares target/session/sequence validation across old and new endpoints. Historical `/sdd/invitation/v1/control` and Python aliases remain readable for compatibility; historical reports/recordings were not rewritten. Low-level synth names `invitationAmount/HarmonyDepth/DiagnosticDepth` remain compatibility controls rather than user-facing event names.

New palette transport is `/sdd/music/v2/control`: the existing 17-value music packet followed by `musicColour` in [0,2], total 18 values. The 17-value `/sdd/music/v1/control` is still accepted unchanged. Nine-value sonification frames and 12-value voicing remain unchanged. Neither music extension nor reimagination updates sound-frame health/watchdog.

## Implementation and evidence

Current raw replay still uses ReplaySource → ControlSession → existing feature processing → SessionRuntime. Eight original roles, recorded LSL clock, unit checks, quality, causal filtering and valid personal scaling remain available; raw never implies no Python filtering. Only F3 energy controls the selected candidate. Other descriptors and body-signal mappings remain fixed/unimplemented. No new raw EEG is collected by replay or the diagnostic runs.

Auditions keep the original oscillator field, six-slot persistent two-bank voice, limiter and safe gain. Optional colour tables are enabled only in the current audition preset; the established core path retains its tested palette. A first oversized table graph exceeded SC's SynthDef OSC buffer; merging the two alternate palettes into compact tables fixed actual NRT and receiver operation. New sounds have no pulse probe or random evolution. Busy-port selection present in the working tree was preserved; the verifier now uses the selected receiver ports too.

Technical verification: all 131 tests passed. Thirteen new 48kHz stereo 24-bit WAVs rendered through the actual SC core; each is finite, has non-silent active RMS and a silent final tail; maximum peak is below 0.08. Non-level average RMS spans less than 1 dB in the delivered comparison files. Runtime verification rejected 10 wrong/duplicate/stale/malformed/non-finite messages, kept one Synth, timed out despite continuous music/reimagination packets and released nodes on stop. Verification output was muted, so it adds no human listening claim.

Files/config/input formulas and note tables: `docs/LISTENING_GUIDE.md`, `config/mapping_audition.json`, `reports/sdd_v1/mapping_audition/20261007/manifest.json` and `raw_audit.json`. The earlier 19 WAVs and selected reference were preserved. New behavioural correspondence, sound-source recognition, pleasure/fatigue, and ownership/reflection effects remain unverified.

Repository work is committed in two steps at the user's explicit request: implementation first, reversible structure cleanup second. No push was requested.
