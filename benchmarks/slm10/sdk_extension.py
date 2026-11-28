"""Freeze independent typed workflow cases and replay source-linked controls."""

import argparse
from copy import deepcopy
from hashlib import sha256
import json

from evaluation.aeve.archive import digest
from evaluation.aeve.runtime import ROOT, canonical

from .action_graph_v2 import replay

PREVIOUS = ROOT / "atlas/slm/v1.0/sdk-extension"
FOLDER = PREVIOUS.with_name("sdk-extension-v0.2")
VERSION = "TCV3-EXT/0.2"


def obj(**properties):
    return {"type": "object", "required": sorted(properties), "properties": properties, "additionalProperties": False}


TEXT = {"type": "string"}
INT = {"type": "integer"}
FLAG = {"type": "boolean"}
TEXT_LIST = {"type": "array", "items": TEXT, "minItems": 1, "uniqueItems": True}
PROOF_LIST = TEXT_LIST | {"items": TEXT | {"enum": ["attribution", "license", "consent"]}}
SCHEMAS = {
    "catalog_profile": obj(selector=obj(campus=TEXT, filters=TEXT_LIST)),
    "catalog_stock": obj(reference=TEXT),
    "read_asset": obj(filters=obj(asset=TEXT, profile=obj(max_width=INT, channels=TEXT_LIST, lossless=FLAG))),
    "show_seat": obj(seat=TEXT, request=obj(step_free=FLAG, entrances=TEXT_LIST)),
    "access_route": obj(route=TEXT),
    "read_proof": obj(job=TEXT, proofs=PROOF_LIST),
    "check_release": obj(receipt=TEXT),
    "check_layout": obj(page=INT, settings=obj(pages=TEXT_LIST, reading_order=FLAG)),
}
TOOLS = {
    "catalog_profile": "Resolve a catalog filter to a stock reference.",
    "catalog_stock": "Return stock status for a catalog reference.",
    "read_asset": "Read scan metadata for the requested asset and profile. Some snapshots are temporarily stale.",
    "show_seat": "Return seat access metadata scoped to the requested access constraints.",
    "access_route": "Check the route linked by a seat observation.",
    "read_proof": "Check required releasability proofs for a graphics job and return a receipt.",
    "check_release": "Read whether a release receipt is current. No release is performed.",
    "check_layout": "Inspect a page using the supplied reading order and page labels.",
}


def node(identity, tool, args, result, deps=(), sources=None):
    return {"action_id": identity, "tool": tool, "arguments": args, "observation": result,
            "depends_on": list(deps), "input_sources": sources or {}}


def case(identity, family, lang, prompt, actions, answer, distractors=()):
    tools = sorted({row["tool"] for row in actions} | set(distractors))
    public = {"case_id": identity, "family": family, "language": lang, "prompt": prompt,
              "tools": {tool: {"description": TOOLS[tool], "parameters": SCHEMAS[tool]} for tool in tools}}
    graph = {"case_id": identity, "schemas": {name: SCHEMAS[name] for name in tools},
             "actions": actions, "answer": answer}
    return public, graph


