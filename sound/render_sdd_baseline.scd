// T09: render the exact control/voicing plan from config/sdd_v1.toml.
(
var root, plan, preset, config, library, definition, score, options, output;
root = PathName(thisProcess.nowExecutingPath).pathOnly +/+ "..";
plan = thisProcess.interpreter.executeFile(root +/+ "reports/sdd_v1/baseline_plan.scd");
thisProcess.interpreter.executeFile(root +/+ "sound/eeg_harmonic_field_v2_core.scd");
library = thisProcess.interpreter.executeFile(root +/+ "sound/eeg_harmonics_manual_config.scd");
config = thisProcess.interpreter.executeFile(root +/+ "config/eeg_organism_v2.scd");
preset = library[\presets][config[\basePreset]].copy;
config[\synthOverrides].keysValuesDo { |k,v| preset[k] = v };
config[\betaProfiles][config[\betaProfile]].keysValuesDo { |k,v| preset[k] = v };
preset[\harmonicGroups] = config[\harmonicGroups];
preset[\voiceCapacity] = config[\voiceCapacity];
definition = ~makeEegOrganismV2HarmonicFieldSynthDef.value(\sddBaseline, preset);
score = List.new;
score.add([0, [\d_recv, definition.asBytes]]);
score.add([0.01, [\s_new, \sddBaseline, 1000, 0, 0, \transportAlive, 1, \masterEnergy, 0]]);
score.add([0.02, [\n_setn, 1000, \voiceFrequenciesA, 6] ++ plan[\frequencies]]);
score.add([0.02, [\n_setn, 1000, \voiceWeightsA, 6] ++ plan[\weights]]);
plan[\frames].do { |event|
    score.add([event[0]+0.03, [\n_set, 1000, \masterEnergy, event[1][0]]]);
    score.add([event[0]+0.03, [\n_setn, 1000, \groupAmplitudes, 4] ++ event[1].copyRange(5,8)]);
};
score.add([plan[\duration], [\n_set, 1000, \transportAlive, 0]]);
score.add([plan[\duration]+0.6, [\n_set, 1000, \gate, 0]]);
score.add([plan[\duration]+3.5, [\c_set, 0, 0]]);
options = ServerOptions.new;
options.numInputBusChannels = 0;
options.numOutputBusChannels = 2;
options.memSize = 262144;
options.sampleRate = 48000;
output = root +/+ "reports/sdd_v1/baseline_energy.wav";
Score(score.asArray).recordNRT(output ++ ".osc", output, sampleRate: 48000,
    headerFormat: "WAV", sampleFormat: "int24", options: options,
    duration: plan[\duration]+3.5,
    action: { "SDD_BASELINE_RENDERED one s_new; stop transport then gate".postln; 0.exit });
)
