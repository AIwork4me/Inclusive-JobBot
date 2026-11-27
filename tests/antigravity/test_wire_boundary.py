from dataclasses import dataclass
from decimal import Decimal
import json

import pytest

from benchmarks.ij06_sdk.wire_boundary import ApprovalQueue
from audit import write_evidence


@dataclass
class Call:
    call_id: str
    name: str
    arguments_raw: str


def test_only_validated_wire_arguments_can_be_claimed_once():
    queue = ApprovalQueue()
    call = Call("x", "lookup", '{"id":"PO-1"}')
    queue.publish([call])
    with pytest.raises(ValueError):
        queue.claim("lookup", {"id": "PO-2"})
    assert queue.claim("lookup", {"id": "PO-1"}) == call
    with pytest.raises(ValueError):
        queue.claim("lookup", {"id": "PO-1"})


def test_argument_type_change_and_ambiguous_callback_rejected():
    queue = ApprovalQueue()
    first = Call("x", "lookup", '{"count":1}')
    second = Call("y", "lookup", '{"count":1}')
    queue.publish([first])
    with pytest.raises(ValueError):
        queue.claim("lookup", {"count": True})
    with pytest.raises(ValueError, match="Duplicate"):
        queue.publish([first])
    queue = ApprovalQueue()
    queue.publish([first, second])
    with pytest.raises(ValueError):
        queue.claim("lookup", {"count": 1})


def test_expiring_turn_and_invalid_arguments_do_not_leave_permits():
    queue = ApprovalQueue()
    call = Call("x", "lookup", '{"id":"PO-1"}')
    queue.publish([call])
    queue.publish([])
    with pytest.raises(ValueError):
        queue.claim("lookup", {"id": "PO-1"})
    with pytest.raises(ValueError):
        queue.publish([Call("y", "lookup", '{"id":"PO-1","id":"PO-2"}')])
    with pytest.raises(ValueError):
        queue.claim("lookup", {"id": "PO-1"})


def test_cancellation_closes_approval_queue():
    queue = ApprovalQueue()
    call = Call("x", "lookup", '{"id":"PO-1"}')
    queue.publish([call])
    queue.close()
    with pytest.raises(ValueError, match="closed"):
        queue.claim("lookup", {"id": "PO-1"})
    with pytest.raises(ValueError, match="closed"):
        queue.publish([call])


def test_checkpoint_preserves_exact_decimal(tmp_path):
    output = tmp_path / "checkpoint.json"
    value = Decimal("123456789.123456789123456789")
    write_evidence(output, {"audit": {"elapsed": value}})
    loaded = json.loads(output.read_text(encoding="utf-8"), parse_float=Decimal)
    assert loaded["audit"]["elapsed"] == value
