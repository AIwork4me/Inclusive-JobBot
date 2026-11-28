"""Load paired JOB-V1 inputs and private business expectations."""

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from ..statistics import ARMS, CONTRASTS, select_repeats


ROOT = Path(__file__).with_name("frozen")
CATEGORIES = ("document-review", "customer-service", "product-information")
LANGUAGES = ("en", "zh", "mixed")
REPEAT_SEED = 23001
TRIAL_SEEDS = (17, 31, 83)
FILES = ("planned-cases.json", "tasks.jsonl", "worlds.jsonl", "oracles.jsonl",
         "repeat-selection.json", "experiment.json")
SHARED_RULES = (
    "Use the latest authoritative information and retain source evidence. Stop for clarification if a material ambiguity remains. "
    "Respect scoped permissions. The task grants no confirmed business submission, stock reservation, or ticket creation."
)
BUDGET = {"model_requests": 12, "output_tokens": 8192, "tool_proposals": 32,
          "user_followups": 2, "machine_ms": 300000}
TREATMENTS = dict(zip(ARMS, ("general_agent", "specialized_schema", "deterministic_orchestration",
                             "purpose_built_small_model", "purpose_built_reference_model", "no_llm_deterministic")))


def canonical(payload):
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def digest(payload):
    return sha256(canonical(payload)).hexdigest()


@dataclass(frozen=True)
class Case:
    plan: dict
    task: dict
    world: dict
    expected: dict

    def input_initial(self):
        return {"operator_message": self.task["operator_message"],
                "attachments": deepcopy(self.task["attachments"]),
                "shared_rules": SHARED_RULES}

    def pairing_sha256(self):
        return digest({"category": self.plan["category"], "routine": self.plan["routine"], "task": self.task,
                       "world": self.world, "common_rules": SHARED_RULES, "budget": BUDGET})


@dataclass(frozen=True)
class Freeze:
    cases: dict[str, Case]
    experiment: dict
    repeat: dict
    manifest: dict


def experiment_contract():
    return {"arms": {arm: {"treatment": TREATMENTS[arm], "status": "NOT_RUN", "measured_rows": 0}
                     for arm in ARMS},
            "contrasts": [list(pair) for pair in CONTRASTS],
            "shared_rules": SHARED_RULES, "budget": BUDGET,
            "planned_business_records": 3600, "planned_repeat_records": 900}


def repeat_selection(plans):
    return select_repeats(plans, n=50, seed=REPEAT_SEED, trial_seeds=TRIAL_SEEDS)


def _index(rows):
    indexed = {}
    for row in rows:
        key = row["case_id"]
        if key in indexed:
            raise ValueError(f"duplicate JOB-V1 case identifier {key}")
        indexed[key] = row
    return indexed


def load(root=ROOT):
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_bytes())
    content = {name: (root / name).read_bytes() for name in FILES}
    hashes = {name: sha256(raw).hexdigest() for name, raw in content.items()}
    if hashes != manifest["sha256"] or digest(hashes) != manifest["freeze_sha256"]:
        raise ValueError("JOB-V1 freeze digest mismatch")
    plans = _index(json.loads(content["planned-cases.json"]))
    indexed = [_index(json.loads(line) for line in content[name].splitlines()) for name in FILES[1:4]]
    if any(plans.keys() != group.keys() for group in indexed):
        raise ValueError("unpaired JOB-V1 partitions")
    cases = {key: Case(plan, *(group[key] for group in indexed)) for key, plan in plans.items()}
    if any(case.plan["pairing_sha256"] != case.pairing_sha256() for case in cases.values()):
        raise ValueError("JOB-V1 pairing digest mismatch")
    return Freeze(cases, json.loads(content["experiment.json"]), json.loads(content["repeat-selection.json"]), manifest)
