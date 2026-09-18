// Centralized overrides for the synthetic-only organism v2 receiver.
// The fundamental remains the selected manual preset's fundamental. The upper
// group uses higher exact members of that same harmonic series, not a new pitch.
(
    basePreset: \warm_organic,
    harmonicGroups: [
        [1, 2, 3],
        [4, 5, 6],
        [7, 9, 12],
        [24, 36, 48]
    ],
    // Beta palette profiles affect group 4 only. `original_24_36_48` is the
    // exact pre-softening behavior: its ceiling is above every partial, its
    // tilt is flat, and its trim is unity. `softened` is the conservative v2
    // default. For human tuning, change only betaUpperPartialTiltDb: 0 is flat
    // and increasingly negative values progressively soften partials 36/48.
    betaProfile: \softened,
    betaProfiles: (
        original_24_36_48: (
            betaCeilingHz: 12000.0,
            betaUpperPartialTiltDb: 0.0,
            betaTrim: 1.0
        ),
        softened: (
            betaCeilingHz: 2700.0,
            betaUpperPartialTiltDb: -3.5,
            betaTrim: 0.90
        )
    ),
    // The voice bank is fixed-capacity and persistent. A voicing update may
    // activate fewer than six slots by setting the remaining weights to zero.
    voiceCapacity: 6,
    synthOverrides: (
        groupTrims: [1.00, 1.00, 1.00, 1.00],
        groupLoudnessComp: [1.00, 1.00, 1.00, 1.00],
        controlLag: 0.35,
        energyLag: 0.25,
        energyMinDb: -40.0,
        energyMaxDb: -18.0,
        voicingCrossfade: 1.35,
        voiceFrequencyMinHz: 40.0,
        voiceFrequencyMaxHz: 500.0,
        polyphonySafetyTrim: 0.82,
        saturationDrive: 1.25,
        reverbMix: 0.18,
        reverbTime: 3.00,
        reverbDamping: 0.68,
        outputTrim: 0.62,
        limiterDb: -1.5,
        attack: 0.50,
        release: 2.50,
        watchdogFade: 0.50
    ),
    watchdogTimeout: 2.0,
    invitationMessageMaxAge: 0.5,
    diagnosticInterval: 1.0
)
