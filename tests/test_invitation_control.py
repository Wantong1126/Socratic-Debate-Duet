import json
import math
from pathlib import Path
import tempfile
import tomllib
import unittest

from src.sdd.invitation_demo import run_demo
from src.sdd.invitation_input import InvitationButton, InvitationEvent
from src.sdd.invitation_osc import (
    INVITATION_CONTROL_ADDRESS,
    InvitationControlMessage,
    InvitationOscSender,
)
from src.sdd.reflection_controller import (
    InvitationEnvelopeConfig,
    InvitationEnvelopeController,
)
from src.sdd.session_runtime import SessionRuntime
from src.sdd.session_recorder import SessionRecorder
from src.sdd.session_types import FrameEnvelope
from src.sonification.protocol import OrganismControlSender


ROOT = Path(__file__).resolve().parents[1]


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Client:
    def __init__(self):
        self.messages = []

    def send_message(self, address, values):
        self.messages.append((address, tuple(values)))


def event(event_id="event-1", target="A", at=0.0, source="audience"):
    return InvitationEvent(
        event_id, "session-1", source, target, "criterion-population", at,
        "Why should population automatically determine the comparison?",
    )


class InvitationControlTests(unittest.TestCase):
    def test_one_press_creates_exactly_one_external_event(self):
        clock = Clock()
        identifiers = iter(("press-1", "press-2"))
        button = InvitationButton(
            session_id="session-1", source="operator", target="A",
            prompt_id="criterion", clock=clock, id_factory=lambda: next(identifiers),
        )
        first = button.press()
        second = button.press()
        self.assertEqual((first.event_id, second.event_id), ("press-1", "press-2"))
        self.assertEqual(first.source, "operator")
        self.assertEqual(first.target, "A")
        self.assertNotIn("name", first.to_dict())

    def test_events_and_actual_termination_are_session_recordable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"session"
            with SessionRecorder(
                path, session_id="session-1", config={}, code_version="test",
                source={"mode": "fixture"}, seed=1,
                monotonic_origin=0, wall_origin=1000,
            ) as recorder:
                created = event()
                recorder.invitation(created)
                controller = InvitationEnvelopeController(
                    InvitationEnvelopeConfig(0.5, 0.5, 0.5, 0.5),
                    termination_sink=recorder.invitation_termination,
                )
                controller.invite(created)
                controller.end("A", 0.25)
                controller.advance("A", 0.75)
            rows = [json.loads(line) for line in
                    (path/"records.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([row["kind"] for row in rows],
                         ["invitation_event", "invitation_termination"])
        self.assertEqual(rows[-1]["data"]["reason"], "ended")

    def test_a_target_does_not_change_b_state(self):
        controller = InvitationEnvelopeController()
        self.assertTrue(controller.invite(event(target="A")))
        self.assertEqual(controller.advance("A", 0.25).phase, "attack")
        b = controller.advance("B", 0.25)
        self.assertEqual((b.phase, b.invitation_amount, b.event_id), ("idle", 0.0, None))

    def test_envelope_is_continuous_at_all_active_boundaries(self):
        controller = InvitationEnvelopeController(InvitationEnvelopeConfig(2, 3, 2, 1))
        controller.invite(event())
        epsilon = 1e-8
        before_attack = controller.advance("A", 2-epsilon).invitation_amount
        at_attack = controller.advance("A", 2).invitation_amount
        before_release = controller.advance("A", 5-epsilon).invitation_amount
        at_release = controller.advance("A", 5).invitation_amount
        before_zero = controller.advance("A", 7-epsilon).invitation_amount
        at_zero = controller.advance("A", 7).invitation_amount
        self.assertAlmostEqual(before_attack, at_attack, places=6)
        self.assertAlmostEqual(before_release, at_release, places=6)
        self.assertAlmostEqual(before_zero, at_zero, places=6)
        self.assertEqual(controller.advance("A", 8).phase, "idle")
        self.assertEqual(controller.terminations[0].reason, "completed")

    def test_repeat_does_not_stack_or_extend(self):
        config = InvitationEnvelopeConfig(1, 1, 1, 1)
        controller = InvitationEnvelopeController(config)
        controller.invite(event("first"))
        self.assertFalse(controller.invite(event("repeat", at=0.5, source="peer_B")))
        sample = controller.advance("A", 2.5)
        self.assertEqual(sample.phase, "release")
        self.assertEqual(sample.event_id, "first")
        self.assertAlmostEqual(sample.invitation_amount, 0.5)
        self.assertEqual(controller.advance("A", 3).phase, "cooldown")
        self.assertEqual(len(controller.terminations), 1)

    def test_decline_and_pause_release_smoothly_and_log_reasons(self):
        config = InvitationEnvelopeConfig(1, 2, 1, 0.5)
        controller = InvitationEnvelopeController(config)
        controller.invite(event("decline", target="A"))
        amount = controller.advance("A", 0.5).invitation_amount
        self.assertTrue(controller.decline("A", 0.5))
        self.assertAlmostEqual(controller.advance("A", 1.0).invitation_amount, amount/2)
        self.assertEqual(controller.advance("A", 1.5).phase, "cooldown")
        self.assertEqual(controller.terminations[-1].reason, "declined")

        controller.invite(event("pause", target="B", at=2.0, source="peer_A"))
        amount = controller.advance("B", 2.4).invitation_amount
        self.assertTrue(controller.pause("B", 2.4))
        self.assertAlmostEqual(controller.advance("B", 2.9).invitation_amount, amount/2)
        self.assertEqual(controller.advance("B", 3.4).phase, "paused")
        self.assertEqual(controller.terminations[-1].reason, "paused")

    def test_all_external_termination_reasons_are_recorded_after_release(self):
        actions = {
            "decline": "declined", "end": "ended", "pause": "paused",
            "signal_loss": "signal_loss", "stop": "stopped",
        }
        for index, (action, expected) in enumerate(actions.items()):
            with self.subTest(action=action):
                controller = InvitationEnvelopeController(
                    InvitationEnvelopeConfig(1, 2, 1, 0.5)
                )
                controller.invite(event(f"event-{index}"))
                self.assertTrue(getattr(controller, action)("A", 0.5))
                controller.advance("A", 1.5)
                self.assertEqual(controller.terminations[-1].reason, expected)

    def test_message_contract_rejects_stale_malformed_nonfinite_and_range(self):
        valid = InvitationControlMessage("session-1", "event-1", "A", 0, 10.0, 0.5)
        self.assertEqual(valid.as_osc_values(now=10.2),
                         (0, "session-1", "event-1", 0, 0.1999999999999993, 0.5))
        for kwargs in (
            {"target": "C"}, {"seq": -1}, {"seq": True},
            {"sampled_at": math.nan}, {"invitation_amount": math.inf},
            {"invitation_amount": -0.1}, {"invitation_amount": 1.1},
        ):
            values = dict(session_id="s", event_id="e", target="A", seq=0,
                          sampled_at=10.0, invitation_amount=0.5)
            values.update(kwargs)
            with self.assertRaises(ValueError):
                InvitationControlMessage(**values)
        with self.assertRaises(ValueError):
            valid.as_osc_values(now=11.0)
        client = Client()
        sender = InvitationOscSender(client=client)
        sender.send(valid, now=10.2)
        self.assertEqual(client.messages[0][0], INVITATION_CONTROL_ADDRESS)

    def test_signal_loss_ends_envelope_without_refreshing_sound_health(self):
        clock, client = Clock(), Client()
        controller = InvitationEnvelopeController(InvitationEnvelopeConfig(1, 2, 1, 1))
        controller.invite(event())
        runtime = SessionRuntime(
            OrganismControlSender(client=client), session_id="session-1", clock=clock,
            invitation_controller=controller,
        )
        runtime.offer(FrameEnvelope(
            "session-1", "A", 0, 0, 0, "fixture", (0.5,)*9,
        ))
        runtime.tick()
        clock.now = 1.0
        runtime.tick()
        self.assertEqual(controller.advance("A", 1.0).phase, "release")
        self.assertEqual(controller._state("A").release_reason, "signal_loss")
        receiver = (ROOT/"sound/eeg_organism_v2_receiver.scd").read_text(encoding="utf-8")
        callback = receiver.split("OSCdef(\\sddInvitationControlV1", 1)[1].split(
            "OSCdef(\\eegOrganismV2Stop", 1
        )[0]
        self.assertNotIn("state[\\lastFrameAt] =", callback)
        self.assertNotIn("synth.set(\\transportAlive", callback)

    def test_receiver_contract_is_separate_strict_and_node_stable(self):
        receiver = (ROOT/"sound/eeg_organism_v2_receiver.scd").read_text(encoding="utf-8")
        core = (ROOT/"sound/eeg_harmonic_field_v2_core.scd").read_text(encoding="utf-8")
        self.assertIn("'/sdd/invitation/v1/control'", receiver)
        self.assertIn("message.size == 7", receiver)
        self.assertIn("target == state[\\invitationTarget]", receiver)
        self.assertIn("seq > state[\\invitationLastSeq]", receiver)
        self.assertIn("invitationMessageMaxAge", receiver)
        self.assertIn("synth.set(\\invitationAmount, amount)", receiver)
        callback = receiver.split("OSCdef(\\sddInvitationControlV1", 1)[1].split(
            "OSCdef(\\eegOrganismV2Stop", 1
        )[0]
        for constructor in ("Synth(", "Group(", "Buffer(", "Routine("):
            self.assertNotIn(constructor, callback)
        self.assertEqual(receiver.count("Synth.tail("), 1)
        self.assertEqual(receiver.count("Group.tail("), 1)
        self.assertIn("NamedControl.kr(\\invitationAmount, 0)", core)
        self.assertIn("NamedControl.kr(\n            \\invitationDiagnosticDepth, 0", core)
        self.assertIn("source = source * invitationDiagnosticGain", core)

    def test_manual_demo_logs_decline_completion_and_existing_voice_packets(self):
        config = tomllib.loads((ROOT/"config/sdd_v1.toml").read_text(encoding="utf-8"))
        clock, client = Clock(), Client()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"demo.jsonl"
            result = run_demo(
                config=config, session_id="manual-test", log_path=path,
                clock=clock, sleeper=clock.sleep, printer=lambda _: None,
                control_client=client,
            )
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(result["events"], 2)
        self.assertEqual(result["terminations"], ["declined", "completed"])
        self.assertEqual(sum(row["kind"] == "invitation_event" for row in rows), 2)
        self.assertEqual([row["data"]["reason"] for row in rows
                          if row["kind"] == "termination"], ["declined", "completed"])
        addresses = [address for address, _ in client.messages]
        self.assertIn("/eeg/organism/v2/frame", addresses)
        self.assertIn("/eeg/organism/v2/voicing", addresses)
        self.assertIn(INVITATION_CONTROL_ADDRESS, addresses)
        self.assertEqual(addresses[-1], "/eeg/organism/v2/stop")
        all_text = json.dumps(rows).lower()
        self.assertNotIn("success", all_text)


if __name__ == "__main__":
    unittest.main()
