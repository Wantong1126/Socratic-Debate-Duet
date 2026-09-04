# Organism v2 beta softening

This change affects only the v2 beta palette (harmonic group 4). The exact
partials remain 24, 36, and 48 of the inherited 65.41 Hz fundamental. It adds no
pitch, noise, detune, trigger, modulation, or transport behavior.

## Profiles and signal path

`config/eeg_organism_v2.scd` selects `softened` by default and retains
`original_24_36_48` as the exact pre-softening comparison. The original profile
has a flat upper-partial tilt, unity beta trim, and a ceiling above all partials.

The group-4 signal path is:

```text
24/36/48 exact partials
-> inherited harmonic roll-off and A-weight compensation
-> beta upper-partial tilt
-> soft beta ceiling above betaCeilingHz
-> existing perceptual energy normalization
-> betaTrim
-> unchanged fixed stereo delay, saturation, reverb and limiter
```

The softened default uses a 2700 Hz soft ceiling, -3.5 dB upper-partial tilt,
and 0.90 trim. The ceiling is a gentle amplitude roll-off above its threshold,
not a new oscillator or pitch. Saturation (1.25), reverb (0.18 mix, 3.0 seconds,
0.68 damping), output trim (0.62), and limiter (-1.5 dB) are unchanged.

## Single human tuning knob

Tune only `betaUpperPartialTiltDb` inside the `softened` profile. Values closer
to 0 retain more of partials 36/48; more-negative values soften them. Keep
`betaCeilingHz` and `betaTrim` fixed as safety/level guards while comparing.
This is an artistic timbre control, not a neurological or mental-state claim.

Render and measure the matched comparison with:

```powershell
.\scripts\render_eeg_organism_v2_beta_profiles.ps1
.\.venv\Scripts\python.exe .\scripts\analyze_eeg_organism_v2_beta_profiles.py
```

The four 48 kHz/24-bit stereo files are written under
`recordings/eeg_organism_v2_beta_profiles`. Objective measurements cannot select
the preferred timbre: final profile approval is **PENDING HUMAN LISTENING**.
