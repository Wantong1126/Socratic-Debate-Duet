"""T10: explicit external invitations; no EEG/audio inference or scoring."""
from dataclasses import asdict, dataclass
import math
import time
import uuid


INVITATION_SOURCES = ("audience", "peer_A", "peer_B", "operator")
PARTICIPANT_IDS = ("A", "B")


@dataclass(frozen=True)
class InvitationEvent:
    event_id: str
    session_id: str
    source: str
    target: str
    prompt_id: str
    at: float
    prompt_text: str | None = None

    def __post_init__(self):
        for name in ("event_id", "session_id", "prompt_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if self.source not in INVITATION_SOURCES:
            raise ValueError(f"source must be one of {INVITATION_SOURCES}")
        if self.target not in PARTICIPANT_IDS:
            raise ValueError("target must be anonymous participant A or B")
        if not isinstance(self.at, (int, float)) or not math.isfinite(self.at):
            raise ValueError("event time must be finite monotonic seconds")
        if self.prompt_text is not None:
            if not isinstance(self.prompt_text, str) or len(self.prompt_text) > 240:
                raise ValueError("prompt_text must be a short optional string")

    def to_dict(self):
        return asdict(self)


class InvitationButton:
    """Convert each explicit press into exactly one immutable event."""

    def __init__(self, *, session_id, source, target, prompt_id,
                 prompt_text=None, clock=time.monotonic, id_factory=None):
        self.session_id = session_id
        self.source = source
        self.target = target
        self.prompt_id = prompt_id
        self.prompt_text = prompt_text
        self.clock = clock
        self.id_factory = id_factory or (lambda: str(uuid.uuid4()))

    def press(self):
        return InvitationEvent(
            event_id=self.id_factory(),
            session_id=self.session_id,
            source=self.source,
            target=self.target,
            prompt_id=self.prompt_id,
            at=self.clock(),
            prompt_text=self.prompt_text,
        )
