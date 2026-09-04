# Organism v2 matched beta profiles

These four files are independent 48 kHz/24-bit stereo NRT renders. Each pair
uses the same score and steady-state measurement window (seconds 2-5); the only
difference is the named beta profile. This is objective evidence, not a claim
that the sound was heard or approved.

| Profile/level | RMS dBFS | Peak | Centroid | 1.5-4 kHz energy | 1.5-4 kHz RMS | A-weighted RMS proxy |
|---|---:|---:|---:|---:|---:|---:|
| original LOW | -36.04 | 0.04666 | 130.90 Hz | <0.00001% | -105.89 dBFS | -49.37 dBFS(A) |
| original HIGH | -33.69 | 0.05467 | 1847.51 Hz | 95.01% | -33.92 dBFS | -32.85 dBFS(A) |
| softened LOW | -36.04 | 0.04666 | 130.90 Hz | <0.00001% | -105.89 dBFS | -49.37 dBFS(A) |
| softened HIGH | -34.13 | 0.05011 | 1637.52 Hz | 92.77% | -34.45 dBFS | -33.41 dBFS(A) |

All samples are finite and no file clips. The two LOW files are byte-identical.
The two original files are also byte-identical to the pre-softening
`recordings/eeg_organism_v2_isolated/beta_{low,high}.wav` renders, confirming
that `original_24_36_48` is an exact comparison rather than an approximation.

Relative to original HIGH, softened HIGH changes:

- RMS: -0.43 dB;
- peak: -0.00456 linear amplitude;
- centroid: -209.99 Hz;
- 1.5-4 kHz share: -2.24 percentage points;
- 1.5-4 kHz RMS: -0.54 dB;
- A-weighted RMS proxy: -0.57 dB.

The softened centroid remains above 1.6 kHz and therefore objectively much
higher than the existing alpha HIGH centroid (about 525 Hz). Whether it is less
piercing while remaining sufficiently audible is **PENDING HUMAN LISTENING**.

Reproduce with:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\render_eeg_organism_v2_beta_profiles.ps1
.\.venv\Scripts\python.exe .\scripts\analyze_eeg_organism_v2_beta_profiles.py
```
