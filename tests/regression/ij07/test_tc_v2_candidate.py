"""Software-only candidate identity and competitive TC-V2 adapter tests."""

import hashlib
import json

import pytest

from benchmarks.competitive_slm import tc_v2_candidate as candidate
from benchmarks.tool_calling_v2.holdout import dataset


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body), encoding="utf-8")


@pytest.fixture
def identity(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    model = tmp_path / "Model-Q8_0.gguf"
    model.write_bytes(b"test-only gguf bytes")
    engine_dir = tmp_path / "engine"
    engine_dir.mkdir()
    binary = engine_dir / "llama-server.exe"
    binary.write_bytes(b"test-only executable")
    plugin = engine_dir / "ggml-vulkan.dll"
    plugin.write_bytes(b"test-only dll")
    model_asset = {
        "status": "PASS", "expected_sha256": sha(model.read_bytes()), "observed_sha256": sha(model.read_bytes()),
        "filename": model.name, "repo": "test/gguf", "revision": "a" * 40, "size": model.stat().st_size,
    }
    passports = root / "evidence/IJ07/model_identity"
    write_json(passports / "B.json", {"runtime_asset": model_asset, "official_model_id": "test/model",
                                    "official_config_and_template": {"config.json": "b" * 64}})
    write_json(root / "configs/ij07/model_candidates.yaml", {
        "schema_version": 1, "candidate_identity": {"B": "evidence/IJ07/model_identity/B.json"},
        "shared_runtime": {"engine_commit": "c" * 40, "backend": "vulkan",
                           "quantization": "Q8_0", "context_tokens": 8192},
    })
    template = "test tokenizer chat template"
    admission = {
        "candidate": "B", "model_id": "test/model", "asset": model_asset, "run_id": "fixture-admission",
        "status": "PASS", "requested_disable_thinking": True,
        "gates": dict.fromkeys(candidate.GATES, "PASS"),
        "gpu_engine": {"exe_sha256": sha(binary.read_bytes()), "dll_sha256": {plugin.name: sha(plugin.read_bytes())}},
        "gpu": {"backend": "vulkan", "build": f"b12359-{'c' * 40}", "template_sha256": sha(template.encode()),
                "layers_total": 4, "layers_offloaded": 4,
                "gpu": {"name": "AMD Radeon(TM) 8060S Graphics", "device": "Vulkan0", "architecture": "gfx1151"}},
    }
    report = passports / "admission_strict/B/report.json"
    write_json(report, admission)
    monkeypatch.setattr(candidate, "read_embedded_template", lambda _: template)
    return root, model, engine_dir, report, admission


def test_model_and_engine_bytes_and_embedded_template_are_pinned(identity, monkeypatch):
    root, model, engine, _, _ = identity
    result = candidate.verify_runtime("B", model, engine, root=root)
    assert result["model"]["model_sha256"] == sha(model.read_bytes())
    assert result["engine"]["dll_sha256"]["ggml-vulkan.dll"] == sha((engine / "ggml-vulkan.dll").read_bytes())
    assert result["template"]["selection"] == "gguf_embedded"
    assert result["budgets"]["version"] == candidate.BUDGETS["version"]
    monkeypatch.setattr(candidate, "read_embedded_template", lambda _: "another template")
    with pytest.raises(ValueError, match="template differs"):
        candidate.verify_runtime("B", model, engine, root=root)


def test_embedded_and_server_digests_use_pinned_lexer_normalization(identity, monkeypatch):
    root, model, engine, path, report = identity
    raw = "line one\r\nline two  \r\n\r\n"
    expected = "line one\nline two  \n"
    report["gpu"]["template_sha256"] = sha(expected.encode())
    write_json(path, report)
    monkeypatch.setattr(candidate, "read_embedded_template", lambda _: raw)
    template = candidate.verify_runtime("B", model, engine, root=root)["template"]
    assert template["embedded_sha256"] == sha(raw.encode())
    assert template["sha256"] == sha(expected.encode())


def test_ministral_template_compatibility_is_the_pinned_builtin_transformation():
    guard = candidate.MISTRAL_EMPTY_MESSAGE_CHECK
    assert candidate.server_template_source("[TOOL_CALLS]" + guard + "\n") == "[TOOL_CALLS]{%- if false %}"
    assert candidate.server_template_source("other template" + guard + "\n") == "other template" + guard


def test_modified_asset_or_extra_dll_blocks_without_fallback(identity):
    root, model, engine, _, _ = identity
    (engine / "ggml-hip.dll").write_bytes(b"unexpected backend")
    with pytest.raises(ValueError, match="Vulkan engine"):
        candidate.verify_runtime("B", model, engine, root=root)
    (engine / "ggml-hip.dll").unlink()
    model.write_bytes(b"x" * model.stat().st_size)
    with pytest.raises(ValueError, match="model digest"):
        candidate.verify_runtime("B", model, engine, root=root)


def test_failed_admission_cannot_be_promoted(identity):
    root, model, engine, report, admission = identity
    admission["status"] = "FAIL"
    admission["gates"]["native_call"] = "FAIL"
    write_json(report, admission)
    with pytest.raises(ValueError, match="strict Vulkan admission"):
        candidate.verify_runtime("B", model, engine, root=root)


def test_case_and_repeat_seed_are_from_the_same_frozen_holdout():
    rows, manifest = dataset.load("holdout")
    chosen = manifest["repeat"]["cases"][0]
    case, trial = candidate.select_case("holdout", chosen, False, 2)
    assert case == next(row for row in rows if row["id"] == chosen)
    assert trial["seed"] == manifest["repeat"]["seeds"][1]
    assert trial["repeat_index"] == 2
    with pytest.raises(ValueError, match="repeat panel"):
        candidate.select_case("holdout", next(row["id"] for row in rows if row["id"] not in manifest["repeat"]["cases"]),
                              False, 1)
    with pytest.raises(ValueError, match="frozen split"):
        candidate.select_case("dev", chosen, False, None)


def test_fixture_wire_runs_the_existing_sqlite_oracle_and_requires_observer(tmp_path, monkeypatch):
    case, trial = candidate.select_case("holdout", "TCV2-H-0001", False, None)
    step = case["oracle"]["steps"][0]
    captures = candidate.BudgetedCapture(8102, tmp_path / "mock-source.jsonl", "fixture-candidate")
    sent = []

    def response(path, body):
        sent.append((path, body))
        if path == "/apply-template":
            data = {"prompt": "rendered fixture prompt"}
        elif path == "/tokenize":
            data = {"tokens": [1, 2, 3]}
        else:
            first = len(captures.requests) == 0
            message = {"role": "assistant"}
            if first:
                message["tool_calls"] = [{"id": "fixture-call", "type": "function", "function": {
                    "name": step["tool"], "arguments": json.dumps(step["args"]),
                }}]
            else:
                message["content"] = json.dumps(case["oracle"]["final"])
            data = {"id": "fixture-id", "usage": {"prompt_tokens": 3, "completion_tokens": 1},
                    "choices": [{"message": message, "finish_reason": "tool_calls" if first else "stop"}]}
        return 200, "application/json", json.dumps(data).encode()

    source = {"completion_id": "fixture-id", "stream": False, "prompt_token_ids": [1, 2, 3],
              "sampled_token_ids": [4], "pre_parser_bytes_hex": "60", "sampled_bytes_hex": "60", "truncated": False}
    monkeypatch.setattr(captures, "_send", response)
    monkeypatch.setattr(captures, "read_trace", lambda: [source])
    result = candidate.runner.run_trajectory(case, captures, tmp_path / "pass.sqlite", stream=False, seed=trial["seed"])
    assert result["status"] == result["business_state_status"] == "PASS"
    assert [body["model"] for path, body in sent if path == "/v1/chat/completions"] == ["fixture-candidate"] * 2
    assert result["requests"][0]["context_budget"]["actual_prompt_tokens"] == 3

    monkeypatch.setattr(captures, "read_trace", lambda: [])
    blocked = candidate.runner.run_trajectory(case, captures, tmp_path / "blocked.sqlite", stream=False, seed=trial["seed"])
    assert blocked["status"] == "BLOCKED"
    assert blocked["after_sqlite"]["audit_events"] == {}


def test_context_overrun_refuses_to_generate(tmp_path, monkeypatch):
    wire = candidate.BudgetedCapture(8102, tmp_path / "mock-source.jsonl", "fixture-candidate")
    calls = []

    def response(path, body):
        calls.append(path)
        data = {"prompt": "fixture"} if path == "/apply-template" else {"tokens": [1] * 8192}
        return 200, "application/json", json.dumps(data).encode()

    monkeypatch.setattr(wire, "_send", response)
    with pytest.raises(candidate.CaptureError, match="context budget"):
        wire.post("/apply-template", {"messages": []})
    assert calls == ["/apply-template", "/tokenize"]
