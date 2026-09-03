// Legacy six-file isolated renderer, retained for reproducibility.
// New preset comparison renders use render_eeg_harmonic_presets.scd.

(
var here, library, preset, audition, initialPreset, def;
var testName, outputPath, duration, renderDuration;
var changes, scoreMessages, options, groupMessage;

here = PathName(thisProcess.nowExecutingPath).pathOnly;
thisProcess.interpreter.executeFile(here +/+ "eeg_harmonic_field_core.scd");
library = thisProcess.interpreter.executeFile(here +/+ "eeg_harmonics_manual_config.scd");
preset = library[\presets][library[\defaultPreset]];
audition = library[\audition];
testName = "EEG_HARMONICS_TEST".getenv ? "master_energy";
outputPath = "EEG_HARMONICS_OUTPUT".getenv;
if(outputPath.isNil) { "EEG_HARMONICS_OUTPUT is required.".error; 1.exit };

initialPreset = preset.copy;
changes = List.new;
groupMessage = { |time, values|
    changes.add([time, [\n_setn, 1000, \groupAmplitudes, 4] ++ values]);
};

switch(testName,
    "master_energy", {
        duration = 12.0;
        initialPreset[\masterEnergy] = audition[\masterLow];
        changes.add([3.0, [\n_set, 1000, \masterEnergy, 1.00]]);
        changes.add([6.2, [\n_set, 1000, \masterEnergy, audition[\masterLow]]]);
    },
    "redistribution", {
        duration = 9.0;
        initialPreset[\baseGroups] = audition[\warmGroups];
        groupMessage.value(3.0, audition[\brightGroups]);
        groupMessage.value(6.2, audition[\warmGroups]);
    },
    "group1", { duration = 5.5; initialPreset[\baseGroups] = [1, 0, 0, 0] },
    "group2", { duration = 5.5; initialPreset[\baseGroups] = [0, 1, 0, 0] },
    "group3", { duration = 5.5; initialPreset[\baseGroups] = [0, 0, 1, 0] },
    "group4", { duration = 5.5; initialPreset[\baseGroups] = [0, 0, 0, 1] },
    { ("Unknown EEG_HARMONICS_TEST: " ++ testName).error; 1.exit }
);

def = ~makeEegHarmonicFieldSynthDef.value(
    \eegManualHarmonicFieldRender,
    initialPreset
);
renderDuration = duration + 4.7;
scoreMessages = List.new;
scoreMessages.add([0.0, [\d_recv, def.asBytes,
    [\s_new, \eegManualHarmonicFieldRender, 1000, 0, 0]]]);
changes.do { |item| scoreMessages.add(item) };
scoreMessages.add([duration, [\n_set, 1000, \gate, 0]]);
scoreMessages.add([renderDuration, [\c_set, 0, 0]]);

options = ServerOptions.new;
options.protocol = \tcp;
options.numOutputBusChannels = 2;
options.numInputBusChannels = 0;
options.sampleRate = 48000;
options.blockSize = 64;
options.memSize = 65536;

Score(scoreMessages).recordNRT(
    outputFilePath: outputPath,
    sampleRate: 48000,
    headerFormat: "WAV",
    sampleFormat: "int24",
    options: options,
    duration: renderDuration,
    action: {
        ("RENDERED " ++ testName ++ " -> " ++ outputPath).postln;
        0.exit;
    }
);
)
