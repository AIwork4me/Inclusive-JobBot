import json
import re

from benchmarks.slm10.mechanical import assess
from benchmarks.slm10 import portable


def test_individual_proof_replay_does_not_certify_an_unqualified_scope():
    packet = {"dimension": "D20", "events": [
        {"id": "trusted-count", "kind": "observation", "value": {"count": 3}},
        {"id": "candidate-answer", "kind": "final_answer", "value": '{"count":3}'},
    ]}
    result = assess("D20", packet)
    assert result["replay_status"] == "PASS"
    assert result["status"] == "BLOCKED"
    assert assess("D05", packet)["status"] == "BLOCKED"


def test_portable_observations_do_not_publish_private_token_encodings(monkeypatch):
    monkeypatch.setattr(portable, "LOCAL_IDENTITIES", {"user_path": re.compile("Users/SyntheticAccount")})
    text = "workspace Users/SyntheticAccount/research"
    raw = {"response": json.dumps({"text": text}), "prompt_token_ids": [4, 5],
           "sampled_bytes_hex": text.encode().hex(), "sampled_token_ids": [6, 7]}
    public = portable.portable(raw)
    assert "SyntheticAccount" not in public["response"]
    assert "SyntheticAccount" not in bytes.fromhex(public["sampled_bytes_hex"]).decode()
    assert "prompt_token_ids" not in public
    assert "sampled_token_ids" not in public
    assert len(public["sampled_bytes_hex_original_sha256"]) == 64
