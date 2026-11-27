"""Bind an independently reviewed read-only release to the MULTITOOL-V2 0.3 roster."""

from pathlib import Path
import re

from evaluation.aeve.archive import digest
from evaluation.aeve.gpu_handoff import HANDOFF, require_handoff
from evaluation.aeve.runtime import ROOT

from .multitool_v2_cases import TOOLS
from .multitool_v2_revised import FOLDER, VERSION
from .multitool_v2_statistics import registered_roster
from .multitool_v2_witness import parse_message
from .planning_roster import is_sha256, object_json, pinned_content


READ_ONLY_MECHANICAL = "READ_ONLY_MECHANICAL"
STATEFUL_SCOPES = ("STRICT", "STATEFUL", "AFFIRMATIVE_WRITE")
CANDIDATE_MANIFEST_SHA256 = "bc9daa18fb5c9dafc63945c5c791637c3b263b3a8d207e5b72dd3ac10264114c"
ROSTER_SHA256 = "7b7b54d2a151942dbe06fb639a5d67cca0431cde358dcf619439717c5e395a8a"
REVIEW_CAPSULE = "reports/SLM10_MULTITOOL_V2_CONTENT_REVIEW.md"
REVIEW_CAPSULE_SHA256 = "be1c7d251b166f4ba736489c3f17702a85a51de341e5cbd62ccfd11c2c1fc870"
EVALUATION_CONTRACT = "atlas/slm/v1.0/evaluation_contract.json"
EVALUATION_CONTRACT_SHA256 = "4626897c8e443ade1a07070d5f37457f9d99b84e8c613c5888f6045e7d5fef88"
CREDENTIALS = ("release_review", "matched_runner", "runtime_admission", "hardware_handoff", "evaluation")
READ_ONLY_MECHANICS = ("public_contract", "provider_tool_linkage", "actual_call_path", "business_facts", "read_only_scope")
READ_ONLY_DIMENSIONS = {"D23": "NOT_RUN", "D24_affirmative": "NOT_RUN", "D25": "BLOCKED"}
TRIAL_FIELDS = {"suite", "candidate", "case_id", "input_sha256", "world_sha256", "oracle_sha256", "track", "seed", "trial_id"}
READ_ONLY_CALLBACKS = frozenset((
    "read_calibration", "read_tolerance", "read_label", "read_translation", "read_layout_revision",
    "read_archive_total", "read_live_totals", "read_maintenance_gate", "read_open_route", "read_bypass_route",
    "read_caption", "preview_caption", "read_image_source", "read_alternate_source", "read_image_metadata",
    "read_booking", "read_venue_access", "read_consent", "read_public_excerpt", "read_redaction_guide",
))


def _read_only_event(public, event):
    if public.get("category") != "scope_update":
        return event is None
    if (not isinstance(event, dict) or event.keys() != {"after_tool", "event_id", "message"}
            or event["after_tool"] != "read_booking" or event["after_tool"] not in public["tools"]
            or not isinstance(event["event_id"], str) or not event["event_id"]
            or not isinstance(event["message"], str)):
        return False
    try:
        update = parse_message(event["message"])
    except ValueError:
        return False
    return (update.keys() == {"venue", "refs"} and isinstance(update["venue"], str) and bool(update["venue"])
            and isinstance(update["refs"], list) and bool(update["refs"])
            and all(isinstance(item, str) and item for item in update["refs"]))


def require_read_only_case(public, world, oracle):
    """Check the versioned allowlist and every offered or referenced callback."""
    tools = public["tools"]
    expected = {name: {"description": TOOLS[name][0], "parameters": TOOLS[name][1]}
                for name in tools if name in READ_ONLY_CALLBACKS}
    if (not tools or tools != expected or world.keys() != {"case_id", "records", "event"}
            or not _read_only_event(public, world["event"])
            or not world["records"].keys() <= tools.keys() or not {node["tool"] for node in oracle["actions"]} <= tools.keys()
            or oracle["schemas"] != {name: definition["parameters"] for name, definition in tools.items()}
            or public["case_id"] != world["case_id"] or public["case_id"] != oracle["case_id"]):
        raise ValueError("candidate case exceeds the versioned MULTITOOL read-only scope")


def _source_binding():
    manifest = object_json(pinned_content(FOLDER, "manifest.json", CANDIDATE_MANIFEST_SHA256))
    if (manifest["version"] != VERSION or manifest["files"]["roster.json"] != ROSTER_SHA256
            or manifest["formal_roster_freeze"] != "NOT_RUN" or manifest["formal_dispatch"] != "BLOCKED"):
        raise ValueError("MULTITOOL 0.3 release source or recorded disposition differs")
    pinned_content(ROOT, REVIEW_CAPSULE, REVIEW_CAPSULE_SHA256)
    pinned_content(ROOT, EVALUATION_CONTRACT, EVALUATION_CONTRACT_SHA256)
    return {"release_scope": READ_ONLY_MECHANICAL, "candidate_manifest_sha256": CANDIDATE_MANIFEST_SHA256,
            "roster_sha256": ROSTER_SHA256, "review_capsule_sha256": REVIEW_CAPSULE_SHA256}


