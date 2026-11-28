#!/usr/bin/env python3
"""Compatibility contract evidence generator (N03 critical path).

Emits the machine-readable contract artifact with per-interface
implementation digests (actual file bytes) so the IJ-NANO runner can pin
and verify its integration target:
evidence/IJEVAL/COMPAT/contract_v1.0.0.json
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from eval_assurance.compat import (CONTRACT_VERSION, N03_BATCH_A,  # noqa: E402
                                   REGISTRY, contract_summary,
                                   verify_contract)
from eval_assurance.evidence import sha256_of_file  # noqa: E402

OUT = ROOT / "evidence" / "IJEVAL" / "COMPAT" / f"contract_v{CONTRACT_VERSION}.json"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    problems = verify_contract()
    if problems:
        print(json.dumps({"REFUSED": problems}, indent=1))
        return 1
    interfaces = []
    for iface in REGISTRY:
        mod_path = iface.module.replace(".", "/") + ".py"
        digest = None
        candidate = ROOT / "src" / mod_path
        if candidate.is_file():
            digest = sha256_of_file(candidate)
        interfaces.append({
            "section": iface.section, "name": iface.name,
            "module": iface.module, "symbols": list(iface.symbols),
            "status": iface.status, "notes": iface.notes,
            "implementation_sha256": digest})
    payload = dict(contract_summary())
    payload["interfaces"] = interfaces
    payload["authorization_rule"] = (
        "N03 (and any runner scope) is authorized ONLY by "
        "eval_assurance.compat.authorization.authorize_runner(...) "
        "returning RunnerAuthorization.allowed=True bound to scope, "
        "coverage, certificate digests and snapshot checksum; a PASS "
        "string or bare certificate object authorizes nothing")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(json.dumps({"out": str(OUT.relative_to(ROOT)),
                      "interfaces": len(interfaces),
                      "status": payload["by_status"],
                      "problems": problems}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
