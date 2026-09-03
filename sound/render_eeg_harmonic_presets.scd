// Render one complete, identical-structure preset audition in scsynth NRT.

(
var here, library, presets, audition, presetName, preset, outputPath, def;
var score, options, time, gateTime, renderDuration, add, setGroups;

here = PathName(thisProcess.nowExecutingPath).pathOnly;
thisProcess.interpreter.executeFile(here +/+ "eeg_harmonic_field_core.scd");
library = thisProcess.interpreter.executeFile(here +/+ "eeg_harmonics_manual_config.scd");
presets = library[\presets];
audition = library[\audition];
presetName = ("EEG_HARMONIC_PRESET".getenv ? "warm_organic").asSymbol;
preset = presets[presetName];
outputPath = "EEG_HARMONIC_PRESET_OUTPUT".getenv;
if(preset.isNil) { ("Unknown preset: " ++ presetName).error; 1.exit };
if(outputPath.isNil) { "EEG_HARMONIC_PRESET_OUTPUT is required.".error; 1.exit };

def = ~makeEegHarmonicFieldSynthDef.value(\eegHarmonicPresetRender, preset);
score = List.new;
add = { |at, message| score.add([at, message]) };
setGroups = { |at, values|
    add.value(at, [\n_setn, 1000, \groupAmplitudes, 4] ++ values);
};

// Identical structure and timestamps for all three presets.
time = 0.0;
add.value(time, [\d_recv, def.asBytes,
    [\s_new, \eegHarmonicPresetRender, 1000, 0, 0]]);

// Base full mix.
time = time + audition[\baseSeconds];

// Master low / high / low with a fixed spectrum.
add.value(time, [\n_set, 1000, \masterEnergy, audition[\masterLow]]);
time = time + audition[\masterStageSeconds];
add.value(time, [\n_set, 1000, \masterEnergy, audition[\masterHigh]]);
time = time + audition[\masterStageSeconds];
add.value(time, [\n_set, 1000, \masterEnergy, audition[\masterLow]]);
time = time + audition[\masterReturnSeconds];

// Warm / bright / warm redistribution at preset baseline energy.
add.value(time, [\n_set, 1000, \masterEnergy, preset[\masterEnergy]]);
setGroups.value(time, audition[\warmGroups]);
time = time + audition[\spectrumStageSeconds];
setGroups.value(time, audition[\brightGroups]);
time = time + audition[\spectrumStageSeconds];
setGroups.value(time, audition[\warmGroups]);
time = time + audition[\spectrumStageSeconds];

// Groups 1 / 2 / 3 / 4 in isolation.
4.do { |index|
    var values;
    values = [0, 0, 0, 0];
    values[index] = 1;
    setGroups.value(time, values);
    time = time + audition[\groupStageSeconds];
};

// Return to preset base full mix.
setGroups.value(time, preset[\baseGroups]);
time = time + audition[\finalBaseSeconds];
gateTime = time;
add.value(gateTime, [\n_set, 1000, \gate, 0]);
renderDuration = gateTime + audition[\renderTailSeconds];
add.value(renderDuration, [\c_set, 0, 0]);

options = ServerOptions.new;
options.protocol = \tcp;
options.numOutputBusChannels = 2;
options.numInputBusChannels = 0;
options.sampleRate = 48000;
options.blockSize = 64;
options.memSize = 65536;

Score(score).recordNRT(
    outputFilePath: outputPath,
    sampleRate: 48000,
    headerFormat: "WAV",
    sampleFormat: "int24",
    options: options,
    duration: renderDuration,
    action: {
        ("RENDERED PRESET " ++ presetName ++ " -> " ++ outputPath).postln;
        0.exit;
    }
);
)
