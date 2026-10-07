// Optional extension attached to the existing participant-A Synth.
// Does not refresh the nine-value audio watchdog or allocate server nodes.
(
var state, lastSeq, sessionID, ranges, receivePort, handler;
state = ~eegOrganismV2;
receivePort = "SDD_AUDITION_OSC_PORT".getenv;
receivePort = if(receivePort.isNil) { 57120 } { receivePort.asInteger };
if((receivePort < 1) or: { receivePort > 65535 }) {
    Error("SDD_AUDITION_OSC_PORT must be a UDP port").throw;
};
lastSeq = -1;
sessionID = nil;
ranges = [[-18,0], [0,1], [0,1], [0,1], [0,1], [0,0.4], [0.5,5],
    [0,0.35], [0,4], [40,160], [0,2], [0,0.9], [0,1]];
handler = { |message|
    var values, valid, sid, seq;
    valid = [18,19].includes(message.size) and: { state[\stopping].not };
    if(valid) {
        sid = message[2]; seq = message[3];
        values = message.copyRange(5,17);
        if(message.size == 19) { values = values ++ [message[18]] };
        valid = message[1] == 0 and: {
            (sid.isKindOf(String) or: { sid.isKindOf(Symbol) }) and: { sid.asString.size > 0 }
        } and: { seq.isNumber and: { seq.isNaN.not } and: {
            seq >= 0 and: { seq <= 2147483647 } and: { seq == seq.asInteger } and: { seq > lastSeq }
        }} and: { message[4].isNumber and: { message[4].isNaN.not }
            and: { message[4] >= 0 } and: { message[4] <= 0.5 }
        } and: { sessionID.isNil or: { sessionID == sid } };
        values.do { |value, i|
            valid = valid and: { value.isNumber and: { value.isNaN.not }
                and: { value >= (if(i == 13) { 0 } { ranges[i][0] }) } and: { value <= (if(i == 13) { 2 } { ranges[i][1] }) } }
        };
        valid = valid and: { [0,1,2,4].includes(values[8]) };
        if(valid) {
            lastSeq = seq; sessionID = sid;
            state[\synth].set(\musicEnabled, 1, \auditionLevelDb, values[0],
                \reverbMix, values[5], \reverbTime, values[6], \musicEchoMix, values[7],
                \musicRhythmPattern, values[8], \invitationHarmonyDepth, values[10],
                \invitationDiagnosticDepth, values[11], \musicPulse, values[12]);
            state[\synth].setn(\musicGroups, values.copyRange(1,4));
            state[\synth].set(\musicColour, if(message.size == 19) { values[13] } { 0 });
            state[\musicLastSeq] = seq;
            state[\musicCount] = (state[\musicCount] ? 0) + 1;
        };
    };
    if(valid.not) { "MUSIC_CONTROL_REJECTED".postln };
};
OSCdef(\sddMusicControl, { |message| if(message.size == 18) { handler.value(message) } { "MUSIC_CONTROL_REJECTED".postln } }, '/sdd/music/v1/control', recvPort: receivePort);
OSCdef(\sddMusicColourControl, { |message| if(message.size == 19) { handler.value(message) } { "MUSIC_CONTROL_REJECTED".postln } }, '/sdd/music/v2/control', recvPort: receivePort);
("MUSIC_CONTROL_READY target=A persistent existing Synth UDP=" ++ receivePort).postln;
)
