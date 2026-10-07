# Task 04 — offline G Lydian voicing decisions

Build a pure Python music-decision module. It must produce data/text only; do not
change OSC or SuperCollider.

Pitch material is exactly G Lydian: `G A B C# D E F#`. Do not use a fixed chord,
fixed triad, or fixed number of active notes. Provide up to six capacity slots
with variable note weights/density.

Mapping:

- centroid targets register;
- spectral entropy targets consonance versus controlled tension;
- novelty controls common-tone retention, bounded voice-leading distance,
  change probability, and selection temperature;
- mobility controls decision/hold timing;
- energy primarily remains presence, with only a secondary density influence.

Generate candidate voicings and score scale membership, interval consonance or
tension, register, spacing, common tones, and voice-leading distance. Low
novelty should preserve pitches and move minimally; high novelty may move more
and less regularly but must remain coherent and bounded. High entropy may allow
seconds, sevenths, or the Lydian tritone; it must not become arbitrary randomness.

Return a typed decision containing MIDI notes, names, frequencies, weights,
hold duration, scores, and a short machine-generated reason. Use a deterministic
seed for tests. Produce JSON traces for calm-stable, bright-stable, tense-stable,
and active-novel scenarios. Add tests and return to the dispatcher.

