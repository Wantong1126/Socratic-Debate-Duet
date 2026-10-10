# Sonification architecture

The project keeps one linear responsibility chain. New harmonic work should extend these boundaries instead of creating another acquisition or preprocessing pipeline.

```text
LSL / acquisition
  -> EEG preprocessing
  -> feature extraction
  -> normalization / mapping
  -> OSC protocol
  -> SuperCollider instrument
```

| Responsibility | Current canonical files | Status and boundary |
|---|---|---|
| LSL / acquisition | `src/window_engine.py`, `src/lsl_probe.py` | Discovers or records the existing six-channel stream. Do not add acquisition loops inside sonification modules. |
| EEG preprocessing | `src/eeg_preprocessing.py` | Stateful causal filtering and same-channel invalid-sample repair. Audification continues to use its existing path unchanged. |
| Feature extraction | `src/eeg_control_features.py`, `src/sdd/audition_features.py`, with earlier helpers in `src/eeg_features.py` | The existing engine extracts energy, centroid, and mobility. The current audition runtime can also compute a separately calibrated `posterior_alpha` input: mean absolute 8–13 Hz Welch power from quality-valid P3 and P4 windows. |
| Normalization / mapping | Legacy calibration in `src/eeg_control_features.py`; v2 boundary mapping in `src/sonification/controls.py`; earlier manual mapping prototype in `src/sonification/harmonics_mapping.py` | V2 keeps master presence independent from the four harmonic groups. Mapping code is pure and has no I/O. |
| OSC protocol | Live legacy protocol in `src/organism_osc.py`; v2 nine-value contract in `src/sonification/protocol.py`; earlier five-value prototype in `src/sonification/harmonics_protocol.py` | Protocol modules own addresses, ordering, validation, clamping, and serialization. They do not extract features. |
| SuperCollider instrument | Current organism receiver/core in `sound/eeg_organism_v2_receiver.scd` and `sound/eeg_harmonic_field_v2_core.scd`, configured by `config/eeg_organism_v2.scd`; tested historical manual files under `sound/eeg_harmonic_field_core.scd` and `sound/eeg_harmonics_manual.scd`; legacy live engine in `sound/eeg_organism_engine.scd` | The current runtime retains one persistent harmonic Synth. It accepts the existing nine-value frame plus separate music control; `mapping_audition` can feed it from raw replay or an explicitly confirmed live LSL stream. SuperCollider owns synthesis, smoothing, effects, watchdog, and output safety. |

`src/sonification/synthetic_demo.py` is the v2 synthetic transport, not a second
acquisition pipeline. It produces no EEG features. The earlier
`harmonics_synthetic_demo.py` dry-run entry point remains available for
compatibility.

## Entry points that remain valid

- Existing live/control modes: `python -m src.eeg_control_demo ...`
- Existing organism launcher: `scripts/start_eeg_organism.ps1`
- Existing manual harmonic instrument: evaluate `sound/eeg_harmonics_manual.scd`
- New dry-run harmonic controls: `python -m src.sonification.harmonics_synthetic_demo --sweep brightness`
- V2 synthetic transport: `python -m src.sonification.synthetic_demo --mode combined`
- Current replay/live audition: `python -m src.sdd.mapping_audition --input f3_energy` or `--input posterior_alpha --candidate brightness`

Do not duplicate LSL discovery, filters, channel repair, baseline calibration, or OSC schemas in future composition/demo files. Import the canonical stage above, and add a compatibility wrapper before relocating any established entry point.
