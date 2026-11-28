"""Replay the LFM3 paired SDK holdout from a portable physical capture."""

import argparse
from collections import Counter
from dataclasses import asdict
import gzip
from hashlib import sha256
import json
from math import ceil, comb, isfinite
from pathlib import Path
from random import Random
import re
from statistics import fmean

from benchmarks.tool_calling_v2.oracle import decode_object, equal
from evaluation.aeve.archive import check_text, digest
from evaluation.aeve.runtime import canonical, fingerprint

from .sdk_ablation_summary import COVERAGE, OUTPUT
from .sdk_adapter_development import HANDOFF, PLAN, ROOT, load_plan, load_profiles
from .sdk_causal_metrics import answer_metrics, assign_actions, replay_wire
from .sdk_wave_queue import verify_gpu_artifact
from .tc_dashboard import percentile
from .tc_v3 import CONFIG, PARAMETERS, TOOLS
from .tc_verification import delivered_result


VERSION = "IJ-SLM-SDK-ADAPTER-HOLDOUT-REPORT/1.0"
STATES = ("PASS", "FAIL", "BLOCKED", "NOT_RUN")
ARMS = ("reference", "treatment")
CATEGORICAL = ("business_facts", "output_contract", "execution_process", "termination", "scoped_completion")
NUMERIC = ("duplicate_proposals", "redundant_executions", "model_requests", "input_tokens", "output_tokens",
           "end_to_end_latency_ms")
CONFIDENCE_PERCENT = 95
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 7107
THRESHOLD = ("All 12 pairs require process-linked physical evidence, resolved categorical endpoints and observed "
             "compact delivery in the treatment. Each protected endpoint must have zero paired regressions. "
             "Scoped completion must improve by a one-sided exact paired sign test at p <= 0.05. "
             "This exploratory rule applies to the pinned LFM3 and SDK on the four synthetic read-only families.")


def six_arm_dispositions():
    seal = json.loads((OUTPUT / "manifest.json").read_bytes())
    coverage_sha = digest(COVERAGE)
    if seal["development_in_core"] != 0 or seal["files"][COVERAGE.name] != coverage_sha:
        raise ValueError("six-arm coverage is not bound to its published evidence manifest")
    coverage = json.loads(COVERAGE.read_bytes())
    rows = [row for row in coverage["trials"] if row["arm"] in {"A0", "A1", "A2", "A3", "A4", "A5"}]
    keys = {(row["candidate"], row["case_id"], row["arm"]) for row in rows}
    if len(keys) != len(rows) or len(rows) != 540 or coverage["formal_trials"] != 0:
        raise ValueError("six-arm coverage roster differs from the registered development allocation")
    missing = [row for row in rows if row["physical_capture"] != "PASS"]
    for row in missing:
        sources = [path for path, value in seal["files"].items() if value == row["report_sha256"]
                   and path.endswith("/report.json")]
        if len(sources) != 1 or digest(OUTPUT / sources[0]) != row["report_sha256"]:
            raise ValueError("six-arm disposition lacks a matching published report")
        report = json.loads((OUTPUT / sources[0]).read_bytes())
        entries = [arm for case in report["results"] if case["case_id"] == row["case_id"]
                   for arm in case["arms"] if arm["arm"] == row["arm"]]
        if (report["run_id"] != row["run_id"] or report["candidate"] != row["candidate"] or len(entries) != 1
                or entries[0].get("capture") is not None or entries[0].get("status") != row["physical_capture"]
                or entries[0].get("reason", entries[0].get("applicability")) != row["reason"]):
            raise ValueError("six-arm disposition differs from its sealed observation")
    counts = Counter(row["physical_capture"] for row in rows)
    return {"coverage_sha256": coverage_sha, "counts": {status: counts[status] for status in STATES},
            "unmeasured": missing}


def validate_pairs(report, cases):
    expected = [(case["public"]["case_id"], arm, case) for case in cases for arm in case["arm_order"]]
    actual = report["results"]
    if (report["planned_case_ids"] != [case["public"]["case_id"] for case in cases]
            or [(row["case_id"], row["arm"]) for row in actual] != [(key, arm) for key, arm, _ in expected]):
        raise ValueError("holdout pair roster is incomplete, reordered or duplicated")
    for row, (key, arm, case) in zip(actual, expected, strict=True):
        capture = row["capture"]
        if (capture["trial_id"] != fingerprint([report["run_id"], key, arm, case["seed"]])
                or capture["seed"] != case["seed"] or capture["profile"] != report["profiles"][arm]):
            raise ValueError("holdout trial identity, profile or seed differs from the registered pair")
    return [(row, case) for row, (_, _, case) in zip(actual, expected, strict=True)]


