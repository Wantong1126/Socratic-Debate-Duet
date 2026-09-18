// Isolated receiver harness for invitation-control validation.
(
var root, output;
root = PathName(thisProcess.nowExecutingPath).pathOnly +/+ "..";
output = "SDD_INVITATION_OUTPUT".getenv;
if(output.isNil) { "SDD_INVITATION_OUTPUT is required.".error; 1.exit };
Server.default = s = Server(\invitationValidation, NetAddr("127.0.0.1", 57130));
s.options.numInputBusChannels = 0;
s.options.numOutputBusChannels = 2;
s.options.memSize = 262144;
s.options.sampleRate = 48000;
s.waitForBoot({
    Routine({
        thisProcess.interpreter.executeFile(root +/+ "sound/eeg_organism_v2_receiver.scd");
        2.wait;
        s.prepareForRecord(output);
        s.sync;
        s.record;
        OSCdef(\invitationTree, { |msg|
            ("INVITATION_TREE " ++ msg).postln
        }, '/g_queryTree.reply');
        OSCdef(\invitationFinish, {
            Routine({
                s.sendMsg('/g_queryTree', 0, 0);
                0.4.wait;
                s.stopRecording;
                0.4.wait;
                s.quit;
                0.5.wait;
                "INVITATION_RUNTIME_COMPLETE".postln;
                0.exit;
            }).play(AppClock)
        }, '/sdd/invitation/test/finish');
        "INVITATION_RUNTIME_READY".postln;
        Routine({
            45.do {
                s.sendMsg('/g_queryTree', 0, 0);
                0.5.wait;
            };
            "INVITATION_RUNTIME_TIMEOUT".postln;
            s.quit;
            1.wait;
            1.exit;
        }).play(AppClock);
    }).play(AppClock);
}, 20, { 1.exit });
)
