"""T06/T08: latest-only single-person transport with validity and freshness gates."""
import math
import time

from .session_types import SessionEvent


class SessionRuntime:
    def __init__(self, sender, *, session_id, participant_id='A', rate=4,
                 max_age=0.5, clock=time.monotonic, recorder=None, mapping=None):
        if not math.isfinite(rate) or not 0 < rate <= 20 or max_age <= 0:
            raise ValueError('invalid timing configuration')
        if participant_id not in ('A', 'B'):
            raise ValueError('anonymous identity required')
        self.sender, self.clock, self.recorder = sender, clock, recorder
        self.mapping = mapping or (lambda frame: frame)
        self.session_id, self.participant_id = session_id, participant_id
        self.period, self.max_age = 1/rate, max_age
        self.next_at = clock()
        self.latest = None
        self.last_seq = -1
        self.last_sampled = float('-inf')
        self.event_seq = 0
        self.last_sent_at = None
        self.loss_reported = False
        self.stopped = False

    def log(self, kind, reason):
        event = SessionEvent(self.session_id, self.event_seq, self.clock(),
                             'system', self.participant_id, kind, reason)
        self.event_seq += 1
        if self.recorder:
            self.recorder.event(event)

    def offer(self, envelope):
        if self.stopped:
            return False
        if (envelope.session_id, envelope.participant_id) != (self.session_id, self.participant_id):
            raise ValueError('runtime is bound to one session/participant')
        now = self.clock()
        if self.recorder:
            self.recorder.frame(envelope)
        if not envelope.valid:
            self.latest = None
            self.log('quality', envelope.reason)
            return False
        if (envelope.seq <= self.last_seq or envelope.sampled_at <= self.last_sampled
                or not 0 <= now-envelope.sampled_at <= self.max_age
                or envelope.received_at > now):
            self.log('quality', 'stale_or_duplicate')
            return False
        self.last_seq, self.last_sampled = envelope.seq, envelope.sampled_at
        self.latest = envelope
        return True

    def tick(self):
        now = self.clock()
        if self.stopped or now < self.next_at:
            return False
        # No += period backlog. One deadline is scheduled from actual send time.
        self.next_at = now + self.period
        envelope, self.latest = self.latest, None
        if envelope is not None and 0 <= now-envelope.sampled_at <= self.max_age:
            self.sender.send(self.mapping(envelope.control_frame()))
            self.last_sent_at = now
            self.loss_reported = False
            return True
        if (self.last_sent_at is not None and now-self.last_sent_at > self.max_age
                and not self.loss_reported):
            self.log('signal_loss', 'no_fresh_valid_frame; receiver_watchdog_will_fade')
            self.loss_reported = True
        return False

    def stop(self, reason='stop'):
        if not self.stopped:
            self.sender.send_stop()
            self.stopped = True
            self.latest = None
            self.log('stop', reason)
