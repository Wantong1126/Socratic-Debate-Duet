// ORGANISM V2 SYNTHETIC RECEIVER: one persistent additive harmonic field.
//
// Evaluate only after the existing SuperDirt/scsynth server is running.
// This file never boots, reboots, or quits the server. It reuses the tested
// harmonic-field SynthDef factory and creates one dedicated Group + one Synth.
// Both six-slot pitch banks live inside that one persistent Synth.
// Frame order: energy, centroid, mobility, spectralEntropy, novelty,
// delta, theta, alpha, beta.

(
var here, library, v2Config, preset, betaProfile, frameOrder, oldState, state;
var clampUnit, clampFrequency, stopReceiver, startReceiver;

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
preset[\voiceCapacity] = v2Config[\voiceCapacity];
betaProfile = v2Config[\betaProfiles][v2Config[\betaProfile]];
if(betaProfile.isNil) {
    Error("Unknown organism v2 beta profile: " ++ v2Config[\betaProfile]).throw
};
betaProfile.keysValuesDo { |key, value| preset[key] = value };
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
state[\released] = false;
state[\preset] = preset;
state[\config] = v2Config;
state[\previousFrameAt] = nil;
state[\receiveInterval] = 0.0;
state[\lastDisplayFrameCount] = 0;
state[\activeVoicingBank] = 0;
state[\voicingCount] = 0;
state[\lastVoicing] = IdentityDictionary.new;
state[\nextVoicingAt] = Main.elapsedTime;
state[\invitationTarget] = 0; // This receiver currently owns participant A only.
state[\invitationSession] = nil;
state[\invitationLastSeq] = -1;
state[\invitationAmount] = 0.0;
state[\invitationCount] = 0;
~eegOrganismV2 = state;

clampUnit = { |item|
    var value;
    value = try { item.asFloat } { 0.0 };
    if(value.isNaN) { value = 0.0 };
    value.clip(0.0, 1.0);
};
clampFrequency = { |item|
    var value;
    value = try { item.asFloat } { preset[\fundamental].asFloat };
    if(value.isNaN) { value = preset[\fundamental].asFloat };
    value.clip(
        preset[\voiceFrequencyMinHz],
        preset[\voiceFrequencyMaxHz]
    );
};

stopReceiver = { |immediate = false|
    var group, synth, watchdogFade, release;
    group = state[\group];
    synth = state[\synth];
    watchdogFade = state[\preset][\watchdogFade].asFloat.clip(0.05, 4);
    release = state[\preset][\release].asFloat.clip(0.1, 15);

    if(immediate and: { state[\stopping] }) {
        state[\releaseTask].tryPerform(\stop);
        if(state[\released].not) {
            // Mark before sending the frees: a later replacement must not issue
            // a second free after this asynchronous server command completes.
            state[\released] = true;
            group.tryPerform(\freeAll);
            group.tryPerform(\free);
        };
        "Organism v2: in-progress release freed for replacement.".postln;
    } {
        if(state[\stopping].not) {
            state[\stopping] = true;
            [\eegOrganismV2Frame, \eegOrganismV2Voicing,
                \sddInvitationControlV1,
                \eegOrganismV2Stop].do { |key|
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
                        // Set before the asynchronous free so a later evaluate
                        // can observe that this dedicated Group is gone.
                        state[\released] = true;
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
        // The receiver is evaluated only with an already-running server. Send
        // this definition directly instead of writing a user synthdef file.
        // Register controls in the language-side SynthDesc library so callers
        // can use the named controls without storing a project .scsyndef.
        definition.asSynthDesc;
        definition.send(s);
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
                if(message.size == 10 and: { state[\stopping].not } and: {
                    message.copyRange(1, 9).every { |item|
                        item.isNumber and: { item.isNaN.not } and: {
                            item >= 0 and: { item <= 1 }
                        }
                    }
                }) {
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
                    "Frame values must be finite numbers in [0,1]; watchdog not refreshed.".warn;
                };
            }, '/eeg/organism/v2/frame', recvPort: 57120);

            OSCdef(\eegOrganismV2Voicing, { |message|
                var frequencies, weights, nextBank, now;
                if(message.size == 13 and: { state[\stopping].not }) {
                    now = Main.elapsedTime;
                    frequencies = message.copyRange(1, 6).collect(clampFrequency);
                    weights = message.copyRange(7, 12).collect(clampUnit);
                    if(now < state[\nextVoicingAt]) {
                        "Organism v2: voicing ignored until current crossfade completes.".warn;
                    } {
                        if(weights.sum > 0.0001) {
                            // Populate only the inaudible bank, then crossfade the
                            // same persistent Synth. No server object is allocated.
                            nextBank = 1 - state[\activeVoicingBank];
                            if(nextBank == 0) {
                                synth.setn(\voiceFrequenciesA, frequencies);
                                synth.setn(\voiceWeightsA, weights);
                            } {
                                synth.setn(\voiceFrequenciesB, frequencies);
                                synth.setn(\voiceWeightsB, weights);
                            };
                            synth.set(\voicingBank, nextBank);
                            state[\activeVoicingBank] = nextBank;
                            state[\lastVoicing][\frequenciesHz] = frequencies;
                            state[\lastVoicing][\weights] = weights;
                            state[\voicingCount] = state[\voicingCount] + 1;
                            state[\nextVoicingAt] = now + preset[\voicingCrossfade];
                            ("Organism v2 voicing=" ++ state[\voicingCount]
                                ++ " bank=" ++ nextBank
                                ++ " frequenciesHz=" ++ frequencies
                                ++ " weights=" ++ weights).postln;
                        } {
                            "Organism v2: rejected silent voicing (all weights zero).".warn;
                        };
                    };
                } {
                    "Organism v2: rejected voicing (expected 6 frequencies + 6 weights).".warn;
                };
            }, '/eeg/organism/v2/voicing', recvPort: 57120);

            OSCdef(\sddInvitationControlV1, { |message|
                var target, sessionID, eventID, seq, age, amount;
                var numericValid, identityValid, targetValid, sequenceValid;
                if(message.size == 7 and: { state[\stopping].not }) {
                    target = message[1];
                    sessionID = message[2];
                    eventID = message[3];
                    seq = message[4];
                    age = message[5];
                    amount = message[6];
                    numericValid = [target, seq, age, amount].every { |item|
                        item.isNumber and: { item.isNaN.not }
                    } and: {
                        seq >= 0 and: { seq <= 2147483647 } and: {
                            seq == seq.asInteger and: {
                                age >= 0 and: {
                                    age <= v2Config[\invitationMessageMaxAge] and: {
                                        amount >= 0 and: { amount <= 1 }
                                    }
                                }
                            }
                        }
                    };
                    // SuperCollider decodes OSC string atoms as Symbols on this
                    // runtime; accept either textual representation, never numbers.
                    identityValid = ((sessionID.class == String) or: {
                        sessionID.class == Symbol
                    }) and: {
                        sessionID.asString.size > 0 and: {
                            ((eventID.class == String) or: {
                                eventID.class == Symbol
                            }) and: { eventID.asString.size > 0 }
                        }
                    };
                    targetValid = target == state[\invitationTarget];
                    sequenceValid = numericValid and: {
                        seq > state[\invitationLastSeq]
                    };
                    if(numericValid and: { identityValid } and: { targetValid }
                        and: { sequenceValid } and: {
                            state[\invitationSession].isNil or: {
                                state[\invitationSession] == sessionID
                            }
                        }) {
                        state[\invitationSession] = sessionID;
                        state[\invitationLastSeq] = seq.asInteger;
                        state[\invitationAmount] = amount.asFloat;
                        state[\invitationCount] = state[\invitationCount] + 1;
                        // This is a neutral control on the existing participant-A
                        // Synth. It creates no node and has no acoustic mapping yet.
                        synth.set(\invitationAmount, amount);
                        ("Invitation control accepted target=A session=" ++ sessionID
                            ++ " event=" ++ eventID ++ " seq=" ++ seq
                            ++ " amount=" ++ amount.round(0.001)
                            ++ " age=" ++ age.round(0.001)).postln;
                    } {
                        ("Invitation control rejected target=" ++ target
                            ++ " session=" ++ sessionID ++ " event=" ++ eventID
                            ++ " seq=" ++ seq ++ " age=" ++ age
                            ++ " amount=" ++ amount
                            ++ " classes[session=" ++ sessionID.class
                            ++ ",event=" ++ eventID.class ++ "]"
                            ++ " checks[numeric=" ++ numericValid
                            ++ ",identity=" ++ identityValid
                            ++ ",target=" ++ targetValid
                            ++ ",sequence=" ++ sequenceValid ++ "]").warn;
                    };
                } {
                    "Invitation control rejected: expected 6 values.".warn;
                };
                // Deliberately do not update lastFrameAt or transportAlive here.
            }, '/sdd/invitation/v1/control', recvPort: 57120);

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
            "Voicing endpoint: /eeg/organism/v2/voicing (6 frequencies + 6 weights).".postln;
            "Invitation endpoint: /sdd/invitation/v1/control (participant A only).".postln;
            "Centroid, mobility, spectral entropy, and novelty are storage/display only.".postln;
            ("Exact harmonic groups: " ++ v2Config[\harmonicGroups]).postln;
            ("Beta profile: " ++ v2Config[\betaProfile]
                ++ " (ceiling=" ++ preset[\betaCeilingHz]
                ++ " Hz, upper tilt=" ++ preset[\betaUpperPartialTiltDb]
                ++ " dB, trim=" ++ preset[\betaTrim] ++ ")").postln;
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
