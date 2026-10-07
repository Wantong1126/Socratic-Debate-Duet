# EEG sonification — start here

Current workflow: one participant-A harmonic voice, raw human EEG replay and an explicit **reimagination** event. The latest menu offers level, melody, brightness, sound colour and harmony. The older pulse/effect menu is archived.

From the repository root in PowerShell:

```powershell
& "C:\Users\cc_10\anaconda3\python.exe" -m src.sdd.mapping_audition
```

The default reads the existing human resting session, recomputes F3 energy and plays a short fragment. No electrodes are needed for replay. The current `.venv` lacks its Python executable; the above installed Python has the tested dependencies.

- [Listening guide, keys, chords and loudness/brightness explanation](docs/LISTENING_GUIDE.md)
- [Actual listener feedback and implementation/validation](reports/sdd_v1/listening_revision_20261007.md)
- [Latest audition evidence and local audio](reports/sdd_v1/mapping_audition/README.md)
- [Project plan and next human validation](SDD_V1_Plan/NEXT_CODEX_TASK.md)
- [Documentation index](docs/README.md)

## Where things belong

| Directory | Purpose |
| --- | --- |
| `src/sdd/` | Current single-participant session, raw replay, quality, mapping and reimagination |
| `src/sonification/` | Established frame/voicing transport and synthesis-facing decisions |
| `sound/` | Existing SuperCollider receiver and harmonic SynthDef |
| `scripts/` | Launch, render and runtime verification helpers |
| `config/` | Montage, units, mapping ranges, note material and timing |
| `tests/` | Protocol, processing, playback and receiver regressions |
| `SDD_V1_Plan/` | Requirements with stable task IDs and dependencies |
| `reports/sdd_v1/live_sessions/` | Existing human raw replay input; preserve it |
| `recordings/`, `traces/` | Original reference/test inputs; preserve their paths |
| `reports/sdd_v1/mapping_audition/20261007/` | Latest renders and curated evidence |
| `docs/archive/`, `reports/archive/` | Earlier task instructions, reports and local audition assets |
| `tidal/` | Earlier Tidal experiments; `BootTidal.hs` stays at root for compatibility |

Generated WAVs, scores and local session logs are ignored; they remain on disk. Existing tracked recordings/raw inputs were neither removed nor republished by the cleanup. The selected reference remains `reports/sdd_v1/t01_render/g_lydian_transition.wav`; the voice-bank test uses `recordings/eeg_organism_v2_voicing/g_lydian_transition.wav`.

```powershell
python -m unittest discover -s tests -q
python -m scripts.verify_mapping_runtime
```

Technical checks pass; revised sound identity, source recognition, comfort and live behavioral correspondence await human evaluation. The runtime currently owns A only. Reimagination is an external request, never an EEG-inferred argument flaw or success score.
