"""Actual Python runtime/dropout/abrupt-exit check against an isolated SC server."""
from pathlib import Path
import subprocess
import sys
import time
import argparse
import re

from pythonosc.udp_client import SimpleUDPClient
from src.sdd.demo import main as demo
from src.sonification.synthetic_music_demo import main as music_demo


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-name', required=True,
                        help='new evidence directory name under reports/sdd_v1')
    args = parser.parse_args(argv)
    # Run only when test ports 57120/57130 are free. The server belongs to this test.
    import socket
    for port in (57120, 57130):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(('127.0.0.1', port))
    root = Path('reports/sdd_v1')
    # Keep prior evidence immutable; a verification run always writes a fresh,
    # explicitly named session directory and log.
    run_name = args.run_name
    if not re.fullmatch(r'[A-Za-z0-9_-]+', run_name):
        parser.error('--run-name must contain only letters, digits, _ or -')
    log_path = root/f'{run_name}.log'
    if (root/run_name).exists() or log_path.exists():
        raise FileExistsError(f'refusing to overwrite prior runtime evidence: {run_name}')
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen([r'D:\OpenBCI\supercollider\sclang.exe', '-D',
                                    'scripts/verify_sdd_runtime.scd'], stdout=log,
                                   stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        client = SimpleUDPClient('127.0.0.1', 57120)
        try:
            deadline = time.monotonic()+40
            while 'SDD_RUNTIME_READY' not in log_path.read_text(encoding='utf-8', errors='replace'):
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('SC not ready; inspect runtime_live.log')
                time.sleep(0.1)
            demo(['--output', str(root/run_name), '--send', '--dropout', '4', '8'])
            time.sleep(4)
            client.send_message('/sdd/test/restart', [])
            time.sleep(2)
            # Deliberate abrupt exit of our child; no finally/stop packet.
            code = ('import os,time; from src.sonification.protocol import OrganismControlSender; '
                    's=OrganismControlSender(); '
                    '[(s.send([0.5]*9),time.sleep(0.25)) for _ in range(4)]; os._exit(17)')
            crashed = subprocess.run([sys.executable, '-c', code], check=False)
            assert crashed.returncode == 17
            time.sleep(4)
            client.send_message('/eeg/organism/v2/stop', [])
            time.sleep(4)
            client.send_message('/sdd/test/restart', [])
            time.sleep(2)
            music_demo(['--scenario', 'combined', '--duration', '16', '--rate', '4', '--seed', '20260904'])
            time.sleep(3)
            client.send_message('/eeg/organism/v2/stop', [])
            time.sleep(4)
            client.send_message('/sdd/test/finish', [])
            process.wait(timeout=10)
            assert process.returncode == 0
        finally:
            client._sock.close()
            if process.poll() is None:
                # Let the test-owned SC harness perform its bounded cleanup.
                process.wait(timeout=90)
    text = log_path.read_text(encoding='utf-8', errors='replace')
    assert text.count('WATCHDOG:') >= 2, 'both dropout and abrupt Python exit must time out'
    assert 'SDD_RUNTIME_COMPLETE' in text
    assert 'ERROR:' not in text and 'FAILURE IN SERVER' not in text
    print('PASS: real Python runtime, music demo, dropout, abrupt child exit, graceful stop; listening pending')


if __name__ == '__main__':
    main()