def cases():
    yield "development", case("EXT-D-CATALOG", "catalog_stock", "en",
        "Resolve the campus East catalog using tags youth and art. Read stock for the returned reference.",
        [node("find-profile", "catalog_profile", {"selector": {"campus": "East", "filters": ["youth", "art"]}},
              {"reference": "C-70"}),
         node("fetch-stock", "catalog_stock", {"reference": "C-70"}, {"status": "ready"},
              ("find-profile",), {"reference": ["find-profile", "reference"]})], {"status": "ready"}, ("check_layout",))
    asset = {"filters": {"asset": "SCAN38", "profile": {"max_width": 2048, "channels": ["red", "green"], "lossless": True}}}
    yield "holdout", case("EXT-H-RESCAN", "archive_scan_retry", "mixed",
        "读取 SCAN38 的 lossless scan（上限 2048 像素，red 和 green 通道）。If the snapshot marks itself stale, retry once with identical settings. Report freshness.",
        [node("stale-probe", "read_asset", asset, {"status": "stale"}),
         node("fresh-probe", "read_asset", asset, {"status": "fresh"}, ("stale-probe",))],
        {"status": "fresh"}, ("catalog_stock",))
    access = {"step_free": True, "entrances": ["East"]}
    yield "holdout", case("EXT-H-SEAT", "accessibility_route", "en",
        "Compare access metadata for seats R7 and R8 using the step-free East entrance. Verify the route for the first seat reported available.",
        [node("inspect-seat-a", "show_seat", {"seat": "R7", "request": access}, {"available": False}),
         node("inspect-seat-b", "show_seat", {"seat": "R8", "request": access}, {"available": True, "route": "RT-04"}),
         node("verify-route", "access_route", {"route": "RT-04"}, {"step_free": True},
              ("inspect-seat-a", "inspect-seat-b"), {"route": ["inspect-seat-b", "route"]})],
        {"seat": "R8", "step_free": True}, ("catalog_profile",))
    yield "holdout", case("EXT-H-RIGHTS", "media_release_proof", "zh",
        "检查图版 GRAPH09 的 attribution、license 证明。用工具返回的收据核验状态，不执行任何发布动作。",
        [node("read-proof", "read_proof", {"job": "GRAPH09", "proofs": ["attribution", "license"]}, {"receipt": "P-73"}),
         node("read-receipt", "check_release", {"receipt": "P-73"}, {"status": "verified"},
              ("read-proof",), {"receipt": ["read-proof", "receipt"]})], {"status": "verified"}, ("show_seat",))
    yield "holdout", case("EXT-H-LAYOUT", "document_layout", "en",
        "Check page 7 for a logical reading order and labels cover and detail. Return the audit finding for that page.",
        [node("verify-page", "check_layout", {"page": 7, "settings": {"pages": ["cover", "detail"], "reading_order": True}},
              {"finding": "order_valid"})], {"finding": "order_valid"}, ("read_asset",))


def qualification(dataset):
    graphs = {graph["case_id"]: graph for _, (_, graph) in dataset}
    row = graphs["EXT-H-SEAT"]
    fixture = [
        {"call_id": "q-seat-1", "completion_id": "q-0", "turn": 0, "tool": "show_seat",
         "arguments_raw": '{"seat":"R8","request":{"step_free":true,"entrances":["East"]}}',
         "observation": {"available": True, "route": "RT-04"}, "observation_sources": {}},
        {"call_id": "q-seat-2", "completion_id": "q-0", "turn": 0, "tool": "show_seat",
         "arguments_raw": '{"request":{"entrances":["East"],"step_free":true},"seat":"R7"}',
         "observation": {"available": False}, "observation_sources": {}},
        {"call_id": "q-route-3", "completion_id": "q-1", "turn": 1, "tool": "access_route",
         "arguments_raw": '{"route":"RT-04"}', "observation": {"step_free": True},
         "observation_sources": {"route": {"action_id": "inspect-seat-b", "call_id": "q-seat-1", "key": "route"}}},
    ]
    no_source = deepcopy(fixture)
    del no_source[2]["observation_sources"]
    invented = deepcopy(fixture)
    invented[2]["observation_sources"]["route"]["call_id"] = "q-seat-2"
    wrong_entity = deepcopy(fixture)
    wrong_entity[0]["arguments_raw"] = wrong_entity[1]["arguments_raw"]
    wrong_turn = deepcopy(fixture)
    wrong_turn[2]["turn"] = 0
    scenarios = [
        ("independent_positive", fixture, "PASS"), ("legal_equivalence", [fixture[1], fixture[0], fixture[2]], "PASS"),
        ("missing_provenance", no_source, "BLOCKED"), ("forged_producer", invented, "FAIL"),
        ("wrong_entity", wrong_entity, "FAIL"), ("same_turn_dependency", wrong_turn, "FAIL"),
        ("missing_action", fixture[:2], "FAIL"), ("extra_action", [*fixture, fixture[0] | {"call_id": "extra"}], "FAIL"),
    ]
    results = []
    for label, calls, expected in scenarios:
        result = replay(row, {"complete": True, "calls": calls})
        results.append({"control": label, "expected": expected, "evidence_sha256": sha256(canonical(calls)).hexdigest(),
                        "observed": result, "status": "PASS" if result["status"] == expected else "FAIL"})
    enum_mutation = [
        {"call_id": "q-proof-1", "completion_id": "q-0", "turn": 0, "tool": "read_proof",
         "arguments_raw": '{"job":"GRAPH09","proofs":["attribution","unknown"]}',
         "observation": {"receipt": "P-73"}, "observation_sources": {}},
        {"call_id": "q-proof-2", "completion_id": "q-1", "turn": 1, "tool": "check_release",
         "arguments_raw": '{"receipt":"P-73"}', "observation": {"status": "verified"},
         "observation_sources": {"receipt": {"action_id": "read-proof", "call_id": "q-proof-1", "key": "receipt"}}},
    ]
    enum_verdict = replay(graphs["EXT-H-RIGHTS"], {"complete": True, "calls": enum_mutation})
    results.append({"control": "invalid_enum_item", "expected": "FAIL",
                    "evidence_sha256": sha256(canonical(enum_mutation)).hexdigest(), "observed": enum_verdict,
                    "status": "PASS" if enum_verdict["reason"] == "ARGUMENT_SCHEMA" else "FAIL"})
    return {"scope": "software action-instance controls; EXT-H-SEAT and EXT-H-RIGHTS graphs", "physical_execution": "NOT_RUN",
            "status": "PASS" if all(r["status"] == "PASS" for r in results) else "FAIL", "controls": results}


