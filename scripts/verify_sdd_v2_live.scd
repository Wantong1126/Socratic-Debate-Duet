// Isolated test server; never touches an existing scsynth server.
(
var root, destination, frameTotal;
root = PathName(thisProcess.nowExecutingPath).pathOnly +/+ "..";
destination = root +/+ "reports/sdd_v1/live.wav";
frameTotal = ("SDD_VERIFY_FRAMES".getenv ? "240").asInteger;
Server.default = s = Server(\sddVerification, NetAddr("127.0.0.1", 57130));
s.options.numInputBusChannels = 0;
s.options.numOutputBusChannels = 2;
s.options.memSize = 262144;
s.options.sampleRate = 48000;
s.waitForBoot({
    Routine({
        var target, recordStart;
        target = NetAddr("127.0.0.1", NetAddr.langPort);
        thisProcess.interpreter.executeFile(root +/+ "sound/eeg_organism_v2_receiver.scd");
        2.wait;
        s.prepareForRecord(destination);
        s.sync;
        s.record;
        recordStart = Main.elapsedTime;
        OSCdef(\sddTree, { |msg| ("SDD_TREE " ++ msg).postln }, '/g_queryTree.reply');
        target.sendMsg('/eeg/organism/v2/voicing', 98, 146.832, 220, 65.41, 65.41, 65.41, 0.48, 0.32, 0.2, 0, 0, 0);
        frameTotal.do { |i|
            target.sendMsg('/eeg/organism/v2/frame', 0.5, 0.24, 0.1, 0.12, 0.04, 0.82, 0.58, 0.28, 0.08);
            if((i % 40) == 0) { s.sendMsg('/g_queryTree', ~eegOrganismV2[\group].nodeID, 0) };
            0.25.wait;
        };
        ("SDD_DISCONNECT t=" ++ (Main.elapsedTime-recordStart)).postln;
        // Invalid traffic must not keep the transport alive.
        16.do {
            target.sendMsg('/eeg/organism/v2/frame', "invalid", 0.24, 0.1, 0.12, 0.04, 0.82, 0.58, 0.28, 0.08);
            0.25.wait;
        };
        ("SDD_INVALID_RESULT count=" ++ ~eegOrganismV2[\frameCount]
            ++ " timedOut=" ++ ~eegOrganismV2[\timedOut]).postln;
        target.sendMsg('/eeg/organism/v2/frame', 0.5, 0.24, 0.1, 0.12, 0.04, 0.82, 0.58, 0.28, 0.08);
        0.5.wait;
        ("SDD_STOP t=" ++ (Main.elapsedTime-recordStart)).postln;
        target.sendMsg('/eeg/organism/v2/stop');
        4.wait;
        s.sendMsg('/g_queryTree', 0, 0);
        0.5.wait;
        s.stopRecording;
        0.5.wait;
        s.quit;
        0.5.wait;
        "SDD_LIVE_COMPLETE".postln;
        0.exit;
    }).play(AppClock);
}, 20, { "SDD_BOOT_FAILED".postln; 1.exit });
)
