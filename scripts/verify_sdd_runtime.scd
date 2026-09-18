// Companion to verify_sdd_runtime.py: isolated server, real Python OSC traffic.
(
var root, begin;
root = PathName(thisProcess.nowExecutingPath).pathOnly +/+ "..";
Server.default = s = Server(\sddRuntimeTest, NetAddr("127.0.0.1", 57130));
s.options.numInputBusChannels = 0;
s.options.numOutputBusChannels = 2;
s.options.memSize = 262144;
s.options.sampleRate = 48000;
begin = { thisProcess.interpreter.executeFile(root +/+ "sound/eeg_organism_v2_receiver.scd") };
s.waitForBoot({
    Routine({
        begin.value;
        2.wait;
        s.prepareForRecord(root +/+ "reports/sdd_v1/runtime.wav");
        s.sync;
        s.record;
        OSCdef(\sddRuntimeTree, { |msg| ("RUNTIME_TREE " ++ msg).postln }, '/g_queryTree.reply');
        OSCdef(\sddRuntimeReset, { begin.value }, '/sdd/test/restart');
        OSCdef(\sddRuntimeFinish, {
            Routine({
                s.sendMsg('/g_queryTree', 0, 0);
                0.3.wait;
                s.stopRecording;
                0.3.wait;
                s.quit;
                0.5.wait;
                "SDD_RUNTIME_COMPLETE".postln;
                0.exit;
            }).play(AppClock)
        }, '/sdd/test/finish');
        "SDD_RUNTIME_READY".postln;
        Routine({
            80.do { s.sendMsg('/g_queryTree', 0, 0); 1.wait };
            "SDD_RUNTIME_TEST_TIMEOUT".postln;
            s.quit;
            1.wait;
            1.exit;
        }).play(AppClock);
    }).play(AppClock);
}, 20, { 1.exit });
)
