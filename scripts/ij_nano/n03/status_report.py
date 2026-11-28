#!/usr/bin/env python3
"""N03 progressive status report generator (IJ-NANO-1.3S order 23/26).

Renders MISSION_STATE_IJNANO_N03_PROGRESSIVE.json + taxonomy.json into
reports/IJNANO_N03_PROGRESSIVE_STATUS.md with the four SEPARATE progress
measures required by the order (engineering readiness, physical execution
coverage, evaluation coverage, semantic accuracy) - never a single blended
percentage. Deterministic; rerun after every state change.
"""
from __future__ import annotations

import json
import pathlib
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[3]
STATE = ROOT / "MISSION_STATE_IJNANO_N03_PROGRESSIVE.json"
TAXONOMY = ROOT / "evaluation" / "ij_nano" / "n03" / "taxonomy.json"
OUT = ROOT / "reports" / "IJNANO_N03_PROGRESSIVE_STATUS.md"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    state = json.loads(STATE.read_text(encoding="utf-8"))
    tax = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    prims = state["primitives"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # slot accounting comes from the roster-derived manifest (N03-D01),
    # never from hand-maintained state fields
    slot_path = ROOT / "evidence" / "IJNANO" / "N03" / "dataset" / \
        "slot_manifest.json"
    slots = json.loads(slot_path.read_text(encoding="utf-8")) if \
        slot_path.is_file() else None
    per_prim_slots = (slots or {}).get("per_primitive", {})

    n = len(prims)
    eng_ready = sum(1 for p in prims.values()
                    if p["development_authorization"] == "AUTHORIZED")
    planned_dev = (slots or {}).get("totals", {}).get("dev_slots", 0)
    planned_conf = (slots or {}).get("totals", {}).get("conf_slots", 0)
    exec_dev = exec_conf = qual_dev = 0          # no runner yet (B4)

    lines = []
    a = lines.append
    a("# N03 Progressive Status")
    a("")
    a(f"Generated {now} from `MISSION_STATE_IJNANO_N03_PROGRESSIVE.json` "
      f"(deterministic render of the machine state; do not hand-edit).")
    a("")
    a(f"- Mission order: `{state['mission_order']}` "
      f"(SHA256 `{state['order_sha256'][:16]}...`)")
    a(f"- Execution plan: `{state['execution_plan']}`")
    a(f"- Taxonomy: `{state['taxonomy']['path']}` "
      f"(SHA256 `{state['taxonomy']['sha256'][:16]}...`, frozen "
      f"{state['taxonomy']['frozen_utc']})")
    a("")
    a("## Authorization")
    a("")
    for name, lvl in state["authorization_levels"].items():
        if name == "controller":
            continue
        a(f"- **{name}**: {'ACTIVE' if lvl['active'] else 'inactive'}"
          f"{' (diagnostic only)' if lvl.get('diagnostic_only') else ''}")
    ctrl = state["authorization_levels"]["controller"]
    ctrl_loc = ctrl.get("planned") or ctrl.get("implemented", "-")
    a(f"- Authorization controller: `{ctrl_loc}` — {ctrl['status']}")
    a("")
    a("## Gates")
    a("")
    a("| Gate | Status |")
    a("|---|---|")
    for g, s in state["gates"].items():
        a(f"| `{g}` | {s} |")
    a("")
    a("## EAE dependencies (Lane A, PR #13)")
    a("")
    a(f"- Lane A status: {state['eae_dependencies']['lane_a_status']}")
    a(f"- Blocking: {', '.join(state['eae_dependencies']['blocking'])}")
    a("")
    a("## Progress measures (kept separate by design)")
    a("")
    a("| Measure | Value |")
    a("|---|---|")
    a(f"| A. Engineering readiness (primitives with qualified evaluation "
      f"contracts) | {eng_ready}/{n} |")
    a(f"| B. Physical execution coverage (authorized slots with physical "
      f"evidence) | {exec_dev + exec_conf} of "
      f"{state['primary_budget']['total']} primary "
      f"({exec_dev} dev + {exec_conf} confirmation executed) |")
    a(f"| C. Evaluation coverage (applicable planned slots with qualified "
      f"evaluable outcomes) | {qual_dev} |")
    a(f"| D. Semantic accuracy (qualified evaluable, semantically correct) | "
      f"not yet measurable (0 qualified slots) |")
    a("")
    a("No single blended progress percentage is reported.")
    a("")
    a("## Per-primitive matrix")
    a("")
    a("| ID | Capability | Batch | Roster | Cert | Dev auth | Conf auth | "
      "Dev slots (plan) | Conf slots (plan) |")
    a("|---|---|---|---|---|---|---|---|---|")
    for pid in sorted(prims):
        p = prims[pid]
        roster = p.get("roster_status", "NOT_STARTED")
        cert = p["certificate_id"][:8] if p["certificate_id"] else "-"
        sp = per_prim_slots.get(pid, {})
        a(f"| {pid} | {p['capability']} | {p['batch']} | {roster} | {cert} |"
          f" {p['development_authorization']} | "
          f"{p['confirmation_authorization']} | "
          f"{sp.get('dev_slots', '-')} | {sp.get('conf_slots', '-')} |")
    a("")
    a(f"Planned primary slots (roster-derived): {planned_dev} dev + "
      f"{planned_conf} confirmation = {planned_dev + planned_conf} "
      f"(target when complete "
      f"{state['primary_budget']['total']}; executed/qualified accounting "
      f"activates with the B4 runner).")
    a("")
    a("## Preserved blockers")
    a("")
    for k, v in state["preserved_blockers"].items():
        a(f"- {k}: {v}")
    a("")
    a(f"Next task: {state['resume']['next_task']}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"status report written: {OUT} "
          f"({len(lines)} lines, {eng_ready}/{n} engineering-ready)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
