// Shared synthesis definition for the disconnected Harmonics manual prototype.
//
// Musical principle adapted from Stephen Whitmarsh / EEGsynth's 2019 and 2020
// Harmonics articles and the official EEGsynth akusmata patch: independently
// controlled, normalized EEG-band values are mapped to harmonic amplitudes of
// one oscillator. This is an original SuperCollider implementation; it does
// not contain or load EEGsynth, FieldTrip, or Redis code.
//
// Evaluating this file only defines a language-side factory function. It does
// not boot a server, create a node, register OSC, or connect live EEG.

~makeEegHarmonicFieldSynthDef = { |defName = \eegManualHarmonicField|
    SynthDef(defName, {
        |out = 0, gate = 1,
        fundamental = 73.42, harmonicCount = 12,
        group1 = 1.0, group2 = 0.70, group3 = 0.34, group4 = 0.16,
        masterEnergy = 0.72, controlLag = 1.25, energyLag = 0.90,
        stereoWidth = 0.62, saturationDrive = 1.25,
        reverbMix = 0.22, reverbRoom = 34, reverbTime = 4.8,
        reverbDamping = 0.58, outputTrim = 0.82,
        attack = 1.2, release = 2.8|
        var harmonicNumbers, pans, groups, groupTrims, partialTrims;
        var partials, perceptualWeights;
        var groupLevels, perceptualNorm, source, width, energy, energyAmp;
        var saturated, wet, signal, life;

        harmonicNumbers = (1..12);
        // Fixed alternating locations create width without detuning, delays,
        // stochastic motion, beating, triggers, or modulation.
        pans = [-0.82, 0.68, -0.38, 0.88, -0.68, 0.34,
            -0.92, 0.56, -0.22, 0.76, -0.52, 0.18];
        groups = [group1, group2, group3, group4].collect { |value|
            VarLag.kr(value.clip(0, 1), controlLag.clip(0.02, 8), warp: -4)
        };
        // Small fixed trims compensate measured group-to-group differences
        // introduced by the saturation/reverb chain. They do not move in time.
        groupTrims = [0.95, 1.10, 0.80, 1.18];
        width = VarLag.kr(stereoWidth.clip(0, 1), controlLag.clip(0.02, 8), warp: -4);

        // For 12 partials the four groups are 1-3, 4-6, 7-9, 10-12.
        // For 8 partials they become 1-2, 3-4, 5-6, 7-8.
        groupLevels = harmonicNumbers.collect { |harmonic|
            var groupFor12, groupFor8, useEight, active;
            groupFor12 = groups[((harmonic - 1) / 3).floor];
            groupFor8 = groups[(((harmonic - 1) / 2).floor).min(3)];
            useEight = harmonicCount <= 8;
            active = harmonic <= harmonicCount;
            Select.kr(useEight, [groupFor12, groupFor8]) * active;
        };
        partialTrims = harmonicNumbers.collect { |harmonic|
            var trimFor12, trimFor8, useEight;
            trimFor12 = groupTrims[((harmonic - 1) / 3).floor];
            trimFor8 = groupTrims[(((harmonic - 1) / 2).floor).min(3)];
            useEight = harmonicCount <= 8;
            Select.kr(useEight, [trimFor12, trimFor8]);
        };

        // Work in an approximate perceptual-energy domain. A gentle 1/sqrt(n)
        // voicing keeps the complete field grounded; inverse A-weighting then
        // compensates some low-frequency sensitivity loss (capped at +14 dB).
        // The L2 norm is calculated before that compensation so redistribution
        // preserves approximate A-weighted energy, not merely sample RMS.
        perceptualWeights = harmonicNumbers.collect { |harmonic, index|
            var frequency, f2, numerator, denominator, aDb, compensation;
            frequency = fundamental.clip(40, 160) * harmonic;
            f2 = frequency.squared;
            numerator = 12194.squared * f2.squared;
            denominator = (f2 + 20.6.squared)
                * ((f2 + 107.7.squared) * (f2 + 737.9.squared)).sqrt
                * (f2 + 12194.squared);
            aDb = (numerator / denominator).ampdb + 2.0;
            compensation = aDb.neg.dbamp.clip(0.35, 5.0);
            groupLevels[index] * harmonic.sqrt.reciprocal
                * compensation * partialTrims[index];
        };
        perceptualNorm = (harmonicNumbers.collect { |harmonic, index|
            (groupLevels[index] * harmonic.sqrt.reciprocal).squared
        }.sum + 1e-9).sqrt;

        partials = harmonicNumbers.collect { |harmonic, index|
            var oscillator, amplitude;
            amplitude = perceptualWeights[index] / perceptualNorm;
            oscillator = SinOsc.ar(fundamental.clip(40, 160) * harmonic, 0, amplitude);
            Pan2.ar(oscillator, pans[index] * width);
        };
        source = LeakDC.ar(Mix(partials));

        // ENERGY is strictly post-spectrum gain on a perceptual dB curve.
        energy = VarLag.kr(masterEnergy.clip(0, 1), energyLag.clip(0.02, 8), warp: -4);
        energyAmp = energy.linlin(0, 1, -38, -15).dbamp;
        source = source * energyAmp;

        // Gentle symmetrical saturation catches additive peaks without adding
        // an envelope or temporal articulation.
        saturated = (source * saturationDrive.clip(1, 2)).tanh
            / saturationDrive.clip(1, 2);

        // GVerb supplies a diffuse algorithmic stereo tail. Its controls are
        // manual/fixed during the tests and are never driven by EEG.
        wet = GVerb.ar(
            saturated.sum * 0.5,
            roomsize: reverbRoom.clip(8, 80),
            revtime: reverbTime.clip(0.5, 12),
            damping: reverbDamping.clip(0, 1),
            inputbw: 0.72,
            spread: 28,
            drylevel: 0,
            earlyreflevel: 0.24,
            taillevel: 0.62,
            maxroomsize: 80
        );
        signal = XFade2.ar(saturated, wet, (reverbMix.clip(0, 1) * 2) - 1);

        life = EnvGen.kr(
            Env.asr(attack.clip(0.05, 8), 1, release.clip(0.1, 15), curve: -4),
            gate,
            doneAction: 2
        );
        signal = Limiter.ar(signal * outputTrim.clip(0, 1) * life, (-1.5).dbamp, 0.01);
        Out.ar(out, signal);
    });
};
