"""One command surface for software reproduction, physical scheduling and audit."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from .archive import export, verify
from .controller import DEFAULT, connect
from .runtime import ROOT


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="command",required=True)
    modules = {"resume":"resume","qualification":"qualification","history":"history","metrics":"metrics",
               "oracle-report":"report_oracle","planning-report":"report_planning","history-report":"report_history",
               "meta":"meta_evaluation","qualification-report":"report_qualification","gates":"progress",
               "blind-packet":"human_review","q2-development":"q2_development",
               "q2-qualification":"q2_qualification","q2-report":"q2_report","queue":"controller"}
    if len(sys.argv) >= 2 and sys.argv[1] in modules:
        from importlib import import_module
        name = modules[sys.argv.pop(1)]
        return import_module("." + name,__package__).main()
    for command in modules:
        commands.add_parser(command)
    for command in ("verify","archive","restore"):
        parser = commands.add_parser(command)
        parser.add_argument("--results",type=Path,default=ROOT/"evaluation/aeve/results")
        parser.add_argument("--state",type=Path,default=DEFAULT)
    args = cli.parse_args()
    if args.command == "verify":
        from .qualification import require_freeze
        from .gold import freeze
        freeze()
        from .q2_gold import freeze as verify_fresh_gold
        from .q2_development import freeze as verify_repair_design
        verify_fresh_gold()
        verify_repair_design()
        manifest = json.loads((ROOT/"atlas/ij073/artifact_manifest.json").read_bytes())
        for name, expected in manifest.items():
            with (ROOT/name).open("rb") as stream:
                if hashlib.file_digest(stream,"sha256").hexdigest() != expected:
                    raise ValueError(f"tracked mission artifact changed: {name}")
        print("protocol",require_freeze(),"sealed attempts",verify(args.results))
        return
    db = connect(args.state)
    try:
        if args.command == "archive":
            print("new sessions",export(db,args.state,args.results),"verified attempts",verify(args.results))
        else:
            from .restore import restore
            print("restored sealed attempts",restore(db,args.state,args.results))
    finally:
        db.close()


if __name__ == "__main__":
    main()