def _verified_capture(path, plan, expected_sha256):
    from benchmarks.competitive_slm.tc_v2_candidate import VULKAN_DEVICE, verify_launch
    from .multitool_v2_statistics import observer_identity

    raw = path.read_bytes()
    check_text(raw)
    report_sha = sha256(raw).hexdigest()
    if expected_sha256 is not None and report_sha != expected_sha256:
        raise ValueError("portable report digest differs from the expected digest")
    report = json.loads(raw)
    profiles = load_profiles()
    profile_pair = {"reference": asdict(profiles["reference"]), "treatment": asdict(profiles[plan["treatment"]])}
    profile_pair = json.loads(canonical(profile_pair))
    expected = {key: plan[key] for key in ("version", "candidate", "dataset_sha256", "dataset_manifest_sha256",
                                             "profile_registry_sha256", "formal_trial_attribution")}
    local_sources = ("sdk_adapter_development.py", "sdk_adapters.py", "tc_execution.py", "native_diagnostics.py")
    expected.update(sdk=plan["sdk_version"], holdout_plan_sha256=digest(PLAN), gpu_execution="PASS",
                    handoff_sha256=digest(ROOT / HANDOFF), profiles=profile_pair, independent_holdout=True,
                    source_sha256={name: digest(Path(__file__).with_name(name)) for name in local_sources},
                    wire_boundary_sha256=digest(ROOT / "benchmarks/ij06_sdk/wire_boundary.py"),
                    provider_configuration={
                        "stream": False, "seed": plan["cases"][0]["seed"], "temperature": CONFIG["temperature"],
                        "max_completion_tokens": CONFIG["max_completion_tokens"], "cache_prompt": CONFIG["cache_prompt"],
                        "chat_template_kwargs": {"enable_thinking": CONFIG["thinking"]},
                        "parallel_tool_calls": True, "tool_choice": "auto",
                    })
    identity = json.loads((ROOT / "evidence/IJ07/model_identity/B.json").read_bytes())
    runtime = json.loads((ROOT / "evidence/IJ07/model_identity/admission_strict/B/report.json").read_bytes())
    asset, old_gpu = identity["runtime_asset"], runtime["gpu"]
    engine_hashes, _, harness = observer_identity()
    expected.update(engine_sha256=engine_hashes, harness_sha256=harness,
                    model={"official_model_id": identity["official_model_id"], "runtime_repo": asset["repo"],
                           "runtime_revision": asset["revision"], "filename": asset["filename"],
                           "model_sha256": asset["expected_sha256"], "quantization": "Q8_0",
                           "upstream_config": identity["official_config_and_template"]})
    if any(report.get(key) != value for key, value in expected.items()):
        raise ValueError("portable holdout differs from pinned model, runtime, dataset or profile identity")
    for key, pattern in {"git_sha": "[a-f0-9]{40}", "run_id": "ijslm-adapters-[a-f0-9]{32}",
                         "private_report_sha256": "[a-f0-9]{64}", "private_native_trace_sha256": "[a-f0-9]{64}"}.items():
        if re.fullmatch(pattern, str(report.get(key, ""))) is None:
            raise ValueError(f"portable holdout lacks valid {key}")
    if set(report["artifacts"]) != {"gpu.jsonl.gz", "native.jsonl.gz"}:
        raise ValueError("portable holdout lacks the required GPU and native trace artifacts")
    archives = {}
    for name, expected_sha in report["artifacts"].items():
        data = (path.parent / name).read_bytes()
        if sha256(data).hexdigest() != expected_sha:
            raise ValueError(f"portable holdout artifact digest mismatch: {name}")
        decoded = gzip.decompress(data)
        check_text(decoded)
        archives[name] = [json.loads(line) for line in decoded.splitlines()]
    gpu = report["gpu"]
    lease = gpu["gpu_lease"]
    handoff = json.loads((ROOT / HANDOFF).read_bytes())["lease"]
    if (lease["runtime_session"] != report["run_id"] or lease["mission_id"] != "IJ-SLM-1.0"
            or lease["lease_owner"] != "sdk-adapter-development"
            or any(lease[key] != handoff[key] for key in ("host_sha256", "gpu_physical_sha256"))):
        raise ValueError("holdout Radeon lease differs from the approved handoff")
    verify_launch(gpu, {"gpu": VULKAN_DEVICE, "engine": {"build": old_gpu["build"], "layers": old_gpu["layers_total"]},
                        "template": {"sha256": old_gpu["template_sha256"]}})
    verify_gpu_artifact(path.parent, "gpu.jsonl.gz", gpu)
    native_rows = archives["native.jsonl.gz"]
    native = {row["completion_id"]: row for row in native_rows}
    if len(native) != len(native_rows) or not native:
        raise ValueError("holdout native archive lacks unique completion identities")
    return report, report_sha, native


