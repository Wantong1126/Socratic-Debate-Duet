# Organism v2 persistent voice bank

Task 05 adds manual pitch capacity without connecting the offline voicing
decision engine or any real EEG source. Subjective transition and timbre quality
remain **PENDING HUMAN LISTENING**.

## Boundary and protocol

The original descriptor packet remains `/eeg/organism/v2/frame` with exactly its
nine values. A separate compatible message is now available:

```text
/eeg/organism/v2/voicing
frequency_1_hz ... frequency_6_hz weight_1 ... weight_6
```

All 12 values are finite. Frequencies are clamped to 40-500 Hz and weights to
0-1. Unused slots retain a safe frequency and have weight zero. At least one
slot must be active. `src/sonification/protocol.py` owns this contract; it does
not import or call `src/sonification/voicing.py`.

Task 06 retains that 500 Hz ceiling and bounds the integrated G Lydian decision
engine to MIDI 71 (493.88 Hz). No integrated note is therefore altered by the
protocol clamp.

## Persistent synthesis behavior

`sound/eeg_harmonic_field_v2_core.scd` still compiles one continuous Synth. It
contains two fixed internal banks, each with six pitch slots. Every slot uses
the same four exact harmonic groups, A-weight compensation, beta softening,
stereo placement, saturation, reverb, and limiter as the approved v2 field.
To fit the fixed banks into a default already-running scsynth without changing
server options, each group's exact partial amplitudes are compiled into one
small local wavetable. The group's stereo position is the amplitude-weighted
mean of its former per-partial positions; this is the Task 05 implementation
adaptation, while the harmonic numbers and group response stay unchanged.

The receiver writes a new voicing into the inactive bank and then changes one
bank-select control. `VarLag` plus `XFade2` makes a finite equal-power 1.35-second
crossfade, so frequency controls never glide while their bank is audible. A new
packet received before that transition completes is ignored rather than queued
or written into the fading bank. The update callback creates no Synth, Group,
Buffer, or Routine. Weighted voices are
L2-normalized, followed by a conservative `polyphonySafetyTrim` of 0.82, the
existing non-finite guard and -1.5 dB limiter, and a final bound at that same
ceiling. Capacity six does not imply six sounding notes.

The local wavetables are part of the one Synth at construction; no server Buffer
is allocated by an update. The existing watchdog multiplies the complete
post-effect output, and graceful stop releases the same single Synth and
dedicated Group. Neither path closes SuperDirt or scsynth.

## Manual audition

Start the existing server and evaluate the unchanged receiver entry point:

```supercollider
"D:/sdd-sonification/sound/eeg_organism_v2_receiver.scd".load;
```

From PowerShell in `D:\sdd-sonification`, send four six-second holds alternating
the fixed `G2-D3-A3` and `C#3-F#3-C#4-F#4` G Lydian voicings:

```powershell
.\.venv\Scripts\python.exe -m src.sonification.manual_voicing_demo
```

The sender also refreshes one unchanged synthetic nine-value bed frame at 4 Hz
so the existing watchdog stays active. Those fixed values do not choose pitch;
only the two hard-coded manual voicing packets do. Use `--dry-run` for protocol
inspection without opening a socket. After the demo, let the watchdog fade or
use the existing stop command:

```powershell
.\.venv\Scripts\python.exe -m src.sonification.synthetic_demo --mode stop
```

## Offline evidence

```powershell
.\scripts\render_eeg_organism_v2_voicing_transition.ps1
.\.venv\Scripts\python.exe .\scripts\analyze_eeg_organism_v2_voicing_transition.py
```

The NRT score creates exactly one Synth, alternates A -> B -> A with `/n_setn`
and `/n_set`, then releases it. The objective metrics and listening status are
recorded beside the 48 kHz/24-bit stereo WAV under
`recordings/eeg_organism_v2_voicing`.
