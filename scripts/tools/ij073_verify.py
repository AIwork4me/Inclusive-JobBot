"""Recompute the IJ073 diagnostic checkpoint and compare all archived rows."""
import argparse
import json
from pathlib import Path

from scripts.tools.ij073_archive_replay import audit as archived
from scripts.tools.ij073_baseline import recount
from scripts.tools.ij073_executable_witness import audit as executable
from scripts.tools.ij073_guard_controls import audit as guards
from scripts.tools.ij073_mutation_replay import run as mutations
from scripts.tools.ij073_public_worlds import run as public_worlds
from scripts.tools.ij073_plan_alignment import audit as align
from scripts.tools.ij073_transport_replay import audit as transport
from scripts.tools.ij073_witness_replay import audit as witnesses


def encoded(result):
    lines = []
    for key, value in sorted(result.items()):
        if key in {"rows", "trials"}:
            inner = ",\n".join("    " + json.dumps(r, sort_keys=True, ensure_ascii=False) for r in value)
            field = "[\n" + inner + "\n  ]"
        else:
            field = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False).replace("\n", "\n  ")
        lines.append("  " + json.dumps(key) + ": " + field)
    return ("{\n" + ",\n".join(lines) + "\n}\n").encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    sources = {"baseline": recount, "oracle/archive_replay": archived, "oracle/legacy_alignment": align,
               "oracle/mutation_replay": mutations, "oracle/witness_replay": witnesses, "oracle/executable_witness": executable,
               "oracle/guard_controls": guards, "oracle/public_worlds": public_worlds,
               "transport/paired_result": transport}
    for name, generate in sources.items():
        path = Path("evidence/IJ073") / (name + ".json")
        expected = encoded(generate())
        if args.write:
            path.write_bytes(expected)
        elif path.read_bytes() != expected:
            raise SystemExit(f"mismatch: {path}")
        print(f"PASS {path.as_posix()}")


if __name__ == "__main__":
    main()