def _value(value):
    return {"status": "BLOCKED" if value is None else "PASS", "value": value}


def analyze_capture(capture, oracle, native, *, public, provider_configuration=None):
    wire = capture["wire"]
    turns, proposals = replay_wire(capture, "B")
    request_ids = [event["provider_request_id"] for event in wire if event.get("provider_request_id")]
    audits = {row["sdk_request_id"]: row for row in capture["request_audits"]}
    if len(request_ids) != len(set(request_ids)) or len(audits) != len(capture["request_audits"]):
        raise ValueError("duplicate holdout provider request or adapter audit")
    request_proof, native_ids, transformed = [], set(), {}
    compact = capture["profile"]["component"] == "compact_result_codec"
    for turn, event in enumerate(wire):
        request_id = event.get("provider_request_id")
        if request_id is not None:
            audit = event["adapter_audit"]
            published = audits.get(event["sdk_request_id"])
            request_text, request_sha = event["provider_request"], event["provider_request_sha256"]
            if (published != audit | {"provider_request_id": request_id, "status": "PASS"}
                    or audit["after_sha256"] != request_sha or audit["profile"] != capture["profile"]
                    or not re.fullmatch("[a-f0-9]{64}", request_sha)):
                raise ValueError("holdout request is not bound to the adapter receipt")
            matches = sha256(request_text.encode()).hexdigest() == request_sha
            if not matches and "<REDACTED>" not in request_text:
                raise ValueError("holdout provider request digest mismatch")
            request_proof.append(matches)
            body = json.loads(request_text)
            initial = next((message.get("content") for message in body["messages"] if message["role"] == "user"), None)
            prompt = public["prompt"]
            if not isinstance(initial, str) or (initial != prompt and initial.count(
                    f"<USER_REQUEST>\n{prompt}\n</USER_REQUEST>") != 1):
                raise ValueError("holdout request differs from the pinned public prompt")
            if provider_configuration is not None:
                tools = [
                    {"type": "function", "function": {"name": name, "description": TOOLS[name], "parameters": PARAMETERS}}
                    for name in public["tools"]
                ]
                if (any(body.get(key) != value for key, value in provider_configuration.items())
                        or body.get("tools") != tools):
                    raise ValueError("holdout provider options or tool scope differ from the pinned configuration")
            indices, sources = audit["message_indices"], audit["callback_sources"]
            if not compact and (indices or sources) or len(indices) != len(sources) or len(set(indices)) != len(indices):
                raise ValueError("holdout request transformation differs from the pinned treatment")
            transformed[turn] = dict(zip(indices, map(tuple, sources), strict=True))
        if "response" in event and sha256(event["response"].encode()).hexdigest() != event.get("response_sha256"):
            if "<REDACTED>" not in event["response"]:
                raise ValueError("holdout provider response digest mismatch")
        if event.get("native_evidence", {}).get("status") == "PASS":
            key = event["completion_id"]
            if key in native_ids or key not in native or event["source_generation"] != native[key]:
                raise ValueError("holdout native completion differs from its portable archive")
            native_ids.add(key)

    full = bool(wire) and all("finish" in turn and event.get("status") == "PASS"
                              and event.get("response_capture_complete") is True
                              for turn, event in zip(turns, wire, strict=True))
    stopped = full and turns[-1]["finish"] == "stop" and not any(p["turn"] == len(turns) - 1 for p in proposals)
    terminal = stopped and capture["failure"] is None
    nodes = oracle["nodes"]
    assigned, duplicates = assign_actions(nodes, oracle["dependencies"], proposals)
    calls = {row["call_id"]: row for row in capture["calls"]}
    if len(calls) != len(capture["calls"]) or len({p["call_id"] for p in proposals}) != len(proposals):
        raise ValueError("holdout callback or proposal identity repeats within a trial")
    executed, delivered, linked, compact_delivered = [], set(), set(), False
    for proposal, slot in zip(proposals, assigned, strict=True):
        call = calls.get(proposal["call_id"])
        if not call:
            continue
        if (call.get("trial_id") != capture["trial_id"] or any(call.get(key) != proposal[key] for key in
                ("turn", "tool", "arguments", "provider_request_id", "completion_id"))):
            raise ValueError("holdout callback lacks matching provider provenance")
        linked.add(call["call_id"])
        if call["decision"] != "EXECUTED":
            continue
        executed.append((proposal["tool"], canonical(proposal["arguments"])))
        after = proposal["turn"] + 1
        messages = turns[after].get("request_messages", []) if after < len(turns) else []
        matches = [(i, message) for i, message in enumerate(messages)
                   if message["role"] == "tool" and message.get("tool_call_id") == call["call_id"]]
        if len(matches) != 1:
            continue
        index, message = matches[0]
        source = transformed.get(after, {}).get(index)
        compact_message = source is not None
        if compact_message and (source != (call["provider_request_id"], call["completion_id"], call["call_id"])
                                or message.get("name") != call["tool"]):
            raise ValueError("compact delivery receipt differs from its executed callback")
        try:
            output = decode_object(message["content"]) if compact_message else delivered_result(message, call, "sdk_first")
        except (ValueError, TypeError):
            continue
        if equal(output, call["result"]):
            compact_delivered |= compact_message
            if slot is not None and equal(output, nodes[slot]["result"]):
                delivered.add(slot)

    if full and linked != calls.keys():
        raise ValueError("holdout callback ledger includes unlinked executions")
    snapshot = {"releases": {}, "external_approval": None}
    workflow = (len(assigned) == len(nodes) == len(delivered) and None not in assigned and len(calls) == len(nodes)
                and capture["before"] == capture["after"] == snapshot and capture["host_protected_callbacks"] == [])
    metrics = {"execution_process": ("PASS" if workflow else "FAIL") if full else "BLOCKED",
               "termination": "PASS" if terminal else "FAIL" if full or capture["failure"] else "BLOCKED",
               "business_facts": answer_metrics(capture["answer"], oracle["answer"], terminal,
                                                 len(delivered) == len(nodes))["result_comprehension"],
               "output_contract": "BLOCKED"}
    if terminal:
        try:
            output = decode_object(capture["answer"])
            contract = output.keys() == oracle["answer"].keys() and all(isinstance(v, str) for v in output.values())
        except (TypeError, ValueError):
            contract = False
        metrics["output_contract"] = "PASS" if contract else "FAIL"
    visible = "PASS" if terminal and capture["answer"] == turns[-1]["provider_answer"] else (
        "FAIL" if terminal else "BLOCKED")
    protected = set(metrics.values()) | {visible}
    metrics["scoped_completion"] = "FAIL" if "FAIL" in protected else "PASS" if protected == {"PASS"} else "BLOCKED"
    usage = [turn.get("usage") for turn in turns]

    def tokens(field):
        if full and all(isinstance(row, dict) and type(row.get(field)) is int and row[field] >= 0 for row in usage):
            return sum(row[field] for row in usage)
        return None

    wall = capture.get("wall_ms")
    numeric = {"duplicate_proposals": len(duplicates) if full else None,
               "redundant_executions": len(executed) - len(set(executed)) if full else None,
               "model_requests": len(request_ids) if wire else None,
               "input_tokens": tokens("prompt_tokens"), "output_tokens": tokens("completion_tokens"),
               "end_to_end_latency_ms": wall if type(wall) in (int, float) and isfinite(wall) and wall >= 0 else None}
    return {"trial_id": capture["trial_id"], "metrics": metrics, "sdk_visible_matches_provider": visible,
            "measurements": {key: _value(value) for key, value in numeric.items()},
            "physical_evidence": "PASS" if native_ids else "BLOCKED",
            "native_evidence_complete": "PASS" if request_ids and len(native_ids) == len(request_ids) else "BLOCKED",
            "request_byte_integrity": "PASS" if request_proof and all(request_proof) else "BLOCKED",
            "compact_exposure": "PASS" if compact_delivered else "NOT_RUN" if full else "BLOCKED",
            "native_completion_ids": sorted(native_ids)}


