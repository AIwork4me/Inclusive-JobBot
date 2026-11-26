"""New holdout worlds for revised Judge configurations. Only warrants synthetic coverage."""
from argparse import ArgumentParser
from collections import Counter
import json

from .contracts import ROOT, sha
from .gold import additional_world, iter_gold, world

FOLDER = ROOT/"AEVE-GOLD-V1"/"q2-holdout"
SPLIT = "qualification-q2-v1"
PRIMARY = 1100
SECONDARY = 132


def generate():
    for index in range(PRIMARY):
        yield world(SPLIT,index)
        if index % 8 == 0:
            yield world(SPLIT,index,1)
    for index in range(SECONDARY):
        yield additional_world(SPLIT,index)


def artifacts():
    entries = list(generate())
    seen_ids = {r["base_id"] for split in ("development","calibration","qualification") for r in iter_gold(split)}
    seen_packets = {sha(r["packet"]) for split in ("development","calibration","qualification") for r in iter_gold(split)}
    if seen_ids.intersection(r["base_id"] for r in entries) or seen_packets.intersection(sha(r["packet"]) for r in entries):
        raise ValueError("revised holdout overlaps an earlier split")
    packets = [{"case_id":r["case_id"],"packet":r["packet"]} for r in entries]
    gold = [{**{k:v for k,v in r.items() if k != "packet"},"packet_sha256":sha(r["packet"])} for r in entries]
    files = {"packets.jsonl": packets,"labels.jsonl": gold}
    encoded = {n: "".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows).encode()
               for n,rows in files.items()}
    from hashlib import sha256
    manifest = {"version":SPLIT,"packets":len(entries),"independent_worlds":PRIMARY+SECONDARY,
                "labels":dict(Counter(r["expected"] for r in entries)),
                "sha256":{n:sha256(b).hexdigest() for n,b in encoded.items()},
                "label_source":"Independent executable synthetic rules using 26 shared templates and a new held-out world namespace.",
                "selection":"Each model uses the frozen development arm with most correct judgments with gold citations, then most correct verdicts, then manifest arm order. Match by exact case and family."}
    return {**encoded,"manifest.json":(json.dumps(manifest,sort_keys=True,indent=2)+"\n").encode()}


def freeze(write=False):
    if write:
        FOLDER.mkdir(parents=True,exist_ok=True)
    files = artifacts()
    for name, expected in files.items():
        path = FOLDER/name
        if write and not path.exists():
            path.write_bytes(expected)
        elif path.read_bytes() != expected:
            raise ValueError(f"revised holdout changed: {name}")
    return json.loads(files["manifest.json"])


def cases():
    freeze()
    def rows(name):
        return [json.loads(line) for line in (FOLDER/name).read_bytes().splitlines()]
    return [{**packet,**label} for packet,label in zip(rows("packets.jsonl"),rows("labels.jsonl"),strict=True)]


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--write",action="store_true")
    print(json.dumps(freeze(parser.parse_args().write)))
