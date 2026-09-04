# Organism v2 temporal novelty

`src/sonification/features.py` provides a reusable, stateful
`NoveltyEstimator`. Novelty here means numerical distance between the current
normalized feature vector and that stream's own recent past. It is not a
psychological or mental-state label.

Each input frame contains normalized energy, centroid, mobility, spectral
entropy, and delta/theta/alpha/beta band powers. With the defaults, each
estimator stores 32 prior frames: about eight seconds at 4 Hz. The current frame
is compared with that prior-only window before it is appended.

For each of the eight dimensions, the reference is its rolling median and the
scale is `1.4826 * MAD`. Exact repetition has zero MAD, so a `0.05` normalized
domain floor keeps an abrupt change measurable and finite. Standardized
distances are capped at `6.0`, averaged with equal weight, then mapped with
`1 - exp(-distance)` and clamped to `[0, 1]`. The scale and cap keep a single
dimension from dominating merely because of scale or one extreme value.

Warm-up lasts until the first 32 valid frames have filled the history and
returns `0.0`. Non-finite or non-numeric inputs raise `ValueError` without
changing state; finite out-of-range values are clamped. Every estimator owns its
deque, so callers must create one instance per independent channel or stream.
`reset()` clears only that instance.

This estimator remains disconnected from OSC, SuperCollider, real EEG/LSL, and
all pitch or musical mapping. Any later use as a musical control is an artistic
mapping, not an inference about a person's mind.
