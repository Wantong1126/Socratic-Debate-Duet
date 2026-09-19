# T18 live LSL and single-energy validation — 2026-09-19

## Result

T18 passes for the selected OpenBCI GUI outlet `obci_eeg1`. The current sonification runtime received eight fresh channels from the existing Cyton-compatible setup at a nominal and observed rate of approximately 250 Hz. The operator confirmed that the outlet is GUI `TimeSeriesRaw`, the values are in `uV`, and the channel order is F3, F4, C3, C4, P3, P4, vertical EOG, jaw EMG. The LSL descriptor itself does not contain labels, units, or filtering metadata, so these facts remain explicitly marked as operator-confirmed configuration.

Three outlets were discoverable. Only `obci_eeg1` produced samples; `obci_eeg2` and `obci_eeg3` each produced zero samples in a four-second check and are rejected as inactive rather than selected implicitly.

An electrode-connected diagnostic received 7510 samples in 30 seconds. All eight columns were finite and non-flat, F3 completed the 20-second personal baseline, and stopping the GUI stream caused the inlet to stop and printed `STOP CONFIRMED no_new_samples_for_s=2`. This is the T18/H07 source, rate, arrival, channel-separation, and stop evidence. No raw human samples or audio recordings were saved.

The earlier no-electrode observation is retained only as history: Ch5, Ch7, and Ch8 appeared railed and that run was not accepted as human EEG. A later quality correction added explicit 98% rail detection against the configured 187500 uV limit. In the live sound run, Ch7/vertical EOG was correctly reported saturated. This does not invalidate the F3-only mapping, but Ch7 is not accepted for a later body-signal mapping until its contact/range is corrected and rechecked.

## Single real-EEG mapping

With explicit playback authorization, one valid EEG input was connected to the existing participant-A harmonic voice:

```text
F3 samples
  -> causal existing filter/window engine
  -> Welch PSD integrated over 4–40 Hz
  -> 20 s personal 5th–95th percentile range
  -> existing 0.5 s smoothing
  -> normalized energy in [0,1]
  -> current nine-value frame energy field
  -> existing SuperCollider participant-A Synth
```

The receiver accepted 371 frames. Live normalized energy ranged approximately from `0.001` to `0.984`. The other eight frame fields remained fixed:

```text
centroid=0.24, mobility=0.10, spectral_entropy=0.12, novelty=0.04,
delta=0.82, theta=0.58, alpha=0.28, beta=0.08
```

The existing voicing was sent once. Invitation control remained separate. No body-signal sound mapping, full live nine-feature calculation, alternate synth, or preset melody was introduced.

The sound run ended through the existing stop message. SuperCollider reported graceful release, disconnected the server, and exited with code 0. Its fixed Group 1000 and Synth 1001 were the only persistent voice nodes; no recording was started. The run''s optional second GUI-stop check did not pass because the GUI outlet continued sending for the whole 90-second wait. That is an operator-timing result, not a stale-data acceptance: the earlier diagnostic already demonstrated actual GUI stream loss, while this run separately demonstrated clean application stop and receiver cleanup.

The transport and audio-control path therefore pass technically. Human listening remains **waiting for audition feedback**; automated tests do not establish whether the energy change was audible or musically useful.

## Reproduction

List and select the active outlet:

```powershell
.\.venv\Scripts\python.exe -m src.sdd.live_eeg --list-streams --wait-time 5
```

Run the eight-channel diagnostic without sound or raw-data saving:

```powershell
.\.venv\Scripts\python.exe -u -m src.sdd.live_eeg --stream-name obci_eeg1 --source live --confirm-live-hardware --confirm-channel-order --duration 30 --wait-time 10 --verify-stop --stop-wait 90
```

During `STOP CHECK`, stop the OpenBCI GUI LSL data stream. Passing requires two seconds without new samples. Restart the GUI LSL stream before an audio run.

Start the existing receiver in one PowerShell window:

```powershell
& "C:\Program Files\SuperCollider-3.14.1\sclang.exe" scripts\run_live_energy_receiver.scd
```

Then run the explicitly authorized low-volume bridge in another:

```powershell
.\.venv\Scripts\python.exe -u -m src.sdd.live_eeg --stream-name obci_eeg1 --source live --confirm-live-hardware --confirm-channel-order --duration 35 --wait-time 10 --sound
```

The command prints provenance, timestamps, rate, units, all eight role-labelled values, flat/saturated channels, baseline state, raw F3 energy, normalized energy, and whether each sound frame is valid. It does not save raw samples.

## Files changed

- `config/live_eeg.toml`
- `src/window_engine.py`
- `src/eeg_control_demo.py`
- `src/eeg_control_features.py`
- `src/sdd/live_eeg.py`
- `scripts/run_live_energy_receiver.scd`
- `tests/test_live_eeg.py`
- `reports/sdd_v1/t18_live_lsl.md`

The supplied corrections remain in their original project files: `SDD_V1_Plan/ATOMIC_REQUIREMENTS.md`, `SDD_V1_Plan/requirements.json`, and `SDD_V1_Plan/PRODUCT_REQUIREMENTS.md`.

## Verification and remaining scope

`python -m unittest discover -s tests -v` passed all 120 tests. Coverage includes explicit multi-stream selection, zero-sample rejection, metadata extraction, microvolt gating, flat and saturated required-channel rejection, reuse of the existing window session without its legacy 18-value output, current frame/runtime regressions, and the no-recording SuperCollider harness contract.

Remaining work is deliberately outside this stage: human listening feedback, correction/recheck of the saturated EOG channel before using it, all nine live sonification features, and EOG/EMG mappings into the current voice.