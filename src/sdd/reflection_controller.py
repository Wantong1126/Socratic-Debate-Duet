"""T11: independent continuous invitation envelopes for participants A and B."""
from dataclasses import asdict, dataclass
import math

from .invitation_input import InvitationEvent, PARTICIPANT_IDS


PHASES = ("idle", "attack", "hold", "release", "cooldown", "paused")
TERMINATION_REASONS = (
    "completed", "declined", "ended", "paused", "signal_loss", "stopped",
)


@dataclass(frozen=True)
class InvitationEnvelopeConfig:
    attack_seconds: float = 0.5
    hold_seconds: float = 1.0
    release_seconds: float = 0.5
    cooldown_seconds: float = 0.5

    def __post_init__(self):
        values = asdict(self)
        if any(not math.isfinite(value) for value in values.values()):
            raise ValueError("invitation durations must be finite")
        if self.attack_seconds <= 0 or self.release_seconds <= 0:
            raise ValueError("attack and release must be positive")
        if self.hold_seconds < 0 or self.cooldown_seconds < 0:
            raise ValueError("hold and cooldown cannot be negative")


@dataclass(frozen=True)
class InvitationSample:
    target: str
    phase: str
    invitation_amount: float
    at: float
    event_id: str | None
    source: str | None


@dataclass(frozen=True)
class InvitationTermination:
    event_id: str
    session_id: str
    target: str
    reason: str
    at: float


@dataclass
class _ParticipantState:
    phase: str = "idle"
    phase_started_at: float = 0.0
    amount: float = 0.0
    release_start_amount: float = 0.0
    release_reason: str | None = None
    event: InvitationEvent | None = None
    last_at: float = float("-inf")


class InvitationEnvelopeController:
    def __init__(self, config=InvitationEnvelopeConfig(), *, termination_sink=None):
        self.config = config
        self.termination_sink = termination_sink
        self._states = {participant: _ParticipantState() for participant in PARTICIPANT_IDS}
        self.terminations = []

    def _state(self, target):
        if target not in self._states:
            raise ValueError("target must be A or B")
        return self._states[target]

    @staticmethod
    def _sample(state, target, at):
        event = state.event
        return InvitationSample(
            target=target,
            phase=state.phase,
            invitation_amount=min(1.0, max(0.0, state.amount)),
            at=at,
            event_id=event.event_id if event else None,
            source=event.source if event else None,
        )

    def invite(self, event):
        if not isinstance(event, InvitationEvent):
            raise TypeError("event must be an InvitationEvent")
        current = self.advance(event.target, event.at)
        state = self._state(event.target)
        if current.phase not in ("idle", "paused"):
            return False
        state.phase = "attack"
        state.phase_started_at = event.at
        state.amount = 0.0
        state.release_start_amount = 0.0
        state.release_reason = None
        state.event = event
        state.last_at = event.at
        return True

    def advance(self, target, at):
        state = self._state(target)
        if not isinstance(at, (int, float)) or not math.isfinite(at):
            raise ValueError("sample time must be finite")
        if at < state.last_at:
            raise ValueError("invitation time must be monotonic per participant")
        state.last_at = at
        while True:
            elapsed = at - state.phase_started_at
            if state.phase == "attack":
                end = state.phase_started_at + self.config.attack_seconds
                if at < end:
                    state.amount = elapsed / self.config.attack_seconds
                    break
                state.phase = "hold"
                state.phase_started_at = end
                state.amount = 1.0
                continue
            if state.phase == "hold":
                end = state.phase_started_at + self.config.hold_seconds
                if at < end:
                    state.amount = 1.0
                    break
                state.phase = "release"
                state.phase_started_at = end
                state.release_start_amount = 1.0
                state.release_reason = "completed"
                continue
            if state.phase == "release":
                end = state.phase_started_at + self.config.release_seconds
                if at < end:
                    fraction = (at - state.phase_started_at) / self.config.release_seconds
                    state.amount = state.release_start_amount * (1.0 - fraction)
                    break
                state.amount = 0.0
                event = state.event
                reason = state.release_reason
                if event is not None:
                    termination = InvitationTermination(
                        event.event_id, event.session_id, target, reason, end,
                    )
                    self.terminations.append(termination)
                    if self.termination_sink is not None:
                        self.termination_sink(termination)
                state.phase_started_at = end
                state.phase = "paused" if reason == "paused" else "cooldown"
                continue
            if state.phase == "cooldown":
                end = state.phase_started_at + self.config.cooldown_seconds
                if at < end:
                    state.amount = 0.0
                    break
                state.phase = "idle"
                state.phase_started_at = end
                state.amount = 0.0
                state.event = None
                state.release_reason = None
                continue
            state.amount = 0.0
            break
        return self._sample(state, target, at)

    def _terminate(self, target, reason, at):
        if reason not in TERMINATION_REASONS or reason == "completed":
            raise ValueError("invalid explicit termination reason")
        sample = self.advance(target, at)
        state = self._state(target)
        if sample.phase not in ("attack", "hold"):
            return False
        state.phase = "release"
        state.phase_started_at = at
        state.release_start_amount = sample.invitation_amount
        state.release_reason = reason
        state.amount = sample.invitation_amount
        return True

    def decline(self, target, at):
        return self._terminate(target, "declined", at)

    def end(self, target, at):
        return self._terminate(target, "ended", at)

    def pause(self, target, at):
        return self._terminate(target, "paused", at)

    def signal_loss(self, target, at):
        return self._terminate(target, "signal_loss", at)

    def stop(self, target, at):
        return self._terminate(target, "stopped", at)
