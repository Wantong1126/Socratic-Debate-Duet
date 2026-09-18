"""T02: internal metadata, never appended to the nine-value OSC packet."""
from dataclasses import asdict, dataclass, replace
import math

from src.sonification.protocol import ORGANISM_PARAMETER_ORDER, OrganismControlFrame


@dataclass(frozen=True)
class FrameEnvelope:
    session_id: str
    participant_id: str
    seq: int
    sampled_at: float
    received_at: float
    mode: str
    values: tuple
    valid: bool = True
    reason: str = ''

    def __post_init__(self):
        if not self.session_id or self.participant_id not in ('A', 'B'):
            raise ValueError('session_id and anonymous A/B identity required')
        if self.mode not in ('live', 'replay', 'fixture'):
            raise ValueError('unknown source mode')
        if not isinstance(self.seq, int) or self.seq < 0:
            raise ValueError('seq must be a nonnegative integer')
        if not all(math.isfinite(t) for t in (self.sampled_at, self.received_at)):
            raise ValueError('timestamps must be finite monotonic seconds')
        if self.sampled_at > self.received_at:
            raise ValueError('sample time must be mapped into receiver clock domain')
        converted = []
        reason = self.reason
        if len(self.values) != len(ORGANISM_PARAMETER_ORDER):
            reason = reason or 'field_count'
        for value in self.values:
            try:
                number = float(value)
            except (TypeError, ValueError, OverflowError):
                number = math.nan
            if not math.isfinite(number):
                converted.append(None)
                reason = reason or 'non_finite_or_nonnumeric'
            else:
                converted.append(number)
                if not 0 <= number <= 1:
                    reason = reason or 'out_of_range'
        valid = self.valid and not reason
        object.__setattr__(self, 'values', tuple(converted))
        object.__setattr__(self, 'valid', valid)
        object.__setattr__(self, 'reason', reason or ('' if valid else 'source_invalid'))

    def control_frame(self):
        if not self.valid:
            raise ValueError(self.reason)
        return OrganismControlFrame.from_values(self.values)

    def to_dict(self):
        return asdict(self)

    def remap(self, frame):
        return replace(self, values=frame.as_osc_values())


@dataclass(frozen=True)
class SessionEvent:
    session_id: str
    seq: int
    at: float
    source: str
    target: str
    kind: str
    reason: str = ''

    def __post_init__(self):
        if not self.session_id or self.target not in ('A', 'B'):
            raise ValueError('event requires session and A/B target')
        if self.source not in ('A', 'B', 'audience', 'system'):
            raise ValueError('unknown event source')
        if self.seq < 0 or not math.isfinite(self.at):
            raise ValueError('invalid event sequence/time')
