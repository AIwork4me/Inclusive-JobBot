from hashlib import sha256
import sqlite3

import pytest

from benchmarks.slm10.registry import MatchConflict, Registry, identity


def test_registry_binds_full_identity_and_counts_a_physical_trial_once(tmp_path):
    digest = lambda name: sha256(name.encode()).hexdigest()
    spec = {field: digest(field) for field in identity.HASH_FIELDS}
    spec |= {"case_id": "test-1", "track": "sdk", "attempt_slot": "first"}
    source = tmp_path / "wire.json"
    source.write_text("raw sample", encoding="utf-8")
    raw = sha256(source.read_bytes()).hexdigest()
    origin = {"git_sha": "1" * 40, "runtime_session": "session-a", "physical_ordinal": 2}
    with sqlite3.connect(tmp_path / "global.sqlite") as db:
        registry = Registry(db)
        assert registry.add("IJ-SDK-1.0", spec, origin, source, raw)
        assert not registry.add("IJ-SLM-1.0", spec, origin, source, raw)
        assert registry.count() == 1
        assert registry.lookup(spec)["evidence_sha256"] == raw
        changed = {**spec, "permissions_sha256": digest("other")}
        assert registry.lookup(changed) is None
        with pytest.raises(MatchConflict):
            registry.add("IJ-SLM-1.0", changed, origin, source, raw)
        with pytest.raises(ValueError, match="sha256"):
            registry.add("IJ-SLM-1.0", spec, origin, source, "0" * 64)
        with pytest.raises(MatchConflict):
            registry.add("IJ-SLM-1.0", spec, {**origin, "physical_ordinal": 3}, source, raw)
