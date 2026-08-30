// PHASE 1B: one-debater sustained harmonic EEG organism.
//
// Evaluate this block only after an existing SuperDirt/scsynth server is running.
// This file never boots or reboots the server. Python's unchanged control frame is:
// F3 energy/centroid/mobility, F4 E/C/M, C3 E/C/M, C4 E/C/M,
// P3 E/C/M, P4 E/C/M (18 floats, nominally 0..1).

(
var oldState, state, configOrder, defaults, clampUnit, stopEngine, startEngine;

oldState = ~eegOrganism;
if(oldState.notNil and: { oldState[\stop].notNil }) {
    "EEG organism: releasing previously evaluated engine before replacement.".postln;
    oldState[\stop].value(true);
};

// Keep this order synchronized with CONFIG_PATHS in src/organism_osc.py.
configOrder = [
    \energyMinDb, \energyMaxDb, \energyLag,
    \tiltMin, \tiltMax, \centroidCompDb, \centroidLag,
    \motionRateMin, \motionRateMax, \motionDepthMin, \motionDepthMax, \mobilityLag,
    \varLagCurve, \fundamental,
    \pH1, \pH2, \pH3, \pH4,
    \cH1, \cH2, \cH3, \cH4,
    \fH1, \fH2, \fH3, \fH4,
    \cellLevel, \reverbMix, \reverbRoom, \reverbDamp,
    \masterLevel, \limiterLevel, \attack, \release, \watchdogFade,
    \panF3, \panF4, \panC3, \panC4, \panP3, \panP4
];

defaults = (
    energyMinDb: -36.0, energyMaxDb: -16.0, energyLag: 0.35,
    tiltMin: -0.85, tiltMax: 0.85, centroidCompDb: -1.0, centroidLag: 0.45,
    motionRateMin: 0.08, motionRateMax: 5.0,
    motionDepthMin: 0.05, motionDepthMax: 0.45, mobilityLag: 0.30,
    varLagCurve: -3.0, fundamental: 73.42,
    pH1: 1.0, pH2: 2.0, pH3: 3.0, pH4: 4.0,
    cH1: 3.0, cH2: 4.0, cH3: 5.0, cH4: 6.0,
    fH1: 6.0, fH2: 8.0, fH3: 10.0, fH4: 12.0,
    cellLevel: 0.28,
    reverbMix: 0.16, reverbRoom: 0.72, reverbDamp: 0.58,
    masterLevel: 0.42, limiterLevel: 0.82,
    attack: 0.35, release: 1.5, watchdogFade: 0.8,
    panF3: -0.38, panF4: 0.38,
    panC3: -0.28, panC4: 0.28,
    panP3: -0.20, panP4: 0.20
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
        state[\releaseTask].tryPerform(\stop);
        group.tryPerform(\freeAll);
        group.tryPerform(\free);
        bus.tryPerform(\free);
        "EEG organism: in-progress old release freed for replacement.".postln;
    } {
        if(state[\stopping].not) {
            state[\stopping] = true;
            [\eegOrganismFrame, \eegOrganismConfig, \eegOrganismAudition,
                \eegOrganismStop].do { |key| OSCdef(key).tryPerform(\free) };
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

        // One deterministic sustained source design serves all six cells.
        // Family identity comes only from configurable harmonic assignments.
        SynthDef(\eegOrgHarmonicCell, {
            |outBus = 0, gate = 1, audition = 1,
            energy = 0.65, centroid = 0.5, mobility = 0.25,
            pan = 0, side = -1, motionPhase = 0,
            fundamental = 73.42, h1 = 1, h2 = 2, h3 = 3, h4 = 4,
            energyMinDb = -36, energyMaxDb = -16, energyLag = 0.35,
            tiltMin = -0.85, tiltMax = 0.85, centroidCompDb = -1,
            centroidLag = 0.45,
            motionRateMin = 0.08, motionRateMax = 5,
            motionDepthMin = 0.05, motionDepthMax = 0.45,
            mobilityLag = 0.30, varLagCurve = -3,
            cellLevel = 0.28, attack = 0.35, release = 1.5|
            var e, c, m, energyDb, amplitude, tilt, blend;
            var frequencies, phases, oscillators, darkWeights, brightWeights;
            var weights, weightNorm, harmonicBody, centroidGain;
            var motionRate, motionDepth, motionNorm, motion, life, signal;

            // ENERGY: only smoothed cell amplitude, on a perceptual dB scale.
            e = Lag.kr(energy.clip(0, 1), energyLag.clip(0.001, 10));
            energyDb = e.linlin(0, 1, energyMinDb.clip(-80, -3),
                energyMaxDb.clip(-80, -3).max(energyMinDb.clip(-80, -3)));
            amplitude = energyDb.dbamp;

            // CENTROID: normalized spectral tilt across the same four harmonics.
            // Normalizing the weight vector keeps oscillator RMS comparatively stable.
            c = VarLag.kr(centroid.clip(0, 1), centroidLag.clip(0.001, 10),
                varLagCurve.clip(-8, 8));
            tilt = c.linlin(0, 1, tiltMin.clip(-1, 1), tiltMax.clip(-1, 1));
            blend = (tilt + 1) * 0.5;
            darkWeights = [1.0, 0.72, 0.30, 0.10];
            brightWeights = [0.28, 0.58, 0.86, 1.0];
            weights = (darkWeights * (1 - blend)) + (brightWeights * blend);
            weightNorm = (weights.squared.sum + 0.0001).sqrt;

            frequencies = fundamental.clip(30, 220) * [h1, h2, h3, h4].collect(_.clip(1, 32));
            phases = [0.0, 0.41, 0.87, 1.31] + (side.clip(-1, 1) * 0.19);
            oscillators = SinOsc.ar(frequencies, phases);
            harmonicBody = Mix(oscillators * weights) / weightNorm;
            centroidGain = (c * centroidCompDb.clip(-12, 12)).dbamp;

            // MOBILITY: continuous deterministic AM only; no triggers or notes.
            // Division by sqrt(1 + depth^2/2) compensates sine-AM RMS.
            m = VarLag.kr(mobility.clip(0, 1), mobilityLag.clip(0.001, 10),
                varLagCurve.clip(-8, 8));
            motionRate = m.linexp(0, 1, motionRateMin.clip(0.01, 20),
                motionRateMax.clip(0.02, 20).max(motionRateMin.clip(0.01, 20)));
            motionDepth = m.linlin(0, 1, motionDepthMin.clip(0, 0.9),
                motionDepthMax.clip(0, 0.9).max(motionDepthMin.clip(0, 0.9)));
            motionNorm = (1 + (motionDepth.squared * 0.5)).sqrt;
            motion = (1 + (SinOsc.kr(motionRate, motionPhase) * motionDepth)) / motionNorm;

            life = EnvGen.kr(Env.asr(attack.clip(0.01, 5), 1,
                release.clip(0.05, 10)), gate, doneAction: 2);
            signal = harmonicBody * amplitude * centroidGain * motion;
            signal = signal * cellLevel.clip(0, 0.8) * Lag.kr(audition.clip(0, 1), 0.08) * life;
            Out.ar(outBus, Pan2.ar(LeakDC.ar(signal), pan.clip(-1, 1)));
        }).add;

        SynthDef(\eegOrgMixer, {
            |inBus = 0, out = 0, gate = 1, alive = 0,
            reverbMix = 0.16, reverbRoom = 0.72, reverbDamp = 0.58,
            masterLevel = 0.42, limiterLevel = 0.82,
            attack = 0.35, release = 1.5, watchdogFade = 0.8|
            var dry, wet, signal, watchdog, life;
            dry = LeakDC.ar(In.ar(inBus, 2));
            // Fixed global space: no EEG control reaches these parameters.
            wet = FreeVerb2.ar(dry[0], dry[1], 1,
                reverbRoom.clip(0, 1), reverbDamp.clip(0, 1));
            signal = XFade2.ar(dry, wet, (reverbMix.clip(0, 1) * 2) - 1);
            watchdog = LagUD.kr(alive.clip(0, 1), 0.04,
                watchdogFade.clip(0.05, 10));
            life = EnvGen.kr(Env.asr(attack.clip(0.01, 5), 1,
                release.clip(0.05, 10)), gate, doneAction: 2);
            signal = Limiter.ar(signal * masterLevel.clip(0, 0.8) * watchdog * life,
                limiterLevel.clip(0.1, 0.99), 0.01);
            // Sum this organism into stereo without replacing SuperDirt output.
            Out.ar(out, signal);
        }).add;

        s.sync;
        if(state[\stopping]) { nil } {
            bus = Bus.audio(s, 2);
            group = Group.tail(s);
            state[\bus] = bus;
            state[\group] = group;

            commonArgs = [
                \outBus, bus.index, \fundamental, defaults[\fundamental],
                \energyMinDb, defaults[\energyMinDb], \energyMaxDb, defaults[\energyMaxDb],
                \energyLag, defaults[\energyLag], \tiltMin, defaults[\tiltMin],
                \tiltMax, defaults[\tiltMax], \centroidCompDb, defaults[\centroidCompDb],
                \centroidLag, defaults[\centroidLag],
                \motionRateMin, defaults[\motionRateMin], \motionRateMax, defaults[\motionRateMax],
                \motionDepthMin, defaults[\motionDepthMin], \motionDepthMax, defaults[\motionDepthMax],
                \mobilityLag, defaults[\mobilityLag], \varLagCurve, defaults[\varLagCurve],
                \cellLevel, defaults[\cellLevel], \attack, defaults[\attack], \release, defaults[\release]
            ];
            cells = [
                Synth.tail(group, \eegOrgHarmonicCell, commonArgs ++ [
                    \h1, defaults[\fH1], \h2, defaults[\fH2], \h3, defaults[\fH3], \h4, defaults[\fH4],
                    \pan, defaults[\panF3], \side, -1, \motionPhase, 0.3]),
                Synth.tail(group, \eegOrgHarmonicCell, commonArgs ++ [
                    \h1, defaults[\fH1], \h2, defaults[\fH2], \h3, defaults[\fH3], \h4, defaults[\fH4],
                    \pan, defaults[\panF4], \side, 1, \motionPhase, 2.1]),
                Synth.tail(group, \eegOrgHarmonicCell, commonArgs ++ [
                    \h1, defaults[\cH1], \h2, defaults[\cH2], \h3, defaults[\cH3], \h4, defaults[\cH4],
                    \pan, defaults[\panC3], \side, -1, \motionPhase, 0.9]),
                Synth.tail(group, \eegOrgHarmonicCell, commonArgs ++ [
                    \h1, defaults[\cH1], \h2, defaults[\cH2], \h3, defaults[\cH3], \h4, defaults[\cH4],
                    \pan, defaults[\panC4], \side, 1, \motionPhase, 2.7]),
                Synth.tail(group, \eegOrgHarmonicCell, commonArgs ++ [
                    \h1, defaults[\pH1], \h2, defaults[\pH2], \h3, defaults[\pH3], \h4, defaults[\pH4],
                    \pan, defaults[\panP3], \side, -1, \motionPhase, 1.4]),
                Synth.tail(group, \eegOrgHarmonicCell, commonArgs ++ [
                    \h1, defaults[\pH1], \h2, defaults[\pH2], \h3, defaults[\pH3], \h4, defaults[\pH4],
                    \pan, defaults[\panP4], \side, 1, \motionPhase, 3.2])
            ];
            mixer = Synth.tail(group, \eegOrgMixer, [
                \inBus, bus.index,
                \reverbMix, defaults[\reverbMix], \reverbRoom, defaults[\reverbRoom],
                \reverbDamp, defaults[\reverbDamp],
                \masterLevel, defaults[\masterLevel], \limiterLevel, defaults[\limiterLevel],
                \attack, defaults[\attack], \release, defaults[\release],
                \watchdogFade, defaults[\watchdogFade]
            ]);
            state[\cells] = cells;
            state[\mixer] = mixer;
            state[\lastFrameAt] = Main.elapsedTime;

            applyConfig = {
                var cfg, shared;
                cfg = state[\config];
                shared = [
                    \fundamental, cfg[\fundamental],
                    \energyMinDb, cfg[\energyMinDb], \energyMaxDb, cfg[\energyMaxDb],
                    \energyLag, cfg[\energyLag], \tiltMin, cfg[\tiltMin],
                    \tiltMax, cfg[\tiltMax], \centroidCompDb, cfg[\centroidCompDb],
                    \centroidLag, cfg[\centroidLag],
                    \motionRateMin, cfg[\motionRateMin], \motionRateMax, cfg[\motionRateMax],
                    \motionDepthMin, cfg[\motionDepthMin], \motionDepthMax, cfg[\motionDepthMax],
                    \mobilityLag, cfg[\mobilityLag], \varLagCurve, cfg[\varLagCurve],
                    \cellLevel, cfg[\cellLevel], \attack, cfg[\attack], \release, cfg[\release]
                ];
                cells.do { |node| node.set(*shared) };
                cells[0].set(\h1, cfg[\fH1], \h2, cfg[\fH2], \h3, cfg[\fH3], \h4, cfg[\fH4], \pan, cfg[\panF3]);
                cells[1].set(\h1, cfg[\fH1], \h2, cfg[\fH2], \h3, cfg[\fH3], \h4, cfg[\fH4], \pan, cfg[\panF4]);
                cells[2].set(\h1, cfg[\cH1], \h2, cfg[\cH2], \h3, cfg[\cH3], \h4, cfg[\cH4], \pan, cfg[\panC3]);
                cells[3].set(\h1, cfg[\cH1], \h2, cfg[\cH2], \h3, cfg[\cH3], \h4, cfg[\cH4], \pan, cfg[\panC4]);
                cells[4].set(\h1, cfg[\pH1], \h2, cfg[\pH2], \h3, cfg[\pH3], \h4, cfg[\pH4], \pan, cfg[\panP3]);
                cells[5].set(\h1, cfg[\pH1], \h2, cfg[\pH2], \h3, cfg[\pH3], \h4, cfg[\pH4], \pan, cfg[\panP4]);
                mixer.set(
                    \reverbMix, cfg[\reverbMix], \reverbRoom, cfg[\reverbRoom],
                    \reverbDamp, cfg[\reverbDamp],
                    \masterLevel, cfg[\masterLevel], \limiterLevel, cfg[\limiterLevel],
                    \attack, cfg[\attack], \release, cfg[\release],
                    \watchdogFade, cfg[\watchdogFade]
                );
            };
            state[\applyConfig] = applyConfig;

            OSCdef(\eegOrganismFrame, { |message|
                var values;
                if(message.size == 19 and: { state[\stopping].not }) {
                    values = message.copyRange(1, 18).collect(clampUnit);
                    cells.do { |node, index|
                        node.set(
                            \energy, values[index * 3],
                            \centroid, values[(index * 3) + 1],
                            \mobility, values[(index * 3) + 2]
                        );
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

            // Audition masks only multiply existing cells; they never create nodes.
            OSCdef(\eegOrganismAudition, { |message|
                var enabled;
                if(message.size == 7 and: { state[\stopping].not }) {
                    enabled = message.copyRange(1, 6).collect(clampUnit);
                    cells.do { |node, index| node.set(\audition, enabled[index]) };
                    ("EEG organism audition mask: " ++ enabled).postln;
                } {
                    "EEG organism: rejected audition mask (expected six values).".warn;
                };
            }, '/eeg/organism/audition', recvPort: 57120);

            OSCdef(\eegOrganismConfig, { |message|
                if(message.size == (configOrder.size + 1) and: { state[\stopping].not }) {
                    configOrder.do { |key, index|
                        var value;
                        value = try { message[index + 1].asFloat } { defaults[key] };
                        if(value.isNaN) { value = defaults[key] };
                        state[\config][key] = value;
                    };
                    state[\applyConfig].value;
                    "EEG organism: Phase 1B config values applied.".postln;
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

            "EEG ORGANISM PHASE 1B READY on UDP 57120".postln;
            "Stable tree: 1 dedicated group + 6 harmonic cells + 1 mixer (8 nodes total).".postln;
            ("Cell node IDs: " ++ cells.collect(_.nodeID) ++ "; mixer: " ++ mixer.nodeID).postln;
            "No noise beds, note triggers, grains, sequences, or autonomous pulses.".postln;
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

// Graceful stop is in sound/stop_eeg_organism.scd or /eeg/organism/stop.
