"""Archive sealed PC-S TC-V2 trials and trace files as scan-checked text."""

from argparse import ArgumentParser
import gzip
from hashlib import sha256
import json
from pathlib import Path

from benchmarks.competitive_slm.tc_v2_batch import PC_S_SCOPE, read_attempts, summarize
from scripts.tools.scan_sensitive import scan


def archive(source):
    run = json.loads((source / "run.json").read_bytes())
    if run["scope"] != PC_S_SCOPE or run["configuration"]["candidate"] not in {"H", "J"}:
        raise ValueError("expected a pinned PC-S Qwen reference TC-V2 run")
    rows = read_attempts(source, run)
    summary = summarize(run, rows)
    if summary != json.loads((source / "summary.json").read_bytes()):
        raise ValueError("sealed trial evidence differs from the terminal summary")
    if summary["coverage_status"] != "PASS":
        raise ValueError("TC-V2 PC-S archive requires all selected trials sealed")
    names = [f"{kind}/{key}.json" for key in sorted(rows) for kind in ("attempts", "trajectories")]
    for tag, session in run["sessions"].items():
        names.extend((f"{tag}-launch.json", session["trace_file"], session["counter_file"]))
    findings = scan(source, names)
    if findings:
        raise ValueError(f"raw archive failed privacy scan: {findings[0]}")
    inventory = []
    raw = []
    for name in names:
        data = (source / name).read_bytes()
        digest = sha256(data).hexdigest()
        inventory.append({"name": name, "bytes": len(data), "sha256": digest})
        raw.append(json.dumps({"name": name, "utf8": data.decode("utf-8")}, ensure_ascii=False))
    raw = ("\n".join(raw) + "\n").encode()
    encoded = gzip.compress(raw, mtime=0)
    manifest = {"run_id": run["run_id"], "source_configuration_sha256": run["configuration_sha256"],
                "gzip_sha256": sha256(encoded).hexdigest(), "uncompressed_sha256": sha256(raw).hexdigest(),
                "entries": inventory}
    return encoded, (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()


def verify_archived(output):
    run = json.loads((output / "run.json").read_bytes())
    manifest = json.loads((output / "raw-manifest.json").read_bytes())
    archive_bytes = (output / "raw.jsonl.gz").read_bytes()
    raw = gzip.decompress(archive_bytes)
    if (manifest["run_id"] != run["run_id"] or manifest["source_configuration_sha256"] != run["configuration_sha256"]
            or manifest["gzip_sha256"] != sha256(archive_bytes).hexdigest()
            or manifest["uncompressed_sha256"] != sha256(raw).hexdigest()):
        raise ValueError("PC-S archive identity or payload digest differs")
    entries = {}
    inventory = []
    for line in raw.splitlines():
        entry = json.loads(line)
        data = entry["utf8"].encode()
        name = entry["name"]
        if name in entries:
            raise ValueError("duplicate archived entry")
        entries[name] = sha256(data).hexdigest()
        inventory.append({"name": name, "bytes": len(data), "sha256": entries[name]})
    if inventory != manifest["entries"]:
        raise ValueError("PC-S source archive entry inventory differs")
    proved = {}
    for tag, session in run["sessions"].items():
        proof = session["proof"]
        if proof["status"] != "PASS":
            raise ValueError("archived TC-V2 source session is unsealed")
        for kind, filename in (("launch", f"{tag}-launch.json"), ("trace", session["trace_file"]),
                               ("counters", session["counter_file"])):
            proved[filename] = proof["artifacts_sha256"][kind]
        for key, checkpoint in proof["checkpoints_sha256"].items():
            proved[f"attempts/{key}.json"] = checkpoint["attempt"]
            proved[f"trajectories/{key}.json"] = checkpoint["trajectory"]
    if entries != proved:
        raise ValueError("PC-S source archive differs from the original session seals")


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--verify-archive", action="store_true",
                        help="verify the portable archive with the first argument as its directory")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.verify_archive:
        if args.output or args.check:
            parser.error("portable verification takes one archive directory")
        verify_archived(args.source)
        print("PC-S TC-V2 archive matches the original session seals")
        return
    if args.output is None:
        parser.error("archive export requires the destination directory")
    payloads = zip(("raw.jsonl.gz", "raw-manifest.json"), archive(args.source), strict=True)
    for name, payload in payloads:
        target = args.output / name
        if args.check:
            if target.read_bytes() != payload:
                parser.error(f"{name} differs from the sealed source")
        else:
            with target.open("xb") as handle:
                handle.write(payload)
    print("PC-S TC-V2 source archive: 100 trajectories, matched journals, raw generations and PID counters")


if __name__ == "__main__":
    main()