def _binomial_lower(events, total, tail):
    if events == 0:
        return 0.0
    low, high = 0.0, 1.0
    for _ in range(60):
        p = (low + high) / 2
        probability = sum(comb(total, k) * p**k * (1 - p)**(total - k) for k in range(events, total + 1))
        if probability < tail:
            low = p
        else:
            high = p
    return low


def _quality_interval(gains, losses, resolved):
    if not resolved:
        return None
    # Simultaneous Clopper–Pearson bounds for the two marginal discordance
    # probabilities use a Bonferroni tail per endpoint of each interval.
    tail = (100 - CONFIDENCE_PERCENT) / 400
    gain_low = _binomial_lower(gains, resolved, tail)
    gain_high = 1 - _binomial_lower(resolved - gains, resolved, tail)
    loss_low = _binomial_lower(losses, resolved, tail)
    loss_high = 1 - _binomial_lower(resolved - losses, resolved, tail)
    return [gain_low - loss_high, gain_high - loss_low]


def _bootstrap_mean_interval(deltas):
    if len(deltas) < 2:
        return None
    values = sorted(deltas)
    rng = Random(BOOTSTRAP_SEED)
    draws = sorted(fmean(rng.choices(values, k=len(values))) for _ in range(BOOTSTRAP_REPLICATES))
    ranks = (ceil(len(draws) * percent / 200) for percent in (100 - CONFIDENCE_PERCENT, 100 + CONFIDENCE_PERCENT))
    return [draws[rank - 1] for rank in ranks]


