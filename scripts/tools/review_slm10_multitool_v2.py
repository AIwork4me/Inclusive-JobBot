"""Reproduce the separate content review of the MULTITOOL-V2 0.2 candidate."""

from collections import Counter, defaultdict
from copy import deepcopy
import json

from benchmarks.slm10 import multitool_v2_balanced as balanced
from evaluation.aeve.archive import digest
from evaluation.aeve.runtime import ROOT, canonical


def data(message):
    return json.loads(message.split("\nDATA ", 1)[1])


class Observations:
    def __init__(self, records):
        self.records = records
        self.attempts = Counter()
        self.route = []

    def read(self, tool, **arguments):
        locator = canonical(arguments).decode()
        key = (tool, locator)
        index = self.attempts[key]
        self.attempts[key] += 1
        self.route.append(key)
        return self.records[tool][locator][index]

    def terminal(self, tool, ref):
        record = self.read(tool, ref=ref)
        while record.get("next_ref") is not None:
            record = self.read(record.get("next_tool", tool), ref=record["next_ref"])
        return record


def expected_business_facts(category, request, host_event, records):
    """Derive one interpretation from public inputs and raw fixture observations."""
    if category == "parallel":
        facts = {"values": {target["ref"]: records.read(**target)["value"] for target in request["targets"]}}
        return facts, "independent_reads", 1
    if category == "serial":
        facts = {"label": records.terminal(**request["start"])["label"]}
        return facts, "successor_chain", len(records.route)
    if category == "aggregation":
        refs = request["collections"]
        archive = {ref: records.read("read_archive_total", ref=ref)["units"] for ref in refs}
        current = records.read("read_live_totals", refs=refs)["counts"]
        conflicts = [ref for ref in refs if archive[ref] != current[ref]]
        return {"total": sum(current.values()), "conflicts": conflicts}, "different_counts" if conflicts else "matching_counts", 2
    if category == "conditional":
        gate = records.read("read_maintenance_gate", ref=request["gate"])
        choice = "main" if gate["open"] else "bypass"
        tool = {"main": "read_open_route", "bypass": "read_bypass_route"}[choice]
        facts = {"destination": records.terminal(tool, gate[f"{choice}_ref"])["destination"]}
        return facts, choice, len(records.route)
    if category == "typed_transfer":
        entries = [records.read("read_caption", ref=ref)["entry"] for ref in request["captions"]]
        form = {"entries": entries, "format": request["format"], "preserve_order": True}
        facts = {"preview_id": records.read("preview_caption", preview=form)["preview_id"]}
        return facts, request["format"], 2
    if category == "recovery":
        initial = records.read("read_image_source", ref=request["primary"])
        if initial["status"] == "retryable":
            terminal = records.terminal("read_image_source", request["primary"])
        elif initial["status"] == "unavailable":
            terminal = records.terminal("read_alternate_source", initial["mirror_ref"])
        else:
            raise ValueError("unreviewed primary result")
        return {"checksum": terminal["checksum"]}, initial["status"], len(records.route)
    if category == "scope_update":
        records.read("read_booking", ref=request["booking"])
        scope = data(host_event["message"])
        venue = scope["venue"]
        features = {ref: records.read("read_venue_access", venue=venue, ref=ref)["feature"] for ref in scope["refs"]}
        return {"venue": venue, "features": features}, "updated_scope", 2
    if category == "authorization":
        consent = records.terminal("read_consent", request["consent"])
        decision = consent["decision"]
        tool = {"permitted": "read_public_excerpt", "withheld": "read_redaction_guide"}[decision]
        note = records.read(tool, ref=consent["guide_ref"])["note"]
        return {"decision": decision, "note": note}, decision, len(records.route)
    raise ValueError(f"unreviewed category {category}")


def critical_path(actions):
    depths = {node["action_id"]: 0 for node in actions}
    pending = list(actions)
    while pending:
        ready = [node for node in pending if all(depths[parent] for parent in node["depends_on"])]
        if not ready:
            raise ValueError("invalid case dependencies")
        for node in ready:
            depths[node["action_id"]] = 1 + max((depths[parent] for parent in node["depends_on"]), default=0)
            pending.remove(node)
    return max(depths.values())