def _verified_trial(trial):
    if (not isinstance(trial, dict) or not TRIAL_FIELDS <= trial.keys() or type(trial["seed"]) is not int
            or not is_sha256(trial["trial_id"])):
        raise ValueError("MULTITOOL trial lacks an exact roster identity")
    manifest, trials, cases = registered_roster()
    expected = trials.get(trial["trial_id"])
    if (manifest != CANDIDATE_MANIFEST_SHA256 or expected is None
            or any(key not in expected or type(expected[key]) is not type(value) or expected[key] != value
                   for key, value in trial.items())):
        raise ValueError("MULTITOOL trial differs from the pinned roster identity")
    require_read_only_case(*cases[expected["case_id"]])
    return expected


def _runtime_identity(trial, runtime):
    profile = "DIRECT_NATIVE" if trial["track"] == "direct_first" else "SDK_NATIVE"
    digests = ("engine_binary_sha256", "model_sha256", "host_sha256", "gpu_physical_sha256", "runner_sha256")
    identifiers = ("engine_build", "model_revision", "runtime_session_id", "run_id")
    if profile == "SDK_NATIVE":
        digests += ("sdk_binary_sha256",)
        identifiers += ("sdk_version",)
    if (not isinstance(runtime, dict) or not isinstance(runtime.get("git_sha"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", runtime["git_sha"])
            or runtime.get("candidate") != trial["candidate"] or runtime.get("backend") != "vulkan"
            or runtime.get("profile") != profile or any(not is_sha256(runtime.get(key)) for key in digests)
            or any(not isinstance(runtime.get(key), str) or not runtime[key].strip() for key in identifiers)):
        raise ValueError("MULTITOOL release requires exact candidate, local Direct or SDK runtime, and hardware identities")
    return {name: runtime[name] for name in ("candidate", "git_sha", "backend", "profile", *digests, *identifiers)}


def _verify_credential(folder, name, pin, bindings):
    try:
        record = object_json(pinned_content(folder, f"{name}.json", pin))
        fields = {"credential", "status", "bindings", "evidence_path", "evidence_sha256"}
        if (record.keys() != fields or record["credential"] != name or record["status"] != "PASS"
                or record["bindings"] != bindings):
            raise ValueError("credential has different bindings or disposition")
        pinned_content(folder, record["evidence_path"], record["evidence_sha256"])
    except (OSError, ValueError) as error:
        raise ValueError(f"MULTITOOL release credential does not establish {name}") from error


def require_release_binding(trial, runtime, credential_pins, credential_folder, *, release_scope=READ_ONLY_MECHANICAL):
    """Verify externally registered pins and return a read-only binding without launching any work.

    The trusted release caller supplies the pins independently of the candidate, model, and runtime.
    The content review documents the input to release review. It carries no release authority itself.
    """
    if release_scope in STATEFUL_SCOPES:
        raise ValueError("MULTITOOL stateful or affirmative release requires a separately reviewed stateful roster and runtime evidence")
    if release_scope != READ_ONLY_MECHANICAL:
        raise ValueError("MULTITOOL requires a recognized release scope")
    if not isinstance(credential_pins, dict) or credential_pins.keys() != set(CREDENTIALS):
        raise ValueError("MULTITOOL requires independent credential pins for the read-only scope")
    source = _source_binding()
    verified = _verified_trial(trial)
    identity = _runtime_identity(verified, runtime)
    hardware = {name: identity[name] for name in ("host_sha256", "gpu_physical_sha256")}
    evaluation = {"evaluation_contract_sha256": EVALUATION_CONTRACT_SHA256,
                  "mechanics": dict.fromkeys(READ_ONLY_MECHANICS, "PASS"), "dimensions": dict(READ_ONLY_DIMENSIONS)}
    requirements = {
        "release_review": source,
        "matched_runner": source | {"runner_sha256": identity["runner_sha256"], "profile": identity["profile"]},
        "runtime_admission": source | identity,
        "hardware_handoff": hardware | {"handoff_sha256": digest(ROOT / HANDOFF)},
        "evaluation": source | evaluation,
    }
    for name, bindings in requirements.items():
        _verify_credential(Path(credential_folder), name, credential_pins[name], bindings)
    handoff = require_handoff(ROOT)
    if any(handoff["lease"].get(name) != value for name, value in hardware.items()):
        raise ValueError("MULTITOOL release runtime differs from the verified hardware handoff")
    return verified | source | identity | evaluation | {
        "credential_sha256": dict(credential_pins), "scope_binding": "PASS", "formal_release": "NOT_RUN",
        "formal_dispatch": "BLOCKED",
        "physical_execution": "NOT_RUN", "strict_e2e": "BLOCKED",
    }
