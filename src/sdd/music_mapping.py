"""Deterministic single-dimension candidates, with explicit parameter ownership."""
import json
import math
from pathlib import Path

CANDIDATES = ('level', 'pitch', 'brightness', 'colour', 'harmony')
RETIRED_CANDIDATES = ('space_reverb', 'space_delay', 'rhythm', 'note_weights')
MUSIC_ADDRESS = '/sdd/music/v2/control'
LEGACY_MUSIC_ADDRESS = '/sdd/music/v1/control'
# Target A (0), session, seq, age, then these controls; never an EEG frame extension.
MUSIC_FIELDS = ('auditionLevelDb', 'musicGroup1', 'musicGroup2', 'musicGroup3', 'musicGroup4',
    'musicReverbMix', 'musicReverbTime', 'musicEchoMix', 'musicRhythmPattern', 'musicTempo',
    'invitationHarmonyDepth', 'invitationDiagnosticDepth', 'musicPulse', 'musicColour')
MUSIC_RANGES = ((-18, 0), *((0, 1),)*4, (0, .4), (.5, 5), (0, .35), (0, 4), (40, 160), (0, 2), (0, .9), (0, 1), (0, 2))


def load_config(path='config/mapping_audition.json'):
    c = json.loads(Path(path).read_text(encoding='utf-8'))
    if c['minimum_hold_seconds'] < 1.35:
        raise ValueError('minimum hold must allow the existing 1.35s voicing crossfade')
    if not 40 <= c['tempo_bpm'] <= 160 or c['smooth_seconds'] <= 0:
        raise ValueError('invalid tempo or smoothing')
    if len(c['voice_weights']) != len(c['base_midi']) or len(c['base_midi']) > 6:
        raise ValueError('base notes and weights must match the six-slot voice')
    for notes in [c['base_midi'], c['pitch_midi'], *c['harmony_midi']]:
        if not all(40 <= hz(m) <= 500 for m in notes):
            raise ValueError('configured notes exceed 40–500 Hz')
    return c


def music_packet(session, seq, controls, age=0.0, target=0):
    values = tuple(controls[k] for k in MUSIC_FIELDS)
    packet = (target, session, seq, age, *values)
    validate_packet(packet)
    return packet


def validate_packet(packet, *, last_seq=-1, session=None):
    if len(packet) != 18:
        raise ValueError('music packet must contain 18 values')
    target, sid, seq, age, *values = packet
    if target != 0 or not isinstance(sid, str) or not sid or (session and session != sid):
        raise ValueError('music target/session mismatch')
    if isinstance(seq, bool) or not isinstance(seq, int) or not last_seq < seq <= 2147483647:
        raise ValueError('duplicate or invalid music sequence')
    if not isinstance(age, (int, float)) or not math.isfinite(age) or not 0 <= age <= .5:
        raise ValueError('stale music packet')
    for value, (low, high) in zip(values, MUSIC_RANGES):
        if not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError('non-finite or out-of-range music control')
    if values[8] not in (0, 1, 2, 4):
        raise ValueError('unknown rhythm pattern')
    return True


def hz(midi):
    return 440*2**((midi-69)/12)


def display_parameters(result):
    candidate, p = result['candidate'], result['controls']
    if candidate == 'level': return {'gain_dB': round(p['auditionLevelDb'], 2)}
    if candidate in ('pitch', 'harmony'):
        return {'MIDI': result['midi'], 'Hz': [round(f, 2) for f in result['frequencies_hz']]}
    if candidate == 'note_weights': return {'note_weights': [round(w, 3) for w in result['note_weights']]}
    if candidate == 'timbre': return {'harmonic_group_weights': [round(p[f'musicGroup{i}'],3) for i in range(1,5)]}
    if candidate == 'brightness': return {'harmonic_group_weights': [round(p[f'musicGroup{i}'],3) for i in range(1,5)]}
    if candidate == 'colour': return {'sound_colour_position': round(p['musicColour'],3), 'palette': 'rounded wood → hollow reed → glass organ'}
    if candidate == 'space_reverb': return {'wet': round(p['musicReverbMix'],3), 'tail_s': round(p['musicReverbTime'],2)}
    if candidate == 'space_delay': return {'echo_mix': round(p['musicEchoMix'],3), 'echo_s': [1/3,2/3]}
    return {'hits_per_bar': p['musicRhythmPattern'], 'tempo_BPM': p['musicTempo'], 'pulse': p['musicPulse'], 'pending_at_s': result['pending_at']}


