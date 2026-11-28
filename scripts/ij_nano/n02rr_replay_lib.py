#!/usr/bin/env python3
"""N02RR corrected artifact loader + replay engine (mission IJ-NANO-1.2R).

Root cause being repaired (RS01): the audited offline-rescore path
(``scripts/ij_nano/n02r_rescore.py`` @ 26445d6, line 71) unpacked the
PERSISTED stage dictionary as a tuple::

    stage, path, http_json, http_error, latency = art["stages"][-1]

Iterating a dict yields its KEYS, so ``http_json`` became the string
``"http"``, the ``isinstance(http_json, dict)`` guard then substituted
``None``, and the parser scored every replayed trial as PARSE_INVALID with
corrupted telemetry. The physical controller path was unaffected because it
unpacks in-memory TUPLES (controller_v2._run_trial).

This module never unpacks persisted stages positionally:

- stage fields are read explicitly by key;
- the artifact schema is validated BEFORE any replay;
- integrity problems raise :class:`ArtifactIntegrityError` (separately
  classified EVIDENCE_INTEGRITY failures) and are NEVER converted into
  ordinary model failures;
- P7S two-stage trials are reconstructed causally (RS02): the stage-1
  selection is recomputed from the preserved stage-1 response, the stage-2
  payload is verified against the ACTUAL selection (not the expected
  tool), and latency/tokens are summed across both stages.

The module deliberately imports the sealed experiment's runtime modules
(controller_v2, arms_v2, scorer) unchanged; callers must assert
``ControllerV2`` identity equality with the frozen manifest before use
(see n02rr_rescore.py).
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

STAGE_KEYS = frozenset({"stage", "path", "http", "http_error", "latency_s"})


class ArtifactIntegrityError(Exception):
    """Separately classified evidence-integrity failure (never a model
    failure). ``code`` is one of the REJECT_* codes below."""

    REJECT_UNPARSEABLE = "ARTIFACT_UNPARSEABLE"
    REJECT_NOT_OBJECT = "ARTIFACT_NOT_OBJECT"
    REJECT_TRIAL_IDENTITY = "TRIAL_IDENTITY_MISMATCH"
    REJECT_MISSING_STAGES = "MISSING_STAGES"
    REJECT_STAGE_NOT_OBJECT = "STAGE_NOT_OBJECT"
    REJECT_STAGE_SCHEMA = "STAGE_SCHEMA_INVALID"
    REJECT_STAGE_ORDER = "STAGE_ORDER_INVALID"
    REJECT_HASH = "HASH_MISMATCH"
    REJECT_INCONSISTENT = "STAGE_HTTP_INCONSISTENT"

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


# -- audited defective fragment (verbatim, for red reproduction) -------------

AUDITED_DEFECT_LINE = ("stage, path, http_json, http_error, latency = "
                       "art[\"stages\"][-1]")


def mutant_unpack_last_stage(art: dict):
    """EXACT audited semantics of n02r_rescore.py@26445d6 lines 71-89:
    positional unpacking of the persisted stage dict, followed by the
    b0d57e9 ``isinstance`` guard and exception mask. Kept verbatim as the
    canonical mutant for the red reproduction and the qualification gate;
    must NEVER be used to produce evidence."""
    stage, path, http_json, http_error, latency = art["stages"][-1]
    return {
        "stage": stage, "path": path,
        "http_json": http_json if isinstance(http_json, dict) else None,
        "http_error": http_error, "latency": latency,
        "raw_http_json": http_json,
    }


# -- validated loader ---------------------------------------------------------

def validate_stage(stage, idx: int) -> None:
    if not isinstance(stage, dict):
        raise ArtifactIntegrityError(
            ArtifactIntegrityError.REJECT_STAGE_NOT_OBJECT,
            f"stage[{idx}] is {type(stage).__name__}, not an object "
            "(positional unpacking of persisted artifacts is forbidden)")
    missing = STAGE_KEYS - set(stage)
    unknown = set(stage) - STAGE_KEYS
    if missing or unknown:
        raise ArtifactIntegrityError(
            ArtifactIntegrityError.REJECT_STAGE_SCHEMA,
            f"stage[{idx}] missing={sorted(missing)} unknown={sorted(unknown)}")
    if not isinstance(stage["stage"], int) or isinstance(stage["stage"], bool):
        raise ArtifactIntegrityError(
            ArtifactIntegrityError.REJECT_STAGE_SCHEMA,
            f"stage[{idx}].stage is {type(stage['stage']).__name__}, not int")
    if not isinstance(stage["path"], str):
        raise ArtifactIntegrityError(
            ArtifactIntegrityError.REJECT_STAGE_SCHEMA,
            f"stage[{idx}].path is {type(stage['path']).__name__}, not str")
    http, err = stage["http"], stage["http_error"]
    if http is not None and not isinstance(http, dict):
        raise ArtifactIntegrityError(
            ArtifactIntegrityError.REJECT_STAGE_SCHEMA,
            f"stage[{idx}].http is {type(http).__name__}, not object|null")
    if err is not None and not isinstance(err, str):
        raise ArtifactIntegrityError(
            ArtifactIntegrityError.REJECT_STAGE_SCHEMA,
            f"stage[{idx}].http_error is {type(err).__name__}, not string|null")
    if (http is None) == (err is None):
        raise ArtifactIntegrityError(
            ArtifactIntegrityError.REJECT_INCONSISTENT,
            f"stage[{idx}] has http={'set' if http is not None else 'null'} "
            f"and http_error={'set' if err is not None else 'null'}; exactly "
            "one must be set")
    lat = stage["latency_s"]
    if isinstance(lat, bool) or not isinstance(lat, (int, float)) or lat < 0:
        raise ArtifactIntegrityError(
            ArtifactIntegrityError.REJECT_STAGE_SCHEMA,
            f"stage[{idx}].latency_s is {lat!r}, not a non-negative number")


def load_artifact(path: pathlib.Path, expected_sha256: str | None = None,
                  expected_trial_id: str | None = None) -> dict:
    """Load and fully validate a persisted response artifact. Returns the
    parsed artifact; raises ArtifactIntegrityError on any rejection."""
    try:
        blob = path.read_bytes()
    except OSError as e:
        raise ArtifactIntegrityError(
            ArtifactIntegrityError.REJECT_UNPARSEABLE,
            f"artifact unreadable: {e}") from e
    if expected_sha256 is not None:
        actual = hashlib.sha256(blob).hexdigest()
        if actual != expected_sha256:
            raise ArtifactIntegrityError(
                ArtifactIntegrityError.REJECT_HASH,
                f"{path.name}: sha256 {actual[:12]}... != recorded "
                f"{expected_sha256[:12]}...")
    try:
        art = json.loads(blob.decode("utf-8"))
    except Exception as e:
        raise ArtifactIntegrityError(
            ArtifactIntegrityError.REJECT_UNPARSEABLE,
            f"{path.name}: {e}") from e
    if not isinstance(art, dict):
        raise ArtifactIntegrityError(
            ArtifactIntegrityError.REJECT_NOT_OBJECT,
            f"top level is {type(art).__name__}")
    tid = art.get("trial_id")
    if not isinstance(tid, str) or not tid:
        raise ArtifactIntegrityError(
            ArtifactIntegrityError.REJECT_TRIAL_IDENTITY,
            f"trial_id missing or {type(tid).__name__}")
    if expected_trial_id is not None and tid != expected_trial_id:
        raise ArtifactIntegrityError(
            ArtifactIntegrityError.REJECT_TRIAL_IDENTITY,
            f"artifact trial_id {tid} != expected {expected_trial_id}")
    stages = art.get("stages")
    if not isinstance(stages, list) or not stages:
        raise ArtifactIntegrityError(
            ArtifactIntegrityError.REJECT_MISSING_STAGES,
            f"stages is {type(stages).__name__} or empty")
    for i, st in enumerate(stages):
        validate_stage(st, i)
        if st["stage"] != i + 1:
            raise ArtifactIntegrityError(
                ArtifactIntegrityError.REJECT_STAGE_ORDER,
                f"stage[{i}].stage == {st['stage']}, expected {i + 1}")
    return art


def stage_of(art: dict, idx: int = -1) -> dict:
    """Explicit key-based read of a validated stage (never positional)."""
    st = art["stages"][idx]
    return {"stage": st["stage"], "path": st["path"], "http": st["http"],
            "http_error": st["http_error"], "latency_s": st["latency_s"]}


# -- replay engine --------------------------------------------------------------

class ReplayEngine:
    """Replays trial records from validated artifacts using the sealed
    experiment's own runtime modules (identity must be asserted equal by
    the caller before construction)."""

    def __init__(self, controller):
        self.c = controller
        from n02r import arms_v2 as arms, scorer  # sealed modules
        self.arms, self.scorer = arms, scorer

    # task lookup keyed once
    def task_for(self, task_id: str) -> dict:
        return next(t for t in self.c.suite if t["task_id"] == task_id)

    def _stage1_selected_tool(self, stage1_http: dict | None, task: dict):
        """Exact reconstruction of controller_v2._run_trial's stage-1
        selection: first integer in the stage-1 content, 1-based over the
        world tool inventory."""
        content = ((stage1_http or {}).get("content")
                   or ((stage1_http or {}).get("choices")
                       and stage1_http["choices"][0]
                       .get("message", {}).get("content"))
                   or "")
        m = re.search(r"\d+", content)
        tools = self.arms._world_tools(task)
        if m and 1 <= int(m.group(0)) <= len(tools):
            return tools[int(m.group(0)) - 1]
        return None

    def replay(self, row: dict, source_row: dict | None = None) -> dict:
        """Re-score one destination-experiment row from its artifact.

        Returns a dict with the corrected verdict, telemetry, provenance
        checks and failure classification. Raises ArtifactIntegrityError
        for evidence-integrity rejections (callers classify those rows
        separately; they are never model failures)."""
        c, arms, scorer = self.c, self.arms, self.scorer
        model, arm, task_id, budget = (row["model"], row["arm"],
                                       row["task_id"], row["budget"])
        art_path = ROOT / row["response_artifact"]
        expected_tid = (source_row or row)["trial_id"]
        art = load_artifact(art_path, row["response_artifact_sha256"],
                            expected_tid)
        task = self.task_for(task_id)

        stages = [stage_of(art, i) for i in range(len(art["stages"]))]
        replay_checks = {"artifact_stages": len(stages)}

        # ---- P7S two-stage causal reconstruction (RS02) ------------------
        p7s = {"applicable": arm == "P7S"}
        selected_tool = None
        if arm == "P7S":
            st1 = stages[0]
            if st1["http"] is None:
                p7s.update(stage1_transport_error=True)
            else:
                selected_tool = self._stage1_selected_tool(st1["http"], task)
                p7s.update(stage1_selected_tool=selected_tool)
            if len(stages) == 1:
                p7s["stage2_executed"] = False
                p7s["stage2_consistent_with_selection"] = (
                    selected_tool is None)   # no selection -> no stage 2
            else:
                p7s["stage2_executed"] = True
                p7s["stage2_consistent_with_selection"] = \
                    selected_tool is not None
                p7s["expected_tool_for_verification"] = task["expected"]["tool"]

        # ---- final-stage parse (physical-path semantics, key-based) ------
        final = stages[-1]
        replay_checks["final_http_is_dict"] = isinstance(final["http"], dict)
        replay_checks["final_stage_number"] = final["stage"]
        parse_arm = {"T2": "M-P1", "P7S": "M-P3"}.get(arm, arm)
        replay_error = None
        try:
            parsed = arms.parse_response(parse_arm, task, final["http"],
                                         final["http_error"])
            scored = scorer.score(task, parsed.get("payload"))
        except Exception as e:      # replay failure, NOT a model failure
            replay_error = f"{type(e).__name__}: {e}"
            parsed = {"structural_ok": False, "warnings": [], "payload": None,
                      "normalizations": []}
            scored = None

        # ---- P7S: wrong stage-1 selection must not be hidden --------------
        stage1_selection_wrong_tool = None
        if arm == "P7S" and selected_tool is not None:
            stage1_selection_wrong_tool = (
                selected_tool != task["expected"]["tool"])
            payload_tool = ((parsed.get("payload") or {}).get("tool"))
            if payload_tool is not None:
                p7s["stage2_payload_tool"] = payload_tool
                p7s["stage2_payload_matches_selection"] = (
                    payload_tool == selected_tool)

        # ---- telemetry: final stage (physical semantics) + totals ---------
        tel = c._telemetry(arm, final["http"], final["http_error"],
                           final["latency_s"])
        per_stage = []
        for st in stages:
            usage = (st["http"] or {}).get("usage") \
                if isinstance(st["http"], dict) else None
            per_stage.append({
                "stage": st["stage"], "path": st["path"],
                "latency_s": st["latency_s"],
                "prompt_tokens": (usage or {}).get("prompt_tokens"),
                "completion_tokens": (usage or {}).get("completion_tokens"),
                "cached_tokens": ((usage or {}).get("prompt_tokens_details")
                                  or {}).get("cached_tokens"),
                "http_error": st["http_error"]})
        lats = [st["latency_s"] for st in stages]
        ptoks = [s["prompt_tokens"] for s in per_stage
                 if isinstance(s["prompt_tokens"], int)]
        ctoks = [s["completion_tokens"] for s in per_stage
                 if isinstance(s["completion_tokens"], int)]
        totals = {
            "total_latency_s": round(sum(lats), 3),
            "total_prompt_tokens": sum(ptoks) if ptoks else None,
            "total_completion_tokens": sum(ctoks) if ctoks else None,
            "stage_count": len(stages),
            "per_stage": per_stage,
        }

        out = {
            "trial_id": row["trial_id"],
            "experiment_id": row["experiment_id"],
            "model": model, "arm": arm, "task_id": task_id,
            "family": row["family"], "lang": row["lang"], "budget": budget,
            "http_ok": final["http"] is not None,
            "http_error": final["http_error"],
            "telemetry": tel,
            "telemetry_totals": totals,
            "parser": {"structural_ok": bool(parsed.get("structural_ok")),
                       "warnings": parsed.get("warnings", []),
                       "normalizations": parsed.get("normalizations", []),
                       "payload": parsed.get("payload")},
            "semantic_correct": (scored["semantic_correct"]
                                 if scored else False),
            "tool_correct": scored["tool_correct"] if scored else False,
            "args_correct": scored["args_correct"] if scored else False,
            "reasons": scored["reasons"] if scored else ["REPLAY_ERROR"],
            "p7s_reconstruction": p7s if arm == "P7S" else None,
            "stage1_selection_wrong_tool": stage1_selection_wrong_tool,
            "replay_error": replay_error,
            "response_artifact": row["response_artifact"],
            "response_artifact_sha256": row["response_artifact_sha256"],
            "replay_checks": replay_checks,
        }
        return out


# -- failure classification (mission RS04-08 taxonomy) ---------------------------

def classify_failure(corrected: dict, source_row: dict | None = None) -> str:
    """One failure-class label per trial from the corrected replay.
    Verdicts are untouched; this is the honest taxonomy layer."""
    if corrected.get("replay_error"):
        return "REPLAY_ERROR"
    if corrected["http_error"] is not None:
        return "TRANSPORT_ERROR"
    if corrected["arm"] == "P7S":
        p7s = corrected.get("p7s_reconstruction") or {}
        if not p7s.get("stage2_executed", True):
            return "STAGE1_SELECTION_FAILED"
        # a correct-looking final response must NOT hide an inconsistent
        # stage-1 selection (RS02): check before the SUCCESS shortcut
        if p7s.get("stage2_payload_matches_selection") is False:
            return "EVIDENCE_INCONSISTENT_STAGE2_TOOL"
    if corrected["semantic_correct"]:
        return "SUCCESS"
    tel, par = corrected["telemetry"], corrected["parser"]
    if par["structural_ok"]:
        # structurally valid but semantically wrong: true model error
        return "SEMANTIC_ERROR"
    content = tel.get("content")
    tool_calls = tel.get("tool_calls")
    if tool_calls:
        return "TOOL_CALL_ONLY_UNPARSED"     # content empty, calls present
    if content is None or content == "":
        # empty final output, split by mechanism: budget exhausted (the
        # reasoning-burn signature) vs model emitted nothing and stopped
        if tel.get("truncated"):
            return "EMPTY_FINAL_CONTENT_TRUNCATED"
        return "EMPTY_FINAL_CONTENT_STOPPED"
    if tel.get("truncated"):
        return "GENERATION_TRUNCATED"
    if any("duplicate JSON" in w for w in par.get("warnings", [])):
        return "STRUCTURAL_GENERATION_ERROR_DUP_KEY"
    return "STRUCTURAL_GENERATION_ERROR"


def change_classification(orig_sem: bool, corr_sem: bool,
                          orig_row: dict, corrected: dict) -> str:
    """Mission section 6 change classes."""
    if corrected.get("replay_error"):
        return "EVIDENCE_INSUFFICIENT"
    verdict_changed = orig_sem != corr_sem
    if verdict_changed:
        return ("CORRECTED_FALSE_NEGATIVE" if corr_sem
                else "CORRECTED_FALSE_POSITIVE")
    # verdict identical: did we repair telemetry/structure on a valid trial?
    orig_struct = bool(orig_row.get("parser", {}).get("structural_ok"))
    corr_struct = bool(corrected["parser"]["structural_ok"])
    orig_tel = orig_row.get("telemetry", {})
    tel_defective = (orig_tel.get("usage")
                     == "NOT_CAPTURED (non-object response body)"
                     or orig_row.get("http_error") == "http_error"
                     or orig_tel.get("finish_reason") == "NOT_CAPTURED")
    if orig_struct != corr_struct or tel_defective:
        return "TELEMETRY_CORRECTED"
    return "UNCHANGED_VALID"


def bootstrap_paths():
    for p in (ROOT / "benchmarks" / "root_cause",
              ROOT / "benchmarks" / "ij_nano", ROOT / "src",
              ROOT / "scripts" / "ij_nano"):
        sp = str(p)
        if sp not in sys.path:
            sys.path.insert(0, sp)
