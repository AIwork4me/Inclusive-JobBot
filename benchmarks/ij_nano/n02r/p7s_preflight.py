#!/usr/bin/env python3
"""One-trial P7S preflight: start S1, execute a single two-stage P7S trial
through the v2 controller path, print both stages."""
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "benchmarks" / "root_cause"))
sys.path.insert(0, str(ROOT / "benchmarks" / "ij_nano"))
sys.path.insert(0, str(ROOT / "src"))
import gpu_lease
from n02r import controller_v2, tasks as tasks_mod

sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    sa = next(t for t in tasks_mod.build_suite()
              if t["family"] == "structured_action")
    if len(sys.argv) != 2:
        print("usage: python -I benchmarks/ij_nano/n02r/p7s_preflight.py "
              "<weights-root>")
        return 2
    args = type("A", (), {"weights_root": sys.argv[1],
                          "models": "S1", "backend": "vulkan",
                          "port": 8097, "phase": "preflight"})()
    c = controller_v2.ControllerV2(args)
    if not (c.run_dir / "manifest.json").exists():
        c.run_dir.mkdir(parents=True, exist_ok=True)
        (c.run_dir / "manifest.json").write_text(
            json.dumps({"identity": c.identity, "created_utc": "preflight"},
                       indent=1), encoding="utf-8")
    (c.run_dir / "responses").mkdir(parents=True, exist_ok=True)
    with gpu_lease.physical_gpu():
        print("[preflight] lease acquired", flush=True)
        rel, alias = controller_v2.MODELS["S1"]
        sess = controller_v2.ServerSession(
            "vulkan", (pathlib.Path(args.weights_root) / rel).resolve(),
            alias, 8097, ROOT / ".runtime" / "ij_nano_n02r_v2" / "preflight",
            [])
        sess.start()
        base = "http://127.0.0.1:8097"
        try:
            proof = sess.wait_ready(time.time() + 900)
            print("[preflight] ready:", proof["socket_owner_pid_verified"],
                  sess.offload_line(), flush=True)
            kw, verified, ev = controller_v2.verify_thinking_kwarg(base)
            c.thinking_kwarg["S1"] = (kw, verified)
            print(f"[preflight] thinking kwarg={kw} verified={verified}",
                  flush=True)
            tid = c._trial_id("S1", "P7S", sa["task_id"], 1024)
            c._run_trial(base, "S1", "P7S", sa, 1024, tid)
            row = json.loads(c.results_path.read_text(encoding="utf-8")
                             .splitlines()[-1])
            art = json.loads((ROOT / row["response_artifact"])
                             .read_text(encoding="utf-8"))
            for s in art["stages"]:
                hj = s["http"] or {}
                print(f"[stage {s['stage']}] {s['path']} err={s['http_error']} "
                      f"content={(hj.get('content') or '')[:120]!r}")
            print("[verdict]", json.dumps(row["parser"], ensure_ascii=False)[:300])
            print("[semantic]", row["semantic_correct"], row["reasons"])
        finally:
            sess.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
