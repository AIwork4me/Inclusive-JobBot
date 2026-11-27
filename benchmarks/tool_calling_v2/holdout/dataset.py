"""Freeze and verify the TC-V2 development set, holdout and repeat roster."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from .templates import DEV, HOLDOUT, Sample


HERE = Path(__file__).resolve().parent
HISTORICAL = tuple(HERE.parents[1] / "tool_calling/datasets" / name for name in (
    "tool_calling_500.jsonl", "tool_calling_dev.jsonl",
))
FILES = {"holdout": "tc_v2_500.jsonl", "dev": "tc_v2_dev.jsonl"}
COUNTS = {"holdout": 500, "dev": 120}
SEEDS = {"holdout": "IJ07-TCV2-001-H", "dev": "IJ07-TCV2-001-D", "panel": "IJ07-TCV2-001-R"}
REPEAT_SEEDS = (101, 211, 307)
FREEZE_INPUTS = ("dataset.py", "templates.py", "host.py", "oracle.py")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def normalized(prompt):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", prompt).casefold()).strip()


def prompts(rows):
    return {
        normalized(message["content"])
        for row in rows
        for message in row.get("messages", [{"role": "user", "content": row.get("prompt", "")}])
        if message.get("role") == "user"
    }


def overlap(left, right):
    return {
        "case_ids": len({row["id"] for row in left} & {row["id"] for row in right}),
        "normalized_user_prompts": len(prompts(left) & prompts(right)),
        "tool_names": len(
            {name for row in left for name in row["tools"]}
            & {tool["function"]["name"] for row in right for tool in row["tools"] if isinstance(tool, dict)}
        ),
    }


def rows_for(split: str) -> list[dict]:
    templates = HOLDOUT if split == "holdout" else DEV
    rows = []
    for family_index, (factory, category, count) in enumerate(templates):
        for i in range(count):
            key = f"{SEEDS[split]}:{factory.__name__}:{i}".encode()
            digest = hashlib.sha256(key).digest()
            ordinal = len(rows) + 1
            namespace = "H" if split == "holdout" else "D"
            lang = ("en", "zh")[(i + family_index) % 2]
            mark = ("keep \\ dry", 'lot "A" / west', "冷藏 & 防潮", "north  dock",
                    "内箱 <外箱>", "alpha, beta; gamma")[digest[6] % 6]
            depots = ("NORTH", "WEST", "DELTA", "HARBOR")
            units = 50 + digest[2]
            reserve = 1 + digest[3] % 45
            sample = Sample(
                f"{namespace}{ordinal:03d}-{digest.hex()[:8].upper()}", lang,
                depots[digest[0] % 4], depots[(digest[0] + 1 + digest[1] % 3) % 4],
                units, reserve, (111 + int.from_bytes(digest[4:6], "big") % 9889) / 100,
                bool(digest[7] & 1), f"{mark} [{digest.hex()[16:22]}]",
            )
            rows.append({
                "id": f"TCV2-{namespace}-{ordinal:04d}", "split": split, "template": factory.__name__,
                "category": category, "language": lang, "reasoning_required": category == "thinking_separation",
                **factory(sample),
            })
    return rows


def panel(rows: list[dict]) -> list[str]:
    selected = set()
    for index, (factory, _, _) in enumerate(HOLDOUT):
        for lang, size in (("en", 3 - index % 2), ("zh", 2 + index % 2)):
            stratum = [row["id"] for row in rows if row["template"] == factory.__name__ and row["language"] == lang]
            selected.update(sorted(stratum, key=lambda case_id: sha(f"{SEEDS['panel']}:{case_id}".encode()))[:size])
    return [row["id"] for row in rows if row["id"] in selected]


def frozen_files() -> dict[str, bytes]:
    splits = {split: rows_for(split) for split in FILES}
    holdout, dev = splits["holdout"], splits["dev"]
    source_manifest = json.loads((HISTORICAL[0].parent / "dataset.manifest.json").read_bytes())
    source_digests = {row["path"]: row["sha256"] for row in source_manifest["files"]}
    inputs = {}
    for path in HISTORICAL:
        digest = sha(path.read_bytes())
        if source_digests[path.name] != digest:
            raise ValueError(f"historical dataset freeze failed: {path.name}")
        intersection = overlap(holdout + dev, read_rows(path))
        if any(intersection.values()):
            raise ValueError(f"historical overlap in {path.name}: {intersection}")
        inputs[path.name] = {"sha256": digest, "overlap": intersection}
    if ({row["id"] for row in holdout} & {row["id"] for row in dev}
            or {row["template"] for row in holdout} & {row["template"] for row in dev}
            or prompts(holdout) & prompts(dev)):
        raise ValueError("development and holdout split overlap")

    data = {}
    manifest = {
        "format": "TC-V2/1.0", "inputs": inputs,
        "authored_source_sha256": {name: sha((HERE / name).read_bytes()) for name in FREEZE_INPUTS},
        "seed_labels": SEEDS, "split": {},
        "first_pass_seed": 47, "streaming_pair": "every holdout case, full independent trajectory",
        "repeat": {
            "cases": panel(holdout), "seeds": list(REPEAT_SEEDS),
            "selection": "Five per template, hash-ranked within language, 25 English and 25 Chinese total",
        },
    }
    for split, rows in splits.items():
        if len(rows) != COUNTS[split] or len({row["id"] for row in rows}) != len(rows) or len(prompts(rows)) != len(rows):
            raise ValueError(f"incorrect case count or duplicate ID/prompt in {split}")
        name = FILES[split]
        data[name] = b"".join(json_bytes(row) + b"\n" for row in rows)
        manifest["split"][split] = {
            "path": name, "sha256": sha(data[name]), "case_count": len(rows),
            "category_counts": dict(Counter(row["category"] for row in rows)),
            "template_counts": dict(Counter(row["template"] for row in rows)),
            "language_counts": dict(Counter(row["language"] for row in rows)),
        }
    data["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    return data


def load(split: str) -> tuple[list[dict], dict]:
    if split not in FILES:
        raise ValueError("unknown split")
    verify = frozen_files()
    for name, data in verify.items():
        if (HERE / name).read_bytes() != data:
            raise ValueError(f"dataset freeze differs from reproducible source: {name}")
    return read_rows(HERE / FILES[split]), json.loads(verify["manifest.json"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write a new freeze in an explicit empty directory")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.write:
        if not args.output:
            parser.error("--write requires --output")
        args.output.mkdir(parents=True, exist_ok=True)
        data = frozen_files()
        if any((args.output / name).exists() for name in data):
            parser.error("freeze artifacts already exist in the output directory")
        for name, content in data.items():
            (args.output / name).write_bytes(content)
    elif args.output:
        parser.error("--output applies with --write")
    else:
        load("holdout")
    print("TC-V2 freeze verified")


if __name__ == "__main__":
    main()
