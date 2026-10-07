# Task 05 — manual persistent multi-voice instrument

Extend the v2 SuperCollider instrument to provide up to six persistent pitch
capacity slots, but do not connect the Python voicing decision engine yet.

- Active voice count/weights may vary; capacity six does not mean six notes must sound.
- Every active voice uses the approved harmonic-field timbre and shared band controls.
- Add one compatible, separately named v2 voicing OSC message; preserve the
  existing nine-value descriptor frame unchanged.
- Pitch changes must create no new server nodes and no unintended glissando,
  click, gain jump, or command accumulation.
- Use two internal banks or an equivalent click-free crossfade strategy.
- Normalize gain safely as weighted polyphony changes.
- Watchdog and stop must silence/release the complete instrument without closing
  SuperDirt/scsynth.

Provide a manual sender that alternates two clearly different G Lydian voicings.
Render transitions, inspect node stability, finite samples, peak, duration, and
clipping. Do not connect descriptors. Mark sound quality `PENDING HUMAN LISTENING`
and return to the dispatcher.

