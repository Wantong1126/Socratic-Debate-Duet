"""T12: strict, versioned invitation control separate from sound frames."""
from dataclasses import dataclass
import math
import time


INVITATION_PROTOCOL_VERSION = 1
INVITATION_CONTROL_ADDRESS = "/sdd/invitation/v1/control"
INVITATION_TARGET_CODES = {"A": 0, "B": 1}
INVITATION_MAX_MESSAGE_AGE_SECONDS = 0.5


def _finite(value, name):
    try:
        converted = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite and numeric") from exc
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite and numeric")
    return converted


@dataclass(frozen=True)
class InvitationControlMessage:
    session_id: str
    event_id: str
    target: str
    seq: int
    sampled_at: float
    invitation_amount: float

    def __post_init__(self):
        if self.target not in INVITATION_TARGET_CODES:
            raise ValueError("target must be A or B")
        if not isinstance(self.session_id, str) or not self.session_id:
            raise ValueError("session_id is required")
        if not isinstance(self.event_id, str) or not self.event_id:
            raise ValueError("event_id is required")
        if not isinstance(self.seq, int) or isinstance(self.seq, bool) or self.seq < 0:
            raise ValueError("seq must be a nonnegative integer")
        sampled_at = _finite(self.sampled_at, "sampled_at")
        amount = _finite(self.invitation_amount, "invitation_amount")
        if not 0.0 <= amount <= 1.0:
            raise ValueError("invitation_amount must be in [0, 1]")
        object.__setattr__(self, "sampled_at", sampled_at)
        object.__setattr__(self, "invitation_amount", amount)

    def as_osc_values(self, *, now, max_age=INVITATION_MAX_MESSAGE_AGE_SECONDS):
        now = _finite(now, "now")
        max_age = _finite(max_age, "max_age")
        age = now - self.sampled_at
        if max_age <= 0 or not 0.0 <= age <= max_age:
            raise ValueError("invitation control message is stale or from the future")
        return (
            INVITATION_TARGET_CODES[self.target], self.session_id, self.event_id,
            self.seq, age, self.invitation_amount,
        )


class InvitationOscSender:
    def __init__(self, host="127.0.0.1", port=57120, *, client=None,
                 address=INVITATION_CONTROL_ADDRESS, clock=time.monotonic):
        if not str(address).startswith("/"):
            raise ValueError("OSC address must start with '/'")
        self.address = str(address)
        self.clock = clock
        if client is None:
            from pythonosc.udp_client import SimpleUDPClient
            client = SimpleUDPClient(host, int(port))
        self.client = client
        self.count = 0

    def send(self, message, *, now=None):
        if not isinstance(message, InvitationControlMessage):
            raise TypeError("message must be InvitationControlMessage")
        sent_at = self.clock() if now is None else now
        self.client.send_message(
            self.address, list(message.as_osc_values(now=sent_at))
        )
        self.count += 1
        return message

    def close(self):
        socket = getattr(self.client, "_sock", None)
        if socket is not None:
            socket.close()
