#!/usr/bin/env python3
"""PR-D01 offline audit: request-level information-equivalence manifest.

Renders every arm's request for one representative task per family and
extracts which legitimate task information the MODEL can actually see
(prompt body / rendered tool definitions) versus which is only enforced
by sampling constraints (schema/grammar are request-side constraints,
not prompt-visible information)."""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmarks" / "ij_nano"))
from n02r import arms, tasks  # noqa: E402


def visible_info(arm: str, task: dict) -> dict:
    path, body = arms.build_request(arm, task, 1024, "enable_thinking")
    prompt_text = ""
    tool_defs = []
    if path == "/v1/chat/completions":
        prompt_text = "\n".join(m.get("content") or "" for m in body.get("messages", []))
        for t in body.get("tools") or []:
            fn = t.get("function", {})
            tool_defs.append(fn.get("name"))
    else:
        prompt_text = body.get("prompt") or ""
    schema = None
    if "response_format" in body:
        schema = body["response_format"]["json_schema"]["schema"]
    elif "json_schema" in body:
        schema = body["json_schema"]
    grammar = body.get("grammar")

    def schema_enums(s):
        found = []
        if isinstance(s, dict):
            if isinstance(s.get("enum"), list):
                found.append(s["enum"])
            for v in s.values():
                found.extend(schema_enums(v))
        elif isinstance(s, list):
            for v in s:
                found.extend(schema_enums(v))
        return found

    g_enum = re.findall(r'"([A-Za-z0-9_.\-]+)"', grammar or "")
    return {
        "arm": arm, "path": path,
        "prompt_chars": len(prompt_text),
        "prompt_lists_tool_names": bool(re.search(
            r"orders\.|inventory\.|logistics\.|customers\.|refunds\.|warehouse\.|"
            r"receiving\.|picking\.|reports\.|alerts\.|addresses\.|customs\.|"
            r"labels\.|couriers\.|escalations\.|notify\.", prompt_text)),
        "prompt_lists_tool_descriptions": "查询" in prompt_text or "check " in prompt_text.lower(),
        "prompt_lists_candidates": bool(re.search(
            r"must be one of|Available answers|available actions|可选动作", prompt_text)),
        "tools_in_request": sorted(tool_defs),
        "constraint_enums_not_in_prompt": (schema_enums(schema) if schema
                                           else ([g_enum[:12]] if g_enum else [])),
        "constraint_kind": ("json_schema" if schema else
                            "gbnf" if grammar else "none"),
    }


def main() -> int:
    manifest = {"schema": "ij_nano.n02r.pr_d01_information_manifest",
                "families": {}}
    for fam in tasks.FAMILIES:
        task = next(t for t in tasks.build_suite() if t["family"] == fam)
        rows = {}
        for arm in arms.ARMS:
            rows[arm] = visible_info(arm, task)
        manifest["families"][fam] = {
            "representative_task": task["task_id"],
            "arms": rows,
            # P5 renders tool definitions INTO the rendered prompt via the
            # chat template; schemas/grammars constrain sampling only.
            "verdict_note": (
                "prompt-visible information differs by arm; see "
                "prompt_lists_* and tools_in_request columns"),
        }
    out = ROOT / "evidence" / "IJNANO" / "N02R" / "pr_d01_information_manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    # human-readable digest
    for fam, f in manifest["families"].items():
        print(f"== {fam} ({f['representative_task']}) ==")
        for arm, r in f["arms"].items():
            print(f"  {arm}: prompt_candidates={r['prompt_lists_candidates']} "
                  f"prompt_tools={r['prompt_lists_tool_names']} "
                  f"tools_in_req={len(r['tools_in_request'])} "
                  f"constraint={r['constraint_kind']} "
                  f"(constraint enums NOT prompt-visible: "
                  f"{any(r['constraint_enums_not_in_prompt'])})")
    print(f"\nmanifest -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
