"""Load versioned job skill manifests and workflows."""

from dataclasses import dataclass
import json
from pathlib import Path

from sop_engine import Step, Workflow


@dataclass(frozen=True)
class Skill:
    name: str
    version: str
    workflow: Workflow

    @classmethod
    def load(cls, path: Path):
        # Each YAML file uses the JSON subset, so loading never evaluates tags.
        manifest = json.loads((path / "job_manifest.yaml").read_text(encoding="utf-8"))
        plan = json.loads((path / "sop.yaml").read_text(encoding="utf-8"))
        if manifest["schema_version"] != 1 or plan["version"] != manifest["version"]:
            raise ValueError("Unsupported skill or mismatched SOP version")
        workflow = Workflow(tuple(
            Step(row["id"], tuple(row["depends_on"]), row["operation"]) for row in plan["steps"]
        ))
        return cls(manifest["id"], manifest["version"], workflow)
