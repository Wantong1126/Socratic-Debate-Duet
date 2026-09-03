// Shared synthesis definition for the disconnected Harmonics instrument.
//
// The musical mapping principle is adapted from Stephen Whitmarsh / EEGsynth.
// This is an original SuperCollider implementation; it does not load EEGsynth,
// FieldTrip, or Redis and does not claim to reproduce Verbos hardware timbre.
// Evaluating this file only defines a factory function.

~makeEegHarmonicFieldSynthDef = { |defName = \eegManualHarmonicField, preset|
    if(preset.isNil) { Error("A centralized harmonic preset is required.").throw };

    SynthDef(defName, {
        |out = 0, gate = 1|
        var harmonicNumbers, fundamental, harmonicCount, harmonicRollOff;
        var groupControls, groupTrims, groupLoudnessComp, panPositions;
        var groupLevels, partialLoudnessComp;
        var spectralShapes, perceptualWeights, perceptualNorm, partials;
        var controlLag, energyLag, width, source, delayed, delayMix;
        var energy, energyAmp, saturated, wet, signal, life;
        var saturationDrive, limiterDb;

        harmonicNumbers = (1..12);
        controlLag = NamedControl.kr(\controlLag, preset[\controlLag]).clip(0.02, 8);
        energyLag = NamedControl.kr(\energyLag, preset[\energyLag]).clip(0.02, 8);
        fundamental = VarLag.kr(
            NamedControl.kr(\fundamental, preset[\fundamental]),
            controlLag, warp: -4
        );
        harmonicCount = NamedControl.kr(\harmonicCount, preset[\harmonicCount]);
        harmonicRollOff = VarLag.kr(
            NamedControl.kr(\harmonicRollOff, preset[\harmonicRollOff]),
            controlLag, warp: -4
        );
        groupControls = NamedControl.kr(\groupAmplitudes, preset[\baseGroups]);
        groupTrims = NamedControl.kr(\groupTrims, preset[\groupTrims]);
        groupLoudnessComp = NamedControl.kr(
            \groupLoudnessComp,
            preset[\groupLoudnessComp]
        );
        panPositions = NamedControl.kr(\panPositions, preset[\panPositions]);

        groupControls = groupControls.collect { |value|
            VarLag.kr(value.clip(0, 1), controlLag, warp: -4)
        };
        groupTrims = groupTrims.collect { |value|
            VarLag.kr(value.clip(0.1, 2), controlLag, warp: -4)
        };
        groupLoudnessComp = groupLoudnessComp.collect { |value|
            VarLag.kr(value.clip(0.25, 2), controlLag, warp: -4)
        };
        panPositions = panPositions.collect { |value|
            VarLag.kr(value.clip(-1, 1), controlLag, warp: -4)
        };
        width = VarLag.kr(
            NamedControl.kr(\stereoWidth, preset[\stereoWidth]).clip(0, 1),
            controlLag, warp: -4
        );

        // 12 partials: 1-3, 4-6, 7-9, 10-12. Eight partials: pairs.
        groupLevels = harmonicNumbers.collect { |harmonic|
            var groupFor12, groupFor8, trimFor12, trimFor8, useEight, active;
            groupFor12 = groupControls[((harmonic - 1) / 3).floor];
            groupFor8 = groupControls[(((harmonic - 1) / 2).floor).min(3)];
            trimFor12 = groupTrims[((harmonic - 1) / 3).floor];
            trimFor8 = groupTrims[(((harmonic - 1) / 2).floor).min(3)];
            useEight = harmonicCount <= 8;
            active = Lag.kr(harmonic <= harmonicCount, controlLag);
            Select.kr(useEight,
                [groupFor12 * trimFor12, groupFor8 * trimFor8]) * active;
        };
        partialLoudnessComp = harmonicNumbers.collect { |harmonic|
            var compFor12, compFor8, useEight;
            compFor12 = groupLoudnessComp[((harmonic - 1) / 3).floor];
            compFor8 = groupLoudnessComp[(((harmonic - 1) / 2).floor).min(3)];
            useEight = harmonicCount <= 8;
            Select.kr(useEight, [compFor12, compFor8]);
        };

        // Trim and roll-off live inside the same perceptual-energy norm.
        spectralShapes = harmonicNumbers.collect { |harmonic, index|
            groupLevels[index] * (harmonic ** harmonicRollOff.neg)
        };
        perceptualNorm = (spectralShapes.collect(_.squared).sum + 1e-9).sqrt;

        // Capped inverse A-weighting is a pragmatic approximation, not a model
        // of human hearing.
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
            spectralShapes[index] * compensation
                * partialLoudnessComp[index] / perceptualNorm;
        };

        partials = harmonicNumbers.collect { |harmonic, index|
            Pan2.ar(
                SinOsc.ar(fundamental.clip(40, 160) * harmonic, 0,
                    perceptualWeights[index]),
                panPositions[index].clip(-1, 1) * width
            )
        };
        source = LeakDC.ar(Mix(partials));

        // Fixed cross-channel delay only: no feedback and no modulation.
        delayed = [
            DelayC.ar(source[1], 0.08,
                NamedControl.kr(\delayTimeLeft, preset[\delayTimeLeft]).clip(0.001, 0.08)),
            DelayC.ar(source[0], 0.08,
                NamedControl.kr(\delayTimeRight, preset[\delayTimeRight]).clip(0.001, 0.08))
        ];
        delayMix = VarLag.kr(
            NamedControl.kr(\delayMix, preset[\delayMix]).clip(0, 0.15),
            controlLag, warp: -4
        );
        source = XFade2.ar(source, delayed, (delayMix * 2) - 1);

        // Master energy is strictly post-spectrum gain.
        energy = VarLag.kr(
            NamedControl.kr(\masterEnergy, preset[\masterEnergy]).clip(0, 1),
            energyLag, warp: -4
        );
        energyAmp = energy.linlin(
            0, 1,
            NamedControl.kr(\energyMinDb, preset[\energyMinDb]),
            NamedControl.kr(\energyMaxDb, preset[\energyMaxDb])
        ).dbamp;
        source = source * energyAmp;

        saturationDrive = VarLag.kr(
            NamedControl.kr(\saturationDrive, preset[\saturationDrive]),
            controlLag, warp: -4
        ).clip(1, 2);
        saturated = (source * saturationDrive).tanh / saturationDrive;

        wet = GVerb.ar(
            saturated.sum * 0.5,
            roomsize: NamedControl.kr(\reverbRoom, preset[\reverbRoom]).clip(8, 80),
            revtime: NamedControl.kr(\reverbTime, preset[\reverbTime]).clip(0.5, 12),
            damping: NamedControl.kr(\reverbDamping, preset[\reverbDamping]).clip(0, 1),
            inputbw: NamedControl.kr(\reverbInputBw, preset[\reverbInputBw]).clip(0.1, 1),
            spread: NamedControl.kr(\reverbSpread, preset[\reverbSpread]).clip(0, 43),
            drylevel: 0,
            earlyreflevel: NamedControl.kr(\reverbEarly, preset[\reverbEarly]).clip(0, 1),
            taillevel: NamedControl.kr(\reverbTail, preset[\reverbTail]).clip(0, 1),
            maxroomsize: 80
        );
        signal = XFade2.ar(
            saturated, wet,
            (VarLag.kr(
                NamedControl.kr(\reverbMix, preset[\reverbMix]).clip(0, 1),
                controlLag, warp: -4
            ) * 2) - 1
        );

        life = EnvGen.kr(
            Env.asr(
                NamedControl.kr(\attack, preset[\attack]).clip(0.05, 8), 1,
                NamedControl.kr(\release, preset[\release]).clip(0.1, 15),
                curve: -4
            ),
            gate,
            doneAction: 2
        );
        limiterDb = NamedControl.kr(\limiterDb, preset[\limiterDb]).clip(-12, -0.1);
        signal = Limiter.ar(
            signal * VarLag.kr(
                NamedControl.kr(\outputTrim, preset[\outputTrim]).clip(0, 1),
                controlLag, warp: -4
            ) * life,
            limiterDb.dbamp, 0.01
        );
        Out.ar(out, signal);
    });
};
