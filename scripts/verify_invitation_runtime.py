"""Exercise invitation OSC against the current participant-A sound receiver."""
import json
import argparse
import os
from pathlib import Path
import socket
import subprocess
import time
import tomllib
import warnings

import numpy as np
from pythonosc.udp_client import SimpleUDPClient
from scipy.io import wavfile

from src.sdd.invitation_demo import run_demo
from src.sonification.protocol import ORGANISM_FRAME_ADDRESS


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-name", required=True)
    args = parser.parse_args(argv)
    if not args.run_name.replace("_", "").replace("-", "").isalnum():
        parser.error("--run-name may contain only letters, digits, _ and -")
    for port in (57120, 57130):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(("127.0.0.1", port))
    root = Path("reports/sdd_v1")
    log_path = root/f"{args.run_name}.log"
    demo_log = root/f"{args.run_name}_manual.jsonl"
    result_path = root/f"{args.run_name}.json"
    audio_path = root/f"{args.run_name}.wav"
    for path in (log_path, demo_log, result_path, audio_path):
        if path.exists():
            raise FileExistsError(f"refusing to overwrite invitation evidence: {path}")
    with log_path.open("w", encoding="utf-8") as log:
        environment = os.environ.copy()
        environment["SDD_INVITATION_OUTPUT"] = str(audio_path.resolve())
        process = subprocess.Popen(
            [r"D:\OpenBCI\supercollider\sclang.exe", "-D",
             "scripts/verify_invitation_runtime.scd"],
            stdout=log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            env=environment,
        )
        client = SimpleUDPClient("127.0.0.1", 57120)
        language = SimpleUDPClient("127.0.0.1", 57120)
        try:
            deadline = time.monotonic()+40
            while "INVITATION_RUNTIME_READY" not in log_path.read_text(
                    encoding="utf-8", errors="replace"):
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("invitation receiver did not become ready")
                time.sleep(0.1)
            client.send_message(ORGANISM_FRAME_ADDRESS, [0.5]*9)
            session = "invitation-live-A"
            event = "watchdog-proof"
            # These valid controls must not keep the sound frame watchdog alive.
            for seq in range(26):
                client.send_message(
                    "/sdd/invitation/v1/control",
                    [0, session, event, seq, 0.0, 0.5],
                )
                time.sleep(0.1)
            # Wrong target, duplicate, stale, malformed, non-finite, out-of-range.
            bad_messages = (
                [1, session, event, 26, 0.0, 0.5],
                [0, session, event, 25, 0.0, 0.5],
                [0, session, event, 26, 9.0, 0.5],
                [0, session, event, 26, 0.0],
                [0, session, event, 26, 0.0, float("nan")],
                [0, session, event, 26, 0.0, 1.5],
            )
            for values in bad_messages:
                client.send_message("/sdd/invitation/v1/control", values)
            time.sleep(0.5)
            config = tomllib.loads(Path("config/sdd_v1.toml").read_text(encoding="utf-8"))
            demo_result = run_demo(
                config=config, session_id=session, log_path=demo_log, send=True,
                initial_invitation_sequence=100,
            )
            time.sleep(4)
            language.send_message("/sdd/invitation/test/finish", [])
            process.wait(timeout=10)
            if process.returncode != 0:
                raise RuntimeError(f"SuperCollider exited {process.returncode}")
        finally:
            client._sock.close()
            language._sock.close()
            if process.poll() is None:
                process.wait(timeout=50)
    text = log_path.read_text(encoding="utf-8", errors="replace")
    if "ERROR:" in text or "FAILURE IN SERVER" in text:
        raise AssertionError("SuperCollider reported an error; inspect invitation_runtime.log")
    if "WATCHDOG:" not in text:
        raise AssertionError("invitation messages incorrectly refreshed the sound watchdog")
    accepted = text.count("Invitation control accepted")
    if accepted < 26 + 2:
        raise AssertionError("valid invitation messages were not accepted")
    if text.count("Invitation control rejected") < len(bad_messages):
        raise AssertionError("not every invalid invitation message was rejected")
    if "target=1" not in text:
        raise AssertionError("wrong-target rejection is not visible")
    active_trees = [line for line in text.splitlines()
                    if "INVITATION_TREE" in line and "eegOrganismV2HarmonicField" in line]
    if not active_trees or any(line.count("eegOrganismV2HarmonicField") != 1
                               for line in active_trees):
        raise AssertionError("participant voice node count changed")
    tree_lines = [line for line in text.splitlines() if "INVITATION_TREE" in line]
    if "eegOrganismV2HarmonicField" in tree_lines[-1]:
        raise AssertionError("participant voice remained after stop")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", wavfile.WavFileWarning)
        rate, audio = wavfile.read(audio_path)
    result = {
        "fixture_only": True,
        "participant_voice": "A",
        "accepted_messages": accepted,
        "rejected_messages": text.count("Invitation control rejected"),
        "watchdog_triggered_while_invitation_active": True,
        "active_tree_queries": len(active_trees),
        "final_voice_node_present": False,
        "demo": demo_result,
        "audio_rate": int(rate),
        "audio_channels": int(audio.shape[1]),
        "audio_finite": bool(np.isfinite(audio).all()),
        "audio_peak": float(np.max(np.abs(audio))),
        "audition": "PENDING HUMAN LISTENING",
    }
    if not result["audio_finite"] or result["audio_peak"] >= 0.999:
        raise AssertionError("runtime recording is invalid or clipped")
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
