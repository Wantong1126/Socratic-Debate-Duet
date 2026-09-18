"""Audible diagnostic: baseline, one invitation envelope, baseline."""
import argparse
from pathlib import Path
import subprocess
import time
import tomllib

from pythonosc.udp_client import SimpleUDPClient

from src.sdd.invitation_input import InvitationButton
from src.sdd.invitation_osc import InvitationControlMessage, InvitationOscSender
from src.sdd.reflection_controller import InvitationEnvelopeConfig, InvitationEnvelopeController
from src.sonification.protocol import OrganismControlFrame, OrganismControlSender, OrganismVoicingFrame


DIAGNOSTIC_DEPTH = 0.85


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=Path("reports/sdd_v1/invitation_audible_demo.log"))
    args = parser.parse_args(argv)
    config = tomllib.loads(Path("config/sdd_v1.toml").read_text(encoding="utf-8"))
    args.log.parent.mkdir(parents=True, exist_ok=True)
    with args.log.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [r"D:\OpenBCI\supercollider\sclang.exe", "-D", "scripts/run_invitation_audible_demo.scd"],
            stdout=log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        client = SimpleUDPClient("127.0.0.1", 57120)
        sound = OrganismControlSender(**config["transport"], client=client)
        invitation = InvitationOscSender(**config["transport"], client=client)
        try:
            deadline = time.monotonic() + 40
            while "INVITATION_AUDIBLE_READY" not in args.log.read_text(encoding="utf-8", errors="replace"):
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError(f"receiver did not become ready; inspect {args.log}")
                time.sleep(0.1)
            fixed = OrganismControlFrame.from_values(config["mapping"]["fixed"])
            voicing = OrganismVoicingFrame.from_active(
                config["mapping"]["frequencies_hz"], config["mapping"]["weights"]
            )
            sound.send_voicing(voicing)
            frame_period = 1 / config["session"]["control_hz"]

            def sustain(seconds):
                end = time.monotonic() + seconds
                while time.monotonic() < end:
                    sound.send(fixed)
                    time.sleep(frame_period)

            print("BASELINE: unchanged participant-A voice for 5 seconds", flush=True)
            sustain(5.0)

            button = InvitationButton(
                session_id="invitation-audible-demo", source="operator", target="A",
                prompt_id="question_weighing_criterion",
                prompt_text="Please reconsider the criterion used to compare these impacts.",
            )
            event = button.press()
            print(f"BUTTON PRESSED source={event.source} target={event.target}", flush=True)
            envelope = InvitationEnvelopeController(InvitationEnvelopeConfig(
                attack_seconds=1.5, hold_seconds=2.0,
                release_seconds=1.5, cooldown_seconds=0.0,
            ))
            envelope.invite(event)
            seq = 0
            next_frame = time.monotonic()
            last_print = float("-inf")
            while True:
                now = time.monotonic()
                if now >= next_frame:
                    sound.send(fixed)
                    next_frame += frame_period
                sample = envelope.advance("A", now)
                if sample.event_id is not None:
                    invitation.send(InvitationControlMessage(
                        event.session_id, event.event_id, "A", seq, now,
                        sample.invitation_amount,
                    ), now=now)
                    seq += 1
                if now - last_print >= 0.25 or sample.phase == "idle":
                    diagnostic_gain = 1.0 - DIAGNOSTIC_DEPTH * sample.invitation_amount
                    print(
                        f"source={sample.source} target={sample.target} phase={sample.phase} "
                        f"invitation_amount={sample.invitation_amount:.3f} "
                        f"invitationDiagnosticGain={diagnostic_gain:.3f}", flush=True,
                    )
                    last_print = now
                if sample.phase == "idle":
                    break
                time.sleep(1 / config["invitation"]["control_hz"])

            print("BASELINE: participant-A voice restored for 5 seconds", flush=True)
            sustain(5.0)
            client.send_message("/sdd/invitation/demo/finish", [])
            process.wait(timeout=15)
            if process.returncode != 0:
                raise RuntimeError(f"SuperCollider exited {process.returncode}; inspect {args.log}")
        finally:
            sound.close()
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
    print("DEMO COMPLETE: receiver stopped cleanly", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
