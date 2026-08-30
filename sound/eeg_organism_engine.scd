// PHASE 1: one-debater EEG organism.
//
// Evaluate the FIRST parenthesized block after an existing SuperDirt/scsynth
// server is running. This file deliberately never calls s.boot or s.reboot.
// Python sends one frame at /eeg/organism/frame in this exact order:
// F3 energy, centroid, mobility, F4 E/C/M, C3 E/C/M, C4 E/C/M,
// P3 E/C/M, P4 E/C/M (18 floats total, each nominally 0..1).

(
var oldState, state, configOrder, defaults, clampUnit, stopEngine, startEngine;

oldState = ~eegOrganism;
if(oldState.notNil and: { oldState[\stop].notNil }) {
    "EEG organism: releasing previously evaluated engine before replacement.".postln;
    oldState[\stop].value(true);
};

configOrder = [
    \ampMin, \ampMax, \cutoffMin, \cutoffMax,
    \moveMin, \moveMax, \roomMin, \roomMax,
    \energyLag, \centroidLag, \mobilityLag, \varLagCurve,
    \presenceDepth, \brightnessDepth, \movementDepth, \spaceDepth,
    \masterLevel, \limiterLevel, \attack, \release, \watchdogFade,
    \centreHz,
    \panF3, \panF4, \panC3, \panC4, \panP3, \panP4
];

defaults = (
    ampMin: 0.012, ampMax: 0.085,
    cutoffMin: 450.0, cutoffMax: 8500.0,
    moveMin: 0.12, moveMax: 11.0,
    roomMin: 0.08, roomMax: 0.62,
    energyLag: 0.35, centroidLag: 0.45, mobilityLag: 0.25,
    varLagCurve: -3.0,
    presenceDepth: 1.0, brightnessDepth: 1.0,
    movementDepth: 1.0, spaceDepth: 0.45,
    masterLevel: 0.42, limiterLevel: 0.82,
    attack: 0.25, release: 1.5, watchdogFade: 0.8,
    centreHz: 110.0,
    panF3: -0.82, panF4: 0.82,
    panC3: -0.46, panC4: 0.46,
    panP3: -0.68, panP4: 0.68
);

state = IdentityDictionary.new;
state[\config] = defaults.copy;
state[\configOrder] = configOrder;
state[\frameCount] = 0;
state[\timedOut] = true;
state[\stopping] = false;
~eegOrganism = state;

clampUnit = { |item|
    var value;
    value = try { item.asFloat } { 0.0 };
    if(value.isNaN) { value = 0.0 };
    value.clip(0.0, 1.0);
};

stopEngine = { |immediate = false|
    var group, bus, releaseTime;
    group = state[\group];
    bus = state[\bus];
    if(immediate and: { state[\stopping] }) {
        // A re-evaluation during an in-progress graceful release must still
        // remove the old tree before the replacement tree is created.
        state[\releaseTask].tryPerform(\stop);
        group.tryPerform(\freeAll);
        group.tryPerform(\free);
        bus.tryPerform(\free);
        "EEG organism: in-progress old release freed for replacement.".postln;
    } {
      if(state[\stopping].not) {
        state[\stopping] = true;
        [\eegOrganismFrame, \eegOrganismConfig, \eegOrganismStop].do { |key|
            OSCdef(key).tryPerform(\free);
        };
        state[\watchdog].tryPerform(\stop);
        releaseTime = state[\config][\release].asFloat.clip(0.05, 10.0);
        if(group.notNil) {
            if(immediate) {
                group.freeAll;
                group.free;
                bus.tryPerform(\free);
            } {
                state[\cells].do { |node| node.set(\gate, 0) };
                state[\mixer].set(\gate, 0);
                state[\releaseTask] = Routine({
                    (releaseTime + 0.25).wait;
                    group.freeAll;
                    group.free;
                    bus.tryPerform(\free);
                }).play(AppClock);
            };
        };
        if(immediate) {
            "EEG organism: old engine freed (immediate replacement cleanup).".postln;
        } {
            "EEG organism: graceful release started.".postln;
        };
      };
    };
};
state[\stop] = stopEngine;

startEngine = {
    Routine({
        var group, bus, cells, mixer, commonArgs, applyConfig;

        SynthDef(\eegOrgShimmerCell, {
            |outBus = 0, gate = 1, energy = 0.5, centroid = 0.5, mobility = 0.5,
            pan = 0, side = -1, centreHz = 110,
            ampMin = 0.012, ampMax = 0.085,
            cutoffMin = 450, cutoffMax = 8500,
            moveMin = 0.12, moveMax = 11,
            energyLag = 0.35, centroidLag = 0.45, mobilityLag = 0.25,
            varLagCurve = -3, presenceDepth = 1, brightnessDepth = 1,
            movementDepth = 1, attack = 0.25, release = 1.5|
            var e, c, m, cDepth, mDepth, amp, cutoff, moveRate;
            var smoothMove, jaggedMove, drift, harmonicAmps, shimmer, air, signal, life;

            e = Lag.kr(energy.clip(0, 1), energyLag.clip(0.001, 10));
            c = VarLag.kr(centroid.clip(0, 1), centroidLag.clip(0.001, 10), varLagCurve.clip(-8, 8));
            m = VarLag.kr(mobility.clip(0, 1), mobilityLag.clip(0.001, 10), varLagCurve.clip(-8, 8));
            cDepth = (0.5 + ((c - 0.5) * brightnessDepth.clip(0, 2))).clip(0, 1);
            mDepth = (m * movementDepth.clip(0, 2)).clip(0, 1);
            amp = ampMin.clip(0, 0.2) + ((ampMax.clip(0, 0.2) - ampMin.clip(0, 0.2)).max(0)
                * e * presenceDepth.clip(0, 2));
            cutoff = cDepth.linexp(0, 1, cutoffMin.clip(60, 18000), cutoffMax.clip(80, 20000));
            moveRate = mDepth.linexp(0, 1, moveMin.clip(0.01, 30), moveMax.clip(0.02, 40));
            smoothMove = LFNoise2.kr(moveRate);
            jaggedMove = LFNoise0.kr(moveRate * 1.37);
            drift = ((smoothMove * (1 - mDepth)) + (jaggedMove * mDepth)) * (0.001 + (mDepth * 0.009));
            harmonicAmps = [0.62, 0.22 + (cDepth * 0.16), cDepth * 0.14, cDepth.squared * 0.08];
            shimmer = Mix(SinOsc.ar(
                centreHz.clip(40, 440) * [1, 2.003, 3.997, 7.01] * (1 + (drift * side)),
                [0, 0.7, 1.4, 2.1] + (side * 0.2), harmonicAmps
            ));
            air = BPF.ar(PinkNoise.ar(0.35), cutoff, 0.18 + ((1 - cDepth) * 0.2)) * (0.05 + (cDepth * 0.22));
            signal = RLPF.ar(shimmer + air, cutoff, 0.28 + ((1 - cDepth) * 0.45));
            life = EnvGen.kr(Env.asr(attack.clip(0.01, 5), 1, release.clip(0.05, 10)), gate, doneAction: 2);
            Out.ar(outBus, Pan2.ar(LeakDC.ar(signal) * amp * life, pan.clip(-1, 1)));
        }).add;

        SynthDef(\eegOrgPulseCell, {
            |outBus = 0, gate = 1, energy = 0.5, centroid = 0.5, mobility = 0.5,
            pan = 0, side = -1, centreHz = 110,
            ampMin = 0.012, ampMax = 0.085,
            cutoffMin = 450, cutoffMax = 8500,
            moveMin = 0.12, moveMax = 11,
            energyLag = 0.35, centroidLag = 0.45, mobilityLag = 0.25,
            varLagCurve = -3, presenceDepth = 1, brightnessDepth = 1,
            movementDepth = 1, attack = 0.25, release = 1.5|
            var e, c, m, cDepth, mDepth, amp, cutoff, rate, trigger, articulation;
            var excitation, resonance, edge, signal, life;

            e = Lag.kr(energy.clip(0, 1), energyLag.clip(0.001, 10));
            c = VarLag.kr(centroid.clip(0, 1), centroidLag.clip(0.001, 10), varLagCurve.clip(-8, 8));
            m = VarLag.kr(mobility.clip(0, 1), mobilityLag.clip(0.001, 10), varLagCurve.clip(-8, 8));
            cDepth = (0.5 + ((c - 0.5) * brightnessDepth.clip(0, 2))).clip(0, 1);
            mDepth = (m * movementDepth.clip(0, 2)).clip(0, 1);
            amp = ampMin.clip(0, 0.2) + ((ampMax.clip(0, 0.2) - ampMin.clip(0, 0.2)).max(0)
                * e * presenceDepth.clip(0, 2));
            cutoff = cDepth.linexp(0, 1, cutoffMin.clip(60, 18000), cutoffMax.clip(80, 20000));
            rate = mDepth.linexp(0, 1, moveMin.clip(0.01, 30), moveMax.clip(0.02, 40));
            trigger = Impulse.kr(rate * (1 + (side * 0.025)));
            articulation = Decay2.kr(trigger, 0.004 + ((1 - mDepth) * 0.035), 0.055 + ((1 - mDepth) * 0.72));
            excitation = (PinkNoise.ar(0.6) + SinOsc.ar(centreHz.clip(40, 440) * 2, 0, 0.18)) * articulation;
            resonance = Mix(Ringz.ar(excitation, centreHz.clip(40, 440) * [1, 2.005], [0.32, 0.16]));
            edge = HPF.ar(excitation, cutoff * 0.45) * cDepth;
            signal = RLPF.ar(resonance + edge, cutoff, 0.22 + ((1 - cDepth) * 0.5));
            life = EnvGen.kr(Env.asr(attack.clip(0.01, 5), 1, release.clip(0.05, 10)), gate, doneAction: 2);
            Out.ar(outBus, Pan2.ar(LeakDC.ar(signal) * amp * life, pan.clip(-1, 1)));
        }).add;

        SynthDef(\eegOrgTailCell, {
            |outBus = 0, gate = 1, energy = 0.5, centroid = 0.5, mobility = 0.5,
            pan = 0, side = -1, centreHz = 110,
            ampMin = 0.012, ampMax = 0.085,
            cutoffMin = 450, cutoffMax = 8500,
            moveMin = 0.12, moveMax = 11, roomMin = 0.08, roomMax = 0.62,
            energyLag = 0.35, centroidLag = 0.45, mobilityLag = 0.25,
            varLagCurve = -3, presenceDepth = 1, brightnessDepth = 1,
            movementDepth = 1, spaceDepth = 0.45, attack = 0.25, release = 1.5|
            var e, c, m, cDepth, mDepth, amp, cutoff, rate, room, grains;
            var colour, tail, signal, life;

            e = Lag.kr(energy.clip(0, 1), energyLag.clip(0.001, 10));
            c = VarLag.kr(centroid.clip(0, 1), centroidLag.clip(0.001, 10), varLagCurve.clip(-8, 8));
            m = VarLag.kr(mobility.clip(0, 1), mobilityLag.clip(0.001, 10), varLagCurve.clip(-8, 8));
            cDepth = (0.5 + ((c - 0.5) * brightnessDepth.clip(0, 2))).clip(0, 1);
            mDepth = (m * movementDepth.clip(0, 2)).clip(0, 1);
            amp = ampMin.clip(0, 0.2) + ((ampMax.clip(0, 0.2) - ampMin.clip(0, 0.2)).max(0)
                * e * presenceDepth.clip(0, 2));
            cutoff = cDepth.linexp(0, 1, cutoffMin.clip(60, 18000), cutoffMax.clip(80, 20000));
            rate = mDepth.linexp(0, 1, moveMin.clip(0.01, 30), moveMax.clip(0.02, 40));
            room = roomMin.clip(0, 1) + ((roomMax.clip(0, 1) - roomMin.clip(0, 1)).max(0)
                * mDepth * spaceDepth.clip(0, 2));
            grains = Decay2.kr(Dust.kr(rate), 0.003, 0.04 + ((1 - mDepth) * 0.55));
            colour = BPF.ar(BrownNoise.ar(1), cutoff, 0.12 + ((1 - cDepth) * 0.35)) * grains;
            colour = colour + (HPF.ar(PinkNoise.ar(0.16), cutoff * 0.6) * grains * cDepth);
            tail = CombC.ar(colour, 0.35, (centreHz.clip(40, 440).reciprocal * (2 + (side * 0.04))).clip(0.01, 0.3),
                0.2 + (room * 2.8));
            signal = FreeVerb.ar(colour + (tail * 0.45), room.clip(0, 1), 0.78, 0.52);
            life = EnvGen.kr(Env.asr(attack.clip(0.01, 5), 1, release.clip(0.05, 10)), gate, doneAction: 2);
            Out.ar(outBus, Pan2.ar(LeakDC.ar(signal) * amp * life, pan.clip(-1, 1)));
        }).add;

        SynthDef(\eegOrgMixer, {
            |inBus = 0, out = 0, gate = 1, alive = 0,
            masterLevel = 0.42, limiterLevel = 0.82,
            attack = 0.25, release = 1.5, watchdogFade = 0.8|
            var signal, watchdog, life;
            signal = LeakDC.ar(In.ar(inBus, 2));
            watchdog = LagUD.kr(alive.clip(0, 1), 0.04, watchdogFade.clip(0.05, 10));
            life = EnvGen.kr(Env.asr(attack.clip(0.01, 5), 1, release.clip(0.05, 10)), gate, doneAction: 2);
            signal = Limiter.ar(signal * masterLevel.clip(0, 0.8) * watchdog * life,
                limiterLevel.clip(0.1, 0.99), 0.01);
            // Sum only this organism into hardware output; never replace or
            // intercept SuperDirt's existing output on bus 0.
            Out.ar(out, signal);
        }).add;

        s.sync;
        if(state[\stopping]) { nil } {
            bus = Bus.audio(s, 2);
            group = Group.tail(s);
            state[\bus] = bus;
            state[\group] = group;

            commonArgs = [
                \outBus, bus.index, \centreHz, defaults[\centreHz],
                \ampMin, defaults[\ampMin], \ampMax, defaults[\ampMax],
                \cutoffMin, defaults[\cutoffMin], \cutoffMax, defaults[\cutoffMax],
                \moveMin, defaults[\moveMin], \moveMax, defaults[\moveMax],
                \energyLag, defaults[\energyLag], \centroidLag, defaults[\centroidLag],
                \mobilityLag, defaults[\mobilityLag], \varLagCurve, defaults[\varLagCurve],
                \presenceDepth, defaults[\presenceDepth], \brightnessDepth, defaults[\brightnessDepth],
                \movementDepth, defaults[\movementDepth], \attack, defaults[\attack], \release, defaults[\release]
            ];
            cells = [
                Synth.tail(group, \eegOrgShimmerCell, commonArgs ++ [\pan, defaults[\panF3], \side, -1]),
                Synth.tail(group, \eegOrgShimmerCell, commonArgs ++ [\pan, defaults[\panF4], \side, 1]),
                Synth.tail(group, \eegOrgPulseCell, commonArgs ++ [\pan, defaults[\panC3], \side, -1]),
                Synth.tail(group, \eegOrgPulseCell, commonArgs ++ [\pan, defaults[\panC4], \side, 1]),
                Synth.tail(group, \eegOrgTailCell, commonArgs ++ [
                    \pan, defaults[\panP3], \side, -1, \roomMin, defaults[\roomMin],
                    \roomMax, defaults[\roomMax], \spaceDepth, defaults[\spaceDepth]
                ]),
                Synth.tail(group, \eegOrgTailCell, commonArgs ++ [
                    \pan, defaults[\panP4], \side, 1, \roomMin, defaults[\roomMin],
                    \roomMax, defaults[\roomMax], \spaceDepth, defaults[\spaceDepth]
                ])
            ];
            mixer = Synth.tail(group, \eegOrgMixer, [
                \inBus, bus.index, \masterLevel, defaults[\masterLevel],
                \limiterLevel, defaults[\limiterLevel], \attack, defaults[\attack],
                \release, defaults[\release], \watchdogFade, defaults[\watchdogFade]
            ]);
            state[\cells] = cells;
            state[\mixer] = mixer;
            state[\lastFrameAt] = Main.elapsedTime;

            applyConfig = {
                var cfg, shared;
                cfg = state[\config];
                shared = [
                    \ampMin, cfg[\ampMin], \ampMax, cfg[\ampMax],
                    \cutoffMin, cfg[\cutoffMin], \cutoffMax, cfg[\cutoffMax],
                    \moveMin, cfg[\moveMin], \moveMax, cfg[\moveMax],
                    \energyLag, cfg[\energyLag], \centroidLag, cfg[\centroidLag],
                    \mobilityLag, cfg[\mobilityLag], \varLagCurve, cfg[\varLagCurve],
                    \presenceDepth, cfg[\presenceDepth], \brightnessDepth, cfg[\brightnessDepth],
                    \movementDepth, cfg[\movementDepth], \centreHz, cfg[\centreHz],
                    \attack, cfg[\attack], \release, cfg[\release]
                ];
                cells.do { |node| node.set(*shared) };
                cells[0].set(\pan, cfg[\panF3]); cells[1].set(\pan, cfg[\panF4]);
                cells[2].set(\pan, cfg[\panC3]); cells[3].set(\pan, cfg[\panC4]);
                cells[4].set(\pan, cfg[\panP3], \roomMin, cfg[\roomMin], \roomMax, cfg[\roomMax], \spaceDepth, cfg[\spaceDepth]);
                cells[5].set(\pan, cfg[\panP4], \roomMin, cfg[\roomMin], \roomMax, cfg[\roomMax], \spaceDepth, cfg[\spaceDepth]);
                mixer.set(\masterLevel, cfg[\masterLevel], \limiterLevel, cfg[\limiterLevel],
                    \attack, cfg[\attack], \release, cfg[\release], \watchdogFade, cfg[\watchdogFade]);
            };
            state[\applyConfig] = applyConfig;

            OSCdef(\eegOrganismFrame, { |message|
                var values;
                if(message.size == 19 and: { state[\stopping].not }) {
                    values = message.copyRange(1, 18).collect(clampUnit);
                    cells.do { |node, index|
                        node.set(\energy, values[index * 3], \centroid, values[(index * 3) + 1],
                            \mobility, values[(index * 3) + 2]);
                    };
                    state[\lastFrameAt] = Main.elapsedTime;
                    state[\frameCount] = state[\frameCount] + 1;
                    if(state[\timedOut]) {
                        state[\timedOut] = false;
                        mixer.set(\alive, 1);
                        "EEG organism: input active.".postln;
                    };
                } {
                    "EEG organism: rejected frame (expected exactly 18 values).".warn;
                };
            }, '/eeg/organism/frame', recvPort: 57120);

            OSCdef(\eegOrganismConfig, { |message|
                if(message.size == (configOrder.size + 1) and: { state[\stopping].not }) {
                    configOrder.do { |key, index|
                        var value;
                        value = try { message[index + 1].asFloat } { defaults[key] };
                        if(value.isNaN) { value = defaults[key] };
                        state[\config][key] = value;
                    };
                    state[\applyConfig].value;
                    "EEG organism: config/sonification.toml values applied.".postln;
                } {
                    "EEG organism: rejected config packet (wrong value count).".warn;
                };
            }, '/eeg/organism/config', recvPort: 57120);

            OSCdef(\eegOrganismStop, {
                state[\stop].value(false);
            }, '/eeg/organism/stop', recvPort: 57120);

            state[\watchdog] = Routine({
                loop {
                    0.25.wait;
                    if(state[\stopping].not and: {
                        (Main.elapsedTime - state[\lastFrameAt]) > 2.0
                    } and: { state[\timedOut].not }) {
                        state[\timedOut] = true;
                        mixer.set(\alive, 0);
                        "EEG organism WATCHDOG: no frame for 2 seconds; fading to silence.".warn;
                    };
                };
            }).play(AppClock);

            "EEG ORGANISM READY on UDP 57120".postln;
            "Stable tree: 1 dedicated group + 6 cells + 1 mixer (8 nodes total).".postln;
            ("Cell node IDs: " ++ cells.collect(_.nodeID) ++ "; mixer: " ++ mixer.nodeID).postln;
            "Waiting for /eeg/organism/frame; output remains silent until the first frame.".postln;
        };
    }).play(AppClock);
};
state[\start] = startEngine;

if(s.serverRunning) {
    state[\start].value;
} {
    "EEG organism NOT started: start SuperDirt/scsynth first, then evaluate this block again. No server was booted or rebooted.".warn;
};
)

// Graceful stop is an explicit, separately loadable block in
// sound/stop_eeg_organism.scd (or send /eeg/organism/stop).
