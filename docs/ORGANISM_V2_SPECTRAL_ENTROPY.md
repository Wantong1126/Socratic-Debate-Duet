# Organism v2 spectral entropy

`src/sonification/features.py` now provides one pure `spectral_entropy`
function. It measures how concentrated or spread out the power spectrum is in
one already-cleaned EEG channel window. It does not acquire EEG, combine
channels, normalize a person, send OSC, or control sound.

The function uses SciPy Welch PSD estimates from 0.5 through 45 Hz. It converts
the valid PSD bins to probabilities and calculates:

```text
-sum(p * log(p)) / log(number of valid bins)
```

A stable sinusoid therefore tends toward a lower result than broadband or
dense multi-frequency input. Overall amplitude has almost no effect because
the result describes spectral distribution, not energy. Any future mapping of
this descriptor to music will be an artistic choice, not a mental-state
inference.

The expected window is at least two seconds long, which gives 0.5 Hz Welch bins.
Non-numeric, non-1D, non-finite, too-short, flatline, invalid-sample-rate, and
zero-band-power input deterministically returns `0.0`. Normal results are finite
and clamped to `[0, 1]`.

This feature remains deliberately disconnected from the v2 OSC frame and the
SuperCollider instrument pending later integration work.
