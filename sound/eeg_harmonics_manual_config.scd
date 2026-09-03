// Centralized palette and audition configuration.
//
// Every audible parameter used by the harmonic field lives here. The core
// contains only synthesis topology, safety bounds, and the A-weighting formula.
// Presets remain manual choices; none is selected as "best" by the software.
(
    defaultPreset: \warm_organic,

    audition: (
        baseSeconds: 4.0,
        masterStageSeconds: 3.0,
        masterReturnSeconds: 4.0,
        spectrumStageSeconds: 4.0,
        groupStageSeconds: 4.0,
        finalBaseSeconds: 6.0,
        renderTailSeconds: 8.0,
        masterLow: 0.18,
        masterHigh: 0.90,
        warmGroups: [1.00, 0.34, 0.08, 0.02],
        brightGroups: [0.02, 0.08, 0.34, 1.00]
    ),

    presets: (
        warm_organic: (
            label: "Warm Organic",
            intent: "Warm, deep and soft; a grounded debate background without a dull blanket.",
            fundamental: 65.41,
            harmonicCount: 12,
            baseGroups: [1.00, 0.72, 0.30, 0.10],
            groupTrims: [1.00, 0.94, 0.80, 0.70],
            groupLoudnessComp: [1.50, 0.73, 0.75, 0.60],
            harmonicRollOff: 0.56,
            panPositions: [-0.55, 0.42, -0.26, 0.60, -0.46, 0.22,
                -0.62, 0.34, -0.16, 0.50, -0.36, 0.12],
            masterEnergy: 0.66,
            energyMinDb: -38.0, energyMaxDb: -17.0,
            controlLag: 1.60, energyLag: 1.00,
            stereoWidth: 0.58, saturationDrive: 1.35,
            delayMix: 0.018, delayTimeLeft: 0.023, delayTimeRight: 0.031,
            reverbMix: 0.30, reverbRoom: 42.0, reverbTime: 6.40,
            reverbDamping: 0.72, reverbInputBw: 0.62, reverbSpread: 24.0,
            reverbEarly: 0.20, reverbTail: 0.58,
            outputTrim: 0.72, limiterDb: -1.5,
            attack: 1.50, release: 4.00
        ),

        air_glass: (
            label: "Air Glass",
            intent: "Bright and spacious with a glassy upper field, restrained before sharpness.",
            fundamental: 82.41,
            harmonicCount: 12,
            baseGroups: [0.82, 0.88, 0.60, 0.34],
            groupTrims: [0.92, 1.00, 1.02, 0.94],
            groupLoudnessComp: [0.85, 1.12, 0.74, 1.28],
            harmonicRollOff: 0.38,
            panPositions: [-0.88, 0.72, -0.44, 0.92, -0.66, 0.36,
                -0.96, 0.58, -0.28, 0.82, -0.52, 0.20],
            masterEnergy: 0.62,
            energyMinDb: -39.0, energyMaxDb: -18.0,
            controlLag: 1.40, energyLag: 0.90,
            stereoWidth: 0.84, saturationDrive: 1.12,
            delayMix: 0.040, delayTimeLeft: 0.023, delayTimeRight: 0.031,
            reverbMix: 0.34, reverbRoom: 52.0, reverbTime: 7.20,
            reverbDamping: 0.60, reverbInputBw: 0.78, reverbSpread: 32.0,
            reverbEarly: 0.22, reverbTail: 0.62,
            outputTrim: 0.68, limiterDb: -1.5,
            attack: 1.35, release: 4.00
        ),

        dark_mineral: (
            label: "Dark Mineral",
            intent: "Dark and weighty with a subtle dry metallic edge, without low-mid mud.",
            fundamental: 58.27,
            harmonicCount: 12,
            baseGroups: [1.00, 0.48, 0.32, 0.16],
            groupTrims: [1.00, 0.82, 1.08, 0.96],
            groupLoudnessComp: [1.72, 0.66, 0.81, 0.77],
            harmonicRollOff: 0.50,
            panPositions: [-0.62, 0.28, -0.18, 0.70, -0.48, 0.14,
                -0.76, 0.46, -0.30, 0.58, -0.40, 0.08],
            masterEnergy: 0.64,
            energyMinDb: -38.0, energyMaxDb: -17.5,
            controlLag: 1.55, energyLag: 1.00,
            stereoWidth: 0.66, saturationDrive: 1.50,
            delayMix: 0.085, delayTimeLeft: 0.023, delayTimeRight: 0.031,
            reverbMix: 0.27, reverbRoom: 35.0, reverbTime: 5.70,
            reverbDamping: 0.48, reverbInputBw: 0.68, reverbSpread: 20.0,
            reverbEarly: 0.30, reverbTail: 0.50,
            outputTrim: 0.68, limiterDb: -1.5,
            attack: 1.45, release: 4.00
        )
    )
)
