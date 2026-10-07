"""Muted real receiver regression: strict extension, watchdog, fixed nodes, stop."""
import json
import os
from pathlib import Path
import time

from src.sdd.mapping_audition import ROOT, start_receiver
from src.sdd.music_mapping import MUSIC_ADDRESS, MusicMapping, load_config, music_packet
from src.sdd.reimagination import ReimaginationOscSender as InvitationOscSender, ReimaginationControlMessage as InvitationControlMessage
from src.sonification.protocol import OrganismControlSender, OrganismControlFrame, OrganismVoicingFrame


def main():
    os.chdir(ROOT)
    os.environ['SDD_AUDITION_SILENT']='1'
    output=ROOT/load_config()['output_directory']
    output.mkdir(parents=True, exist_ok=True)
    log_path=output/'protocol_runtime.log'
    process, log, control_port, server_port=start_receiver(log_path)
    sender=OrganismControlSender(port=control_port)
    invitation=InvitationOscSender(client=sender.client)
    c=load_config()
    result=MusicMapping('colour',c,invitation=True).update(.5,0)
    packet=music_packet('receiver-regression',0,result['controls'])
    try:
        sender.send_voicing(OrganismVoicingFrame.from_active(result['frequencies_hz'],result['note_weights']))
        sender.send(OrganismControlFrame.from_values(c['fixed_frame']))
        sender.client.send_message(MUSIC_ADDRESS,packet)
        time.sleep(.1)
        invalid=[packet,packet[:-1],(*packet[:-1],float("nan"))]
        for index,value in ((0,1),(1,'other-session'),(3,.6),(4,float('nan')),(4,float('inf')),(9,.8),(12,3)):
            p=list(packet);p[2]=1;p[index]=value;invalid.append(p)
        for p in invalid:
            sender.client.send_message(MUSIC_ADDRESS,p)
        # Valid music and invitation messages keep arriving; neither may keep
        # the participant's audio watchdog alive without valid sound frames.
        started=time.monotonic()
        seq=1
        while time.monotonic()-started < 3:
            now=time.monotonic()
            sender.client.send_message(MUSIC_ADDRESS,music_packet('receiver-regression',seq,result['controls']))
            invitation.send(InvitationControlMessage('receiver-regression','explicit-test-event','A',seq,now,.4),now=now)
            seq+=1
            time.sleep(.1)
        sender.client.send_message('/sdd/music/v1/inspect',[])
        time.sleep(.3)
        sender.send_stop()
        process.wait(timeout=12)
    finally:
        if process.poll() is None:
            sender.send_stop()
            process.wait(timeout=12)
        sender.close();log.close()
    text=log_path.read_text(encoding='utf-8',errors='replace')
    assert process.returncode==0 and 'MAPPING_AUDITION_COMPLETE' in text
    assert 'ERROR:' not in text and 'FAILURE IN SERVER' not in text
    assert text.count('MUSIC_CONTROL_REJECTED') == len(invalid)
    assert 'MUSIC_STATUS frames=1' in text and 'timedOut=true' in text
    assert 'WATCHDOG' in text
    trees=text.split('NODE TREE Group 0')[1:]
    assert len(trees)>=3
    assert '1001 eegOrganismV2HarmonicField' in trees[0] and '1001 eegOrganismV2HarmonicField' in trees[1]
    assert '1001 eegOrganismV2HarmonicField' not in trees[-1]
    result=dict(passed=True,invalid_packets_rejected=len(invalid),watchdog_not_refreshed=True,
        persistent_voice_synths=1,stop_released=True,audio_output='muted; no listening claim')
    (output/'protocol_runtime.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
