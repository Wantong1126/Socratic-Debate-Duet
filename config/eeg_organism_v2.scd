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
    synthOverrides: (
        groupTrims: [1.00, 1.00, 1.00, 1.00],
        groupLoudnessComp: [1.00, 1.00, 1.00, 1.00],
        controlLag: 0.35,
        energyLag: 0.25,
        energyMinDb: -40.0,
        energyMaxDb: -18.0,
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
    diagnosticInterval: 1.0
)
