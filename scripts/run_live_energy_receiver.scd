// Current participant-A receiver for an explicitly authorized live-energy audition.
(
var root;
root = PathName(thisProcess.nowExecutingPath).pathOnly +/+ "..";
Server.default = s = Server(\liveEnergyAudition, NetAddr("127.0.0.1", 57130));
s.options.numInputBusChannels = 0;
s.options.numOutputBusChannels = 2;
s.options.memSize = 262144;
s.options.sampleRate = 48000;
s.waitForBoot({
    Routine({
        thisProcess.interpreter.executeFile(root +/+ "sound/eeg_organism_v2_receiver.scd");
        2.wait;
        "LIVE_ENERGY_RECEIVER_READY".postln;
        while({ ~eegOrganismV2[\stopping].not }, { 0.25.wait });
        3.wait;
        s.sendMsg('/g_queryTree', 0, 0);
        0.5.wait;
        s.quit;
        0.5.wait;
        "LIVE_ENERGY_RECEIVER_COMPLETE".postln;
        0.exit;
    }).play(AppClock);
}, 20, { 1.exit });
)
