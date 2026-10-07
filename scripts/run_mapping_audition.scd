(
    var root, controlPort, serverPort;
root = PathName(thisProcess.nowExecutingPath).pathOnly +/+ "..";
    controlPort = "SDD_AUDITION_OSC_PORT".getenv;
    controlPort = if(controlPort.isNil) { 57120 } { controlPort.asInteger };
    serverPort = "SDD_AUDITION_SERVER_PORT".getenv;
    serverPort = if(serverPort.isNil) { 57130 } { serverPort.asInteger };
    if((controlPort < 1) or: { controlPort > 65535 }) {
        Error("SDD_AUDITION_OSC_PORT must be a UDP port").throw;
    };
    if((serverPort < 1) or: { serverPort > 65535 }) {
        Error("SDD_AUDITION_SERVER_PORT must be a UDP port").throw;
    };
Server.default = s = Server(\mappingAudition, NetAddr("127.0.0.1", serverPort));
s.options.numInputBusChannels = 0;
s.options.numOutputBusChannels = 2;
s.options.memSize = 262144;
s.options.numWireBufs = 1024;
~sddAuditionColours = true;
s.options.sampleRate = 48000;
s.waitForBoot({
    Routine({
        thisProcess.interpreter.executeFile(root +/+ "sound/eeg_organism_v2_receiver.scd");
        while({ ~eegOrganismV2[\synth].isNil }, { 0.1.wait });
        if("SDD_AUDITION_SILENT".getenv == "1") {
            ~eegOrganismV2[\synth].set(\outputTrim, 0);
            "OUTPUT_MUTED_FOR_RUNTIME_VERIFICATION".postln;
        };
        thisProcess.interpreter.executeFile(root +/+ "sound/music_audition_control.scd");
        OSCdef(\mappingInspect, {
            ("MUSIC_STATUS frames=" ++ ~eegOrganismV2[\frameCount]
                ++ " music=" ++ ~eegOrganismV2[\musicCount]
                ++ " timedOut=" ++ ~eegOrganismV2[\timedOut]).postln;
            s.queryAllNodes;
        }, '/sdd/music/v1/inspect', recvPort: controlPort);
        ("MAPPING_AUDITION_READY control_udp=" ++ controlPort
            ++ " server_udp=" ++ serverPort).postln;
        s.queryAllNodes;
        while({ ~eegOrganismV2[\stopping].not }, { 0.25.wait });
        OSCdef(\sddMusicControl).free;
        OSCdef(\sddMusicColourControl).free;
        OSCdef(\mappingInspect).free;
        4.wait;
        s.queryAllNodes;
        ("MAPPING_COUNTS frames=" ++ ~eegOrganismV2[\frameCount]
            ++ " music=" ++ ~eegOrganismV2[\musicCount]).postln;
        0.2.wait;
        s.quit;
        0.5.wait;
        "MAPPING_AUDITION_COMPLETE".postln;
        0.exit;
    }).play(AppClock);
}, 20, { 1.exit });
)