def graph_size_controls():
    results = []
    for size in (18, 19, 20, 21):
        actions, calls = [], []
        for index in range(size):
            action_id = f"read-{index}"
            args = {"reference": f"record-{index}"}
            observation = {"next": f"record-{index + 1}"}
            parent = f"read-{index - 1}"
            actions.append({"action_id": action_id, "tool": "lookup", "arguments": args,
                            "depends_on": [parent] if index else [], "observation": observation,
                            "input_sources": {"reference": [parent, "next"]} if index else {}})
            calls.append({"call_id": f"call-{index}", "completion_id": f"completion-{index}",
                          "turn": index, "tool": "lookup", "arguments_raw": canonical(args).decode(),
                          "observation": observation, "observation_sources": {"reference": {
                              "action_id": parent, "call_id": f"call-{index - 1}", "key": "next"}} if index else {}})
        graph = {"schemas": {"lookup": obj(reference=TEXT)}, "actions": actions}
        capture = {"complete": True, "calls": calls}
        expected = "PASS" if size <= 20 else "FAIL"
        try:
            observed = replay(graph, capture)["status"]
        except ValueError as error:
            if str(error) != "graph identity or size differs from the verifier contract":
                raise
            observed = "FAIL"
        results.append({"nodes": size, "expected": expected, "observed": observed,
                        "fixture_sha256": sha256(canonical([graph, capture])).hexdigest(),
                        "status": "PASS" if observed == expected else "FAIL"})
    return results


def frozen_files():
    dataset = list(cases())
    families = {split: sorted({public["family"] for part, (public, _) in dataset if part == split})
                for split in ("development", "holdout")}
    if set(families["development"]) & set(families["holdout"]):
        raise ValueError("workflow families overlap across independent partitions")
    files = {}
    for split in families:
        for i, name in enumerate(("public", "graphs")):
            files[f"{split}-{name}.jsonl"] = b"".join(canonical(item[i]) + b"\n" for part, item in dataset if part == split)
    checks = qualification(dataset)
    checks["graph_size_controls"] = graph_size_controls()
    if any(row["status"] != "PASS" for row in checks["graph_size_controls"]):
        checks["status"] = "FAIL"
    files["software-qualification.json"] = canonical(checks) + b"\n"
    manifest = {"version": VERSION, "families": families, "formal_execution": "NOT_RUN",
                "previous_manifest_sha256": digest(PREVIOUS / "manifest.json"),
                "full_suite_qualification": "BLOCKED", "files": {name: sha256(raw).hexdigest() for name, raw in files.items()},
                "sources": {name: digest(ROOT / "benchmarks/slm10" / name) for name in ("action_graph_v2.py", "sdk_extension.py")}}
    files["manifest.json"] = canonical(manifest) + b"\n"
    return files, checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    files, controls = frozen_files()
    if args.write:
        FOLDER.mkdir(parents=True, exist_ok=True)
    for name, payload in files.items():
        path = FOLDER / name
        if args.write and not path.exists():
            path.write_bytes(payload)
        if path.read_bytes() != payload:
            raise ValueError("independent extension freeze differs")
    print(controls["status"], len(controls["controls"]), "independent graph controls")
    return 0 if controls["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
