"""Current name for the external request to rethink an argument-weighing metric.

The envelope and six-value payload keep their established safety semantics.
Historical invitation imports/endpoints remain compatibility entry points.
"""
from dataclasses import asdict
from .invitation_input import ReimaginationEvent, ReimaginationButton
from .invitation_osc import InvitationControlMessage, InvitationOscSender
from .reflection_controller import (
    InvitationEnvelopeConfig as ReimaginationEnvelopeConfig,
    InvitationEnvelopeController as ReimaginationEnvelopeController,
)

REIMAGINATION_CONTROL_ADDRESS = '/sdd/reimagination/v1/control'
ReimaginationControlMessage = InvitationControlMessage


class ReimaginationOscSender(InvitationOscSender):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('address', REIMAGINATION_CONTROL_ADDRESS)
        super().__init__(*args, **kwargs)


def sample_dict(sample):
    values = asdict(sample)
    values['reimagination_amount'] = values.pop('invitation_amount')
    return values
