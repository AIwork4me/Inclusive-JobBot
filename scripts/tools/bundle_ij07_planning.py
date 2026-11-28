"""Bundle a verified raw planning archive into digest-bound gzip text parts."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
from shutil import copyfile
from tempfile import TemporaryDirectory


PART_BYTES = 20 * 1024 * 1024


def digest(file):
    with file.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def manifest(folder):
    return json.loads((folder / "archive_manifest.json").read_bytes())


def safe_name(name):
    path = PurePosixPath(name)
    if (not path.parts or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name
            or path.as_posix() != name):
        raise ValueError(f"invalid archive member name: {name}")
    return name


def pack(source, output):
    inventory = manifest(source)
    groups, size = [[]], 0
    for member, expected in sorted(inventory["sha256"].items()):
        path = source / safe_name(member)
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"verified input changed: {member}")
        member_bytes = path.stat().st_size
        if groups[-1] and size + member_bytes > PART_BYTES:
            groups.append([])
            size = 0
        groups[-1].append((member, path))
        size += member_bytes
    output.mkdir(parents=True, exist_ok=False)
    for name in ("archive_manifest.json", "diagnostic.json"):
        copyfile(source / name, output / name)
    parts = {}
    for index, files in enumerate(groups, 1):
        part = output / f"planning-part-{index:02}.jsonl.gz"
        with part.open("wb") as stream:
            with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0, compresslevel=6) as archive:
                for name, path in files:
                    row = {"name": name, "raw_text": path.read_bytes().decode("utf-8")}
                    archive.write((json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode())
        parts[part.name] = {"sha256": digest(part), "members": len(files), "size": part.stat().st_size}
    record = {"run_id": inventory["run_id"], "archive_manifest_sha256": digest(output / "archive_manifest.json"),
              "format": "utf-8-jsonl-gzip",
              "parts": parts, "members": len(inventory["sha256"])}
    (output / "bundle.json").write_bytes((json.dumps(record, indent=2, sort_keys=True) + "\n").encode())


def verify(folder, destination=None):
    inventory = manifest(folder)
    record = json.loads((folder / "bundle.json").read_bytes())
    if (record["archive_manifest_sha256"] != digest(folder / "archive_manifest.json")
            or record["run_id"] != inventory["run_id"] or record["format"] != "utf-8-jsonl-gzip"):
        raise ValueError("bundle manifest belongs to a different archive")
    if digest(folder / "diagnostic.json") != inventory["sha256"]["diagnostic.json"]:
        raise ValueError("standalone planning metrics differ from the raw archive")
    seen = set()
    for name, part in record["parts"].items():
        path = folder / safe_name(name)
        if path.stat().st_size != part["size"] or digest(path) != part["sha256"]:
            raise ValueError(f"compressed planning part differs: {name}")
        count = 0
        with gzip.open(path, "rb") as archive:
            for line in archive:
                row = json.loads(line)
                if row.keys() != {"name", "raw_text"} or type(row["raw_text"]) is not str:
                    raise ValueError(f"invalid archive row in {name}")
                key = safe_name(row["name"])
                if key in seen or key not in inventory["sha256"]:
                    raise ValueError(f"unexpected archive member: {key}")
                raw = row["raw_text"].encode("utf-8")
                if hashlib.sha256(raw).hexdigest() != inventory["sha256"][key]:
                    raise ValueError(f"planning archive member differs: {key}")
                if destination is not None:
                    target = destination / key
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(raw)
                seen.add(key)
                count += 1
        if count != part["members"]:
            raise ValueError(f"unexpected number of members in {name}")
    if seen != inventory["sha256"].keys() or len(seen) != record["members"]:
        raise ValueError("planning bundle is missing raw evidence")
    print(f"PASS: {len(seen)} exact planning files in {len(record['parts'])} gzip text parts")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--output", type=Path, help="Pack a verified raw archive into a new directory")
    action.add_argument("--restore", type=Path, help="Restore all verified text members into a new directory")
    args = parser.parse_args()
    if args.output:
        pack(args.source, args.output)
    if args.restore:
        if args.restore.exists():
            parser.error("restore requires a fresh output directory")
        args.restore.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=args.restore.parent) as temp:
            staging = Path(temp) / "restored"
            staging.mkdir()
            verify(args.source, staging)
            copyfile(args.source / "archive_manifest.json", staging / "archive_manifest.json")
            staging.rename(args.restore)
    else:
        verify(args.output or args.source)


if __name__ == "__main__":
    main()
