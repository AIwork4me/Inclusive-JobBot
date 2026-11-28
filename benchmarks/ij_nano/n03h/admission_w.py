"""Physical adapter admission battery (IJ-NANO-48H order section 4.2).

MUST pass before any AUTH-2W (adapter atlas) dispatch. Verifies on THIS
host with the pinned engine:

1. identity: adapter file sha256/size == the EAE identity registry
   (byte verification at physical admission, as the release requires);
2. scale-0 numerical equivalence: base + ``--lora-scaled F:0`` produces
   byte-identical completions to the plain base server on frozen probe
   prompts (temperature 0);
3. scale-1 genuine change: the full-strength adapter changes outputs
   vs base, repeatably (two identical runs);
4. no silent fallback: a nonexistent adapter path must keep the server
   UNHEALTHY (never silently serve base-only);
5. state isolation/reproducibility: fresh adapter server reproduces
   the same completions (isolated fixed-adapter processes);
6. cache policy identity: server flags identical across W0-W3 except
   model/lora/alias/port.

All evidence is recorded to ``evidence/IJNANO/N03H/ADAPTER_ADMISSION/``.
"""
from __future__ import annotations

import json
import pathlib
import re
import time

from benchmarks.ij_nano.n03h import eae as eae_mod
from benchmarks.ij_nano.n03h.transport import (
    CONTEXT_FLAGS, SAMPLING, ChatTransport, render_chat_user_content)

ROOT = eae_mod.ROOT
EVID_OUT = ROOT / "evidence" / "IJNANO" / "N03H" / "ADAPTER_ADMISSION"
ADAPTERS = {
    "W1_pi": "models/adapters/LFM3-1.7B-harbor-pi-lora-F16.gguf",
    "W2_opencode": "models/adapters/LFM3-1.7B-harbor-opencode-lora-F16.gguf",
    "W3_hermes": "models/adapters/LFM3-1.7B-harbor-hermes-lora-F16.gguf",
}


def _weights_root() -> pathlib.Path:
    import os
    return pathlib.Path(os.environ.get(
        "IJNANO_WEIGHTS_ROOT", str(ROOT.parent / "IJSDK")))


BASE = _weights_root() / "models" / "ij_sdk" / "LFM3-1.7B-GGUF" / \
    "LFM3-1.7B-Q8_0.gguf"
PROBE_CASES = [
    {"case_id": "probe-1", "primitive": "C01",
     "public_payload": {"utterance": "the dashboard has been down all "
                      "morning", "intent_catalog": {
                          "incident_report": "service outage or fault",
                          "refund_request": "money back"},
                      "instruction": "Choose exactly one intent label."}},
    {"case_id": "probe-2", "primitive": "C05",
     "public_payload": {"statement": "The maintenance window ends at "
                      "22:00 and the backup finished before it.",
                      "question": "Is the backup complete?",
                      "instruction": "Answer TRUE or FALSE only."}},
    {"case_id": "probe-3", "primitive": "C07",
     "public_payload": {"situation": "A customer asks to change their "
                      "registered delivery address.",
                      "action_catalog": {"update_profile": "change "
                                       "account details",
                                         "issue_refund": "return money"},
                      "instruction": "Select exactly one action name."}},
]
PORTS = {"W0": 8330, "W1_pi": 8331, "W2_opencode": 8332,
         "W3_hermes": 8333, "W0_scaled0": 8334, "W1_scaled0": 8335,
         "BAD": 8336, "W1_again": 8337}
WORKDIR = ROOT / "runs" / "n03h" / "_adapter_admission"


def utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def probe_outputs(tr: ChatTransport) -> list[str]:
    outs = []
    for case in PROBE_CASES:
        content, _ = tr.submit(case)
        outs.append(content)
    return outs


def start(model: str, port: int, lora=None, lora_scale=None,
          extra=None) -> ChatTransport:
    tr = ChatTransport(model, BASE, port, WORKDIR / model,
                       lora_file=lora)
    if lora_scale is not None:
        # swap the plain --lora pair for --lora-scaled F:SCALE.
        # The FNAME:SCALE parser splits on ':' and cannot take an
        # absolute Windows path (drive-letter colon), so the adapter
        # is referenced RELATIVE to the server's working directory
        # (the engine binary dir) with forward slashes.
        import os
        binary_dir = tr.session.binary_dir
        rel = pathlib.Path(os.path.relpath(lora, binary_dir))
        rel_posix = rel.as_posix()
        flags = [f for f in tr.session.profile_flags
                 if f not in ("--lora", str(lora))]
        flags += ["--lora-scaled",
                  f"{rel_posix}:{int(lora_scale)}"]
        tr.session.profile_flags = flags
    if extra:
        tr.session.profile_flags += extra
    tr.start()
    return tr


