# Task 02 — real spectral entropy feature

Implement a reusable pure spectral-entropy function in the appropriate
`src/sonification` feature module. Do not connect it to OSC or sound yet.

- Input: one cleaned EEG window and sample rate.
- Analyze only 0.5–45 Hz using the project's existing NumPy/SciPy conventions.
- Normalize PSD bins to probabilities and compute
  `-sum(p*log(p))/log(number_of_valid_bins)`.
- Return a finite value clamped to `[0,1]`.
- Define behavior for flatline, too-short, NaN, and Inf input.
- Keep it channel-independent so separate estimator instances can be used later.

Tests must show: a stable sinusoid has lower entropy than broadband or a dense
multi-frequency signal; amplitude scaling barely changes entropy; invalid input
is handled deterministically. Add a short plain-language doc and return to the
dispatcher.

