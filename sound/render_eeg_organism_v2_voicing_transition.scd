// Render two fixed G Lydian voicings through one persistent two-bank Synth.
(
var here, library, v2Config, preset, betaProfile;
var outputPath, oscScorePath, archiveDirectory, definition, score, options;
var frequenciesA, weightsA, frequenciesB, weightsB;
var setArray, releaseAt, renderDuration;

here = PathName(thisProcess.nowExecutingPath).pathOnly;
thisProcess.interpreter.executeFile(here +/+ "eeg_harmonic_field_v2_core.scd");
library = thisProcess.interpreter.executeFile(here +/+ "eeg_harmonics_manual_config.scd");
v2Config = thisProcess.interpreter.executeFile(here +/+ "../config/eeg_organism_v2.scd");
preset = library[\presets][v2Config[\basePreset]].copy;
v2Config[\synthOverrides].keysValuesDo { |key, value| preset[key] = value };
preset[\harmonicGroups] = v2Config[\harmonicGroups];
preset[\voiceCapacity] = v2Config[\voiceCapacity];
betaProfile = v2Config[\betaProfiles][v2Config[\betaProfile]];
betaProfile.keysValuesDo { |key, value| preset[key] = value };

outputPath = "EEG_ORGANISM_V2_OUTPUT".getenv;
if(outputPath.isNil) { "EEG_ORGANISM_V2_OUTPUT is required.".error; 1.exit };
oscScorePath = outputPath ++ ".osc";
archiveDirectory = "EEG_ORGANISM_V2_ARCHIVE_DIR".getenv;
if(archiveDirectory.notNil) { Archive.archiveDir = archiveDirectory };

frequenciesA = [97.998859, 146.832384, 220.0, 65.41, 65.41, 65.41];
weightsA = [0.48, 0.32, 0.20, 0.0, 0.0, 0.0];
frequenciesB = [138.591315, 184.997211, 277.182631, 369.994423, 65.41, 65.41];
weightsB = [0.34, 0.28, 0.22, 0.16, 0.0, 0.0];
setArray = { |nodeID, control, values|
    [\n_setn, nodeID, control, values.size] ++ values
};

definition = ~makeEegOrganismV2HarmonicFieldSynthDef.value(
    \eegOrganismV2VoicingTransitionRender,
    preset
);
releaseAt = 16.0;
renderDuration = releaseAt + preset[\release] + 0.5;
score = [
    [0.0, [\d_recv, definition.asBytes]],
    [0.01, [\s_new, \eegOrganismV2VoicingTransitionRender, 1000, 0, 0,
        \masterEnergy, 0.68, \transportAlive, 1, \voicingBank, 0]],
    [0.02, setArray.value(1000, \voiceFrequenciesA, frequenciesA)],
    [0.02, setArray.value(1000, \voiceWeightsA, weightsA)],
    // A hold -> B transition -> B hold -> A transition -> A hold.
    [4.0, setArray.value(1000, \voiceFrequenciesB, frequenciesB)],
    [4.0, setArray.value(1000, \voiceWeightsB, weightsB)],
    [4.01, [\n_set, 1000, \voicingBank, 1]],
    [9.0, setArray.value(1000, \voiceFrequenciesA, frequenciesA)],
    [9.0, setArray.value(1000, \voiceWeightsA, weightsA)],
    [9.01, [\n_set, 1000, \voicingBank, 0]],
    [releaseAt, [\n_set, 1000, \gate, 0]],
    [renderDuration, [\c_set, 0, 0]]
];

options = ServerOptions.new;
options.protocol = \tcp;
options.numOutputBusChannels = 2;
options.numInputBusChannels = 0;
options.sampleRate = 48000;
options.blockSize = 64;
options.memSize = 262144;

Score(score).recordNRT(
    oscFilePath: oscScorePath,
    outputFilePath: outputPath,
    sampleRate: 48000,
    headerFormat: "WAV",
    sampleFormat: "int24",
    options: options,
    duration: renderDuration,
    action: {
        File.delete(oscScorePath);
        ("RENDERED V2 VOICING TRANSITION -> " ++ outputPath).postln;
        0.exit;
    }
);
)
