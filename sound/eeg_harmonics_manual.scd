// DISCONNECTED MANUAL AUDITION: one persistent additive harmonic field.
//
// No /eeg/organism/frame OSCdef, LSL, Python, FieldTrip, Redis, clocked sound,
// random source, note trigger, or autonomous modulation is created here.
// This file never boots, reboots, or quits the existing server.

(
var here, library, presets, audition, defaultName, defaultPreset;
var def, state, oldState, setGroups, setEnergy, setPreset;
var auditionGroup, sweepMaster, sweepBrightness, sweepGroups, stop;

here = PathName(thisProcess.nowExecutingPath).pathOnly;
thisProcess.interpreter.executeFile(here +/+ "eeg_harmonic_field_core.scd");
thisProcess.interpreter.executeFile(here +/+ "eeg_harmonics_preset_support.scd");
library = thisProcess.interpreter.executeFile(here +/+ "eeg_harmonics_manual_config.scd");
presets = library[\presets];
audition = library[\audition];
defaultName = library[\defaultPreset];
defaultPreset = presets[defaultName];

oldState = ~eegHarmonicsManual;
if(oldState.notNil and: { oldState[\stop].notNil }) {
    oldState[\stop].value(true);
};

state = IdentityDictionary.new;
state[\library] = library;
state[\presets] = presets;
state[\audition] = audition;
state[\presetName] = defaultName;
state[\preset] = defaultPreset.copy;
state[\stopping] = false;
~eegHarmonicsManual = state;

setGroups = { |g1, g2, g3, g4|
    var values;
    values = if(g1.isNil) {
        state[\preset][\baseGroups].copy
    } {
        [g1, g2, g3, g4].collect { |value| value.asFloat.clip(0, 1) }
    };
    state[\synth].tryPerform(\setn, \groupAmplitudes, values);
    ("Harmonic groups: " ++ values).postln;
};
setEnergy = { |value|
    var target;
    target = value ? state[\preset][\masterEnergy];
    target = target.asFloat.clip(0, 1);
    state[\synth].tryPerform(\set, \masterEnergy, target);
    ("Harmonics master energy: " ++ target).postln;
};
setPreset = { |name = \warm_organic|
    var key, preset;
    key = name.asSymbol;
    preset = presets[key];
    if(preset.isNil) {
        ("Unknown harmonic preset: " ++ key
            ++ ". Available: " ++ presets.keys.asArray.sort).warn;
    } {
        state[\sweep].tryPerform(\stop);
        state[\presetName] = key;
        state[\preset] = preset.copy;
        ~applyEegHarmonicPreset.value(state[\synth], preset);
        ("Harmonic preset -> " ++ key ++ " (same persistent Synth)").postln;
    };
};
auditionGroup = { |oneBasedIndex = 1|
    var values, index;
    index = oneBasedIndex.asInteger.clip(1, 4) - 1;
    values = [0, 0, 0, 0];
    values[index] = 1;
    setGroups.value(*values);
    ("Harmonics isolated group " ++ (index + 1)).postln;
};

// Finite, manually invoked control demonstrations. No routine loops.
sweepMaster = {
    state[\sweep].tryPerform(\stop);
    state[\sweep] = Routine({
        setGroups.value(*state[\preset][\baseGroups]);
        setEnergy.value(audition[\masterLow]);
        audition[\masterStageSeconds].wait;
        setEnergy.value(audition[\masterHigh]);
        audition[\masterStageSeconds].wait;
        setEnergy.value(audition[\masterLow]);
    }).play(AppClock);
};
sweepBrightness = {
    state[\sweep].tryPerform(\stop);
    state[\sweep] = Routine({
        setEnergy.value(state[\preset][\masterEnergy]);
        setGroups.value(*audition[\warmGroups]);
        audition[\spectrumStageSeconds].wait;
        setGroups.value(*audition[\brightGroups]);
        audition[\spectrumStageSeconds].wait;
        setGroups.value(*audition[\warmGroups]);
    }).play(AppClock);
};
sweepGroups = {
    state[\sweep].tryPerform(\stop);
    state[\sweep] = Routine({
        4.do { |index|
            auditionGroup.value(index + 1);
            audition[\groupStageSeconds].wait;
        };
        setGroups.value(*state[\preset][\baseGroups]);
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
                (state[\preset][\release] + 0.25).wait;
                state[\group].tryPerform(\free);
            }).play(AppClock);
        };
        "Disconnected Harmonics manual field stopped.".postln;
    };
};

state[\setGroups] = setGroups;
state[\setEnergy] = setEnergy;
state[\setPreset] = setPreset;
state[\auditionGroup] = auditionGroup;
state[\sweepMaster] = sweepMaster;
state[\sweepBrightness] = sweepBrightness;
state[\sweepGroups] = sweepGroups;
state[\stop] = stop;

if(s.serverRunning) {
    Routine({
        var group, synth;
        def = ~makeEegHarmonicFieldSynthDef.value(
            \eegManualHarmonicField,
            defaultPreset
        );
        def.add;
        s.sync;
        if(state[\stopping].not) {
            group = Group.tail(s);
            synth = Synth.tail(group, \eegManualHarmonicField);
            state[\group] = group;
            state[\synth] = synth;
            "DISCONNECTED EEG HARMONICS PRESET PALETTE READY".postln;
            ("Preset: " ++ state[\presetName]).postln;
            "Stable tree: one Group + one continuous Synth.".postln;
            "No live EEG OSC endpoint was registered.".postln;
            "Switch: ~eegHarmonicsManual[\\setPreset].value(\\warm_organic);".postln;
            "        \\air_glass or \\dark_mineral".postln;
        };
    }).play(AppClock);
} {
    "Harmonics palette NOT started: start the existing scsynth/SuperDirt server, then evaluate again.".warn;
};
)
