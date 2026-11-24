"""Load the byte-identified MULTITOOL-V1 fixture freeze."""

from dataclasses import dataclass
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from benchmarks.tool_calling_v2.evaluator import Node, Ref, Workflow
from benchmarks.tool_calling_v2.oracle import Effect, FinalAnswer, StateOracle
from business_tools.store import TABLES


ROOT = Path(__file__).with_name("frozen")
DEPTHS = ((2, 3), (4, 5), (6, 10), (11, 15), (16, 20))
CATEGORIES = tuple(f"MT-{n:02}" for n in range(1, 9))
LANGUAGES = ("en", "zh", "mixed")
SEEDS = (48707, 65719, 98123)
FILES = ("prompts.jsonl", "worlds.jsonl", "oracles.jsonl", "tools.json", "repeat_panel.json")


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def object_schema(**properties):
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def deserialize(value):
    if isinstance(value, dict):
        if value.keys() == {"$ref"}:
            node, *path = value["$ref"]
            return Ref(node, tuple(path))
        return {key: deserialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [deserialize(item) for item in value]
    return value


@dataclass(frozen=True)
class Case:
    case_id: str
    prompt: dict
    world: dict
    oracle: dict
    tools: dict

    def model_input(self):
        return {"messages": [{"role": "user", "content": self.prompt["text"]}],
                "tools": [{"type": "function", "function": {"name": name, **deepcopy(self.tools[name])}}
                          for name in self.prompt["tools"]]}

    def workflow(self):
        nodes = tuple(Node(node["id"], node["tool"], deserialize(node["arguments"]),
                           tuple(node["depends_on"]), node["result"]) for node in self.oracle["nodes"])
        schemas = {name: self.tools[name]["parameters"] for name in self.prompt["tools"]}
        state = None
        if self.oracle["state"] is not None:
            initial = {table: {} for table in TABLES if table != "audit_events"}
            state = StateOracle({**initial, **self.oracle["state"]["before"]},
                                {**initial, **self.oracle["state"]["after"]},
                                tuple(Effect(**effect) for effect in self.oracle["state"]["effects"]))
        return Workflow(nodes, schemas, frozenset(self.oracle["forbidden"]),
                        FinalAnswer(self.oracle["answer"]), state)


@dataclass(frozen=True)
class Freeze:
    active: dict[str, Case]
    controls: dict[str, Case]
    panel: dict
    manifest: dict


def _case_rows(payload):
    rows = {}
    for line in payload.splitlines():
        row = json.loads(line)
        identity = row.pop("case_id")
        if identity in rows:
            raise ValueError(f"duplicate case identity {identity}")
        rows[identity] = row
    return rows


def load_freeze(root=ROOT):
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_bytes())
    payloads = {name: (root / name).read_bytes() for name in FILES}
    hashes = {name: sha256(value).hexdigest() for name, value in payloads.items()}
    if hashes != manifest["sha256"] or sha256(canonical(hashes)).hexdigest() != manifest["freeze_sha256"]:
        raise ValueError("MULTITOOL-V1 frozen file digest mismatch")
    prompts, worlds, oracles = (_case_rows(payloads[name]) for name in FILES[:3])
    if prompts.keys() != worlds.keys() or prompts.keys() != oracles.keys():
        raise ValueError("case identities differ between frozen partitions")
    tools = json.loads(payloads["tools.json"])
    groups = {"holdout": {}, "diagnostic": {}}
    for case_id, prompt in prompts.items():
        groups[prompt["split"]][case_id] = Case(case_id, prompt, worlds[case_id], oracles[case_id], tools)
    return Freeze(groups["holdout"], groups["diagnostic"], json.loads(payloads["repeat_panel.json"]), manifest)