def manual_trajectory(t, duration=24):
    # Equal duration plateaus and ramps: low -> middle -> high -> low.
    points = [(0, 0), (3, 0), (7, .5), (10, .5), (14, 1), (17, 1), (22, 0), (24, 0)]
    t = min(24, max(0, t*24/duration))
    for (a, x), (b, y) in zip(points, points[1:]):
        if t <= b:
            return x+(y-x)*(t-a)/(b-a)
    return 0.


class MusicMapping:
    def __init__(self, candidate, config, *, reimagination=False, invitation=None, diagnostic=False):
        if invitation is not None:
            reimagination = invitation  # compatibility for saved scripts
        invitation = reimagination
        candidate = 'brightness' if candidate == 'timbre' else candidate
        if candidate not in CANDIDATES:
            raise ValueError('unknown candidate')
        if invitation and candidate in config['reserved_for_reimagination']:
            raise ValueError('parameter conflict: reimagination reserves upper voice/harmony; choose level, brightness, or colour')
        if invitation and diagnostic and candidate == 'level':
            raise ValueError('parameter conflict: diagnostic reimagination uses level')
        self.candidate, self.config = candidate, config
        self.invitation, self.diagnostic = invitation, diagnostic
        self.value, self.previous_time, self.state, self.changed_at = None, None, 0, -1e9
        self.pending = None

    def update(self, amount, at):
        if not math.isfinite(amount) or not 0 <= amount <= 1 or not math.isfinite(at):
            raise ValueError('control amount/time must be finite and amount in [0,1]')
        c = self.config
        if self.previous_time is not None and at < self.previous_time:
            raise ValueError('mapping clock must be monotonic')
        dt = 0 if self.previous_time is None else at-self.previous_time
        self.value = amount if self.value is None else self.value+(amount-self.value)*(1-math.exp(-dt/c['smooth_seconds']))
        self.previous_time = at
        x = self.value
        desired = self.state
        state_count = len(c['harmony_midi']) if self.candidate == 'harmony' else 3
        if x > (self.state+1)/state_count+c['hysteresis'] and self.state < state_count-1:
            desired += 1
        elif x < self.state/state_count-c['hysteresis'] and self.state > 0:
            desired -= 1
        discrete = self.candidate in ('pitch', 'harmony')
        changed = False
        if discrete and desired != self.state and at-self.changed_at >= c['minimum_hold_seconds']:
            self.state, self.changed_at, changed = desired, at, True
        lerp = lambda pair: pair[0]+x*(pair[1]-pair[0])
        controls = dict(zip(MUSIC_FIELDS, [0, *c['fixed_frame'][5:], .18, 3, 0, 0,
            c['tempo_bpm'], c['reimagination_semitones'] if self.invitation and not self.diagnostic else 0,
            .85 if self.diagnostic else 0, 1, 0]))
        midi, weights = list(c['base_midi']), list(c['voice_weights'])
        if self.candidate == 'level':
            controls['auditionLevelDb'] = lerp(c['level_db'])
        elif self.candidate == 'pitch':
            midi[-1] = c['pitch_midi'][self.state]
        elif self.candidate == 'brightness':
            for i in range(4):
                controls[f'musicGroup{i+1}'] = lerp([c['groups_low'][i], c['groups_high'][i]])
        elif self.candidate == 'colour':
            controls['musicColour'] = x*2
        elif self.candidate == 'harmony':
            midi = c['harmony_midi'][self.state]
        frequencies = [hz(m) for m in midi]
        if not all(40 <= f <= 500 for f in frequencies):
            raise ValueError('voicing exceeds current 40–500 Hz interface')
        music_packet('validation', 0, controls)
        return dict(amount=amount, smoothed_amount=x, candidate=self.candidate,
            controls=controls, frequencies_hz=frequencies, note_weights=weights,
            midi=midi, state=self.state, discrete_changed=changed, effective_at=at,
            pending_at=None if self.pending is None else self.pending[0])
