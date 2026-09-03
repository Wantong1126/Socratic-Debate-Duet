// Render one deterministic, disconnected manual-audition test with scsynth NRT.
// Called by scripts/render_eeg_harmonics_manual.ps1; never opens an audio device.

(
var here, config, def, testName, outputPath, duration, renderDuration;
var initial, changes, scoreMessages, synthMessage, options;

here = PathName(thisProcess.nowExecutingPath).pathOnly;
thisProcess.interpreter.executeFile(here +/+ "eeg_harmonic_field_core.scd");
config = thisProcess.interpreter.executeFile(here +/+ "eeg_harmonics_manual_config.scd");
testName = "EEG_HARMONICS_TEST".getenv ? "master_energy";
outputPath = "EEG_HARMONICS_OUTPUT".getenv;

if(outputPath.isNil) {
    "EEG_HARMONICS_OUTPUT is required.".error;
    1.exit;
};

def = ~makeEegHarmonicFieldSynthDef.value(\eegManualHarmonicFieldRender);
initial = config.copy;
initial[\harmonicCount] = if(config[\harmonicCount] <= 8) { 8 } { 12 };
changes = List.new;

switch(testName,
    "master_energy", {
        // Leave a longer final low plateau so the fixed reverb can fully shed
        // the preceding high-energy tail before the comparison window.
        duration = 12.0;
        initial.putAll((
            group1: 1.00, group2: 0.70, group3: 0.34, group4: 0.16,
            masterEnergy: 0.18
        ));
        changes.add([3.0, [\n_set, 1000, \masterEnergy, 1.00]]);
        changes.add([6.2, [\n_set, 1000, \masterEnergy, 0.18]]);
    },
    "redistribution", {
        duration = 9.0;
        initial.putAll((
            group1: 1.00, group2: 0.34, group3: 0.08, group4: 0.02,
            masterEnergy: 0.72
        ));
        changes.add([3.0, [\n_set, 1000,
            \group1, 0.02, \group2, 0.08, \group3, 0.34, \group4, 1.00]]);
        changes.add([6.2, [\n_set, 1000,
            \group1, 1.00, \group2, 0.34, \group3, 0.08, \group4, 0.02]]);
    },
    "group1", {
        duration = 5.5;
        initial.putAll((group1: 1, group2: 0, group3: 0, group4: 0, masterEnergy: 0.72));
    },
    "group2", {
        duration = 5.5;
        initial.putAll((group1: 0, group2: 1, group3: 0, group4: 0, masterEnergy: 0.72));
    },
    "group3", {
        duration = 5.5;
        initial.putAll((group1: 0, group2: 0, group3: 1, group4: 0, masterEnergy: 0.72));
    },
    "group4", {
        duration = 5.5;
        initial.putAll((group1: 0, group2: 0, group3: 0, group4: 1, masterEnergy: 0.72));
    },
    {
        ("Unknown EEG_HARMONICS_TEST: " ++ testName).error;
        1.exit;
    }
);

renderDuration = duration + config[\release] + 0.7;
synthMessage = [\s_new, \eegManualHarmonicFieldRender, 1000, 0, 0]
    ++ initial.asKeyValuePairs;
scoreMessages = List.new;
scoreMessages.add([0.0, [\d_recv, def.asBytes, synthMessage]]);
changes.do { |item| scoreMessages.add(item) };
scoreMessages.add([duration, [\n_set, 1000, \gate, 0]]);
scoreMessages.add([renderDuration, [\c_set, 0, 0]]);

options = ServerOptions.new;
// Score.recordNRT defaults to port 57110. The persistent project server already
// owns UDP 57110, so use TCP for this separate offline process and avoid any
// contact with, restart of, or interruption to that server.
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
