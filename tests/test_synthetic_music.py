import unittest

from src.sonification.synthetic_music_demo import (
    SCENARIO_NAMES, build_music_timeline, run_music_transport,
)
from src.sonification.protocol import OrganismControlSender


class MusicIntegrationTests(unittest.TestCase):
    def test_plans_repeat_and_do_not_clamp_pitches(self):
        for scenario in SCENARIO_NAMES:
            first = build_music_timeline(scenario, duration=12, seed=20260904)
            self.assertEqual(first, build_music_timeline(scenario, duration=12, seed=20260904))
            self.assertEqual(len(first.frames), 49)
            for event in first.decisions:
                n = len(event.decision.frequencies_hz)
                self.assertEqual(event.voicing.frequencies_hz[:n], event.decision.frequencies_hz)
                self.assertTrue(all(40 <= hz <= 500 for hz in event.voicing.frequencies_hz))
            self.assertLess(len(first.sent_voicings), len(first.frames))

    def test_late_sender_skips_and_never_sends_stop_implicitly(self):
        class Clock:
            now = 0.0
            def sleep(self, seconds):
                self.now += seconds
        clock = Clock()
        messages = []
        class Client:
            def send_message(self, address, values):
                messages.append((clock.now, address, values))
                if len(messages) == 1:
                    clock.now += 0.8
        result = run_music_transport(
            'calm-stable', duration=2, sender=OrganismControlSender(client=Client()),
            clock=lambda: clock.now, sleeper=clock.sleep, printer=lambda _: None,
        )
        times = [t for t, a, _ in messages if a.endswith('/frame')]
        self.assertGreater(result.skipped_deadlines, 0)
        self.assertTrue(all(b - a >= 0.25 for a, b in zip(times, times[1:])))
        self.assertFalse(any(a.endswith('/stop') for _, a, _ in messages))


if __name__ == '__main__':
    unittest.main()
