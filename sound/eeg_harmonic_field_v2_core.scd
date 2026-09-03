// Targeted v2 variant of the tested additive harmonic field.
//
// The topology remains one continuous exact-harmonic SinOsc bank, fixed stereo
// placement/delay, restrained saturation, GVerb, and limiter. Differences from
// the historical manual core are confined to configurable exact harmonic groups,
// normalization after perceptual weighting, and a post-effect transportAlive
// watchdog control. Evaluating this file only defines a factory function.

~makeEegOrganismV2HarmonicFieldSynthDef = {
    |defName = \eegOrganismV2HarmonicField, preset|
    var harmonicGroups, harmonicNumbers, groupIndexes;
    if(preset.isNil) { Error("A centralized v2 harmonic preset is required.").throw };
    harmonicGroups = preset[\harmonicGroups];
    if(harmonicGroups.isNil or: { harmonicGroups.size != 4 }) {
        Error("The v2 preset must define exactly four harmonicGroups.").throw
    };
    harmonicNumbers = harmonicGroups.flat;
    groupIndexes = harmonicGroups.collect { |group, index|
        Array.fill(group.size, index)
    }.flat;

    SynthDef(defName, {
        |out = 0, gate = 1|
        var fundamental, harmonicRollOff, controlLag, energyLag;
        var groupControls, groupTrims, groupLoudnessComp, panPositions;
        var weightedShapes, perceptualNorm, partials, source, delayed, delayMix;
        var energy, energyAmp, saturated, wet, signal, life, transportAlive;
        var saturationDrive, limiterDb;

        fundamental = NamedControl.kr(
            \fundamental, preset[\fundamental]
        ).clip(40, 160);
        harmonicRollOff = NamedControl.kr(
            \harmonicRollOff, preset[\harmonicRollOff]
        ).clip(0, 2);
        controlLag = NamedControl.kr(
            \controlLag, preset[\controlLag]
        ).clip(0.02, 8);
        energyLag = NamedControl.kr(
            \energyLag, preset[\energyLag]
        ).clip(0.02, 8);
        groupControls = NamedControl.kr(
            \groupAmplitudes, preset[\baseGroups]
        ).collect { |value|
            VarLag.kr(value.clip(0, 1), controlLag, warp: -4)
        };
        groupTrims = NamedControl.kr(
            \groupTrims, preset[\groupTrims]
        ).collect { |value| value.clip(0.1, 2) };
        groupLoudnessComp = NamedControl.kr(
            \groupLoudnessComp, preset[\groupLoudnessComp]
        ).collect { |value| value.clip(0.25, 2) };
        panPositions = NamedControl.kr(
            \panPositions, preset[\panPositions]
        ).collect { |value| value.clip(-1, 1) };

        // Normalize the final perceptually weighted amplitudes, so an isolated
        // band changes spectral location much more than aggregate level.
        weightedShapes = harmonicNumbers.collect { |harmonic, index|
            var frequency, f2, numerator, denominator, aDb, compensation;
            var groupIndex;
            groupIndex = groupIndexes[index];
            frequency = fundamental * harmonic;
            f2 = frequency.squared;
            numerator = 12194.squared * f2.squared;
            denominator = (f2 + 20.6.squared)
                * ((f2 + 107.7.squared) * (f2 + 737.9.squared)).sqrt
                * (f2 + 12194.squared);
            aDb = (numerator / denominator).ampdb + 2.0;
            compensation = aDb.neg.dbamp.clip(0.35, 5.0);
            groupControls[groupIndex]
                * groupTrims[groupIndex]
                * groupLoudnessComp[groupIndex]
                * (harmonic ** harmonicRollOff.neg)
                * compensation;
        };
        perceptualNorm = (weightedShapes.collect(_.squared).sum + 1e-9).sqrt;

        partials = harmonicNumbers.collect { |harmonic, index|
            Pan2.ar(
                SinOsc.ar(
                    fundamental * harmonic,
                    0,
                    weightedShapes[index] / perceptualNorm
                ),
                panPositions[index].clip(-1, 1)
                    * NamedControl.kr(
                        \stereoWidth, preset[\stereoWidth]
                    ).clip(0, 1)
            )
        };
        source = LeakDC.ar(Mix(partials));

        // Fixed, feedback-free and unmodulated cross-channel delay.
        delayed = [
            DelayC.ar(source[1], 0.08,
                NamedControl.kr(
                    \delayTimeLeft, preset[\delayTimeLeft]
                ).clip(0.001, 0.08)),
            DelayC.ar(source[0], 0.08,
                NamedControl.kr(
                    \delayTimeRight, preset[\delayTimeRight]
                ).clip(0.001, 0.08))
        ];
        delayMix = NamedControl.kr(
            \delayMix, preset[\delayMix]
        ).clip(0, 0.15);
        source = XFade2.ar(source, delayed, (delayMix * 2) - 1);

        // Energy remains strictly post-spectrum and pre-effect.
        energy = VarLag.kr(
            NamedControl.kr(
                \masterEnergy, preset[\masterEnergy]
            ).clip(0, 1),
            energyLag,
            warp: -4
        );
        energyAmp = energy.linlin(
            0, 1,
            NamedControl.kr(\energyMinDb, preset[\energyMinDb]),
            NamedControl.kr(\energyMaxDb, preset[\energyMaxDb])
        ).dbamp;
        source = source * energyAmp;

        saturationDrive = NamedControl.kr(
            \saturationDrive, preset[\saturationDrive]
        ).clip(1, 2);
        saturated = (source * saturationDrive).tanh / saturationDrive;
        wet = GVerb.ar(
            saturated.sum * 0.5,
            roomsize: NamedControl.kr(
                \reverbRoom, preset[\reverbRoom]
            ).clip(8, 80),
            revtime: NamedControl.kr(
                \reverbTime, preset[\reverbTime]
            ).clip(0.5, 12),
            damping: NamedControl.kr(
                \reverbDamping, preset[\reverbDamping]
            ).clip(0, 1),
            inputbw: NamedControl.kr(
                \reverbInputBw, preset[\reverbInputBw]
            ).clip(0.1, 1),
            spread: NamedControl.kr(
                \reverbSpread, preset[\reverbSpread]
            ).clip(0, 43),
            drylevel: 0,
            earlyreflevel: NamedControl.kr(
                \reverbEarly, preset[\reverbEarly]
            ).clip(0, 1),
            taillevel: NamedControl.kr(
                \reverbTail, preset[\reverbTail]
            ).clip(0, 1),
            maxroomsize: 80
        );
        signal = XFade2.ar(
            saturated,
            wet,
            (NamedControl.kr(
                \reverbMix, preset[\reverbMix]
            ).clip(0, 1) * 2) - 1
        );

        life = EnvGen.kr(
            Env.asr(
                NamedControl.kr(\attack, preset[\attack]).clip(0.05, 8),
                1,
                NamedControl.kr(\release, preset[\release]).clip(0.1, 15),
                curve: -4
            ),
            gate,
            doneAction: 2
        );
        transportAlive = LagUD.kr(
            NamedControl.kr(\transportAlive, 0).clip(0, 1),
            0.05,
            NamedControl.kr(
                \watchdogFade, preset[\watchdogFade]
            ).clip(0.05, 4)
        );
        limiterDb = NamedControl.kr(
            \limiterDb, preset[\limiterDb]
        ).clip(-12, -0.1);
        signal = Limiter.ar(
            signal
                * NamedControl.kr(
                    \outputTrim, preset[\outputTrim]
                ).clip(0, 1)
                * transportAlive
                * life,
            limiterDb.dbamp,
            0.01
        );
        Out.ar(out, signal);
    });
};
