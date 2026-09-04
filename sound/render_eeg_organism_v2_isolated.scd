// Render one steady-state organism v2 LOW or HIGH condition in NRT.
(
var here, library, v2Config, preset, betaProfileName, betaProfile;
var field, level, outputPath, oscScorePath, archiveDirectory;
var groups, bandNames, bandIndex, definition, score, options;
var gateTime, renderDuration;

here = PathName(thisProcess.nowExecutingPath).pathOnly;
thisProcess.interpreter.executeFile(here +/+ "eeg_harmonic_field_v2_core.scd");
library = thisProcess.interpreter.executeFile(here +/+ "eeg_harmonics_manual_config.scd");
v2Config = thisProcess.interpreter.executeFile(
    here +/+ "../config/eeg_organism_v2.scd"
);
preset = library[\presets][v2Config[\basePreset]].copy;
v2Config[\synthOverrides].keysValuesDo { |key, value| preset[key] = value };
preset[\harmonicGroups] = v2Config[\harmonicGroups];
betaProfileName = ("EEG_ORGANISM_V2_BETA_PROFILE".getenv
    ? v2Config[\betaProfile].asString).asSymbol;
betaProfile = v2Config[\betaProfiles][betaProfileName];
if(betaProfile.isNil) {
    ("Unknown organism v2 beta profile: " ++ betaProfileName).error;
    1.exit
};
betaProfile.keysValuesDo { |key, value| preset[key] = value };

field = ("EEG_ORGANISM_V2_FIELD".getenv ? "energy").asSymbol;
level = ("EEG_ORGANISM_V2_LEVEL".getenv ? "low").asSymbol;
outputPath = "EEG_ORGANISM_V2_OUTPUT".getenv;
if(outputPath.isNil) { "EEG_ORGANISM_V2_OUTPUT is required.".error; 1.exit };
// Keep the temporary NRT score beside the requested workspace output instead
// of relying on a user-profile temp directory that may not be writable.
oscScorePath = outputPath ++ ".osc";
archiveDirectory = "EEG_ORGANISM_V2_ARCHIVE_DIR".getenv;
if(archiveDirectory.notNil) { Archive.archiveDir = archiveDirectory };

groups = preset[\baseGroups].copy;
if(field == \energy) {
    preset[\masterEnergy] = if(level == \high) { 1.0 } { 0.0 };
} {
    bandNames = [\delta, \theta, \alpha, \beta];
    bandIndex = bandNames.indexOf(field);
    if(bandIndex.isNil) { ("Unknown v2 field: " ++ field).error; 1.exit };
    preset[\masterEnergy] = 0.68;
    groups = [0.01, 0.01, 0.01, 0.01];
    groups[bandIndex] = if(level == \high) { 1.0 } { 0.0 };
};
preset[\baseGroups] = groups;

definition = ~makeEegOrganismV2HarmonicFieldSynthDef.value(
    \eegOrganismV2IsolatedRender,
    preset
);
gateTime = 6.0;
renderDuration = gateTime + preset[\release] + 0.5;
score = [
    [0.0, [\d_recv, definition.asBytes,
        [\s_new, \eegOrganismV2IsolatedRender, 1000, 0, 0,
            \transportAlive, 1]]],
    [gateTime, [\n_set, 1000, \gate, 0]],
    [renderDuration, [\c_set, 0, 0]]
];

options = ServerOptions.new;
options.protocol = \tcp;
options.numOutputBusChannels = 2;
options.numInputBusChannels = 0;
options.sampleRate = 48000;
options.blockSize = 64;
options.memSize = 65536;

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
        ("RENDERED V2 " ++ field ++ " " ++ level ++ " -> " ++ outputPath).postln;
        0.exit;
    }
);
)
