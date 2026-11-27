"""Replay the portable LFM3-HA hashes and native numerical controls."""

from itertools import combinations
import json

from evaluation.aeve.archive import digest
from evaluation.aeve.runtime import ROOT

from .lfm3_ha_admission import ATLAS, compare, equivalent, intervention


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def verify():
    manifest = json.loads((ATLAS / "EVIDENCE_MANIFEST.json").read_bytes())
    for name, expected in manifest["files"].items():
        target = (ROOT / name).resolve()
        require(target.is_relative_to(ROOT) and digest(target) == expected, f"artifact differs: {name}")
    admission = json.loads((ATLAS / "RADEON_ADMISSION.json").read_bytes())
    baseline = admission["arms"]["Original"]
    require(baseline["status"] == "PASS" and all(compare(
        baseline["baseline"], baseline["baseline_repeat"], equivalent)), "Original numerical replay differs")
    registered = json.loads((ATLAS / "MODEL_ADAPTER_REGISTRY.json").read_bytes())["adapters"]
    adapted = set(admission["arms"]) - {"Original"}
    require(adapted == set(registered) and set(registered) == {"HA-O", "HA-P", "HA-H"},
            "admission must cover all three adapters")
    require(all(row["status"] == "PASS" for row in admission["load_controls"].values())
            and admission["base_reverified_after_run"] == "PASS"
            and admission["registry_sha256"] == digest(ATLAS / "MODEL_ADAPTER_REGISTRY.json"),
            "asset or load-control evidence differs")
    for arm in sorted(adapted):
        result = admission["arms"][arm]
        rows = result["native_numeric"]
        reference = baseline["baseline"]
        require(all(compare(reference, rows["zero"], equivalent)), f"{arm} zero equivalence")
        require(all(compare(reference, rows["zero_after"], equivalent)), f"{arm} zero after intervention")
        require(any(compare(reference, rows["one"], intervention)), f"{arm} intervention")
        require(all(compare(rows["one"], rows["one_repeat"], equivalent)), f"{arm} repeat")
        pinned = [artifact for filename, artifact in registered[arm]["artifacts"].items()
                  if filename.endswith(".gguf")]
        require(pinned == [result["adapter"]], f"{arm} adapter identity")
        require(result["status"] == "PASS" and result["gpu_execution"] == "PASS"
                and result["sdk_callbacks"] == "PASS" and result["sdk_confirmed_callbacks"] >= 1
                and result["wrong_base_control"]["status"] == "PASS"
                and result["guarded_route_controls"] == {"wrong_model": "PASS", "wrong_adapter": "PASS"}
                and result["native_invalid_id_http_status"] == 200 and result["unguarded_native_route"] == "FAIL",
                f"{arm} transport, routing or GPU disposition differs")
    for left, right in combinations(sorted(adapted), 2):
        left_numeric = admission["arms"][left]["native_numeric"]["one"]
        right_numeric = admission["arms"][right]["native_numeric"]["one"]
        require(any(compare(left_numeric, right_numeric, intervention)), "adapter outputs were indistinguishable")

    panel = json.loads((ATLAS / "CROSS_HARNESS_TRANSFER_MATRIX.json").read_bytes())
    require(len(panel["arms"]) == 8 and sum(arm["planned"] for arm in panel["arms"]) == 480
            and sum(arm["NOT_RUN"] for arm in panel["arms"]) == 480
            and panel["core_trial_attribution"] == admission["core_trial_attribution"] == 0,
            "development scope or trial counts differ")
    for name, expected in panel["files"].items():
        target = ATLAS / name
        require(digest(target) == expected and len(target.read_bytes().splitlines()) == 60,
                f"development input differs: {name}")
    return admission["run_id"]


if __name__ == "__main__":
    print("Portable LFM3-HA replay PASS", verify())
