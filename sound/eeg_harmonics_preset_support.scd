// Language-side preset helpers shared by the manual engine.
// This file creates no Synth, OSC endpoint, clock, or server connection.

~eegHarmonicScalarPresetKeys = [
    \fundamental, \harmonicCount, \harmonicRollOff,
    \masterEnergy, \energyMinDb, \energyMaxDb,
    \controlLag, \energyLag, \stereoWidth, \saturationDrive,
    \delayMix, \delayTimeLeft, \delayTimeRight,
    \reverbMix, \reverbRoom, \reverbTime, \reverbDamping,
    \reverbInputBw, \reverbSpread, \reverbEarly, \reverbTail,
    \outputTrim, \limiterDb, \attack, \release
];

~applyEegHarmonicPreset = { |synth, preset|
    var scalarArgs;
    scalarArgs = ~eegHarmonicScalarPresetKeys.collect { |key|
        [key, preset[key]]
    }.flat;
    synth.set(*scalarArgs);
    synth.setn(\groupAmplitudes, preset[\baseGroups]);
    synth.setn(\groupTrims, preset[\groupTrims]);
    synth.setn(\groupLoudnessComp, preset[\groupLoudnessComp]);
    synth.setn(\panPositions, preset[\panPositions]);
};
