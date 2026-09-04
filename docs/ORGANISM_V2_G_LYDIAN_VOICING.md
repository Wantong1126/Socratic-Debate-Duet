# Organism v2 offline G Lydian voicing decisions

`src/sonification/voicing.py` is a pure Python, data-only music-decision
module. It sends no OSC and changes no SuperCollider state. Its pitch material
is exactly G Lydian: G, A, B, C#, D, E, and F#. A decision activates between
two and six of six capacity slots; it is not a fixed chord, triad, or voice
count.

The inputs are five normalized descriptors. These are artistic musical
mappings, not inferences about mental state:

- centroid sets the target mean register inside the persistent bank's tested
  40-500 Hz fundamental range;
- spectral entropy sets a consonance-to-controlled-tension target, allowing
  scale seconds, sevenths, and the G-C# Lydian tritone at its high end;
- novelty sets change probability, common-tone and voice-leading priorities,
  a hard motion bound, and seeded selection temperature;
- mobility maps to the hold duration from 12 seconds down to 2 seconds;
- energy contributes no amplitude here and has only a secondary, at-most-about
  one-slot influence on target density. Master presence remains outside this
  module.

For each decision the engine enumerates nearby G Lydian candidates, rejects
over-wide spacing and novelty-dependent motion violations, then scores scale
membership, interval consonance/tension fit, register, spacing, common tones,
voice-leading distance, and density. Low novelty normally retains the current
pitches and, when it changes, strongly rewards common tones and small motion.
High novelty raises the bounded change probability and seeded selection
temperature, but candidates remain in-scale, register-local, width-limited,
and voice-leading-limited.

`VoicingDecision` contains MIDI notes, octave-qualified names, equal-tempered
frequencies, relative weights that sum to one, hold duration, named score
components, and a machine-generated reason. Relative weights deliberately do
not encode energy, so a later integration can keep energy as master presence.

Task 06's integration audit found that the earlier offline ceiling (MIDI 91)
exceeded the persistent bank's 500 Hz protocol ceiling. Candidate generation is
therefore now bounded at MIDI 71 (B4, 493.88 Hz), and the centroid target spans
roughly the lower third through upper fourth octave. This is a compatibility
correction: it avoids clamping distinct G Lydian notes onto 500 Hz and keeps
their 24/36/48 upper partials within the bank's intended safety design.

Generate the four deterministic audit traces with Python 3.12:

```powershell
.venv\Scripts\python.exe -m src.sonification.voicing `
  --output-dir traces/organism_v2_g_lydian `
  --seed 20260904 --decisions 12
```

The output files are `calm-stable.json`, `bright-stable.json`,
`tense-stable.json`, and `active-novel.json`. They are decisions and scores for
inspection only; they are not recordings and are not connected to live EEG.
