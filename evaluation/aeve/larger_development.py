"""Run larger candidates on the existing blinded, paired development roster."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

from .archive import check_text, digest
from .contracts import validate_judgment
from .history import lines
from .metrics import _score
from .q2_development import ARMS, FREEZE, freeze, grade, request, roster
from .q2_closure import wall_summary
from .runtime import canonical, fingerprint, infer


def matched_requests(candidate):
    freeze()
    return [request(case, candidate, arm) for case in roster() for arm in ARMS]


def score_response(spec, case, transport, raw):
    verdict, answer, attempted = "INVALID", None, False
    if transport == "PASS":
        try:
            parsed = grade(spec, raw)
            attempted = parsed.get("verdict") in {"PASS", "FAIL"}
            answer = validate_judgment(spec["packet"], parsed)
            verdict = answer["verdict"]
        except (KeyError, TypeError, ValueError):
            pass
    score = {"label": case["expected"], "prediction": verdict, "attempted_decision": attempted,
             "citation_correct": bool(answer and verdict == case["expected"]
                                      and set(answer["evidence_refs"]) == set(case["required_refs"]))}
    return answer, score


def summarize(specs, rows):
    by_arm = defaultdict(list)
    timings = defaultdict(list)
    for row in rows:
        by_arm[row["arm"]].append(row["score"])
        timings[row["arm"]].append(row["capture"]["wall_ms"])
    return {"evidence_scope": "development_only", "coverage": "PASS", "required": len(specs),
            "recorded": sum(map(len, by_arm.values())), "reference_freeze_sha256": digest(FREEZE),
            "analysis_source_sha256": digest(Path(__file__)),
            "wire_roster_sha256": fingerprint(specs),
            "arms": {arm: {"metrics": _score(by_arm[arm]), "wall": wall_summary(timings[arm])} for arm in ARMS}}


def evaluate_development(candidate, client, journal):
    specs = matched_requests(candidate)
    expected = {case["case_id"]: case for case in roster()}
    rows = []
    with journal.open("xb") as output:
        for spec in specs:
            transport, raw, capture = infer(client, spec["body"])
            cid, arm = spec["case_id"], spec["arm"]
            answer, score = score_response(spec, expected[cid], transport, raw)
            row = {"case_id": cid, "arm": arm, "spec": spec, "capture": capture,
                   "transport": transport, "answer": answer, "score": score}
            data = canonical(row)
            check_text(data)
            output.write(data + b"\n")
            output.flush()
            rows.append(row)
    return summarize(specs, rows)


def replay_development(candidate, journal, trace):
    specs = matched_requests(candidate)
    expected = {case["case_id"]: case for case in roster()}
    generation = {row["completion_id"]: fingerprint(row) for row in lines(trace)}
    rows = list(lines(journal))
    for spec, row in zip(specs, rows, strict=True):
        capture = row["capture"]
        if (spec != row["spec"] or spec["case_id"] != row["case_id"] or spec["arm"] != row["arm"]
                or capture["request"] != {**spec["body"], "verbose": True, "return_tokens": True}):
            raise ValueError("larger candidate development request differs from its matched roster")
        raw = None
        if row["transport"] == "PASS":
            wire = json.loads(capture["raw_response"])
            source = capture["source_generation"]
            if (wire["choices"][0]["finish_reason"] != "stop" or source["truncated"] is not False
                    or generation.pop(wire["id"], None) != fingerprint(source)):
                raise ValueError("larger candidate completion differs from native token evidence")
            raw = wire["choices"][0]["message"]["content"]
        result = score_response(spec, expected[row["case_id"]], row["transport"], raw)
        if result != (row["answer"], row["score"]):
            raise ValueError("larger candidate score differs from its captured wire reply")
    return summarize(specs, rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("portable", type=Path)
    folder = parser.parse_args().portable
    report = json.loads((folder / "report.json").read_bytes())
    if report["status"] != "PASS" or report["matched_development"]["coverage"] != "PASS":
        raise ValueError("portable report has no completed matched GPU development roster")
    for name, expected in report["sha256"].items():
        if Path(name).name != name or digest(folder / name) != expected:
            raise ValueError("portable larger Judge evidence differs from the report")
    replay = replay_development(report["candidate"]["code"], folder / "development.jsonl.gz",
                                folder / (report["gpu"]["trace_file"] + ".gz"))
    if replay != report["matched_development"]:
        raise ValueError("development quality does not replay")
    print(f"{replay['recorded']} matched development requests verified")


if __name__ == "__main__":
    main()