def route_probes(rows):
    # Use production evaluation here to see whether specific route mutations
    # are accepted. Witnesses never supply the independent factual expectations.
    from benchmarks.slm10.multitool_v2_candidate import evaluate
    from benchmarks.slm10.multitool_v2_witness import Scenario, witness

    typed = [row for row in rows if row[0]["category"] == "typed_transfer" and row[0]["required_actions"] >= 3]
    reversed_caption_reads = Counter()
    for public, world, graph in typed:
        sample = witness(public, world)
        calls = list(reversed(sample["calls"][:-1])) + sample["calls"][-1:]
        for turn, call in enumerate(calls):
            call.update(turn=turn, completion_id=f"reversed-caption-{turn}")
        reversed_caption_reads[evaluate(public, world, graph, sample | {"calls": calls})["status"]] += 1

    stale_scope_reads = Counter()
    for public, world, _ in rows:
        if public["category"] != "scope_update":
            continue
        service = Scenario(public, world)
        booking = data(public["message"])["booking"]
        result, _ = service.read("read_booking", {"ref": booking}, 0, "booking")
        service.take_event(1)
        stale_args = {"venue": result["venue"], "ref": result["refs"][0]}
        try:
            observed, _ = service.read("read_venue_access", stale_args, 1, "stale")
        except ValueError:
            stale_scope_reads["rejected"] += 1
        else:
            stale_scope_reads[observed["feature"]] += 1
    return {"reversed_caption_reads": dict(reversed_caption_reads), "sandbox_stale_scope_reads": dict(stale_scope_reads)}


def review():
    rows, repeats = balanced.candidate()
    bands = ((2, 3), (4, 5), (6, 10), (11, 15), (16, 20))
    by_band = Counter()
    repeat_bands = Counter()
    repeat_cross = Counter()
    exact_counts = Counter()
    intent_templates = set()
    expected_mismatches = []
    branch_counts = defaultdict(Counter)
    complexity = defaultdict(Counter)
    leak_predictions = Counter()
    predictable_branches = {"conditional": ("gate", "main"), "recovery": ("primary", "retryable"),
                            "authorization": ("consent", "permitted")}
    for public, world, graph in rows:
        category, key = public["category"], public["case_id"]
        request = data(public["message"])
        observations = Observations(world["records"])
        facts, branch, dependency_depth = expected_business_facts(category, request, world["event"], observations)
        actual_depth = critical_path(graph["actions"])
        count = public["required_actions"]
        graph_reads = [(node["tool"], canonical(node["arguments"]).decode()) for node in graph["actions"]]
        if (facts != graph["answer"] or observations.route != graph_reads or len(graph_reads) != count
                or actual_depth != dependency_depth or actual_depth != graph["critical_path"]):
            expected_mismatches.append(key)
        band = next(f"{lo}-{hi}" for lo, hi in bands if lo <= count <= hi)
        by_band[band, category, public["language"]] += 1
        exact_counts[count] += 1
        branch_counts[category][branch] += 1
        complexity[category][actual_depth] += 1
        intent_templates.add(public["message"].split("\nDATA ", 1)[0])
        if key in repeats:
            repeat_bands[band] += 1
            repeat_cross[band, category, public["language"]] += 1
        public_id, even_branch = predictable_branches.get(category, (None, None))
        if public_id and (int(request[public_id][-1], 16) % 2 == 0) == (branch == even_branch):
            leak_predictions[category] += 1

    messages = {public["message"] for public, _, _ in rows}
    historical = ROOT / "benchmarks/multitool_v1/frozen/prompts.jsonl"
    old_messages = {json.loads(line)["text"] for line in historical.read_bytes().splitlines()}
    return {"manifest_sha256": digest(balanced.FOLDER / "manifest.json"), "cases": len(rows),
            "literal_distinct_prompts": len(messages), "literal_historical_matches": len(messages & old_messages),
            "instruction_templates": len(intent_templates), "repeat_cases": len(repeats),
            "first_band_cell_histogram": dict(Counter(by_band.values())), "repeat_bands": dict(repeat_bands),
            "repeat_occupied_cross_cells": len(repeat_cross), "exact_action_counts": dict(exact_counts),
            "expected_mismatches": expected_mismatches, "branches": dict(branch_counts),
            "dependency_depth_histograms": dict(complexity), "public_id_branch_predictions": dict(leak_predictions),
            **route_probes(rows)}


if __name__ == "__main__":
    print(json.dumps(review(), sort_keys=True))
