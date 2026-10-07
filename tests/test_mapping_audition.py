import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from src.sdd.audition_features import EnergyProcessor, recompute
from src.sdd.mapping_audition import prepare_replay, receiver_port_candidates
from src.sdd.mapping_render import make_trace, score_for
from src.sdd.music_mapping import CANDIDATES, MusicMapping, load_config, music_packet, validate_packet
from src.sdd.replay_source import RawSampleReplay

ROOT = Path(__file__).resolve().parents[1]
RECORDING = ROOT/'reports/sdd_v1/live_sessions/obci_eeg1_20260919_194100'


class Clock:
    def __init__(self): self.now = 0.
    def __call__(self): return self.now


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(ROOT/'config/mapping_audition.json')

    def test_candidate_ownership_and_isolation(self):
        allowed = {
            'level': {'auditionLevelDb'},
            'pitch': set(), 'harmony': set(), 'note_weights': set(),
            'brightness': {f'musicGroup{i}' for i in range(1, 5)},
            'colour': {'musicColour'},
            'space_reverb': {'musicReverbMix', 'musicReverbTime', 'musicPulse'},
            'space_delay': {'musicEchoMix', 'musicPulse'},
            'rhythm': {'musicRhythmPattern', 'musicPulse'},
        }
        for candidate in CANDIDATES:
            mapping = MusicMapping(candidate, self.config)
            before = mapping.update(0., 0)
            for i in range(1, 201):
                after = mapping.update(1., i*.05)
            changes = {k for k in before['controls'] if before['controls'][k] != after['controls'][k]}
            self.assertLessEqual(changes, allowed[candidate])
            if candidate not in ('pitch', 'harmony'):
                self.assertEqual(before['frequencies_hz'], after['frequencies_hz'])
            if candidate != 'note_weights':
                self.assertEqual(before['note_weights'], after['note_weights'])
            self.assertEqual(after['controls']['invitationDiagnosticDepth'], 0)
        for candidate in self.config['reserved_for_reimagination']:
            with self.assertRaisesRegex(ValueError, 'conflict'):
                MusicMapping(candidate, self.config, invitation=True)

    def test_pitch_hysteresis_and_crossfade_hold(self):
        m = MusicMapping('pitch', self.config)
        transitions = []
        for i in range(1000):
            r = m.update(.34+(.02 if i%2 else -.02), i*.05)
            if r['discrete_changed']: transitions.append(i*.05)
        self.assertEqual(transitions, [])
        for i in range(1000, 1400):
            r = m.update(1, i*.05)
            if r['discrete_changed']: transitions.append(i*.05)
        self.assertTrue(all(b-a >= 1.5 for a,b in zip(transitions, transitions[1:])))
        self.assertEqual(r['midi'], [44,51,55,60,67])

    def test_retired_candidates_are_not_active_and_no_pulse_is_added(self):
        for candidate in ('space_reverb','space_delay','rhythm','note_weights'):
            with self.assertRaises(ValueError): MusicMapping(candidate,self.config)
        for candidate in CANDIDATES:
            m=MusicMapping(candidate,self.config)
            for i in range(100):
                r=m.update(i/100,i*.05)
                self.assertEqual(r['controls']['musicRhythmPattern'],0)
                self.assertEqual(r['controls']['musicPulse'],1)

    def test_harmony_is_ab_major_seventh_with_four_distinct_chords(self):
        m=MusicMapping('harmony',self.config)
        seen=set()
        for i in range(500):
            r=m.update(min(1,i/150),i*.05)
            seen.add(tuple(r['midi']))
        self.assertEqual(len(seen),4)
        self.assertEqual(self.config['harmony_names'][0],'Abmaj7')
        self.assertEqual(set(self.config['harmony_midi'][0]),{44,51,55,60,63})

    def test_extension_rejects_wrong_target_stale_duplicate_and_nonfinite(self):
        controls = MusicMapping('timbre', self.config).update(.5,0)['controls']
        packet = music_packet('test', 5, controls)
        self.assertTrue(validate_packet(packet, last_seq=4, session='test'))
        for index, value in ((0,1),(1,'other'),(2,5),(3,.51),(4,float('nan')),(4,float('inf')),(9,.9),(12,3)):
            bad = list(packet); bad[index] = value
            with self.assertRaises(ValueError):
                validate_packet(bad, last_seq=5 if index==2 else 4, session='test')
        with self.assertRaises(ValueError): validate_packet(packet[:-1])

    def test_invitation_keeps_contemporary_timbre_and_existing_voice(self):
        rows = [dict(t=i*.25, amount=(i%40)/40, valid=True, raw_energy_uv2=100) for i in range(500)]
        only = make_trace('timbre', self.config, rows, source='replay', comparison='physiology_only')
        together = make_trace('timbre', self.config, rows, source='replay', comparison='combined')
        self.assertEqual(len(together['reimagination_events']),1)
        self.assertEqual(together['terminations'][0]['reason'],'completed')
        for a,b in zip(only['frames'],together['frames']):
            for i in range(1,5):
                self.assertEqual(a['controls'][f'musicGroup{i}'],b['controls'][f'musicGroup{i}'])
        self.assertEqual(together['frames'][-1]['reimagination']['reimagination_amount'],0)
        score,_ = score_for(together)
        self.assertEqual(sum(r[1][0]=='s_new' for r in score),1)
        self.assertTrue(any(r[1][0]=='n_set' and 'gate' in r[1] for r in score))

    def test_raw_sample_clock_pause_restart_and_no_writer_pacing(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p/'metadata.json').write_text(json.dumps({'config':{'analysis':{'rail_limit_uv':187500,'saturation_fraction':.98}}}))
            stamps = [100,100.004,100.003,100.012]
            row = dict(kind='raw',t=50,data=dict(channels=['F3','F4','C3','C4','P3','P4','vertical_EOG','jaw_EMG'],
                units=['uV']*8,mode='live',participant_id='A',samples=[[i]*8 for i in range(4)],
                sampled_at=stamps,sample_rate=250))
            (p/'records.jsonl').write_text(json.dumps(row)+'\n')
            clock=Clock(); source=RawSampleReplay(p,clock=clock)
            self.assertEqual(source.original_lsl.tolist(),stamps)
            self.assertEqual(len(source.poll_samples()[0]),1)
            clock.now=.005
            self.assertEqual(len(source.poll_samples()[0]),2)
            source.pause(); clock.now=100
            self.assertEqual(len(source.poll_samples()[0]),0)
            source.resume()
            self.assertEqual(len(source.poll_samples()[0]),0)
            clock.now+=.01
            self.assertEqual(len(source.poll_samples()[0]),1)
            source.restart()
            self.assertEqual(len(source.poll_samples()[0]),1)
            row['data']['units'][0]='V'
            (p/'records.jsonl').write_text(json.dumps(row)+'\n')
            with self.assertRaises(ValueError): RawSampleReplay(p)

    def test_missing_recording_does_not_fall_back(self):
        with self.assertRaises(FileNotFoundError): RawSampleReplay(ROOT/'missing-human-session')

    def test_receiver_uses_next_isolated_port_pair_when_defaults_are_busy(self):
        with patch('src.sdd.mapping_audition._udp_port_available',
                   side_effect=[False, True, True]):
            self.assertEqual(next(receiver_port_candidates()), (57140, 57150))

    def test_gap_resets_feature_and_scaling_state(self):
        import tomllib
        c=tomllib.loads((ROOT/'config/live_eeg.toml').read_text())
        p=EnergyProcessor(c)
        t=np.arange(250)/250
        x=np.tile(np.sin(2*np.pi*10*t)[:,None],(1,8))
        p.add(x,t)
        previous=p.session
        p.add(x,t+2)
        self.assertIsNot(previous,p.session)
        self.assertIsNone(p.session.engine.bounds)
        self.assertFalse(any(r['valid'] for r in p.rows))

    @unittest.skipUnless(RECORDING.exists(), 'private human recording absent; no fixture substitution')
    def test_real_raw_recompute_is_repeatable_and_rejects_bad_eog(self):
        s, rows, audit = recompute(RECORDING)
        self.assertEqual(audit['samples'],30000)
        self.assertGreater(audit['saturated_fraction_by_channel'][6],.1)
        self.assertLess(audit['near_endpoint_fraction'],.05)
        self.assertGreater(audit['first_valid_seconds'],50)
        clock=Clock()
        source, processor = prepare_replay(RECORDING,60,clock)
        clock.now=4
        x,original,relative=source.poll_samples()
        processor.add(x,relative)
        expected = [r for r in rows if r['t'] <= 64]
        self.assertEqual(processor.rows,expected)


if __name__ == '__main__': unittest.main()
