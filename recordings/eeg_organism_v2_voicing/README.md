# Persistent voice-bank transition

`g_lydian_transition.wav` is a deterministic NRT safety render of one persistent
Synth: grounded G Lydian hold, crossfade to the brighter four-note voicing, then
crossfade back. This file exists for objective transition checks and morning
audition; sound quality is **PENDING HUMAN LISTENING**.

Objective metrics from `scripts/analyze_eeg_organism_v2_voicing_transition.py`:

- format: 48,000 Hz, stereo, 24-bit PCM;
- duration: 19.0013 seconds (912,064 frames);
- all decoded samples finite: yes;
- peak: 0.0576684 (-24.781 dBFS);
- maximum in the two 100 ms transition windows: 0.0546780;
- maximum adjacent-sample step in those windows: 0.00447774;
- samples at or above 0.999: none; clipped: no.

Static node audit: the NRT score contains one `/s_new`; pitch-bank preparation
and switching use only `/n_setn` and `/n_set`. The live receiver likewise owns
one Group and one Synth, and its voicing callback contains no Synth, Group,
Buffer, or Routine constructor.
