// ORGANISM V2 SYNTHETIC RECEIVER: one persistent additive harmonic field.
//
// Evaluate only after the existing SuperDirt/scsynth server is running.
// This file never boots, reboots, or quits the server. It reuses the tested
// harmonic-field SynthDef factory and creates one dedicated Group + one Synth.
// Frame order: energy, centroid, mobility, spectralEntropy, novelty,
// delta, theta, alpha, beta.

(
var here, library, v2Config, preset, frameOrder, oldState, state;
var clampUnit, stopReceiver, startReceiver;

here = PathName(thisProcess.nowExecutingPath).pathOnly;
thisProcess.interpreter.executeFile(here +/+ "eeg_harmonic_field_v2_core.scd");
thisProcess.interpreter.executeFile(here +/+ "eeg_harmonics_preset_support.scd");
library = thisProcess.interpreter.executeFile(here +/+ "eeg_harmonics_manual_config.scd");
v2Config = thisProcess.interpreter.executeFile(
    here +/+ "../config/eeg_organism_v2.scd"
);
preset = library[\presets][v2Config[\basePreset]].copy;
v2Config[\synthOverrides].keysValuesDo { |key, value| preset[key] = value };
preset[\harmonicGroups] = v2Config[\harmonicGroups];
frameOrder = [
    \energy, \centroid, \mobility, \spectralEntropy, \novelty,
    \delta, \theta, \alpha, \beta
];

oldState = ~eegOrganismV2;
if(oldState.notNil and: { oldState[\stop].notNil }) {
    "Organism v2: freeing the previous receiver before replacement.".postln;
    oldState[\stop].value(true);
};

state = IdentityDictionary.new;
state[\frameOrder] = frameOrder;
state[\lastFrame] = IdentityDictionary.new;
state[\frameCount] = 0;
state[\lastFrameAt] = Main.elapsedTime;
state[\lastDisplayAt] = Main.elapsedTime - 1;
state[\timedOut] = true;
state[\stopping] = false;
state[\preset] = preset;
state[\config] = v2Config;
state[\previousFrameAt] = nil;
state[\receiveInterval] = 0.0;
state[\lastDisplayFrameCount] = 0;
~eegOrganismV2 = state;

clampUnit = { |item|
    var value;
    value = try { item.asFloat } { 0.0 };
    if(value.isNaN) { value = 0.0 };
    value.clip(0.0, 1.0);
};

stopReceiver = { |immediate = false|
    var group, synth, watchdogFade, release;
    group = state[\group];
    synth = state[\synth];
    watchdogFade = state[\preset][\watchdogFade].asFloat.clip(0.05, 4);
    release = state[\preset][\release].asFloat.clip(0.1, 15);

    if(immediate and: { state[\stopping] }) {
        state[\releaseTask].tryPerform(\stop);
        group.tryPerform(\freeAll);
        group.tryPerform(\free);
        "Organism v2: in-progress release freed for replacement.".postln;
    } {
        if(state[\stopping].not) {
            state[\stopping] = true;
            [\eegOrganismV2Frame, \eegOrganismV2Stop].do { |key|
                OSCdef(key).tryPerform(\free)
            };
            state[\watchdog].tryPerform(\stop);
            if(group.notNil) {
                if(immediate) {
                    group.freeAll;
                    group.free;
                } {
                    // Transport gain fades first, then the existing ASR releases.
                    synth.tryPerform(\set, \transportAlive, 0);
                    state[\releaseTask] = Routine({
                        (watchdogFade + 0.1).wait;
                        synth.tryPerform(\set, \gate, 0);
                        (release + 0.25).wait;
                        group.tryPerform(\free);
                    }).play(AppClock);
                };
            };
            if(immediate) {
                "Organism v2 receiver freed for replacement.".postln;
            } {
                "Organism v2 graceful release started; server remains running.".postln;
            };
        };
    };
};
state[\stop] = stopReceiver;

startReceiver = {
    Routine({
        var definition, group, synth;
        definition = ~makeEegOrganismV2HarmonicFieldSynthDef.value(
            \eegOrganismV2HarmonicField,
            preset
        );
        definition.add;
        s.sync;

        if(state[\stopping].not) {
            group = Group.tail(s);
            synth = Synth.tail(
                group, \eegOrganismV2HarmonicField,
                [\masterEnergy, 0, \transportAlive, 0]
            );
            state[\group] = group;
            state[\synth] = synth;
            state[\nodeIDs] = [group.nodeID, synth.nodeID];

            OSCdef(\eegOrganismV2Frame, { |message|
                var values, now, displayElapsed, effectiveHz, age;
                if(message.size == 10 and: { state[\stopping].not }) {
                    now = Main.elapsedTime;
                    values = message.copyRange(1, 9).collect(clampUnit);
                    frameOrder.do { |key, index|
                        state[\lastFrame][key] = values[index]
                    };

                    // The callback only updates the already-running Synth.
                    // No descriptor other than energy is a synthesis parameter yet.
                    synth.set(
                        \masterEnergy, values[0],
                        \transportAlive, 1
                    );
                    synth.setn(\groupAmplitudes, values.copyRange(5, 8));
                    if(state[\previousFrameAt].notNil) {
                        state[\receiveInterval] = now - state[\previousFrameAt]
                    };
                    state[\previousFrameAt] = now;
                    state[\lastFrameAt] = now;
                    state[\frameCount] = state[\frameCount] + 1;
                    if(state[\timedOut]) {
                        state[\timedOut] = false;
                        "Organism v2: synthetic input active.".postln;
                    };
                    displayElapsed = now - state[\lastDisplayAt];
                    if(displayElapsed >= v2Config[\diagnosticInterval]) {
                        effectiveHz = if(state[\frameCount] <= 1) {
                            0.0
                        } {
                            (
                                state[\frameCount] - state[\lastDisplayFrameCount]
                            ) / displayElapsed.max(0.001)
                        };
                        age = Main.elapsedTime - state[\lastFrameAt];
                        (
                            "Organism v2 rx count=" ++ state[\frameCount]
                            ++ " interval=" ++ state[\receiveInterval].round(0.001)
                            ++ "s effectiveHz=" ++ effectiveHz.round(0.01)
                            ++ " age=" ++ age.round(0.001)
                            ++ "s energy=" ++ values[0].round(0.001)
                            ++ " delta=" ++ values[5].round(0.001)
                            ++ " theta=" ++ values[6].round(0.001)
                            ++ " alpha=" ++ values[7].round(0.001)
                            ++ " beta=" ++ values[8].round(0.001)
                        ).postln;
                        state[\lastDisplayAt] = now;
                        state[\lastDisplayFrameCount] = state[\frameCount];
                    };
                } {
                    "Organism v2: rejected frame (expected exactly 9 values).".warn;
                };
            }, '/eeg/organism/v2/frame', recvPort: 57120);

            OSCdef(\eegOrganismV2Stop, {
                state[\stop].value(false);
            }, '/eeg/organism/v2/stop', recvPort: 57120);

            state[\watchdog] = Routine({
                loop {
                    0.25.wait;
                    if(state[\stopping].not and: {
                        (Main.elapsedTime - state[\lastFrameAt])
                            > v2Config[\watchdogTimeout]
                    } and: { state[\timedOut].not }) {
                        state[\timedOut] = true;
                        synth.set(\transportAlive, 0);
                        (
                            "Organism v2 WATCHDOG: no frame for "
                            ++ v2Config[\watchdogTimeout]
                            ++ " seconds; transport gain fading to silence."
                        ).warn;
                    };
                };
            }).play(AppClock);

            "ORGANISM V2 SYNTHETIC RECEIVER READY on UDP 57120".postln;
            "Stable tree: one dedicated Group + one persistent harmonic Synth.".postln;
            ("Node IDs: " ++ state[\nodeIDs]).postln;
            "Waiting for /eeg/organism/v2/frame; silent until the first frame.".postln;
            "Centroid, mobility, spectral entropy, and novelty are storage/display only.".postln;
            ("Exact harmonic groups: " ++ v2Config[\harmonicGroups]).postln;
        };
    }).play(AppClock);
};
state[\start] = startReceiver;

if(s.serverRunning) {
    state[\start].value;
} {
    "Organism v2 NOT started: start the existing SuperDirt/scsynth server, then evaluate again.".warn;
};
)
