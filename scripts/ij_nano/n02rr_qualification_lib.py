#!/usr/bin/env python3
"""N02RR replay integration qualification battery (mission IJ-NANO-1.2R
section 4).

End-to-end control suite:

    raw API artifact -> artifact loader -> stage reconstruction ->
    parser -> evaluator -> trial record -> analyzer aggregate

Controls include the audited dictionary-unpacking mutant. Positive controls
are REQUIRED to reach the parser as actual response dictionaries. The
battery is executed twice:

  - RED   (mutant loader active): positive controls must come back
          PARSE_INVALID / the gate must REJECT the mutant;
  - GREEN (corrected loader):     all controls must pass.

Only when red-to-green evidence exists may N02R_OFFLINE_REPLAY_INTEGRITY_GO
be granted (granted by n02rr_qualification.py which persists the evidence).
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]
                       / "scripts" / "ij_nano"))
import n02rr_replay_lib as rl  # noqa: E402

rl.bootstrap_paths()

from n02r import arms_v2 as arms             # noqa: E402
from n02r import scorer                       # noqa: E402
from n02r.controller_v2 import ControllerV2   # noqa: E402


def default_weights_root() -> str:
    """IJSDK sibling worktree (read-only weights host); overridable via
    the IJNANO_WEIGHTS_ROOT environment variable."""
    import os
    return os.environ.get("IJNANO_WEIGHTS_ROOT",
                          str(rl.ROOT.parent / "IJSDK"))


def make_controller() -> ControllerV2:
    cargs = type("A", (), {"weights_root": default_weights_root(),
                           "models": "S1,S2,S3",
                           "backend": "vulkan", "port": 8096,
                           "phase": "main"})()
    return ControllerV2(cargs)


def chat_response(content=None, tool_calls=None, usage=None, finish="stop"):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    body = {"choices": [{"index": 0, "finish_reason": finish,
                         "message": msg}], "object": "chat.completion"}
    if usage is not None:
        body["usage"] = usage
    return body


def completion_response(content, usage=None, stop_type="eos"):
    body = {"content": content, "stop_type": stop_type}
    if usage is not None:
        body["usage"] = usage
    return body


def tool_call(name, arguments: str):
    return {"id": "call_1", "type": "function",
            "function": {"name": name, "arguments": arguments}}


USAGE = {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110,
         "prompt_tokens_details": {"cached_tokens": 4}}


class ControlBattery:
    """Builds synthetic artifacts + trial rows; runs them through either the
    corrected engine (green) or the audited mutant path (red)."""

    def __init__(self, controller: ControllerV2, tmpdir: pathlib.Path):
        self.c = controller
        self.engine = rl.ReplayEngine(controller)
        self.tmp = tmpdir
        self.art_dir = tmpdir / "artifacts"
        self.art_dir.mkdir(parents=True, exist_ok=True)
        self.tasks = {t["task_id"]: t for t in controller.suite}
        self._n = 0

    # -- artifact construction ------------------------------------------------

    def write_artifact(self, stages, artifact_trial_id: str | None = None,
                       raw_bytes: bytes | None = None) -> dict:
        """Writes one artifact and returns the synthetic trial ROW pointing
        at it (sha over the final on-disk bytes)."""
        self._n += 1
        tid = artifact_trial_id or f"qual{self._n:04d}"
        p = self.art_dir / f"{tid}.json"
        if raw_bytes is not None:
            p.write_bytes(raw_bytes)
        else:
            p.write_text(json.dumps({"trial_id": tid, "stages": stages},
                                    indent=1, ensure_ascii=False),
                         encoding="utf-8")
        row = {"trial_id": tid, "experiment_id": "qual",
               "model": "S1", "arm": "M-P1", "task_id": "TS01",
               "family": "tool_selection", "lang": "en", "budget": 1024,
               "response_artifact": str(p.relative_to(rl.ROOT)),
               "response_artifact_sha256":
                   hashlib.sha256(p.read_bytes()).hexdigest()}
        return row

    def stage(self, http=None, http_error=None, path="/v1/chat/completions",
              stage_no=1, latency=0.123):
        return {"stage": stage_no, "path": path, "http": http,
                "http_error": http_error, "latency_s": latency}

    # -- the audited mutant path (red) ------------------------------------------

    def mutant_replay(self, row: dict) -> dict:
        """Audited n02r_rescore.py@26445d6 semantics via the canonical
        mutant (rl.mutant_unpack_last_stage). Returns the verdict the
        defective path would seal."""
        art = json.loads((rl.ROOT / row["response_artifact"])
                         .read_text(encoding="utf-8"))
        m = rl.mutant_unpack_last_stage(art)
        task = self.tasks[row["task_id"]]
        try:
            parsed = arms.parse_response(
                {"T2": "M-P1", "P7S": "M-P3"}.get(row["arm"], row["arm"]),
                task, m["http_json"], m["http_error"])
            scored = scorer.score(task, parsed.get("payload"))
        except Exception as e:
            parsed = {"structural_ok": False,
                      "warnings": [f"rescore parse error: {e!r}"],
                      "payload": None, "normalizations": []}
            scored = {"semantic_correct": False, "reasons": ["PARSE_INVALID"],
                      "tool_correct": False, "args_correct": False}
        return {"semantic_correct": scored["semantic_correct"],
                "structural_ok": parsed["structural_ok"],
                "reasons": scored["reasons"],
                "parser_received_none": (parsed.get("payload") is None
                                         and m["http_json"] is None)}

    # -- controls ---------------------------------------------------------------

    def controls(self) -> list[dict]:
        C: list[dict] = []

        def add(name, row, task_id, arm, expect):
            t = self.tasks[task_id]
            row.update({"task_id": task_id, "arm": arm,
                        "family": t["family"], "lang": t["lang"]})
            C.append({"name": name, "row": row, "expect": expect})

        # task facts (from the frozen suite tables)
        ts1_tool = "orders.get_refund_eligibility"      # TS01 expected tool
        sx1_val = "ORD-1042"                            # SX01 entity slot
        sa1 = {"tool": "refunds.submit", "order_id": "ORD-1042",
               "amount": {"value": 120.0, "unit": "CNY"},
               "reason": "damaged_item"}                 # SA01 expected action

        # 1. correct chat JSON (M-P1)
        add("correct_chat_json",
            self.write_artifact([self.stage(http=chat_response(
                content=json.dumps({"tool": ts1_tool}), usage=USAGE))]),
            "TS01", "M-P1",
            {"semantic": True, "structural": True, "failure": "SUCCESS",
             "parser_input_is_dict": True})

        # 2. correct completion JSON (M-P3)
        add("correct_completion_json",
            self.write_artifact([self.stage(
                http=completion_response(
                    content=json.dumps({"value": sx1_val}), usage=USAGE),
                path="/completion")]),
            "SX01", "M-P3",
            {"semantic": True, "structural": True, "failure": "SUCCESS",
             "parser_input_is_dict": True})

        # 3. correct native tool call (P5A)
        add("correct_native_tool_call",
            self.write_artifact([self.stage(http=chat_response(
                content=None, tool_calls=[tool_call(
                    ts1_tool, json.dumps({"order_id": "ORD-1042"}))],
                usage=USAGE))]),
            "TS01", "P5A",
            {"semantic": True, "structural": True, "failure": "SUCCESS",
             "parser_input_is_dict": True})

        # 4. valid DSL (M-P6)
        add("valid_dsl",
            self.write_artifact([self.stage(
                http=completion_response(
                    content="TOOL refunds.submit order_id=ORD-1042 "
                            "amount=120@CNY reason=damaged_item"),
                path="/completion")]),
            "SA01", "M-P6",
            {"semantic": True, "structural": True, "failure": "SUCCESS",
             "parser_input_is_dict": True})

        # 5. correct two-stage action (P7S): stage-1 selects #4
        #    (refunds.submit), stage-2 fills that selection correctly
        add("correct_two_stage_action",
            self.write_artifact([
                self.stage(http=chat_response(content="4", usage=USAGE)),
                self.stage(http=completion_response(
                    content=json.dumps(sa1), usage=USAGE), path="/completion",
                    stage_no=2)]),
            "SA01", "P7S",
            {"semantic": True, "structural": True, "failure": "SUCCESS",
             "p7s_stage1_selected_tool": "refunds.submit",
             "p7s_payload_matches_selection": True,
             "parser_input_is_dict": True,
             "total_latency": 0.246,
             "total_prompt_tokens": 200})

        # 6. incorrect first-stage selection (P7S): stage-1 selects #2
        #    (cancel); stage-2 causally fills the SELECTED tool; the trial
        #    must fail semantically (wrong tool executed)
        add("incorrect_first_stage_selection",
            self.write_artifact([
                self.stage(http=chat_response(content="2", usage=USAGE)),
                self.stage(http=completion_response(
                    content=json.dumps({"tool": "orders.cancel_order",
                                        "order_id": "ORD-1042"}),
                    usage=USAGE), path="/completion", stage_no=2)]),
            "SA01", "P7S",
            {"semantic": False, "structural": True,
             "failure": "SEMANTIC_ERROR",
             "p7s_stage1_selected_tool": "orders.cancel_order",
             "p7s_stage1_selection_wrong_tool": True,
             "p7s_payload_matches_selection": True})

        # 6b. hidden-wrong-selection attempt: stage-1 selects the WRONG tool
        #     but stage-2 carries the expected action (causally impossible);
        #     a correct-looking final response must NOT hide this
        add("wrong_selection_hidden_by_final_response",
            self.write_artifact([
                self.stage(http=chat_response(content="2", usage=USAGE)),
                self.stage(http=completion_response(
                    content=json.dumps(sa1), usage=USAGE), path="/completion",
                    stage_no=2)]),
            "SA01", "P7S",
            {"failure": "EVIDENCE_INCONSISTENT_STAGE2_TOOL",
             "p7s_stage1_selected_tool": "orders.cancel_order",
             "p7s_stage1_selection_wrong_tool": True,
             "p7s_payload_matches_selection": False})

        # 7. empty final content (model emitted nothing and stopped)
        add("empty_final_content",
            self.write_artifact([self.stage(
                http=chat_response(content="", usage=USAGE))]),
            "TS01", "M-P1",
            {"semantic": False, "structural": False,
             "failure": "EMPTY_FINAL_CONTENT_STOPPED"})

        # 8. actual HTTP error
        add("actual_http_error",
            self.write_artifact([self.stage(
                http=None, http_error="HTTP 500: synthetic server error")]),
            "TS01", "M-P1",
            {"semantic": False, "structural": False,
             "failure": "TRANSPORT_ERROR"})

        # 9. missing response (artifact file does not exist)
        row9 = self.write_artifact([self.stage()])
        row9["response_artifact"] = "evidence/IJNANO/N02RR/does_not_exist.json"
        add("missing_response", row9, "TS01", "M-P1",
            {"integrity": rl.ArtifactIntegrityError.REJECT_UNPARSEABLE})

        # 10. malformed artifact (invalid JSON bytes; sha recorded over the
        #     malformed bytes so the hash gate passes and the parse gate fires)
        self._n += 1
        add("malformed_artifact",
            self.write_artifact(None, artifact_trial_id="qual_malformed",
                                raw_bytes=b"{not valid json"),
            "TS01", "M-P1",
            {"integrity": rl.ArtifactIntegrityError.REJECT_UNPARSEABLE})

        # 11. duplicate JSON key in model output
        add("duplicate_json_key",
            self.write_artifact([self.stage(http=chat_response(
                content='{"tool": "%s", "tool": "orders.cancel_order"}'
                        % ts1_tool, usage=USAGE))]),
            "TS01", "M-P1",
            {"semantic": False, "structural": False,
             "failure": "STRUCTURAL_GENERATION_ERROR_DUP_KEY"})

        # 12. unexpected tool argument (field outside the supplied contract;
        #     the undeclared-argument contract is evaluated on
        #     structured_action, tool_selection isolates selection only)
        add("unexpected_tool_argument",
            self.write_artifact([self.stage(http=chat_response(
                content=json.dumps({**sa1, "priority": "urgent"}),
                usage=USAGE))]),
            "SA01", "M-P1",
            {"semantic": False, "structural": True,
             "failure": "SEMANTIC_ERROR",
             "reasons_contains": "ARGUMENT_UNDECLARED"})

        # 13. invalid stage order (numbers not 1..n)
        add("invalid_stage_order",
            self.write_artifact([self.stage(
                http=chat_response(content="{}"), stage_no=2),
                self.stage(http=chat_response(content="{}"), stage_no=3)]),
            "TS01", "M-P1",
            {"integrity": rl.ArtifactIntegrityError.REJECT_STAGE_ORDER})

        # 14. hash mismatch (recorded sha256 wrong)
        row14 = self.write_artifact([self.stage(http=chat_response(
            content=json.dumps({"tool": ts1_tool})))])
        row14["response_artifact_sha256"] = "0" * 64
        add("hash_mismatch", row14, "TS01", "M-P1",
            {"integrity": rl.ArtifactIntegrityError.REJECT_HASH})

        # 15. wrong trial identity (artifact trial_id != row trial_id)
        row15 = self.write_artifact([self.stage(http=chat_response(
            content=json.dumps({"tool": ts1_tool})))],
            artifact_trial_id="qual_artifact_15")
        row15["trial_id"] = "qual_row_15"
        add("wrong_trial_identity", row15, "TS01", "M-P1",
            {"integrity": rl.ArtifactIntegrityError.REJECT_TRIAL_IDENTITY})

        # 16. missing telemetry (no usage field anywhere)
        add("missing_telemetry",
            self.write_artifact([self.stage(http=chat_response(
                content=json.dumps({"tool": ts1_tool})), latency=0.5)]),
            "TS01", "M-P1",
            {"semantic": True, "structural": True, "failure": "SUCCESS",
             "usage_marker": "NOT_CAPTURED", "usage_is_not_zero": True})

        # 17. valid response stored in a dictionary (regression for the
        #     defect class: dict-stored responses MUST reach the parser as
        #     actual dictionaries)
        add("valid_response_stored_in_dictionary",
            self.write_artifact([self.stage(http={
                "choices": [{"finish_reason": "stop", "message": {
                    "role": "assistant",
                    "content": json.dumps({"branch": "auto_approve"})}}],
                "usage": USAGE})]),
            "CB01", "M-P1",
            {"semantic": True, "structural": True, "failure": "SUCCESS",
             "parser_input_is_dict": True,
             "telemetry_prompt_tokens": 100})

        # 18. non-object body in the http field (schema violation must be
        #     rejected, never silently parsed)
        add("http_field_not_object",
            self.write_artifact([self.stage(http="http")]),
            "TS01", "M-P1",
            {"integrity": rl.ArtifactIntegrityError.REJECT_STAGE_SCHEMA})

        return C

    # -- execution ---------------------------------------------------------------

    def run_green(self) -> list[dict]:
        results = []
        for ctl in self.controls():
            name, row, expect = ctl["name"], ctl["row"], ctl["expect"]
            fail = None
            try:
                rec = self.engine.replay(row)
                fail = rl.classify_failure(rec)
                checks: dict = {}
                if "integrity" in expect:
                    ok, detail = False, \
                        "loader accepted an artifact it must reject"
                    checks["unexpected_success"] = True
                else:
                    ok, detail = True, ""

                    def chk(key, cond):
                        nonlocal ok
                        ok = ok and bool(cond)
                        checks[key] = bool(cond)

                    if "semantic" in expect:
                        chk("semantic", rec["semantic_correct"]
                            == expect["semantic"])
                    if "structural" in expect:
                        chk("structural", rec["parser"]["structural_ok"]
                            == expect["structural"])
                    if "failure" in expect:
                        chk("failure_class", fail == expect["failure"])
                    if expect.get("parser_input_is_dict"):
                        chk("parser_input_is_dict",
                            rec["replay_checks"].get("final_http_is_dict")
                            is True
                            and rec["parser"]["payload"] is not None)
                    p7 = rec.get("p7s_reconstruction") or {}
                    if "p7s_stage1_selected_tool" in expect:
                        chk("p7s_selected_tool",
                            p7.get("stage1_selected_tool")
                            == expect["p7s_stage1_selected_tool"])
                    if "p7s_stage1_selection_wrong_tool" in expect:
                        chk("p7s_wrong_tool_flag",
                            rec["stage1_selection_wrong_tool"]
                            == expect["p7s_stage1_selection_wrong_tool"])
                    if "p7s_payload_matches_selection" in expect:
                        chk("p7s_payload_matches_selection",
                            p7.get("stage2_payload_matches_selection")
                            == expect["p7s_payload_matches_selection"])
                    if "total_latency" in expect:
                        chk("total_latency",
                            abs(rec["telemetry_totals"]["total_latency_s"]
                                - expect["total_latency"]) < 1e-9)
                    if "total_prompt_tokens" in expect:
                        chk("total_prompt_tokens",
                            rec["telemetry_totals"]["total_prompt_tokens"]
                            == expect["total_prompt_tokens"])
                    if "reasons_contains" in expect:
                        chk("reasons_contains",
                            expect["reasons_contains"] in rec["reasons"])
                    if "usage_marker" in expect:
                        chk("usage_marker",
                            rec["telemetry"].get("usage")
                            == expect["usage_marker"])
                    if expect.get("usage_is_not_zero"):
                        chk("usage_not_zero",
                            rec["telemetry"].get("usage") != 0)
                    if "telemetry_prompt_tokens" in expect:
                        chk("telemetry_tokens",
                            (rec["telemetry"].get("usage") or {}).get(
                                "prompt_tokens")
                            == expect["telemetry_prompt_tokens"])
                results.append({"control": name, "passed": ok,
                                "checks": checks, "failure_class": fail,
                                "detail": detail})
            except rl.ArtifactIntegrityError as e:
                ok = ("integrity" in expect
                      and e.code == expect["integrity"])
                # sanitize: never leak absolute local paths into evidence
                detail = e.detail
                if "artifact unreadable" in detail:
                    detail = "artifact unreadable: <path omitted>"
                results.append({"control": name, "passed": ok,
                                "checks": {"integrity_code": e.code},
                                "failure_class": None, "detail": detail})
        return results

    def run_red(self) -> dict:
        """Run the positive controls through the AUDITED mutant path. The
        gate must REJECT the mutant: every positive control that expects a
        valid response must come back PARSE_INVALID with the parser having
        received None."""
        mutant_detected = []
        for ctl in self.controls():
            expect = ctl["expect"]
            if "integrity" in expect or not expect.get("semantic"):
                continue      # negatives say nothing about the mutant
            m = self.mutant_replay(ctl["row"])
            diverged = (m["semantic_correct"] is False
                        and m["reasons"] == ["PARSE_INVALID"]
                        and m["parser_received_none"])
            mutant_detected.append({"control": ctl["name"],
                                    "mutant_verdict": m["reasons"],
                                    "expected_semantic":
                                        expect["semantic"],
                                    "mutant_diverges": diverged})
        all_diverge = bool(mutant_detected) and all(
            c["mutant_diverges"] for c in mutant_detected)
        return {"controls": mutant_detected,
                "mutant_rejected": all_diverge,
                "n_positive_controls": len(mutant_detected)}


def analyzer_integration(battery: ControlBattery) -> dict:
    """Trial record -> analyzer layer: aggregate over the corrected replay
    records of the success-path controls with explicit sample counts."""
    rows = []
    for ctl in battery.controls():
        if "integrity" in ctl["expect"]:
            continue
        try:
            rows.append(battery.engine.replay(ctl["row"]))
        except rl.ArtifactIntegrityError:
            continue
    n = len(rows)
    sem = sum(1 for r in rows if r["semantic_correct"])
    empty = sum(1 for r in rows
                if (rl.classify_failure(r) or "").startswith("EMPTY_FINAL_CONTENT"))
    lats = [r["telemetry"]["latency_s"] for r in rows
            if isinstance(r["telemetry"].get("latency_s"), (int, float))]
    pts = [r["telemetry_totals"]["total_prompt_tokens"] for r in rows
           if isinstance(r["telemetry_totals"]["total_prompt_tokens"], int)]
    return {"n_records": n, "semantic_pass": sem,
            "semantic_rate_denominator": n, "empty_final_content": empty,
            "mean_latency_s": round(sum(lats) / len(lats), 4) if lats else None,
            "latency_sample_n": len(lats),
            "mean_prompt_tokens": round(sum(pts) / len(pts), 1) if pts else None,
            "prompt_token_sample_n": len(pts)}