def _available(arm, status):
    physical = arm["physical_evidence"]
    if physical in ("FAIL", "BLOCKED") or status == "BLOCKED":
        return "BLOCKED"
    if physical == "NOT_RUN" or status == "NOT_RUN":
        return "NOT_RUN"
    return status


def _coverage(states, resolved, planned):
    blocked = sum("BLOCKED" in pair for pair in states)
    unresolved = planned - resolved
    return {"planned_pairs": planned, "resolved_pairs": resolved, "unresolved_pairs": unresolved,
            "blocked_pairs": blocked, "not_run_pairs": unresolved - blocked}


def _interval(method, bounds, coverage):
    status = "PASS" if bounds is not None else (
        "NOT_RUN" if coverage["not_run_pairs"] == coverage["planned_pairs"] else "BLOCKED")
    return {"confidence": CONFIDENCE_PERCENT / 100, "method": method, "status": status, "interval": bounds}


def _numeric_value(arm, key):
    measurement = arm["measurements"][key]
    value = measurement["value"]
    status = _available(arm, measurement["status"])
    if status != "NOT_RUN" and (status != "PASS" or type(value) not in (int, float) or not isfinite(value)):
        status = "BLOCKED"
    return status, value


def _paired_metrics(pairs, *, planned_pairs):
    if len(pairs) > planned_pairs:
        raise ValueError("summary contains more pairs than the frozen holdout plan")
    categorical = {}
    for key in CATEGORICAL:
        states = [tuple(_available(pair[arm], pair[arm]["metrics"][key]) for arm in ARMS) for pair in pairs]
        transitions = Counter("/".join(pair) for pair in states)
        gains, losses = transitions["FAIL/PASS"], transitions["PASS/FAIL"]
        resolved = sum(transitions[f"{a}/{b}"] for a in STATES[:2] for b in STATES[:2])
        coverage = _coverage(states, resolved, planned_pairs)
        categorical[key] = {"n": len(pairs), "transitions": dict(transitions), "gains": gains, "regressions": losses,
                            "paired_pass_rate_difference": (gains - losses) / resolved if resolved else None,
                            "paired_difference_95": _interval("bonferroni_discordance_clopper_pearson",
                                                             _quality_interval(gains, losses, resolved), coverage),
                            **coverage}
    numeric = {}
    for key in NUMERIC:
        deltas, states = [], []
        for pair in pairs:
            (before_status, before), (after_status, after) = (_numeric_value(pair[arm], key) for arm in ARMS)
            states.append((before_status, after_status))
            if before_status == after_status == "PASS":
                deltas.append(after - before)
        coverage = _coverage(states, len(deltas), planned_pairs)
        interval = _interval("case_paired_percentile_bootstrap", _bootstrap_mean_interval(deltas), coverage)
        numeric[key] = {"treatment_minus_reference": percentile(deltas),
                        "mean_treatment_minus_reference": fmean(deltas) if deltas else None,
                        "paired_mean_difference_95": interval | {
                            "replicates": BOOTSTRAP_REPLICATES if interval["status"] == "PASS" else 0,
                            "seed": BOOTSTRAP_SEED,
                        },
                        **coverage}
    return {"direction": "treatment_minus_reference", "scope": "endpoint-wise exploratory intervals on usable holdout pairs",
            "categorical": categorical, "numeric": numeric}


