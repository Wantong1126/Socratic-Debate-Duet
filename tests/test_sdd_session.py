from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from src.sdd.fixture_source import control_fixture, simulated_raw
from src.sdd.session_types import FrameEnvelope, SessionEvent
from src.sdd.session_recorder import SessionRecorder
from src.sdd.replay_source import ReplaySource
from src.sdd.session_runtime import SessionRuntime
from src.sonification.controls import single_dimension_baseline
from src.sonification.protocol import OrganismControlSender


class Clock:
    now = 0.0
    def __call__(self):
        return self.now


class Client:
    def __init__(self):
        self.messages = []
    def send_message(self, address, values):
        self.messages.append((address, values))


class SessionTests(unittest.TestCase):
    def frame(self, seq=0, at=0.0):
        return FrameEnvelope('test', 'A', seq, at, at, 'fixture', (0.5,)*9)

    def recorder(self, path, **kwargs):
        return SessionRecorder(path, session_id='test', config={'rate': 4},
                               code_version='test', source={'mode': 'fixture'},
                               seed=123, monotonic_origin=0, wall_origin=1000, **kwargs)

    def test_t02_invalid_is_not_sanitized_into_valid_silence(self):
        for value in (float('nan'), float('inf'), 'bad', -0.1, 1.1):
            frame = replace(self.frame(), values=(value,)+(0.5,)*8)
            self.assertFalse(frame.valid)
            self.assertTrue(frame.reason)
            with self.assertRaises(ValueError):
                frame.control_frame()
        self.assertEqual(len(self.frame().control_frame().as_osc_values()), 9)
        with self.assertRaises(ValueError):
            replace(self.frame(), participant_id='name')

    def test_t03_record_provenance_raw_events_and_consent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'record'
            with self.recorder(path) as recorder:
                recorder.frame(self.frame())
                recorder.raw(at=0, sampled_at=0, **simulated_raw(seed=123))
                recorder.event(SessionEvent('test', 0, 0, 'audience', 'A', 'button'))
                recorder.frame(replace(self.frame(1, 0.25), values=(float('nan'),)*9))
                with self.assertRaises(PermissionError):
                    recorder.frame(replace(self.frame(2, 0.5), mode='live'))
            metadata = json.loads((path/'metadata.json').read_text())
            self.assertEqual(metadata['seed'], 123)
            self.assertTrue(metadata['simulated'])
            rows = [json.loads(line) for line in (path/'records.jsonl').read_text().splitlines()]
            self.assertEqual([row['kind'] for row in rows], ['frame', 'raw', 'event', 'frame'])
            self.assertEqual(rows[-1]['t'], 0.25)
            self.assertFalse(rows[-1]['data']['valid'])
            raw_replay = ReplaySource(path, mode='raw', clock=Clock())
            self.assertEqual([r['kind'] for r in raw_replay.rows], ['raw', 'event'])
            self.assertEqual(raw_replay.rows[0]['data']['samples'], simulated_raw(seed=123)['samples'])

    def test_t04_reproducible_single_field_and_dropouts(self):
        first = list(control_fixture(duration=3, dropout=[(1,2)]))
        self.assertEqual(first, list(control_fixture(duration=3, dropout=[(1,2)])))
        self.assertEqual(len(first), 8)
        self.assertEqual(len({f.values[1:] for f in first}), 1)
        self.assertEqual(simulated_raw(seed=123), simulated_raw(seed=123))
        self.assertNotEqual(simulated_raw(seed=123), simulated_raw(seed=124))

    def test_t05_replay_mode_pause_and_same_input_for_two_mappings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'record'
            with self.recorder(path) as recorder:
                for i in range(9):
                    recorder.frame(self.frame(i, i/4))
            clock = Clock()
            a = ReplaySource(path, mode='control', clock=clock)
            b = ReplaySource(path, mode='control', clock=clock)
            self.assertEqual(a.rows, b.rows)
            self.assertEqual(a.metadata['seed'], b.metadata['seed'])
            self.assertEqual(len(a.poll()), 1)
            clock.now = 0.1
            a.pause()
            clock.now = 50
            self.assertEqual(a.poll(), [])
            a.resume()
            self.assertEqual(a.poll(), [])
            clock.now = 50.2
            self.assertEqual(a.poll()[0]['data']['seq'], 1)
            clock.now = 52
            self.assertEqual(len(a.poll()), 1)  # no overdue-frame burst
            with self.assertRaises(ValueError):
                ReplaySource(path, mode='raw')
            frame = FrameEnvelope(**b.rows[0]['data'])
            mapped = [single_dimension_baseline(frame.control_frame(), field=field,
                      fixed=(0.2,)*9) for field in ('energy', 'beta')]
            self.assertNotEqual(mapped[0], mapped[1])

    def test_t06_latest_only_no_catchup_and_no_health_from_invalid(self):
        clock, client = Clock(), Client()
        runtime = SessionRuntime(OrganismControlSender(client=client), session_id='test', clock=clock)
        runtime.offer(self.frame())
        self.assertTrue(runtime.tick())
        clock.now = 0.1
        runtime.offer(self.frame(1, 0.1))
        self.assertFalse(runtime.tick())
        clock.now = 0.2
        runtime.offer(replace(self.frame(2, 0.2), values=(0.8,)*9))
        clock.now = 0.25
        self.assertTrue(runtime.tick())
        self.assertEqual(client.messages[-1][1], [0.8]*9)
        clock.now = 2
        self.assertFalse(runtime.tick())
        self.assertFalse(runtime.offer(self.frame(3, 0.3)))
        self.assertFalse(runtime.offer(replace(self.frame(4, 2), values=(float('nan'),)*9)))
        self.assertEqual(runtime.last_sent_at, 0.25)
        self.assertEqual(len(client.messages), 2)

    def test_t08_stop_once_no_restart_or_duplicate_health(self):
        clock, client = Clock(), Client()
        runtime = SessionRuntime(OrganismControlSender(client=client), session_id='test', clock=clock)
        runtime.offer(self.frame())
        runtime.tick()
        self.assertFalse(runtime.offer(self.frame()))
        runtime.stop('keyboard_interrupt')
        runtime.stop()
        clock.now = 1
        self.assertFalse(runtime.offer(self.frame(1, 1)))
        self.assertFalse(runtime.tick())
        self.assertEqual(sum(a.endswith('/stop') for a, _ in client.messages), 1)

    def test_invalid_flood_and_stale_queued_frame_do_not_refresh_health(self):
        clock, client = Clock(), Client()
        runtime = SessionRuntime(OrganismControlSender(client=client), session_id='test', clock=clock)
        runtime.offer(self.frame())
        runtime.tick()
        clock.now = 0.1
        runtime.offer(self.frame(1, 0.1))
        clock.now = 1
        self.assertFalse(runtime.tick())
        for i in range(8):
            clock.now += 0.25
            runtime.offer(replace(self.frame(i+2, clock.now), valid=False, reason='signal_quality'))
            self.assertFalse(runtime.tick())
        self.assertEqual(runtime.last_sent_at, 0)
        self.assertEqual(len(client.messages), 1)

    def test_new_invalid_input_cancels_unsent_pending_frame(self):
        clock, client = Clock(), Client()
        runtime = SessionRuntime(OrganismControlSender(client=client), session_id='test', clock=clock)
        runtime.offer(self.frame())
        runtime.offer(replace(self.frame(1), valid=False, reason='quality'))
        self.assertFalse(runtime.tick())
        self.assertEqual(client.messages, [])

    def test_t09_mapping_freezes_all_other_dimensions(self):
        fixed = (0.5, 0.24, 0.1, 0.12, 0.04, 0.82, 0.58, 0.28, 0.08)
        for level in (0.2, 0.5, 0.8):
            frame = replace(self.frame(), values=(level,)*9).control_frame()
            output = single_dimension_baseline(frame, field='energy', fixed=fixed)
            self.assertEqual(output.as_osc_values(), (level,)+fixed[1:])


if __name__ == '__main__':
    unittest.main()
