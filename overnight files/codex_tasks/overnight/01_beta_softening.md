# Task 01 — soften beta safely

Change only the v2 beta palette. Trace its partial weights, trim, filtering,
saturation, reverb, and limiter. Add centralized, documented config controls for
beta ceiling and upper-partial tilt/softening.

Target: beta remains clearly brighter than alpha but loses the narrow
whistle/alarm quality around the 24/36/48 partials. Prefer relative partial
weights, conservative trim, and gentle roll-off. Do not add noise, detune,
randomness, rhythm, or a new pitch. Do not alter transport or other mappings.

Make a conservative softened setting the v2 default while retaining the old
setting as a named comparison profile. Render matched-condition old/softened
beta HIGH and beta LOW WAVs. Report RMS, peak, centroid, 1.5–4 kHz energy, and a
perceptual/A-weighted loudness proxy. Ensure finite output and no clipping.

Add focused tests and document the single human tuning knob. Mark the final
choice `PENDING HUMAN LISTENING` and return to the dispatcher.

