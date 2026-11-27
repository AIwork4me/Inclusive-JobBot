"""Advance verified Q2 evidence to candidate runtime admission and record routing gates."""
import json

from .archive import digest
from .controller import gpu_lock
from .larger_candidate_admission import PINS, test
from .q2_closure import build, markdown
from .runtime import write_json


def routing_readiness(report, families):
    return {
        "q2_passing": sorted(code for code, row in report["models"].items() if row["status"] == "PASS"),
        "formal_history": "BLOCKED",
        "independent_q3_qualification": "NOT_RUN",
        "reason": "Q3 qualification and independent route credentials are required for historical evaluation",
        "subject_families": {family: {"physical_trials": count, "status": "BLOCKED"}
                             for family, count in sorted(families.items())},
    }


def admission_runs(out, candidate):
    sealed = []
    for path in sorted(out.glob("*/portable/report.json")):
        report = json.loads(path.read_bytes())
        if report["candidate"] != candidate:
            continue
        if (report["pins_sha256"] != digest(PINS) or report["run_id"] != path.parent.parent.name
                or any(digest(path.with_name(name)) != sha for name, sha in report["sha256"].items())):
            raise ValueError("larger candidate admission evidence differs from its seal")
        development = report.get("matched_development", {})
        if development.get("coverage") == "PASS":
            from .larger_development import replay_development
            actual = replay_development(candidate["code"], path.with_name("development.jsonl.gz"),
                                        path.with_name(report["gpu"]["trace_file"] + ".gz"))
            if actual != development:
                raise ValueError("larger candidate development report does not replay")
        sealed.append({"status": report["status"], "run_id": report["run_id"], "report_sha256": digest(path),
                       "matched_development": report.get("matched_development", {}).get("coverage", "NOT_RUN")})
    return sealed


def candidate_admission(state, assets, port):
    out = state / "larger-candidate-admission"
    out.mkdir(parents=True, exist_ok=True)
    results = {}
    for candidate in json.loads(PINS.read_bytes())["candidates"]:
        code = candidate["code"]
        sealed = admission_runs(out, candidate)
        if not sealed:
            try:
                with gpu_lock(state):
                    test(candidate, assets, out, port, matched_development=True)
            except FileNotFoundError:
                results[code] = {"status": "BLOCKED", "reason": "pinned local weight or runtime is absent"}
                continue
            except BlockingIOError:
                results[code] = {"status": "BLOCKED", "reason": "GPU lease is held"}
                continue
            except (ValueError, OSError) as error:
                write_json(out / f"{code}-last-error.json", {"error": type(error).__name__, "message": str(error)})
                results[code] = {"status": "BLOCKED", "reason": "runtime admission interrupted before sealing"}
                continue
            sealed = admission_runs(out, candidate)
        status = "PASS" if any(row["status"] == "PASS" for row in sealed) else (
            "FAIL" if any(row["status"] == "FAIL" for row in sealed) else "BLOCKED")
        matched = "PASS" if any(row["matched_development"] == "PASS" for row in sealed) else (
            "BLOCKED" if any(row["matched_development"] == "BLOCKED" for row in sealed) else "NOT_RUN")
        results[code] = {"status": status, "runs": sealed, "matched_development": matched}
    return results


def advance(state, archive, history, assets, port):
    closure = build(archive)
    report_path = state / "q2-closure.json"
    write_json(report_path, closure)
    (state / "q2-closure.md").write_text(markdown(closure), encoding="utf8")
    coverage = json.loads((history / "coverage.json").read_bytes())
    result = {"q2_report_sha256": digest(report_path),
              **routing_readiness(closure, coverage["source_families"])}
    progress = state / "qualification-transition.json"
    write_json(progress, result)
    result["larger_runtime_admission"] = candidate_admission(state, assets, port)
    write_json(progress, result)
    return result
