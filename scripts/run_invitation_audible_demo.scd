// Boots the current receiver and enables only its diagnostic invitation gain.
(
var root;
root = PathName(thisProcess.nowExecutingPath).pathOnly +/+ "..";
Server.default = s = Server(\invitationAudibleDemo, NetAddr("127.0.0.1", 57130));
s.options.numInputBusChannels = 0;
s.options.numOutputBusChannels = 2;
s.options.memSize = 262144;
s.options.sampleRate = 48000;
s.waitForBoot({
    Routine({
        thisProcess.interpreter.executeFile(root +/+ "sound/eeg_organism_v2_receiver.scd");
        2.wait;
        ~eegOrganismV2[\synth].set(\invitationDiagnosticDepth, 0.85);
        OSCdef(\invitationAudibleFinish, {
            Routine({
                ~eegOrganismV2[\stop].value(false);
                3.wait;
                s.quit;
                0.5.wait;
                "INVITATION_AUDIBLE_COMPLETE".postln;
                0.exit;
            }).play(AppClock)
        }, '/sdd/invitation/demo/finish');
        "INVITATION_AUDIBLE_READY".postln;
    }).play(AppClock);
}, 20, { 1.exit });
)
