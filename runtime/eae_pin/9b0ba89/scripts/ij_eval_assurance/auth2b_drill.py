"""AUTH-2 Batch B consumer revocation drill — ISOLATED SUBPROCESS.

Copies the qualification registry to a temp dir, registers a THROWAWAY
evidence binding against the copy (same digests, same artifacts),
imports the REAL IJ-NANO authorization module, issues through its
provider, then revokes EAE-side and verifies the provider refuses the
next issuance. The live registry, the live Batch B registration and
the Batch A registration are never touched (the compat module state is
process-local; this subprocess dies with the drill).
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

EVID = ROOT / "evidence" / "IJEVAL" / "EA03_N03"
AUTH2B = ROOT / "evidence" / "IJEVAL" / "AUTH2B"
EA18 = ROOT / "evidence" / "IJEVAL" / "EA18"
EA13B = ROOT / "evidence" / "IJEVAL" / "EA13B"
PIN_FULL = EVID / "pinned_full"
SRC = ROOT / "src" / "eval_assurance"

EXPERIMENT = "N03-AUTH2-DEVELOPMENT-BATCH-B-v1-DRILL"
MODELS = ["MiniCPM5-2B", "LFM3-1.7B", "Qwen3.5-2B"]
PRIMS = [f"C{i:02d}" for i in range(9, 17)]


def main() -> int:
    from eval_assurance.compat import execution_authorization as ea
    from eval_assurance.authoritative import (
        AuthoritativeQualificationState)
    from eval_assurance.qualification.store import CertificateStore

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="auth2b_drill_"))
    try:
        shutil.copyfile(EVID / "certificates" / "registry.json",
                        tmp / "registry.json")
        store = CertificateStore.load_registry(tmp / "registry.json")
        state = AuthoritativeQualificationState(store, tmp / "state.json")
        ea.clear_execution_evidence()
        ea.register_trusted_execution_evidence(
            authoritative_state=state,
            experiment_id=EXPERIMENT, auth_purpose="AUTH-2",
            primitives=PRIMS, protocols=["chat"], models=MODELS,
            dataset_file=PIN_FULL / "n03_cases.public.jsonl",
            roster_file=AUTH2B / "development_roster_480.json",
            parser_file=SRC / "production" / "parser_b.py",
            evaluator_file=SRC / "production" / "evaluator_b.py",
            interpreter_file=SRC / "reference" / "interpreter_b.py",
            oracle_file=SRC / "reference" / "oracle_b.py",
            certificate_store=store,
            shared_core_acceptance_file=AUTH2B /
                "auth2b_shared_core_acceptance.json",
            canary_evidence_file=AUTH2B / "canary_integration.json",
            breaker_evidence_file=AUTH2B / "breaker_drill.json",
            witness_suite_file=EVID / "dualpath_witnesses_batch_b.json",
            mutation_report_file=EVID /
                "production_mutation_campaign_batch_b.json",
            ea13_scope_file=EA13B /
                "primitive_qualification_batch_b.json",
            ea18_scope_file=EA18 / "independent_acceptance.json",
            dispatch_limits={"max_trials": 1})

        ijnano = (ROOT.parent / "IJNANO").resolve()
        sys.path.insert(0, str(ijnano))
        try:
            import importlib
            mod = importlib.import_module(
                "benchmarks.ij_nano.n03.authorization")
            provider = mod.EAEExecutionAuthorizationProvider(
                pinned_revision=ea.EAE_CONTRACT_REVISION,
                contract_module=
                    "eval_assurance.compat.execution_authorization")
            request = mod.RunRequest(
                experiment_id=EXPERIMENT,
                dataset_digest=_sha(PIN_FULL / "n03_cases.public.jsonl"),
                roster_digest=_sha(
                    AUTH2B / "development_roster_480.json"),
                primitives=frozenset(PRIMS), protocols=frozenset(["chat"]),
                models=frozenset(MODELS),
                eae_revision=ea.EAE_CONTRACT_REVISION,
                auth_level="AUTH-2")
            issued = provider.issue_execution_authorization(request)
            mod.validate_against(issued, request)
            state.revoke(issued.certificate_ref,
                         reason="consumer-verification drill (Batch B)")
            refused = False
            refusal_error = ""
            try:
                provider.issue_execution_authorization(request)
            except (mod.AuthorizationError, ea.AuthorizationError,
                    RuntimeError) as exc:
                # the refusal may surface as either module's
                # AuthorizationError family (distinct classes by
                # design; both are fail-closed refusals)
                refused = True
                refusal_error = f"{type(exc).__name__}: {exc}"
        finally:
            sys.path.remove(str(ijnano))

        result = {"revoked_refused": refused,
                  "issued_qualifying_class": issued.qualifying_class,
                  "revoked_certificate": issued.certificate_ref,
                  "refusal_error": refusal_error}
        out = ROOT / ".runtime" / "auth2b_drill_result.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=1), encoding="utf-8")
        print("drill refused-after-revocation:", refused)
        return 0 if refused else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _sha(p) -> str:
    import hashlib
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
