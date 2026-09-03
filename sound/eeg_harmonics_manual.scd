// DISCONNECTED MANUAL AUDITION: one persistent additive harmonic field.
//
// This prototype deliberately has no /eeg/organism/frame OSCdef and no LSL,
// Python, FieldTrip, Redis, clocks, triggers, notes, noise, or autonomous motion.
// It does not boot/reboot scsynth and does not replace eeg_organism_engine.scd.

(
var here, config, def, state, oldState, synthArgs, setGroups, setEnergy;
var auditionGroup, sweepMaster, sweepBrightness, sweepGroups, stop;

here = PathName(thisProcess.nowExecutingPath).pathOnly;
thisProcess.interpreter.executeFile(here +/+ "eeg_harmonic_field_core.scd");
config = thisProcess.interpreter.executeFile(here +/+ "eeg_harmonics_manual_config.scd");

oldState = ~eegHarmonicsManual;
if(oldState.notNil and: { oldState[\stop].notNil }) {
    oldState[\stop].value(true);
};

state = IdentityDictionary.new;
state[\config] = config.copy;
state[\stopping] = false;
~eegHarmonicsManual = state;

setGroups = { |g1 = 1, g2 = 0.7, g3 = 0.34, g4 = 0.16|
    state[\synth].tryPerform(\set,
        \group1, g1.clip(0, 1), \group2, g2.clip(0, 1),
        \group3, g3.clip(0, 1), \group4, g4.clip(0, 1));
    [g1, g2, g3, g4].collect(_.clip(0, 1)).postln;
};
setEnergy = { |value = 0.72|
    state[\synth].tryPerform(\set, \masterEnergy, value.clip(0, 1));
    ("Harmonics master energy: " ++ value.clip(0, 1)).postln;
};
auditionGroup = { |oneBasedIndex = 1|
    var values, index;
    index = oneBasedIndex.asInteger.clip(1, 4) - 1;
    values = [0, 0, 0, 0];
    values[index] = 1;
    setGroups.value(*values);
    ("Harmonics isolated group " ++ (index + 1)).postln;
};

// These are finite, manually invoked demonstrations; none loops or retriggers.
sweepMaster = {
    state[\sweep].tryPerform(\stop);
    state[\sweep] = Routine({
        setGroups.value(1, 0.70, 0.34, 0.16);
        setEnergy.value(0.18); 3.wait;
        setEnergy.value(1.00); 4.wait;
        setEnergy.value(0.18);
    }).play(AppClock);
};
sweepBrightness = {
    state[\sweep].tryPerform(\stop);
    state[\sweep] = Routine({
        setEnergy.value(0.72);
        setGroups.value(1.00, 0.34, 0.08, 0.02); 3.wait;
        setGroups.value(0.02, 0.08, 0.34, 1.00); 4.wait;
        setGroups.value(1.00, 0.34, 0.08, 0.02);
    }).play(AppClock);
};
sweepGroups = {
    state[\sweep].tryPerform(\stop);
    state[\sweep] = Routine({
        4.do { |index|
            auditionGroup.value(index + 1);
            3.wait;
        };
        setGroups.value(1, 0.70, 0.34, 0.16);
    }).play(AppClock);
};
stop = { |immediate = false|
    if(state[\stopping].not) {
        state[\stopping] = true;
        state[\sweep].tryPerform(\stop);
        if(immediate) {
            state[\group].tryPerform(\freeAll);
            state[\group].tryPerform(\free);
        } {
            state[\synth].tryPerform(\set, \gate, 0);
            Routine({
                (config[\release] + 0.25).wait;
                state[\group].tryPerform(\free);
            }).play(AppClock);
        };
        "Disconnected Harmonics manual field stopped.".postln;
    };
};

state[\setGroups] = setGroups;
state[\setEnergy] = setEnergy;
state[\auditionGroup] = auditionGroup;
state[\sweepMaster] = sweepMaster;
state[\sweepBrightness] = sweepBrightness;
state[\sweepGroups] = sweepGroups;
state[\stop] = stop;

if(s.serverRunning) {
    Routine({
        var group, synth;
        def = ~makeEegHarmonicFieldSynthDef.value(\eegManualHarmonicField);
        def.add;
        s.sync;
        if(state[\stopping].not) {
            group = Group.tail(s);
            synthArgs = config.asKeyValuePairs;
            // Enforce the documented 8-or-12 choice.
            synthArgs[synthArgs.indexOf(\harmonicCount) + 1] =
                if(config[\harmonicCount] <= 8) { 8 } { 12 };
            synth = Synth.tail(group, \eegManualHarmonicField, synthArgs);
            state[\group] = group;
            state[\synth] = synth;
            "DISCONNECTED EEG HARMONICS MANUAL PALETTE READY".postln;
            "Stable tree: one dedicated Group + one continuous Synth.".postln;
            "No live EEG OSC endpoint was registered.".postln;
            "Try: ~eegHarmonicsManual[\sweepMaster].value;".postln;
            "     ~eegHarmonicsManual[\sweepBrightness].value;".postln;
            "     ~eegHarmonicsManual[\sweepGroups].value;".postln;
            "     ~eegHarmonicsManual[\auditionGroup].value(1); // 1..4".postln;
        };
    }).play(AppClock);
} {
    "Harmonics manual palette NOT started: start the existing scsynth/SuperDirt server, then evaluate again.".warn;
};
)

s.quit;