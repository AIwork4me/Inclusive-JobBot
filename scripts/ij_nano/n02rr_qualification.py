#!/usr/bin/env python3
"""N02RR replay qualification runner (mission section 4).

Executes the control battery in RED order first (audited mutant active ->
gate must reject it), then GREEN (corrected loader -> all controls pass),
plus the analyzer-integration aggregate, and persists:

    evidence/IJNANO/N02RR/replay_qualification.json

N02R_OFFLINE_REPLAY_INTEGRITY_GO is granted by this script ONLY on
red-to-green evidence (mutant rejected AND green all-pass AND the published
witness artifact replays to its independently expected verdict).
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]
                       / "scripts" / "ij_nano"))
import n02rr_replay_lib as rl            # noqa: E402
import n02rr_qualification_lib as qlib   # noqa: E402

RUNS = rl.ROOT / "evidence" / "IJNANO" / "N02R" / "runs"
DST_RUN = RUNS / "ec5b95357e960f99"
WITNESS = "003abb9e2604141bd8b016ec"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    c = qlib.make_controller()
    man = json.loads((DST_RUN / "manifest.json").read_text(encoding="utf-8"))
    identity_ok = (json.dumps(c.identity, sort_keys=True)
                   == json.dumps(man["identity"], sort_keys=True))
    if not identity_ok:
        print("REFUSED: sealed modules no longer reproduce ec5b95357e960f99")
        return 3

    with tempfile.TemporaryDirectory(prefix="n02rr_qual_",
                                      dir=str(rl.ROOT / ".runtime")) as td:
        battery = qlib.ControlBattery(c, pathlib.Path(td))

        # RED phase: the audited mutant must be rejected
        red = battery.run_red()

        # GREEN phase: corrected loader + full pipeline
        green = battery.run_green()

        # analyzer layer integration
        analyzer = qlib.analyzer_integration(battery)

    # published-witness integration: the real sealed artifact must replay to
    # the source experiment's independently computed physical verdict
    engine = rl.ReplayEngine(c)
    dst_rows = [json.loads(l) for l in (DST_RUN / "results.jsonl")
                .read_text(encoding="utf-8").splitlines()]
    wrow = next(r for r in dst_rows
                if r["response_artifact"].endswith(WITNESS + ".json"))
    src = {r["trial_id"]: r for r in (
        json.loads(l) for l in (RUNS / "7a1b9d7d160202d8" / "results.jsonl")
        .read_text(encoding="utf-8").splitlines())}
    srow = src[wrow["execution"]["source_trial_id"]]
    wrec = engine.replay(wrow, source_row=srow)
    witness_ok = (wrec["parser"]["structural_ok"] is True
                  and wrec["parser"]["payload"] == srow["parser"]["payload"]
                  and wrec["telemetry"]["latency_s"]
                  == srow["telemetry"]["latency_s"])
    witness = {"artifact": wrow["response_artifact"],
               "corrected_payload": wrec["parser"]["payload"],
               "source_payload": srow["parser"]["payload"],
               "corrected_matches_source": witness_ok}

    green_all = all(g["passed"] for g in green)
    gate_go = bool(red["mutant_rejected"]) and green_all and witness_ok

    out = {
        "mission": "IJ-NANO-1.2R section 4",
        "gate": "N02R_OFFLINE_REPLAY_INTEGRITY_GO",
        "granted": gate_go,
        "identity_reproduced": identity_ok,
        "pipeline": "raw API artifact -> validated loader -> stage "
                    "reconstruction -> parser -> evaluator -> trial record "
                    "-> analyzer",
        "red_phase_mutant": red,
        "green_phase_controls": green,
        "green_all_pass": green_all,
        "analyzer_integration": analyzer,
        "published_witness_integration": witness,
        "controls_total": len(green),
        "positive_controls_reaching_parser_as_dicts": sum(
            1 for g in green
            if g["checks"].get("parser_input_is_dict") is True),
    }
    outdir = rl.ROOT / "evidence" / "IJNANO" / "N02RR"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "replay_qualification.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"gate": out["gate"], "granted": gate_go,
                      "controls_total": len(green),
                      "green_all_pass": green_all,
                      "mutant_rejected": red["mutant_rejected"],
                      "witness_ok": witness_ok}, indent=1))
    return 0 if gate_go else 1


if __name__ == "__main__":
    sys.exit(main())
