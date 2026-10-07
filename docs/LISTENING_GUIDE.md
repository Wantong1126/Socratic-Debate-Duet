# Current listening guide — 2026-10-07

From `D:\sdd-sonification`, run:

```powershell
& "C:\Users\cc_10\anaconda3\python.exe" -m src.sdd.mapping_audition
```

Default input: raw recomputation of the operator-confirmed human resting recording `obci_eeg1_20260919_194100`, original sample seconds 60–84. Default candidate: sound colour. No electrodes are needed for replay. No new raw samples or audio recording are saved by the interactive player.

| Key | Candidate | What changes | What stays fixed |
| --- | --- | --- | --- |
| 1 | Level | Overall gain -12 to 0 dB | Notes, harmonic spectrum, continuous articulation, effects |
| 2 | Melody | Upper line Eb4 → F4 → G4 over an Abmaj7 bed | Four bed notes, sound colour, articulation, effects |
| 3 | Brightness | Higher harmonic groups gradually become more prominent | Notes, sound-colour template, articulation, effects |
| 4 | Sound colour | Rounded wood → hollow reed → glass organ, interpolated | Notes, overall energy, continuous articulation, fixed effects |
| 5 | Harmony | Abmaj7 → Cmaj7(#11)/G → Dbmaj9 → Bb13sus4 | Note weights, sound colour, continuous articulation, effects |

The colour labels describe spectral palettes within the existing harmonic voice, not recorded acoustic instruments. Brightness controls the balance between harmonic groups; colour changes the harmonic pattern within those groups. A reed palette strongly suppresses even harmonics; the glass palette favours harmonics 2, 6 and 12. All use the same continuing participant-A Synth.

R restarts the same raw fragment and processing state. Space pauses/resumes. Q or Ctrl+C stops and releases the receiver. Candidate keys switch and repeat the same fragment. The player prints exact note frequencies, weights, applied voicing times and the current mapped parameter. There is a keyboard trigger, no graphical button.

V enables/disables **reimagination**. I creates one external event; E ends it and D declines it. `--reimagination-source peer_B` attributes the explicit button event to debater B, targeting A. Reimagination means a request to reconsider the metric used to weigh arguments; it does not score argument quality or report successful reflection. It moves the current upper voices by up to two semitones and returns, while physiological colour/brightness/level continue. Melody and harmony are refused while reimagination owns the upper voices. A voice for B is not implemented.

```powershell
python -m src.sdd.mapping_audition --mode manual --candidate harmony
python -m src.sdd.mapping_audition --candidate colour --reimagination --reimagination-source peer_B
python -m src.sdd.mapping_audition --render-all
```

Manual uses the same low→middle→high→low trajectory; +/- sets a manual amount and T restores the trajectory. Replay and manual are distinct source labels. Live remains opt-in through `--mode live --stream-name obci_eeg1 --confirm-live-hardware`; the new palettes/progression still need live behavioral validation.

## How to hear loudness versus brightness

Loudness means the overall perceived level. Brightness means the relative prominence of higher harmonics: rounded/dark to sharp/clear. Listen to manual_level first: the chord should fade without moving its notes or changing the harmonic balance. Then hear manual_brightness at a comfortable, similar playback level: seek a change in edge/colour while overall measured energy stays close. Human hearing becomes less sensitive to bass and treble at low levels, so a quieter sound can also seem darker; perceived brightness and loudness cannot be perfectly separated by a meter.

In the previous menu, option 2 kept G2 and D3 while replacing A3 with B3 or C#4. These are G5(add9, no third), open G major, and G5(#11, no third). During the 1.35-second crossfade both upper notes can briefly coexist, explaining the impression that B was added and then disappeared. The new melody candidate keeps a complete Abmaj7 bed and moves a separate upper slot.

## Actual pitch material

| Chord | MIDI slots | Notes | Frequencies Hz, approximately |
| --- | --- | --- | --- |
| Abmaj7 | 44,51,55,60,63 | Ab2 Eb3 G3 C4 Eb4 | 103.826,155.563,195.998,261.626,311.127 |
| Cmaj7(#11)/G | 43,48,52,59,66 | G2 C3 E3 B3 F#4 | 97.999,130.813,164.814,246.942,369.994 |
| Dbmaj9 | 49,53,56,60,63 | Db3 F3 Ab3 C4 Eb4 | 138.591,174.614,207.652,261.626,311.127 |
| Bb13sus4 | 46,51,56,60,67 | Bb2 Eb3 Ab3 C4 G4 | 116.541,155.563,207.652,261.626,391.995 |

All five slots use weights 0.26,0.16,0.18,0.22,0.18; the sixth is inactive. Frequencies remain within the established 40–500 Hz interface. Discrete state changes retain hysteresis and at least 1.5 s hold; bank crossfade stays 1.35 s. Mapping smoothing increased from 0.35 to 0.9 s. There is no autonomous rhythm or added randomness. Old options 4/5/7 and 8 were removed from the active menu following listening feedback.

New audio: `reports/sdd_v1/mapping_audition/20261007/`, five manual + five real replay + three source comparisons. The old 19-WAV delivery and the selected G Lydian reference remain intact. The new sound changes are **awaiting human audition**, even after technical checks pass. Please report whether colour really sounds like a different sonic identity, whether harmony differs clearly from melody, source recognition for reimagination, and comfort/fatigue.
