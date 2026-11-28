"""Sequential GPU queue for the IJ-NANO-48H campaign.

Each scope's campaign runs in its OWN subprocess (one EAE pin revision
per process). The queue stops fail-closed on the first nonzero exit;
every subprocess logs to ``runs/n03h/queue_logs/<scope>.log``.
The adapter admission battery gates the AUTH-2W stage.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[3]
LOGS = ROOT / "runs" / "n03h" / "queue_logs"

QUEUE = [
    # (stage, command, requires_admission)
    ("AUTH-2C", ["run", "--scope", "AUTH-2C"], False),
    ("AUTH-2D", ["run", "--scope", "AUTH-2D"], False),
    ("AUTH-2A-RQ", ["run", "--scope", "AUTH-2A-RQ"], False),
    ("ADAPTER-ADMISSION", ["__admission__"], False),
    ("AUTH-2W", ["run", "--scope", "AUTH-2W"], True),
]


def utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def run_stage(name: str, argv: list[str]) -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    log_path = LOGS / f"{name}.log"
    if argv and argv[0] == "__admission__":
        cmd = [sys.executable, "-m",
               "benchmarks.ij_nano.n03h.admission_w"]
    else:
        cmd = [sys.executable, "-m",
               "benchmarks.ij_nano.n03h.campaign"] + argv
    print(f"[{utc()}] {name}: launching", flush=True)
    with open(log_path, "wb") as log:
        proc = subprocess.run(cmd, cwd=str(ROOT), stdout=log,
                              stderr=subprocess.STDOUT)
    status = "OK" if proc.returncode == 0 else f"EXIT {proc.returncode}"
    print(f"[{utc()}] {name}: {status} (log: {log_path})", flush=True)
    return proc.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-stage", default=None,
                    help="skip stages before this one")
    args = ap.parse_args()
    started = False
    results = {}
    admission_ok = None
    # a previously-executed admission stage's durable verdict counts:
    # the battery's evidence file IS the gate record (never fabricated)
    adm_file = (ROOT / "evidence" / "IJNANO" / "N03H" /
                "ADAPTER_ADMISSION" / "adapter_admission.json")
    if adm_file.is_file():
        import json as _json
        verdict = _json.loads(adm_file.read_text(
            encoding="utf-8")).get("verdict")
        admission_ok = verdict == "PASS"
        print(f"[{utc()}] adapter admission verdict on record: "
              f"{verdict}", flush=True)
    for name, argv, needs_admission in QUEUE:
        if args.from_stage and not started:
            if name != args.from_stage:
                continue
            started = True
        if needs_admission and admission_ok is not True:
            print(f"[{utc()}] {name}: BLOCKED - adapter admission "
                  "did not pass", flush=True)
            results[name] = "BLOCKED"
            continue
        code = run_stage(name, argv)
        results[name] = "OK" if code == 0 else f"EXIT {code}"
        if name == "ADAPTER-ADMISSION":
            admission_ok = code == 0
        if code != 0:
            print(f"[{utc()}] queue stopped fail-closed at {name}",
                  flush=True)
            break
    print(json.dumps({"stages": results}, indent=1), flush=True)
    return 0 if all(v == "OK" for v in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
