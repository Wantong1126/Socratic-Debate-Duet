# Organism v2 isolated LOW/HIGH measurements

Ten independent 48 kHz/24-bit stereo NRT renders were measured over seconds 2-5
of each steady state. “Relevant energy” is the percentage of measured 20-12000 Hz
spectral power inside the target group's frequency region. These are objective
measurements, not a listening-test result.

| Control | RMS LOW/HIGH (dBFS) | HIGH−LOW RMS | Centroid LOW→HIGH | Relevant energy LOW→HIGH | Peak LOW/HIGH | Clipping |
|---|---:|---:|---:|---:|---:|---:|
| energy | -51.09 / -29.14 | +21.96 dB | 116.14→115.96 Hz | 100.00%→100.00% (40–4000 Hz) | 0.0079 / 0.0984 | none |
| delta | -34.03 / -36.24 | -2.21 dB | 363.18→105.20 Hz | 0.00002%→99.999% (50–220 Hz) | 0.0608 / 0.0392 | none |
| theta | -36.20 / -34.00 | +2.20 dB | 117.06→301.12 Hz | 0.00001%→99.905% (240–420 Hz) | 0.0372 / 0.0527 | none |
| alpha | -36.06 / -34.26 | +1.80 dB | 127.46→525.34 Hz | 0.00001%→99.433% (430–820 Hz) | 0.0470 / 0.0495 | none |
| beta | -36.04 / -33.69 | +2.35 dB | 130.90→1847.51 Hz | <0.00001%→95.012% (1500–3250 Hz) | 0.0467 / 0.0547 | none |

Energy changes level by 21.96 dB while moving centroid by less than 0.2 Hz. The
four band tests keep HIGH−LOW RMS within 2.35 dB while moving energy into their
assigned exact-partial regions. Delta correctly moves the centroid downward;
theta, alpha, and beta move it upward.

Reproduce with:

```powershell
.\scripts\render_eeg_organism_v2_isolated.ps1
.\.venv\Scripts\python.exe .\scripts\analyze_eeg_organism_v2_isolated.py
```
