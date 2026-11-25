"""Execute public-input MULTITOOL-V1 witnesses and independently read SQLite state."""

from argparse import ArgumentParser
from collections import Counter
from contextlib import closing
from dataclasses import replace
import gzip
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from benchmarks.atlas_validity.multitool_witness import solve
from benchmarks.multitool_v1.dataset import load_freeze
from benchmarks.multitool_v1.runtime import Scenario, score
from benchmarks.tool_calling_v2.evaluator import Call
from benchmarks.tool_calling_v2.oracle import decode_object, equal
from business_tools import encode_state

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "evidence/IJ072/benchmark_validity/multitool-witness.json.gz"
DRAFT_CONTROLS = ROOT / "evidence/IJ072/benchmark_validity/multitool-observed-draft-controls.json.gz"


def draft_controls(case, database, calls):
    draft = next((call for call in calls if call.name == "create_hold_draft"), None)
    if draft is None:
        return {"status": "NOT_APPLICABLE"}
    reference = decode_object(draft.arguments_raw)["record_id"]
    legacy = Scenario(case, database.with_name(database.stem + "-legacy-early.sqlite"))
    legacy_early = legacy.call("early", draft.name, draft.arguments_raw, turn=0)
    guarded = Scenario(case, database.with_name(database.stem + "-observed-review.sqlite"),
                       require_observed_draft=True)
    early = guarded.call("early", draft.name, draft.arguments_raw, turn=0)
    permission = guarded.call("review", "read_review", encode_state({"record_id": reference}), turn=1)
    same_turn = guarded.call("same-turn", draft.name, draft.arguments_raw, turn=1)
    unchanged = not guarded.snapshot()["review_drafts"]
    allowed = guarded.call("prior-turn", draft.name, draft.arguments_raw, turn=2)
    saved = guarded.snapshot()["review_drafts"]
    guarded.call("duplicate", draft.name, draft.arguments_raw, turn=3)
    unchanged_after_repeat = guarded.snapshot()["review_drafts"] == saved
    if (legacy_early.get("status") != "drafted" or early != {"error": "POLICY_DENIED"} or
            permission.get("draft_permission") is not True or same_turn != {"error": "POLICY_DENIED"}
            or not unchanged or allowed != draft.result or set(saved) != {reference} or not unchanged_after_repeat):
        raise ValueError("guarded draft control did not match the expected authorization lifecycle")
    return {"status": "PASS", "legacy_early_status": "FAIL", "new_early": early["error"],
            "new_same_turn": same_turn["error"], "verified_draft": allowed["status"],
            "state_unchanged_on_denial_and_repeat": True}


def execute_case(case, database, *, observed_draft=False):
    scenario = Scenario(case, database, require_observed_draft=observed_draft)
    before = scenario.snapshot()
    calls, events = [], []

    def execute(tool, args):
        turn = len(calls)
        call_id = f"witness-{turn + 1}"
        raw = encode_state(args)
        observed = scenario.call(call_id, tool, raw, turn=turn)
        calls.append(Call(turn, call_id, tool, raw, observed))
        return observed

    def take_messages():
        observed = scenario.take_events()
        events.extend((len(calls) - 1, key) for key, _ in observed)
        return [message for _, message in observed]

    final = solve(case.model_input(), execute, take_messages)
    after = scenario.snapshot()
    storage = "NOT_APPLICABLE"
    if before is not None:
        expected = {}
        if final.get("status") == "drafted":
            ref = final["draft_ref"]
            expected[ref] = {"review_ref": ref, "submitted": False, "reason": "route_review"}
            final = {"status": "drafted", "review_ref": ref}
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
            drafts = {key: decode_object(value) for key, value in db.execute("SELECT id, body FROM review_drafts")}
        storage = "PASS" if equal(drafts, expected) else "FAIL"
    facts = encode_state(final)
    observations = {"before": before, "after": after, "delivered_events": events}
    result = score(case, calls, facts, **observations)
    mutations = {
        "missing_first_action": score(case, calls[1:], facts, **observations)["status"],
        "invalid_first_argument": score(case, [replace(calls[0], arguments_raw="{}"), *calls[1:]],
                                        facts, **observations)["status"],
        "wrong_final_facts": score(case, calls, "{}", **observations)["status"],
    }
    if events:
        mutations["missing_user_update"] = score(case, calls, facts, before=before, after=after)["status"]
    if set(mutations.values()) != {"FAIL"}:
        raise ValueError("MULTITOOL scoring accepted a critical mutation")
    row = {"case_id": case.case_id, "status": result["status"], "sqlite_review_drafts": storage,
           "final": final, "events": events, "mutations": mutations,
           "calls": [{"tool": call.name, "arguments": call.arguments_raw, "observation": encode_state(call.result)}
                     for call in calls],
           "finding_codes": [finding["code"] for finding in result["findings"]]}
    if observed_draft:
        row["draft_guard"] = draft_controls(case, database, calls)
    return row


def execute(*, observed_draft=False):
    frozen = load_freeze()
    with TemporaryDirectory() as folder:
        rows = []
        for case in frozen.active.values():
            try:
                rows.append(execute_case(case, Path(folder).resolve() / (case.case_id + ".sqlite"),
                                         observed_draft=observed_draft))
            except (KeyError, ValueError) as error:
                raise ValueError(f"{case.case_id}: {error}") from error
    if observed_draft:
        return {"scope": "MULTITOOL-V1 active frozen roster with the explicit prior-turn draft guard",
                "evidence_class": "deterministic_software_control", "freeze_sha256": frozen.manifest["freeze_sha256"],
                "counts": dict(Counter(row["status"] for row in rows)),
                "guard_counts": dict(Counter(row["draft_guard"]["status"] for row in rows)),
                "trials": [{key: row[key] for key in ("case_id", "status", "sqlite_review_drafts", "draft_guard")}
                           for row in rows]}
    return {"scope": "MULTITOOL-V1 active frozen roster", "evidence_class": "deterministic_software_control",
            "freeze_sha256": frozen.manifest["freeze_sha256"], "counts": dict(Counter(row["status"] for row in rows)),
            "persisted_counts": dict(Counter(row["sqlite_review_drafts"] for row in rows)), "trials": rows}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--observed-draft-controls", action="store_true")
    args = parser.parse_args()
    result = execute(observed_draft=args.observed_draft_controls)
    output = DRAFT_CONTROLS if args.observed_draft_controls else OUTPUT
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.check:
        if gzip.decompress(output.read_bytes()) != raw:
            parser.error("MULTITOOL witness evidence differs")
    else:
        with output.open("xb") as stream:
            stream.write(gzip.compress(raw, mtime=0))
    print(result["counts"], result.get("guard_counts", result.get("persisted_counts")))


if __name__ == "__main__":
    main()
