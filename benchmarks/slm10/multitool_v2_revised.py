"""Replay the balanced MULTITOOL-V2 candidate revised after content review."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from benchmarks.tool_calling_v2.oracle import decode_object, equal
from evaluation.aeve.archive import digest
from evaluation.aeve.runtime import canonical, fingerprint

from . import multitool_v2_balanced as balanced
from . import multitool_v2_candidate as original
from .multitool_v2_cases import Author, BUILDERS, add_chain
from .multitool_v2_witness import Reference, Scenario as ReadService, _solve, parse_message


VERSION = "MULTITOOL-V2/candidate-0.3"
FOLDER = balanced.FOLDER.with_name("multitool-v2-candidate-0.3")
BRANCH_REFS = {"conditional": "gate", "recovery": "primary", "authorization": "consent"}
TYPED_MESSAGE = {
    "en": "Read every listed caption entry in any order. Preview the exact entries in the listed order with "
          "preserve_order true and the requested format. Return JSON with preview_id.",
    "zh": "以任意顺序读取所有列出的字幕条目。按列表顺序使用原始条目、preserve_order=true 和指定格式预览。"
          "仅返回含 preview_id 的 JSON。",
    "mixed": "Read all listed captions，读取顺序不限。Preview exact entries in listed order，"
             "preserve_order=true，使用指定 format。只输出 JSON preview_id。",
}


def _conditional(author, opened):
    gate, main, bypass = (author.ref(group) for group in ("GATE", "MAIN", "BYP"))
    selected, field, opposite = ("read_open_route", "main_ref", "read_bypass_route") if opened else (
        "read_bypass_route", "bypass_ref", "read_open_route")
    root = author.add("read_maintenance_gate", {"ref": gate}, {"open": opened, "main_ref": main, "bypass_ref": bypass})
    refs = [main if opened else bypass] + [author.ref("PATH", i) for i in range(1, author.depth - 1)]
    answer = {"destination": author.ref("ROOM")}
    add_chain(author, [{"tool": selected, "ref": ref} for ref in refs], answer | {"next_ref": None}, root, field)
    author.record(opposite, {"ref": bypass if opened else main}, {"destination": "wrong-branch", "next_ref": None})
    return author.finish({"gate": gate}, answer, ("read_maintenance_gate", "read_open_route", "read_bypass_route"))


def _recovery(author, retry):
    primary, mirror = author.ref("IMAGE"), author.ref("MIRROR")
    fault = {"status": "retryable"} if retry else {"status": "unavailable", "mirror_ref": mirror}
    root = author.add("read_image_source", {"ref": primary}, fault)
    tool, ref = ("read_image_source", primary) if retry else ("read_alternate_source", mirror)
    targets = [{"tool": "read_image_metadata", "ref": author.ref("META", i)} for i in range(author.depth - 2)]
    answer = {"checksum": author.ref("CHECK")}
    result = {"next_tool": targets[0]["tool"], "next_ref": targets[0]["ref"]} if targets else answer | {"next_ref": None}
    second = author.add(tool, {"ref": ref}, result, (root,), {} if retry else {"ref": [root, "mirror_ref"]})
    add_chain(author, targets, answer | {"next_ref": None}, second)
    return author.finish({"primary": primary}, answer, ("read_image_source", "read_alternate_source", "read_image_metadata"))


def _authorization(author, permitted):
    refs = [author.ref("CONSENT", i) for i in range(author.depth - 1)]
    decision = "permitted" if permitted else "withheld"
    allowed, opposite = ("read_public_excerpt", "read_redaction_guide") if permitted else (
        "read_redaction_guide", "read_public_excerpt")
    lookup, note = author.ref("GUIDE"), author.ref("NOTE")
    parent = None
    for index, ref in enumerate(refs):
        result = {"next_ref": refs[index + 1]} if index + 1 < len(refs) else {"decision": decision, "guide_ref": lookup}
        parent = author.add("read_consent", {"ref": ref}, result, (parent,) if parent else (),
                            {"ref": [parent, "next_ref"]} if parent else {})
    author.add(allowed, {"ref": lookup}, {"note": note}, (parent,), {"ref": [parent, "guide_ref"]})
    author.record(opposite, {"ref": lookup}, {"note": "unapproved"})
    return author.finish({"consent": refs[0]}, {"decision": decision, "note": note},
                         ("read_consent", "read_public_excerpt", "read_redaction_guide"))


BRANCH_BUILDERS = {"conditional": _conditional, "recovery": _recovery, "authorization": _authorization}


def build_case(category, depth, language, variant, *, branch=None):
    author = Author(category, depth, language, variant)
    author.identity = f"MT2-C03-{category}-{depth:02}-{language}-{variant}"
    if category in BRANCH_BUILDERS:
        # Choose the world outcome separately from every model-visible reference.
        fixture_decision = int(fingerprint([VERSION, "private fixture outcome", author.identity])[0], 16) % 2 == 0
        return BRANCH_BUILDERS[category](author, fixture_decision if branch is None else branch)
    row = BUILDERS[category](author)
    if category == "typed_transfer":
        row[0]["message"] = TYPED_MESSAGE[language] + "\nDATA " + canonical(parse_message(row[0]["message"])).decode()
    return row


def branch_taken(category, oracle):
    if category == "authorization":
        return oracle["answer"]["decision"] == "permitted"
    first = oracle["actions"][0]["observation"]
    return first["open"] if category == "conditional" else first["status"] == "retryable"


def candidate():
    prior_rows, prior_repeats = balanced.candidate()
    rows = [build_case(case["category"], case["required_actions"], case["language"], int(case["case_id"].rsplit("-", 1)[-1]))
            for case, _, _ in prior_rows]
    revised_id = {prior[0]["case_id"]: new[0]["case_id"] for prior, new in zip(prior_rows, rows, strict=True)}
    return rows, [revised_id[key] for key in prior_repeats]


class Scenario(ReadService):
    """Serve venue-access records only under the delivered scope event."""

    def __init__(self, public, world):
        super().__init__(public, world)
        self.access = None

    def take_event(self, turn):
        event = super().take_event(turn)
        scope = parse_message(event["message"])
        self.access = turn, scope["venue"], frozenset(scope["refs"])
        return event

    def read(self, tool, arguments, turn, call_id):
        if tool == "read_venue_access" and tool in self.schemas and self.schemas[tool].is_valid(arguments):
            if self.access is None or turn < self.access[0] or arguments["venue"] != self.access[1] or (
                    arguments["ref"] not in self.access[2]):
                raise ValueError("venue access is outside the active scope")
        return super().read(tool, arguments, turn, call_id)


def witness(public, world):
    service = Scenario(public, world)
    reference = Reference(service)
    answer = _solve(parse_message(public["message"]), reference)
    return {"complete": True, "calls": reference.calls, "answer": answer, "events": service.delivered}


def evaluate(public, world, oracle, capture):
    verdict = original.evaluate(public, world, oracle, capture)
    if verdict["status"] != "PASS" or public["category"] != "scope_update":
        return verdict
    service = Scenario(public, world)
    try:
        for call in sorted(capture["calls"], key=lambda row: row["turn"]):
            if service.pending and service.pending["before_turn"] <= call["turn"]:
                service.take_event(service.pending["before_turn"])
            result, _ = service.read(call["tool"], decode_object(call["arguments_raw"]), call["turn"], call["call_id"])
            if not equal(result, call["observation"]):
                raise ValueError("observation differs from the scoped venue service")
        if service.delivered != capture["events"]:
            raise ValueError("scope event differs from the captured evidence")
    except (KeyError, TypeError, ValueError) as error:
        return {"status": "FAIL", "reason": str(error)}
    return verdict


def _review_regressions(rows):
    branches = {category: Counter() for category in BRANCH_REFS}
    typed, scope = Counter(), Counter()
    for row in rows:
        public, world, oracle = row
        category = public["category"]
        if category in BRANCH_REFS:
            reference = parse_message(public["message"])[BRANCH_REFS[category]]
            branches[category][f"{int(reference[-1], 16) % 2}/{str(branch_taken(category, oracle)).lower()}"] += 1
        elif category == "typed_transfer" and public["required_actions"] > 2:
            alternative = witness(public, world)
            reads = list(reversed(alternative["calls"][:-1]))
            alternative["calls"] = reads + alternative["calls"][-1:]
            for turn, call in enumerate(alternative["calls"]):
                call.update(turn=turn, completion_id=f"alternative-{turn}")
            typed[evaluate(*row, alternative)["status"]] += 1
            args = decode_object(alternative["calls"][-1]["arguments_raw"])
            args["preview"]["entries"].reverse()
            alternative["calls"][-1]["arguments_raw"] = canonical(args).decode()
            typed["wrong_preview_rejected"] += evaluate(*row, alternative)["status"] == "FAIL"
        elif category == "scope_update":
            service = Scenario(public, world)
            booking = parse_message(public["message"])["booking"]
            previous, _ = service.read("read_booking", {"ref": booking}, 0, "booking")
            update = parse_message(world["event"]["message"])
            old = {"venue": previous["venue"], "ref": previous["refs"][0]}
            current = {"venue": update["venue"], "ref": update["refs"][0]}

            def access_denied(arguments, turn):
                try:
                    service.read("read_venue_access", arguments, turn, "probe")
                except ValueError as error:
                    return str(error) == "venue access is outside the active scope"
                return False

            scope["undelivered_denied"] += access_denied(current, 1)
            service.take_event(1)
            scope["booking_turn_denied"] += access_denied(current, 0)
            scope["obsolete_denied"] += access_denied(old, 1)
            actual, _ = service.read("read_venue_access", current, 1, "valid")
            scope["current_allowed"] += equal(actual, oracle["actions"][1]["observation"])

    counterfactuals = {}
    for category in BRANCH_REFS:
        first, second = (build_case(category, 5, "en", 0, branch=outcome) for outcome in (True, False))
        positive = [witness(*row[:2]) for row in (first, second)]
        counterfactuals[category] = first[0] == second[0] and all(
            evaluate(*row, positive[i])["status"] == "PASS" and evaluate(*row, positive[1 - i])["status"] == "FAIL"
            for i, row in enumerate((first, second)))
    return {
        "public_parity_and_world_counterfactuals": {
            "status": "PASS" if all(len(counts) == 4 for counts in branches.values()) and all(counterfactuals.values())
            else "FAIL", "parity_by_outcome": branches, "opposite_world_same_public_input": counterfactuals,
        },
        "typed_read_order_and_exact_preview": {
            "status": "PASS" if typed["PASS"] == typed["wrong_preview_rejected"] == 68 else "FAIL",
            "reverse_read_order_accepted": typed["PASS"], "reverse_preview_order_rejected": typed["wrong_preview_rejected"],
        },
        "service_scope_revocation": {
            "status": "PASS" if len(scope) == 4 and set(scope.values()) == {75} else "FAIL", "controls": dict(scope),
        },
    }


def files():
    plan = json.loads(original.PLAN.read_bytes())
    if plan["suites"]["MULTITOOL-V2"] != original.COUNTS or tuple(plan["panel"]) != original.MODELS:
        raise ValueError("candidate roster differs from the registered execution plan")
    rows, repeats = candidate()
    strata = balanced.shape(rows, repeats)
    report = original._qualification(rows)
    report["balanced_controls"] = balanced._balanced_controls(rows)
    report["review_regressions"] = _review_regressions(rows)
    report["coverage"].update(independent_business_and_content_review="NOT_RUN",
                              independently_authored_expected_outcomes="NOT_RUN")
    report["open_gates"].append("independently authored expected outcomes for the formal roster")
    witness_results, proven, categories, counts = Counter(), [], Counter(), Counter()
    for public, world, oracle in rows:
        capture = witness(public, world)
        status = evaluate(public, world, oracle, capture)["status"]
        witness_results[status] += 1
        proven.append([public["case_id"], fingerprint(capture), status])
        if status == "PASS":
            categories[public["category"]] += 1
            counts[str(public["required_actions"])] += 1
    report.update(independent_witnesses={key: witness_results[key] for key in ("PASS", "FAIL", "BLOCKED", "NOT_RUN")},
                  witness_set_sha256=fingerprint(proven), positive_by_category=dict(categories),
                  positive_by_exact_action_count=dict(counts))
    if witness_results["PASS"] != len(rows) or any(control["status"] != "PASS"
            for name in ("balanced_controls", "review_regressions") for control in report[name].values()):
        report["software_qualification"] = "FAIL"

    def revised_trials(model):
        trials = balanced.trial_roster(model, rows, repeats)
        for trial in trials:
            trial["suite"] = VERSION
            trial["trial_id"] = fingerprint({key: value for key, value in trial.items() if key != "trial_id"})
        return fingerprint(trials)

    roster = {
        "cases": [{key: public[key] for key in ("case_id", "category", "language", "required_actions")}
                  | {"critical_path": oracle["critical_path"], "model_input_sha256": fingerprint(
                      {"message": public["message"], "tools": public["tools"]}),
                      "world_sha256": fingerprint(world), "oracle_sha256": fingerprint(oracle)}
                  for public, world, oracle in rows], "repeat_case_ids": repeats,
        "repeat_seeds": list(original.REPEAT_SEEDS), "first_seed": original.FIRST_SEED,
        "per_model_candidate_roster_sha256": {model: revised_trials(model) for model in original.MODELS},
    }
    outputs = {"roster.json": canonical(roster) + b"\n", "software-qualification.json": canonical(report) + b"\n"}
    manifest = {
        "version": VERSION, "execution_plan_sha256": digest(original.PLAN),
        "prior_candidate_manifest_sha256": digest(balanced.FOLDER / "manifest.json"),
        "counts_per_model": original.COUNTS, "panel": list(original.MODELS),
        "planned_trials": len(original.MODELS) * sum(original.COUNTS.values()), "attributed_physical_trials": 0,
        "candidate_roster_status": "PASS", "formal_roster_freeze": "NOT_RUN", "formal_dispatch": "BLOCKED",
        "physical_execution": "NOT_RUN", "cohort_strata": strata,
        "source_sha256": {name: digest(Path(__file__).with_name(name)) for name in (
            Path(__file__).name, "multitool_v2_balanced.py", "multitool_v2_candidate.py", "multitool_v2_cases.py",
            "multitool_v2_witness.py", "action_graph_v2.py",
        )},
        "files": {name: sha256(raw).hexdigest() for name, raw in outputs.items()},
    }
    return {"manifest.json": canonical(manifest) + b"\n", **outputs}, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    expected, report = files()
    if args.write:
        FOLDER.mkdir(parents=True, exist_ok=True)
    for name, raw in expected.items():
        target = FOLDER / name
        if args.write and not target.exists():
            target.write_bytes(raw)
        if target.read_bytes() != raw:
            raise ValueError(f"{VERSION} artifact differs: {name}")
    print(report["software_qualification"], report["independent_witnesses"]["PASS"],
          "software witnesses; physical execution", report["physical_execution"])
    return 0 if report["software_qualification"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