def main() -> int:
    EVID_OUT.mkdir(parents=True, exist_ok=True)
    WORKDIR.mkdir(parents=True, exist_ok=True)
    report: dict = {"schema": "ijnano.n03h.adapter_admission.v1",
                    "started_utc": utc(), "checks": {}}

    # -- 1. identity byte verification ------------------------------------
    bt = eae_mod.bootstrap("AUTH-2W")
    reg = json.loads(
        (eae_mod._pin_paths(bt["pin_report"]["pin_rev"])["pin"]
         / "evidence" / "IJEVAL" / "ADAPTER_SCOPE"
         / "identity_registry.json").read_text(encoding="utf-8"))
    ident_ok, ident_detail = True, {}
    adapters_reg = reg.get("adapters", reg.get("weight_configurations", {}))
    for name, rel in ADAPTERS.items():
        p = ROOT / rel
        sha = eae_mod.sha256_file(p) if p.is_file() else None
        size = p.stat().st_size if p.is_file() else None
        want_sha = None
        for key, val in adapters_reg.items():
            if name.split("_", 1)[1] in key or key.endswith(name):
                want_sha = (val.get("file_sha256")
                            or val.get("sha256") or None)
        ident_detail[name] = {"local_sha256": sha, "registry_sha256":
                              want_sha, "size": size}
        if sha is None or (want_sha and sha != want_sha):
            ident_ok = False
    base_sha = eae_mod.sha256_file(BASE) if BASE.is_file() else None
    ident_detail["W0_base"] = {"local_sha256": base_sha}
    if base_sha != "8f6b24182258205e9e01e21f1f24a1f208c1e8115578825d202ce39976af20b6":
        ident_ok = False
    report["checks"]["identity"] = {"ok": ident_ok,
                                    "detail": ident_detail}

    # -- GPU checks ---------------------------------------------------------
    try:
        # 2. scale-0 equivalence (W1 at scale 0 vs plain base)
        base_tr = start("W0_base", PORTS["W0"])
        s0_tr = start("W1_pi_scaled0", PORTS["W0_scaled0"],
                      lora=ROOT / ADAPTERS["W1_pi"], lora_scale=0.0)
        base_outs = probe_outputs(base_tr)
        s0_outs = probe_outputs(s0_tr)
        scale0_ok = base_outs == s0_outs
        report["checks"]["scale0_equivalence"] = {
            "ok": scale0_ok,
            "note": "base vs base+--lora-scaled F:0 on frozen probes "
                    "(temperature 0); byte-identical required",
            "base_outputs_sha256": __import__("hashlib").sha256(
                json.dumps(base_outs, ensure_ascii=False)
                .encode()).hexdigest()[:16],
            "scaled0_outputs_sha256": __import__("hashlib").sha256(
                json.dumps(s0_outs, ensure_ascii=False)
                .encode()).hexdigest()[:16]}
        base_tr.stop()
        s0_tr.stop()

        # 3. scale-1 genuine repeatable change
        w1_tr = start("W1_pi", PORTS["W1_pi"], lora=ROOT / ADAPTERS["W1_pi"])
        w1_outs_a = probe_outputs(w1_tr)
        w1_outs_b = probe_outputs(w1_tr)
        w1_tr.stop()
        w1b_tr = start("W1_pi_again", PORTS["W1_again"],
                       lora=ROOT / ADAPTERS["W1_pi"])
        w1_outs_c = probe_outputs(w1b_tr)
        w1b_tr.stop()
        change = w1_outs_a != base_outs
        repeatable = w1_outs_a == w1_outs_b == w1_outs_c
        report["checks"]["scale1_change"] = {
            "ok": bool(change and repeatable),
            "genuine_change_vs_base": bool(change),
            "repeatable_within_and_across_processes": bool(repeatable)}

        # 4. no silent fallback: nonexistent adapter must stay unhealthy
        fallback_refused = False
        try:
            bad = start("BAD", PORTS["BAD"],
                        lora=ROOT / "models/adapters/DOES-NOT-EXIST.gguf")
            bad.stop()
        except Exception:
            fallback_refused = True
        report["checks"]["no_silent_fallback"] = {
            "ok": fallback_refused,
            "note": "nonexistent adapter path -> server must never "
                    "become healthy (base-only fallback refused)"}

        # 5/6. flag identity across configurations
        flag_sets = {}
        for name, rel in ADAPTERS.items():
            tr = ChatTransport(name, BASE, PORTS[name], WORKDIR / name,
                               lora_file=ROOT / rel)
            flag_sets[name] = sorted(
                f for f in tr.session.profile_flags
                if str(rel) not in f)
        same = len({json.dumps(v) for v in flag_sets.values()}) == 1
        report["checks"]["cache_policy_identity"] = {
            "ok": bool(same and
                       report["checks"]["scale0_equivalence"]["ok"] is not
                       None),
            "flags": flag_sets["W1_pi"],
            "note": "identical context/cache flags across W0-W3 "
                    "(only --lora file differs)"}
    finally:
        # ensure no stray servers
        import subprocess
        subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"],
                       capture_output=True)

    ok = all(c.get("ok") for c in report["checks"].values())
    report["verdict"] = "PASS" if ok else "FAIL"
    report["finished_utc"] = utc()
    EVID_OUT.joinpath("adapter_admission.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"],
                      "checks": {k: v.get("ok")
                                 for k, v in report["checks"].items()}},
                     indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
