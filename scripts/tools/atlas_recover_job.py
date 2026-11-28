"""Reconcile sealed JOB-V1 checkpoints without writing to the legacy run."""

from argparse import ArgumentParser
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from benchmarks.job_productivity_v1.holdout.dataset import digest, load
from benchmarks.job_productivity_v1.holdout.run_f import create_plan
from benchmarks.job_productivity_v1.holdout.run_models import summarize
from benchmarks.tool_calling_v2.holdout.qualify import pid_counter_proof, read_checkpoint
from benchmarks.tool_calling.runner.run_benchmark import sha256_of


def recover(raw_root):
    freeze = load()
    roster = create_plan(freeze, "primary", [])
    arms = {}
    for arm in "AB":
        folder = raw_root / f"ij07-job-full-{arm}-primary"
        run_bytes = (folder / "run.json").read_bytes()
        run = json.loads(run_bytes)
        config = run["configuration"]
        if config["arm"] != arm or config["roster"] != roster or digest(config) != run["fingerprint"]:
            raise ValueError(f"JOB-V1 roster or configuration mismatch for arm {arm}")
        sealed = {}
        for tag, session in run["sessions"].items():
            if "proof" in session:
                proof = pid_counter_proof(folder, session)
                if proof != session["proof"]:
                    raise ValueError(f"sealed process evidence mismatch for arm {arm}")
                sealed[tag] = proof
        rows, files, unresolved = {}, {}, {}
        for path in sorted((folder / "cases").glob("*.json")):
            row = read_checkpoint(path, run, path.stem, folder / "sqlite")
            case = freeze.cases[row["case_id"]]
            if (row["trial"] != roster[path.stem] or row["arm"] != arm
                    or row["pairing_sha256"] != case.plan["pairing_sha256"]):
                raise ValueError(f"JOB-V1 checkpoint identity mismatch for arm {arm}")
            checkpoint = {"status": row["status"], "session": row["session"], "sha256": sha256_of(path),
                          "database_sha256": row["database_sha256"]}
            if sealed.get(row["session"], {}).get("status") == "PASS":
                rows[path.stem] = row
                files[path.stem] = checkpoint
            else:
                unresolved[path.stem] = {"recorded": checkpoint, "qualification_status": "BLOCKED"}
        terminal = summarize(run, rows, set(unresolved))
        historical = json.loads((folder / "summary.json").read_bytes())
        if (historical["run_id"] != run["run_id"] or historical["terminal_rows"] != len(rows)
                or int(historical["first_pass_successes"]) != terminal["first_pass_successes"]):
            raise ValueError(f"retrospective summary does not match sealed rows for arm {arm}")
        arms[arm] = {"summary": terminal, "run_sha256": sha256(run_bytes).hexdigest(), "git": config["git"],
                     "model_sha256": config["model_sha256"], "executable_sha256": config["engine"]["exe_sha256"],
                     "freeze_sha256": config["freeze_sha256"],
                     "sessions": sealed, "sealed_checkpoints": files, "unsealed_checkpoints": unresolved}
    return {"scope": "local JOB-V1 primary A and B only; raw directories remain at their original paths",
            "arms": arms}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("raw_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = recover(args.raw_root)
    data = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.check:
        if args.output.read_bytes() != data:
            parser.error("JOB-V1 checkpoint reconciliation differs")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as output:
            output.write(data)
    for arm, entry in result["arms"].items():
        print(arm, entry["summary"]["outcomes"])


if __name__ == "__main__":
    main()
