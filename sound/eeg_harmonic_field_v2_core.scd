// Targeted v2 variant of the tested additive harmonic field.
//
// The topology remains one continuous exact-harmonic oscillator field, fixed stereo
// placement/delay, restrained saturation, GVerb, and limiter. The v2 core has
// two internal six-slot banks so pitch material can crossfade without creating
// nodes or changing the approved timbre. Evaluating this file only defines a
// factory function.

~makeEegOrganismV2HarmonicFieldSynthDef = {
    |defName = \eegOrganismV2HarmonicField, preset|
    var harmonicGroups, harmonicNumbers, groupIndexes, betaHarmonics;
    var betaLowestHarmonic, betaHighestHarmonic;
    var voiceCapacity, defaultVoiceFrequencies, defaultVoiceWeights;
    var weightedShapes, groupWavetables, groupEnergyScales, groupPanPositions;
    var wavetableSignalSize, maximumHarmonic;
    var colourWavetables, colourEnergyScales;
    if(preset.isNil) { Error("A centralized v2 harmonic preset is required.").throw };
    harmonicGroups = preset[\harmonicGroups];
    if(harmonicGroups.isNil or: { harmonicGroups.size != 4 }) {
        Error("The v2 preset must define exactly four harmonicGroups.").throw
    };
    harmonicNumbers = harmonicGroups.flat;
    betaHarmonics = harmonicGroups[3];
    betaLowestHarmonic = betaHarmonics.minItem;
    betaHighestHarmonic = betaHarmonics.maxItem;
    voiceCapacity = preset[\voiceCapacity] ? 6;
    if(voiceCapacity != 6) {
        Error("The organism v2 voiceCapacity must remain exactly six.").throw
    };
    defaultVoiceFrequencies = Array.fill(voiceCapacity, preset[\fundamental]);
    defaultVoiceWeights = [1.0] ++ Array.fill(voiceCapacity - 1, 0.0);
    groupIndexes = harmonicGroups.collect { |group, index|
        Array.fill(group.size, index)
    }.flat;
    wavetableSignalSize = 128;
    maximumHarmonic = harmonicNumbers.maxItem;

    // Compile the approved harmonic envelope into four small persistent local
    // wavetables. This keeps the graph narrow enough for an already-running
    // default scsynth while preserving every configured exact harmonic number.
    weightedShapes = harmonicNumbers.collect { |harmonic, index|
        var frequency, f2, numerator, denominator, aDb, compensation;
        var groupIndex, betaShape, betaPosition, ceilingRatio, betaTrim;
        groupIndex = groupIndexes[index];
        frequency = preset[\fundamental] * harmonic;
        f2 = frequency.squared;
        numerator = 12194.squared * f2.squared;
        denominator = (f2 + 20.6.squared)
            * ((f2 + 107.7.squared) * (f2 + 737.9.squared)).sqrt
            * (f2 + 12194.squared);
        aDb = (numerator / denominator).ampdb + 2.0;
        compensation = aDb.neg.dbamp.clip(0.35, 5.0);
        betaShape = if(groupIndex == 3) {
            betaPosition = (harmonic - betaLowestHarmonic)
                / (betaHighestHarmonic - betaLowestHarmonic).max(1);
            ceilingRatio = (frequency / preset[\betaCeilingHz]).max(1.0);
            (betaPosition * preset[\betaUpperPartialTiltDb]).dbamp
                * ceilingRatio.squared.reciprocal
        } {
            1.0
        };
        betaTrim = if(groupIndexes[index] == 3) { preset[\betaTrim] } { 1.0 };
        preset[\groupTrims][groupIndex]
            * preset[\groupLoudnessComp][groupIndex]
            * (harmonic ** preset[\harmonicRollOff].neg)
            * compensation
            * betaShape
            * betaTrim;
    };
    if(weightedShapes.collect(_.squared).sum <= 0) {
        Error("The organism v2 harmonic envelope must have nonzero energy.").throw
    };
    groupWavetables = harmonicGroups.collect { |group|
        var amplitudes, signal;
        amplitudes = Array.fill(maximumHarmonic, 0.0);
        group.do { |harmonic|
            amplitudes[harmonic - 1] = weightedShapes[harmonicNumbers.indexOf(harmonic)]
        };
        // Instance sineFill deliberately avoids class-side peak normalization;
        // groupEnergyScales below is therefore the single level normalizer.
        signal = Signal.newClear(wavetableSignalSize);
        signal.sineFill(amplitudes);
        signal.asWavetable;
    };
    groupEnergyScales = harmonicGroups.collect { |group|
        (group.collect { |harmonic|
            weightedShapes[harmonicNumbers.indexOf(harmonic)].squared
        }.sum + 1e-9).sqrt
    };
    groupPanPositions = harmonicGroups.collect { |group|
        var indexes, weights, weightSum;
        indexes = group.collect { |harmonic| harmonicNumbers.indexOf(harmonic) };
        weights = indexes.collect { |index| weightedShapes[index].abs };
        weightSum = weights.sum.max(1e-9);
        indexes.collect { |index, localIndex|
            preset[\panPositions][index] * weights[localIndex]
        }.sum / weightSum
    };

    // Optional audition palettes use the same notes, oscillator field and
    // persistent Synth. The legacy factory path retains its original graph.
    if(preset[\auditionColours] ? false) {
        var shapes;
        shapes = [1, 2].collect { |palette|
            harmonicNumbers.collect { |harmonic, index|
                var multiplier;
                multiplier = if(palette == 1) {
                    if(harmonic.odd) { 1.0 } { 0.015 }
                } {
                    if([2, 6, 12].includes(harmonic)) { 3.0 } { 0.12 }
                };
                weightedShapes[index] * multiplier * preset[\baseGroups][groupIndexes[index]];
            }
        };
        colourWavetables = shapes.collect { |shape|
            var amplitudes, signal;
            amplitudes = Array.fill(maximumHarmonic, 0.0);
            harmonicNumbers.do { |harmonic, index| amplitudes[harmonic-1] = shape[index] };
            signal = Signal.newClear(wavetableSignalSize);
            signal.sineFill(amplitudes);
            signal.asWavetable;
        };
        colourEnergyScales = shapes.collect { |shape|
            (shape.collect(_.squared).sum + 1e-9).sqrt
        };
    };

    SynthDef(defName, {
        |out = 0, gate = 1|
        var controlLag, energyLag, groupControls, stereoWidth, invitationAmount;
        var invitationDiagnosticDepth, invitationDiagnosticGain;
        var musicEnabled, musicGroups, musicEcho, musicPattern, musicPulse, rhythmBlend, invitationShift;
        var colourBuffers, colourPosition, colourWeights;
        var wavetableBuffers, groupNorm, makeBank;
        var sourceA, sourceB, bankPosition;
        var source, delayed, delayMix;
        var energy, energyAmp, saturated, wet, signal, life, transportAlive;
        var saturationDrive, limiterDb;
        var voiceFrequenciesA, voiceFrequenciesB, voiceWeightsA, voiceWeightsB;
        var voiceFrequencyMinHz, voiceFrequencyMaxHz, polyphonySafetyTrim;

        controlLag = NamedControl.kr(
            \controlLag, preset[\controlLag]
        ).clip(0.02, 8);
        energyLag = NamedControl.kr(
            \energyLag, preset[\energyLag]
        ).clip(0.02, 8);
        musicEnabled = NamedControl.kr(\musicEnabled, 0).clip(0, 1);
        musicGroups = NamedControl.kr(\musicGroups, preset[\baseGroups]);
        groupControls = NamedControl.kr(
            \groupAmplitudes, preset[\baseGroups]
        ).collect { |value, index|
            (VarLag.kr(value.clip(0, 1), controlLag, warp: -4) * (1-musicEnabled))
                + (Lag.kr(musicGroups[index].clip(0, 1), controlLag) * musicEnabled)
        };
        stereoWidth = NamedControl.kr(
            \stereoWidth, preset[\stereoWidth]
        ).clip(0, 1);
        invitationAmount = NamedControl.kr(\invitationAmount, 0).clip(0, 1);
        invitationShift = (Lag.kr(invitationAmount, 0.05)
            * NamedControl.kr(\invitationHarmonyDepth, 0).clip(0, 2)).midiratio;
        invitationDiagnosticDepth = NamedControl.kr(
            \invitationDiagnosticDepth, 0
        ).clip(0, 0.9);
        invitationDiagnosticGain = 1 - (
            invitationAmount * invitationDiagnosticDepth
        );
        voiceFrequencyMinHz = NamedControl.kr(
            \voiceFrequencyMinHz, preset[\voiceFrequencyMinHz]
        ).clip(20, 200);
        voiceFrequencyMaxHz = NamedControl.kr(
            \voiceFrequencyMaxHz, preset[\voiceFrequencyMaxHz]
        ).clip(200, 2000);
        polyphonySafetyTrim = NamedControl.kr(
            \polyphonySafetyTrim, preset[\polyphonySafetyTrim]
        ).clip(0.5, 1.0);
        voiceFrequenciesA = NamedControl.kr(
            \voiceFrequenciesA, defaultVoiceFrequencies
        ).collect { |value, index|
            (value * if(index >= 2) { invitationShift } { 1 }).clip(voiceFrequencyMinHz, voiceFrequencyMaxHz)
        };
        voiceFrequenciesB = NamedControl.kr(
            \voiceFrequenciesB, defaultVoiceFrequencies
        ).collect { |value, index|
            (value * if(index >= 2) { invitationShift } { 1 }).clip(voiceFrequencyMinHz, voiceFrequencyMaxHz)
        };
        voiceWeightsA = NamedControl.kr(
            \voiceWeightsA, defaultVoiceWeights
        ).collect { |value| value.clip(0, 1) };
        voiceWeightsB = NamedControl.kr(
            \voiceWeightsB, defaultVoiceWeights
        ).collect { |value| value.clip(0, 1) };
        wavetableBuffers = groupWavetables.collect { |wavetable|
            LocalBuf.newFrom(wavetable)
        };
        if(colourWavetables.notNil) {
            colourBuffers = colourWavetables.collect { |wavetable| LocalBuf.newFrom(wavetable) };
            colourPosition = Lag.kr(NamedControl.kr(\musicColour, 0).clip(0,2), 0.9);
            colourWeights = [
                (1-colourPosition).clip(0,1),
                (1-(colourPosition-1).abs).clip(0,1),
                (colourPosition-1).clip(0,1)
            ];
        };
        groupNorm = (groupControls.collect { |value, index|
            (value * groupEnergyScales[index]).squared
        }.sum + 1e-9).sqrt;
        makeBank = { |frequencies, weights|
            var weightNorm, groups, colourSources;
            // L2 normalization holds aggregate signal energy approximately
            // steady as weighted polyphony changes. The fixed safety trim and
            // final limiter cover correlated worst cases.
            weightNorm = (weights.collect(_.squared).sum + 1e-9).sqrt;
            groups = wavetableBuffers.collect { |buffer, index|
                var voiceMix;
                voiceMix = Mix(Osc.ar(
                    buffer,
                    frequencies,
                    0,
                    weights / weightNorm
                ));
                Pan2.ar(
                    voiceMix
                        * groupControls[index]
                        / groupNorm,
                    groupPanPositions[index].clip(-1, 1) * stereoWidth
                )
            };
            if(colourBuffers.notNil) {
                colourSources = colourBuffers.collect { |buffer, palette|
                    var voiceMix;
                    voiceMix = Mix(Osc.ar(buffer, frequencies, 0, weights/weightNorm));
                    Pan2.ar(voiceMix / colourEnergyScales[palette], 0)
                        * colourWeights[palette+1];
                };
                LeakDC.ar((Mix(groups) * colourWeights[0]) + Mix(colourSources)) * polyphonySafetyTrim;
            } {
                LeakDC.ar(Mix(groups)) * polyphonySafetyTrim;
            };
        };
        sourceA = makeBank.value(voiceFrequenciesA, voiceWeightsA);
        sourceB = makeBank.value(voiceFrequenciesB, voiceWeightsB);
        bankPosition = VarLag.kr(
            NamedControl.kr(\voicingBank, 0).clip(0, 1),
            NamedControl.kr(
                \voicingCrossfade, preset[\voicingCrossfade]
            ).clip(0.1, 5),
            warp: \sin
        ) * 2 - 1;
        source = XFade2.ar(sourceA, sourceB, bankPosition);
        // Diagnostic-only audibility. Depth defaults to zero, so the normal
        // runtime remains unchanged. The dedicated demo enables it explicitly.
        source = source.sanitize;
        source = source * invitationDiagnosticGain;
        // Optional audition rhythm: deterministic host beat grid, smoothed
        // attacks on this same oscillator field, never per-onset Synth nodes.
        musicPattern = NamedControl.kr(\musicRhythmPattern, 0).clip(0, 4);
        musicPulse = LagUD.kr(NamedControl.kr(\musicPulse, 1).clip(0, 1), 0.015, 0.10);
        rhythmBlend = Lag.kr(musicPattern > 0, 0.1);
        source = source * ((1-rhythmBlend) + (rhythmBlend * (0.12 + (0.88 * musicPulse)) * 2.25));

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
        source = source * Lag.kr(NamedControl.kr(\auditionLevelDb, 0).clip(-18, 0), 0.1).dbamp;
        // Two finite feed-forward repeats. No feedback path can self-excite.
        musicEcho = Lag.kr(NamedControl.kr(\musicEchoMix, 0).clip(0, 0.35), 0.2);
        source = (source + (DelayC.ar(source, 0.7, 1/3) * musicEcho)
            + (DelayC.ar(source, 0.7, 2/3) * musicEcho * 0.55))
            / (1 + musicEcho.squared + (musicEcho * 0.55).squared).sqrt;

        saturationDrive = NamedControl.kr(
            \saturationDrive, preset[\saturationDrive]
        ).clip(1, 2);
        saturated = ((source.sanitize * saturationDrive).tanh / saturationDrive).sanitize;
        wet = GVerb.ar(
            saturated.sum * 0.5,
            roomsize: NamedControl.kr(
                \reverbRoom, preset[\reverbRoom]
            ).clip(8, 80),
            revtime: Lag.kr(NamedControl.kr(
                \reverbTime, preset[\reverbTime]
            ).clip(0.5, 12), 0.2),
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
            (Lag.kr(NamedControl.kr(
                \reverbMix, preset[\reverbMix]
            ).clip(0, 1), 0.2) * 2) - 1
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
            signal.sanitize
                * NamedControl.kr(
                    \outputTrim, preset[\outputTrim]
                ).clip(0, 1)
                * transportAlive
                * life,
            limiterDb.dbamp,
            0.01
        );
        // A final bounded guard catches pathological startup samples from the
        // persistent local-wavetable/effect graph without changing normal audio.
        signal = Clip.ar(signal.sanitize, limiterDb.dbamp.neg, limiterDb.dbamp);
        Out.ar(out, signal);
    });
};
