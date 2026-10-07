# Task 03 — real temporal novelty feature

Implement a reusable stateful novelty estimator, without OSC or sound wiring.

Novelty means distance between the current normalized feature vector and its
own recent past; it is not a psychological label.

- Accept normalized energy, centroid, mobility, spectral entropy, and band powers.
- Maintain independent history per estimator/stream.
- Use roughly eight seconds of prior frames at 4 Hz, excluding the current frame.
- Use a rolling median plus robust scale such as MAD/IQR so one dimension cannot
  dominate solely because of scale.
- Aggregate and map deterministically to finite `[0,1]` output.
- Define warm-up and zero-scale behavior.

Tests: stable repetition stays low; an abrupt multidimensional change peaks;
continued new state causes novelty to settle; one-channel histories do not leak;
all output is finite and reproducible. Document the algorithm and return to the
dispatcher.

