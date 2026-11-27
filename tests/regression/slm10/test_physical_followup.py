from collections import Counter
from pathlib import Path

import pytest

from benchmarks.slm10.physical_followup import OUTPUT, describe, verified_payload, wire_observation


def test_replay_and_original_dispositions():
    summary, paired = describe(OUTPUT)
    assert paired["measured_pairs"] == 12
    assert paired["scoped_effect"]["one_sided_exact_sign_p"] == 0.75
    assert sum(run["attempts"] for run in summary["p0e"]) == 42
    assert sum((Counter(run["assessments"]) for run in summary["p0e"]), Counter()) == {
        "PASS": 8, "BLOCKED": 34,
    }
    assert sum((Counter(run["mechanical"]) for run in summary["extension"]), Counter()) == {
        "FAIL": 10, "BLOCKED": 5,
    }


def test_portable_payload_rejects_changed_digest(tmp_path: Path):
    path = tmp_path / "report.json"
    path.write_bytes(b"{}")
    with pytest.raises(ValueError, match="digest mismatch"):
        verified_payload(path, "0" * 64)


def test_used_completion_cannot_be_reused_between_trials():
    source = {"completion_id": "sample"}
    event = {"native_evidence": {"status": "PASS"}, "completion_id": "sample", "source_generation": source}
    with pytest.raises(ValueError, match="native completion"):
        wire_observation({"wire": [event]}, {"sample": source}, {"sample"})
