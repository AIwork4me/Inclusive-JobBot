"""Plan scoped panels from already verified independent qualification credentials."""
import re

from .contracts import DIMENSIONS, sha

BOUND_FIELDS = (
    "model_sha256", "engine_binary_sha256", "runtime_configuration_sha256", "prompt_sha256",
    "rubric_sha256", "judgment_schema_sha256", "algorithm_sha256", "qualification_report_sha256",
)
HEX256 = re.compile("[0-9a-f]{64}")
REVISION = re.compile("[0-9a-f]{40,64}")
RISKS = {"read", "write", "critical"}


def plan_panel(profiles, subject, dimension, risk):
    """A routing plan has no authority to certify a profile or dispatch an evaluation."""
    if not subject.strip() or subject.casefold() in {"unknown", "unresolved"}:
        raise ValueError("unresolved historical subject family")
    if dimension not in DIMENSIONS or risk not in RISKS:
        raise ValueError("unknown dimension or risk range")
    selection = {}
    codes = set()
    for profile in profiles:
        if profile["status"] != "PASS" or profile["qualification_cycle"] != "Q3":
            continue
        code, family = profile.get("code", ""), profile.get("family", "")
        if (not code or not family.strip() or family.casefold() in {"unknown", "unresolved"}
                or not profile.get("quantization") or not REVISION.fullmatch(profile.get("model_revision", ""))
                or any(not HEX256.fullmatch(profile.get(field, "")) for field in BOUND_FIELDS)
                or not profile.get("scopes")):
            raise ValueError("incomplete qualified evaluator binding")
        if code in codes:
            raise ValueError("multiple qualified bindings for the same evaluator code")
        codes.add(code)
        key = family.casefold()
        if key != subject.casefold() and f"{dimension}/{risk}" in profile["scopes"]:
            selection.setdefault(key, profile)
    selected = list(selection.values())
    if len(selected) < 3:
        return {"status": "BLOCKED", "eligible_distinct_families": [item["family"] for item in selected]}
    first, second, dispute = selected[:3]
    return {"status": "PASS", "primary": [first["code"], second["code"]], "dispute": dispute["code"],
            "bindings": {item["code"]: sha(item) for item in (first, second, dispute)}}