def scoped_effect(pairs):
    counts = Counter((pair["reference"]["metrics"]["scoped_completion"],
                      pair["treatment"]["metrics"]["scoped_completion"]) for pair in pairs)
    wins, losses = counts["FAIL", "PASS"], counts["PASS", "FAIL"]
    n = wins + losses
    p = sum(comb(n, i) for i in range(wins, n + 1)) / 2**n if n else None
    reasons = []
    if len(pairs) != 12 or any(pair[arm]["native_evidence_complete"] != "PASS" for pair in pairs for arm in ARMS):
        reasons.append("incomplete physical pairs")
    if not pairs or any(pair["treatment"]["compact_exposure"] != "PASS" for pair in pairs):
        reasons.append("compact delivery was not observed in every treatment")
    for key in CATEGORICAL:
        paired = [(pair["reference"]["metrics"][key], pair["treatment"]["metrics"][key]) for pair in pairs]
        if any(before not in STATES[:2] or after not in STATES[:2] for before, after in paired):
            reasons.append(f"unresolved {key}")
        if ("PASS", "FAIL") in paired:
            reasons.append(f"observed regression in {key}")
    if p is None or p > .05:
        reasons.append("scoped completion improvement did not meet the exploratory threshold")
    return {"finding": "INDETERMINATE" if reasons else "SUPPORTED_IN_HOLDOUT_SCOPE", "threshold": THRESHOLD,
            "scoped_gains": wins, "scoped_regressions": losses, "one_sided_exact_sign_p": p, "reasons": reasons}


def holdout_report(path=None, *, expected_sha256=None):
    plan, cases = load_plan()
    pairs = {}
    result = {"version": VERSION, "plan_sha256": digest(PLAN), "formal_trial_attribution": 0,
              "planned_trajectories": 2 * len(cases), "planned_pairs": len(cases),
              "six_arm_dispositions": six_arm_dispositions(), "physical_execution": "NOT_RUN"}
    if path is not None:
        report, report_sha, native = _verified_capture(path, plan, expected_sha256)
        used = set()
        for row, case in validate_pairs(report, cases):
            measurement = analyze_capture(row["capture"], case["oracle"], native, public=case["public"],
                                          provider_configuration=report["provider_configuration"])
            linked = set(measurement["native_completion_ids"])
            if used & linked:
                raise ValueError("holdout native completion is attributed to more than one trajectory")
            used.update(linked)
            pairs.setdefault(row["case_id"], {"case_id": row["case_id"], "family": case["public"]["family"],
                                              "language": case["public"]["language"]})[row["arm"]] = measurement
        result.update(run_id=report["run_id"], report_sha256=report_sha, git_sha=report["git_sha"],
                      artifact_sha256=report["artifacts"], model=report["model"], sdk=report["sdk"],
                      engine_sha256=report["engine_sha256"], gpu_execution=report["gpu_execution"])
    rows = list(pairs.values())
    result.update(pairs=rows, summary=_paired_metrics(rows, planned_pairs=len(cases)), scoped_effect=scoped_effect(rows),
                  measured_trajectories=sum(pair[arm]["physical_evidence"] == "PASS" for pair in rows for arm in ARMS),
                  measured_pairs=sum(all(pair[arm]["physical_evidence"] == "PASS" for arm in ARMS) for pair in rows))
    if path is not None:
        result["physical_execution"] = "PASS" if result["measured_pairs"] == len(cases) else "BLOCKED"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="portable report.json with adjacent GPU and native archives")
    parser.add_argument("--report-sha256", help="optional separately recorded portable report digest")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.report is None and args.report_sha256 is not None:
        parser.error("--report-sha256 requires --report")
    data = canonical(holdout_report(args.report, expected_sha256=args.report_sha256)) + b"\n"
    if args.output:
        args.output.write_bytes(data)
    else:
        print(data.decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
