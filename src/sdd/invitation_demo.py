"""Manual T10-T12 demo: two invitations reach participant A's continuing voice."""
import argparse
import json
from pathlib import Path
import time
import tomllib

from src.sonification.protocol import (
    OrganismControlFrame, OrganismControlSender, OrganismVoicingFrame,
)
from .invitation_input import InvitationButton
from .invitation_osc import InvitationControlMessage, InvitationOscSender
from .reflection_controller import (
    InvitationEnvelopeConfig, InvitationEnvelopeController,
)


class _DryClient:
    def __init__(self):
        self.messages = []

    def send_message(self, address, values):
        self.messages.append((address, tuple(values)))


def run_demo(*, config, session_id, log_path, send=False,
             clock=time.monotonic, sleeper=time.sleep, printer=print,
             control_client=None, initial_invitation_sequence=0):
    invitation_config = InvitationEnvelopeConfig(
        attack_seconds=config["invitation"]["attack_seconds"],
        hold_seconds=config["invitation"]["hold_seconds"],
        release_seconds=config["invitation"]["release_seconds"],
        cooldown_seconds=config["invitation"]["cooldown_seconds"],
    )
    controller = InvitationEnvelopeController(invitation_config)
    client = control_client or (None if send else _DryClient())
    sound_sender = OrganismControlSender(**config["transport"], client=client)
    invitation_sender = InvitationOscSender(
        **config["transport"], client=sound_sender.client, clock=clock,
    )
    fixed = OrganismControlFrame.from_values(config["mapping"]["fixed"])
    voicing = OrganismVoicingFrame.from_active(
        config["mapping"]["frequencies_hz"], config["mapping"]["weights"]
    )
    invitation_hz = config["invitation"]["control_hz"]
    interval = 1.0 / invitation_hz
    frame_interval = 1.0 / config["session"]["control_hz"]
    started = clock()
    first_button = InvitationButton(
        session_id=session_id, source="audience", target="A",
        prompt_id="question_weighing_criterion_population",
        prompt_text="Why should a larger affected population automatically matter more?",
        clock=clock,
    )
    second_button = InvitationButton(
        session_id=session_id, source="peer_B", target="A",
        prompt_id="question_weighing_criterion",
        prompt_text="Please reconsider the criterion used to compare these impacts.",
        clock=clock,
    )
    decline_at = invitation_config.attack_seconds + 0.25
    second_at = decline_at + invitation_config.release_seconds \
        + invitation_config.cooldown_seconds + 0.1
    finish_at = second_at + invitation_config.attack_seconds \
        + invitation_config.hold_seconds + invitation_config.release_seconds \
        + invitation_config.cooldown_seconds + 0.15
    next_frame = 0.0
    sequence = initial_invitation_sequence
    first_event = first_button.press()
    controller.invite(first_event)
    second_event = None
    declined = False
    termination_index = 0
    previous_phase = None
    next_print = 0.0
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("x", encoding="utf-8") as log:
        def write(kind, data):
            log.write(json.dumps({"kind": kind, "data": data},
                                 ensure_ascii=False, allow_nan=False) + "\n")
            log.flush()

        write("invitation_event", first_event.to_dict())
        sound_sender.send_voicing(voicing)
        try:
            while True:
                now = clock()
                elapsed = now - started
                if not declined and elapsed >= decline_at:
                    controller.decline("A", now)
                    declined = True
                    write("action", {"target": "A", "action": "decline", "at": now})
                if second_event is None and elapsed >= second_at:
                    second_event = second_button.press()
                    if not controller.invite(second_event):
                        raise RuntimeError("second explicit invitation was not accepted")
                    write("invitation_event", second_event.to_dict())
                if elapsed + 1e-9 >= next_frame:
                    sound_sender.send(fixed)
                    next_frame += frame_interval
                sample = controller.advance("A", now)
                if sample.event_id is not None:
                    invitation_sender.send(InvitationControlMessage(
                        session_id=session_id,
                        event_id=sample.event_id,
                        target="A",
                        seq=sequence,
                        sampled_at=now,
                        invitation_amount=sample.invitation_amount,
                    ), now=now)
                    sequence += 1
                sample_row = {
                    "source": sample.source,
                    "target": sample.target,
                    "phase": sample.phase,
                    "invitation_amount": sample.invitation_amount,
                    "at": sample.at,
                    "event_id": sample.event_id,
                }
                write("invitation_sample", sample_row)
                if sample.phase != previous_phase or elapsed + 1e-9 >= next_print:
                    printer(
                        f"INVITATION source={sample.source} target={sample.target} "
                        f"phase={sample.phase} amount={sample.invitation_amount:.3f}"
                    )
                    previous_phase = sample.phase
                    next_print = elapsed + 0.25
                while termination_index < len(controller.terminations):
                    termination = controller.terminations[termination_index]
                    write("termination", {
                        "event_id": termination.event_id,
                        "session_id": termination.session_id,
                        "target": termination.target,
                        "reason": termination.reason,
                        "at": termination.at,
                    })
                    termination_index += 1
                if elapsed >= finish_at and sample.phase == "idle":
                    break
                sleeper(interval)
        except KeyboardInterrupt:
            now = clock()
            controller.stop("A", now)
            write("action", {"target": "A", "action": "stop", "at": now})
        finally:
            sound_sender.send_stop()
            sound_sender.close()
    return {
        "events": 2,
        "terminations": [item.reason for item in controller.terminations],
        "frames": sound_sender.frame_count,
        "invitation_messages": invitation_sender.count,
        "sent": send,
        "log": str(log_path),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/sdd_v1.toml"))
    parser.add_argument("--session-id", default="invitation-manual-A")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args(argv)
    config = tomllib.loads(args.config.read_text(encoding="utf-8"))
    result = run_demo(
        config=config, session_id=args.session_id, log_path=args.log,
        send=args.send,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
