import hashlib
import json

import pytest

from scripts.tools.verify_ij06_evidence import validate_run


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def run(tmp_path):
    (tmp_path / "source.json").write_text('{"labels":["build"]}', encoding="utf-8")
    (tmp_path / "holdout.jsonl").write_text(
        '{"id":"case-1","template_id":"lookup"}\n{"id":"case-2","template_id":"review"}\n', encoding="utf-8",
    )
    (tmp_path / "development.jsonl").write_text('{"id":"dev-1","template_id":"dev"}\n', encoding="utf-8")
    (tmp_path / "gpu_launch.json").write_text(
        '{"pid":321,"backend":"vulkan","status":"PASS","owns_port":true,"layers_offloaded":43}', encoding="utf-8",
    )
    (tmp_path / "gpu_counters.jsonl").write_text(
        '{"kind":"gpu_engine","instance":"pid_321_x","engtype":"Compute","utilization":4}\n'
        '{"kind":"gpu_process_memory","instance":"pid_321_x","committed_bytes":100}\n', encoding="utf-8",
    )
    traces = [
        {"id": cid, "run_id": "run-1", "config_id": "vulkan-q8", "status": "PASS"}
        for cid in ("case-1", "case-2")
    ]
    raw = tmp_path / "results.jsonl"
    raw.write_text("".join(json.dumps(row) + "\n" for row in traces), encoding="utf-8")
    identity = {
        key: "1" * 64 for key in (
            "evaluator_sha256", "engine_binary_sha256", "model_sha256", "chat_template_sha256",
            "oracle_sha256", "tool_schema_sha256", "policy_sha256",
        )
    }
    identity.update(
        run_id="run-1", git_commit_sha="a" * 40, git_dirty_state=False, engine_commit="b" * 40,
        runtime_dll_sha256={"backend.dll": "2" * 64}, modelscope_revision="c" * 40,
        parser_version="p1", sdk_version="0.1.24", backend="vulkan",
        gpu_identity={"architecture": "gfx1151"}, seed=123, configuration={"id": "vulkan-q8"},
        start_time_utc="2026-11-24T00:01:00Z", end_time_utc="2026-11-24T00:02:00Z",
        dataset_sha256=digest(tmp_path / "holdout.jsonl"),
        source_manifest_sha256=digest(tmp_path / "source.json"),
    )
    document = {
        "qualification": True, "evidence_type": "REAL_GPU", "identity": identity,
        "files": {
            key: {"path": name, "sha256": digest(tmp_path / name)}
            for key, name in (
                ("source_manifest", "source.json"), ("dataset", "holdout.jsonl"),
                ("development", "development.jsonl"), ("traces", "results.jsonl"),
                ("gpu_counters", "gpu_counters.jsonl"), ("gpu_launch", "gpu_launch.json"),
                ("cpu_reference", "source.json"),
            )
        },
        "holdout": {
            "candidate_frozen_utc": "2026-11-24T00:00:00Z", "tuned_using_holdout": False,
            "independence_review": "PASS",
            "candidate_git_sha": identity["git_commit_sha"],
        },
        "summary": {"cases": 2, "PASS": 2, "FAIL": 0, "BLOCKED": 0, "NOT_RUN": 0},
        "gates": {"parser": "PASS", "safety": "PASS"}, "go": True,
    }
    return document, traces, tmp_path


def test_valid_run(run):
    assert validate_run(run[0], run[2], {"parser", "safety"}) == []


@pytest.mark.parametrize(("field", "value", "expected"), [
    ("evidence_type", "MOCK", "GPU"),
    ("summary", {"cases": 3}, "summary"),
    ("gates", {"parser": "PASS", "safety": "FAIL"}, "GO"),
    ("gates", {"parser": "PASS"}, "GO"),
    ("gates", {"parser": "GREEN", "safety": "PASS"}, "gate status"),
    ("holdout", {"tuned_using_holdout": True}, "holdout"),
])
def test_metadata_mutations(run, field, value, expected):
    document, _, root = run
    document[field] = value
    assert any(expected in issue for issue in validate_run(document, root, {"parser", "safety"}))


@pytest.mark.parametrize(("field", "value", "expected"), [
    ("id", "case-1", "duplicate"), ("status", "GREEN", "trace status"),
    ("config_id", "hip-q4", "configuration"), ("run_id", "another-run", "configuration"),
])
def test_trace_mutations(run, field, value, expected):
    document, traces, root = run
    traces[1][field] = value
    path = root / "results.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in traces), encoding="utf-8")
    document["files"]["traces"]["sha256"] = digest(path)
    assert any(expected in issue for issue in validate_run(document, root, {"parser", "safety"}))


def test_missing_digest_or_source_identity(run):
    document, _, root = run
    del document["identity"]["engine_commit"]
    document["identity"]["git_dirty_state"] = True
    document["files"]["traces"]["sha256"] = "0" * 64
    document["files"]["source_manifest"]["path"] = "../source.json"
    errors = " ".join(validate_run(document, root, {"parser", "safety"}))
    assert all(word in errors for word in ("engine_commit", "dirty", "digest", "path"))


def test_wrong_process_gpu_counters(run):
    document, _, root = run
    path = root / "gpu_counters.jsonl"
    path.write_text(path.read_text().replace("pid_321_", "pid_123_"), encoding="utf-8")
    document["files"]["gpu_counters"]["sha256"] = digest(path)
    assert any("GPU process" in issue for issue in validate_run(document, root, {"parser", "safety"}))


def test_holdout_template_overlap(run):
    document, _, root = run
    path = root / "development.jsonl"
    path.write_text('{"id":"distinct","template_id":"review"}\n', encoding="utf-8")
    document["files"]["development"]["sha256"] = digest(path)
    assert any("overlap" in issue for issue in validate_run(document, root, {"parser", "safety"}))
