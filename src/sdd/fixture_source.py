"""T04: control fixtures and separately labelled simulated raw EEG."""
import math
import random

from src.sonification.protocol import ORGANISM_PARAMETER_ORDER
from .session_types import FrameEnvelope


def control_fixture(*, session_id='fixture', participant_id='A', duration=12,
                    rate=4, field='energy', levels=(0.2, 0.5, 0.8),
                    fixed=(0.5, 0.24, 0.1, 0.12, 0.04, 0.82, 0.58, 0.28, 0.08),
                    dropout=(), origin=0.0):
    if field not in ORGANISM_PARAMETER_ORDER or duration <= 0 or not 0 < rate <= 20:
        raise ValueError('invalid fixture configuration')
    if not levels or len(fixed) != 9:
        raise ValueError('levels and nine fixed values required')
    index = ORGANISM_PARAMETER_ORDER.index(field)
    for seq in range(int(duration * rate)):
        elapsed = seq / rate
        if any(start <= elapsed < end for start, end in dropout):
            continue
        values = list(fixed)
        values[index] = levels[min(len(levels)-1, int(elapsed / duration * len(levels)))]
        yield FrameEnvelope(session_id, participant_id, seq, origin+elapsed,
                            origin+elapsed, 'fixture', tuple(values))


def simulated_raw(*, seed=20260904, sample_rate=250, duration=1):
    """Synthetic 10 Hz plus seeded noise, volts; never real EEG."""
    if sample_rate <= 20 or duration <= 0:
        raise ValueError('invalid simulated sample clock')
    rng = random.Random(seed)
    return dict(mode='fixture', sample_rate=sample_rate, channels=['simulated'],
                units='V', samples=[[20e-6 * math.sin(2*math.pi*10*i/sample_rate)
                                   + rng.gauss(0, 1e-6)]
                                  for i in range(int(sample_rate*duration))])
