"""Run deterministic wire controls through the original IJ-0.7 benchmark runners."""

from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from benchmarks.agentic_planning_v1 import runner as planning
from benchmarks.agentic_planning_v1.run import load_jsonl
from benchmarks.job_productivity_v1.holdout import dataset as job_data, verify as job
from benchmarks.multitool_v1 import dataset as multi_data, run as multi, verify as multi_verify
from benchmarks.tool_calling_v2.holdout import dataset as tc_data, runner as tc
from benchmarks.tool_calling_v2.oracle import decode_object
from business_tools import encode_state


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def completion(calls=(), *, text=None, reasoning=None):
    message = {
        "role": "assistant",
        "content": text,
        "tool_calls": [
            {"type": "function", "id": key, "function": {"name": tool, "arguments": raw}}
            for key, tool, raw in calls
        ],
    }
    if reasoning:
        message["reasoning_content"] = reasoning
    return {"choices": [{"finish_reason": "tool_calls" if calls else "stop", "message": message}]}


class FixtureClient:
    """Software-only client. Synthetic capture placeholders satisfy the runner's wire interface."""

    base_url = "http://127.0.0.1:1"

    def __init__(self, respond):
        self.respond = respond
        self.requests = []

    def chat(self, base_url, body):
        if base_url != self.base_url:
            raise ValueError("Fixture client received an unexpected endpoint")
        reply = self.respond(body, len(self.requests))
        self.requests.append({
            "render_status": 200, "http_status": 200, "raw_response": encoded(reply),
            "source_generation": {"prompt_token_ids": [], "truncated": False},
        })
        return reply


def scripted(replies):
    return FixtureClient(lambda _body, index: replies[index])


def tc_witness(case, database):
    steps = case["oracle"]["steps"]

    def respond(body, index):
        if index == len(steps):
            reasoning = "Fixture reasoning channel" if case["reasoning_required"] else None
            return completion(text=encoded(case["oracle"]["final"]), reasoning=reasoning)
        observations = [decode_object(m["content"]) for m in body["messages"] if m["role"] == "tool"]
        prior = {step["id"]: result for step, result in zip(steps[:index], observations, strict=True)}
        step = steps[index]
        args = {key: prior[value["ref"][0]][value["ref"][1]] if isinstance(value, dict) and "ref" in value
                else value for key, value in step["args"].items()}
        return completion([(f"fixture-{index}", step["tool"], encoded(args))])

    return tc.run_trajectory(case, FixtureClient(respond), database, stream=False, seed=47)


def comparable_state(snapshot):
    if snapshot is None:
        return None
    events = Counter(
        encode_state({key: value for key, value in row.items() if key not in {"transaction_id", "elapsed_ms"}})
        for row in snapshot["audit_events"].values()
    )
    return {**snapshot, "audit_events": events}


def multitool_witness(case, directory):
    reference, calls, final, before, after, events = multi_verify.replay_reference(case, directory)
    groups = {}
    for call in calls:
        groups.setdefault(call.turn, []).append((call.call_id, call.name, call.arguments_raw))
    replies = [completion(batch) for batch in groups.values()] + [completion(text=final)]
    result = multi.run_case(case, scripted(replies), directory / f"{case.case_id}-wire.sqlite", seed=47)
    if (reference["status"], comparable_state(before), comparable_state(after), list(events)) != (
            result["status"], comparable_state(result["before_sqlite"]), comparable_state(result["after_sqlite"]),
            result["delivered_events"]):
        result["status"] = "FAIL"
        result["findings"].append({"code": "REFERENCE_WIRE_DIVERGENCE"})
    return result


def planning_witness(case, graph, track):
    actions, replies = [], []
    for name in graph["witness"]:
        node = graph["nodes"][name]
        args = {**node["args"], **{key: {"from": src, "field": field}
                                  for key, (src, field) in node["requires"].items()}}
        if node["tool"] == "stage" and graph["policy_condition"]:
            args["assessment"] = {"from": "crosscheck", "field": "observed_metric", "evaluate": "policy_assessment"}
        actions.append({"id": name, "tool": node["tool"], "arguments": args, "depends_on": node["after"],
                        "preconditions": ["Check prior observations and stop on denial."]})
        replies.append(completion([(name, node["tool"], encoded(node["args"]))]))
    if track == "P":
        plan = {"goal": graph["goal"], "subgoals": ["Resolve this request"], "actions": actions,
                "success_conditions": ["Verify the outcome"], "stop_conditions": ["Stop when done or denied"]}
        replies.insert(0, completion(text=encoded(plan)))
    replies.append(completion(text=encoded(graph["final"])))
    return planning.run_trajectory(case, graph, scripted(replies), track=track, seed=47)


def record(case_id, verdict):
    return {"case_id": case_id, "status": verdict["status"],
            "findings": [f["code"] for f in verdict.get("findings", [])] + verdict.get("errors", [])}


def run(directory):
    tc_cases, _ = tc_data.load("holdout")
    groups = {"tc_v2": [record(c["id"], tc_witness(c, directory / f"{c['id']}.sqlite")) for c in tc_cases]}
    multi_cases = multi_data.load_freeze().active
    groups["multitool_v1"] = [record(key, multitool_witness(c, directory)) for key, c in multi_cases.items()]
    planning_root = ROOT / "benchmarks/agentic_planning_v1"
    public = load_jsonl(planning_root / "datasets/holdout.jsonl")
    private = {g["case_id"]: g for g in load_jsonl(planning_root / "task_graphs/holdout.jsonl")}
    for track in ("A", "P"):
        groups[f"planning_v1_{track}"] = [
            record(c["case_id"], planning_witness(c, private[c["case_id"]], track)) for c in public
        ]
    groups["job_v1"] = [
        record(key, job.evaluate(c, **job.replay_reference(c, directory))) for key, c in job_data.load().cases.items()
    ]
    return {
        "schema_version": 1,
        "evidence_class": "deterministic_software_control",
        "independently_authored": False,
        "cohorts": {
            name: {"counts": dict(Counter(r["status"] for r in rows)), "trials": rows}
            for name, rows in groups.items()
        },
    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="atlas-controls-") as directory:
        result = run(Path(directory))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8", newline="\n")
    print({key: cohort["counts"] for key, cohort in result["cohorts"].items()})
    return int(any(cohort["counts"].get("FAIL") or cohort["counts"].get("BLOCKED")
                   for cohort in result["cohorts"].values()))


if __name__ == "__main__":
    raise SystemExit(main())
