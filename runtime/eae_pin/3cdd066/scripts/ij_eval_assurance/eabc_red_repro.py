#!/usr/bin/env python3
"""Wave B/C hardening — red reproduction of EA-R01..EA-R04 (addendum
sections 2, 3, 8, 9). Observes the audited implementation at HEAD 9963926;
each probe records what the CURRENT code does. After hardening, the green
battery asserts the closure. Evidence: evidence/IJEVAL/EABC/.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from eval_assurance.contracts import (EvaluationResult, EvaluationStatus,  # noqa: E402
                                      EvidenceIntegrity, ExecutionStatus,
                                      ParserStatus, PublicationEligibility,
                                      QualificationStatus, SemanticVerdict,
                                      VerifiedEvidence, eligible_for_semantic_statistics,
                                      verify_evidence)
from eval_assurance.qualification import CertificateStore  # noqa: E402
from eval_assurance.statistics import aggregate_semantic  # noqa: E402

PROV = {"experiment_id": "e1", "trial_id": "t1", "task_id": "k1",
        "model": "S1", "dataset_id": "d1", "parser_version": "p1",
        "evaluator_version": "v1"}
SHA = "a" * 64


def observe(f):
    try:
        return {"result": f(), "error": None}
    except Exception as e:                      # noqa: BLE001
        return {"result": None, "error": f"{type(e).__name__}: {e}"}


def ok_record(**over):
    base = dict(
        execution_status=ExecutionStatus.EXECUTED,
        evaluation_status=EvaluationStatus.VALID,
        parser_status=ParserStatus.PARSE_OK,
        semantic_verdict=SemanticVerdict.CORRECT,
        qualification=QualificationStatus.QUALIFIED,
        publication=PublicationEligibility.ELIGIBLE,
        evidence=EvidenceIntegrity.VERIFIED,
        provenance=dict(PROV),
        verified_evidence=verify_evidence(
            PROV, artifact_sha256_computed=SHA, artifact_sha256_expected=SHA,
            schema_validated=True, trial_identity_match=True))
    base.update(over)
    return EvaluationResult(**base)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    r: dict = {}

    # ---- EA-R01: certificate issuance without evidence ---------------
    def arbitrary_store_cert():
        store = CertificateStore()          # caller-created, no evidence
        store.issue(scope="semantic", dataset_id="d1", parser_version="p1",
                    evaluator_version="v1",
                    reference_evaluator_version="")   # empty reference id
        return eligible_for_semantic_statistics(ok_record(), store).eligible
    r["EA_R01"] = {
        "issuance_without_evidence_authorizes_formal": observe(
            arbitrary_store_cert),
        "empty_reference_identity_accepted": observe(lambda: CertificateStore()
                                                     .issue(
                                                         scope="semantic",
                                                         dataset_id="d1",
                                                         parser_version="p1",
                                                         evaluator_version="v1",
                                                         reference_evaluator_version="")),
        "reference_equals_production_accepted": observe(lambda: CertificateStore()
                                                        .issue(
                                                            scope="semantic",
                                                            dataset_id="d1",
                                                            parser_version="p1",
                                                            evaluator_version="v1",
                                                            reference_evaluator_version="v1")),
        "digest_binding_fields_exist": observe(
            lambda: [f for f in CertificateStore().issue(
                scope="semantic", dataset_id="d1", parser_version="p1",
                evaluator_version="v1",
                reference_evaluator_version="r").__dict__
                if "sha256" in f or "digest" in f]),
    }

    # ---- EA-R02: verified evidence provenance ------------------------
    r["EA_R02"] = {
        "non_hash_strings_accepted": observe(lambda: verify_evidence(
            PROV, artifact_sha256_computed="banana",
            artifact_sha256_expected="banana", schema_validated=True,
            trial_identity_match=True)),
        "wrong_length_digest_accepted": observe(lambda: verify_evidence(
            PROV, artifact_sha256_computed="a" * 63,
            artifact_sha256_expected="a" * 63, schema_validated=True,
            trial_identity_match=True)),
        "identical_untrusted_pair_accepted": observe(lambda: verify_evidence(
            PROV, artifact_sha256_computed=SHA, artifact_sha256_expected=SHA,
            schema_validated=True, trial_identity_match=True,
            basis="no bytes were ever read")),
        "direct_envelope_construction": observe(lambda: VerifiedEvidence(
            schema_version="1.0.0", verified_keys=tuple(PROV),
            identity=dict(PROV), artifact_sha256=SHA,
            verification_checks={"forged": True})),
        "envelope_identity_dict_is_mutable": observe(lambda: (
            lambda env: (env.identity.update(trial_id="hacked")
                         or env.identity["trial_id"]))(
                VerifiedEvidence(schema_version="1.0.0",
                                 verified_keys=tuple(PROV),
                                 identity=dict(PROV), artifact_sha256=SHA,
                                 verification_checks={}))),
    }

    # ---- EA-R03: publication boundary --------------------------------
    empty = CertificateStore()
    unrelated = CertificateStore()
    unrelated.issue(scope="other-scope", dataset_id="other",
                    parser_version="x", evaluator_version="y",
                    reference_evaluator_version="z")
    revoked = CertificateStore()
    c = revoked.issue(scope="semantic", dataset_id="d1", parser_version="p1",
                      evaluator_version="v1", reference_evaluator_version="r")
    revoked.revoke(c.certificate_id, reason="probe")
    dec = ok_record()
    crit = ok_record(semantic_verdict=SemanticVerdict.NOT_EVALUABLE,
                     evaluation_status=EvaluationStatus.ARTIFACT_ERROR,
                     parser_status=ParserStatus.PARSER_SOFTWARE_ERROR,
                     evidence=EvidenceIntegrity.REJECTED,
                     publication=PublicationEligibility.BLOCKED)
    r["EA_R03"] = {
        "empty_store_permits_ALLOWED": observe(
            lambda: aggregate_semantic([dec], certificates=empty)
            .formal_publication),
        "unrelated_certs_permits_ALLOWED": observe(
            lambda: aggregate_semantic([dec], certificates=unrelated)
            .formal_publication),
        "revoked_only_permits_ALLOWED": observe(
            lambda: aggregate_semantic([dec], certificates=revoked)
            .formal_publication),
        "zero_qualified_rows_still_ALLOWED": observe(
            lambda: aggregate_semantic([dec], certificates=empty)
            .formal_publication),
        "critical_not_evaluable_blocks": observe(
            lambda: aggregate_semantic([dec, crit], certificates=empty)
            .formal_publication),
        "duplicate_trial_ids_both_counted": observe(
            lambda: [x for x in [
                aggregate_semantic([dec, ok_record()],
                                   certificates=empty).qualified_eligible]]),
        "planned_roster_support": "ABSENT (no roster parameter exists)",
    }

    # ---- EA-R04: revocation / time-of-check --------------------------
    store = CertificateStore()
    store.issue(scope="semantic", dataset_id="d1", parser_version="p1",
                evaluator_version="v1", reference_evaluator_version="r")
    rep = aggregate_semantic([dec], certificates=store)
    certs = list(store._certs.values())
    store.revoke(certs[0].certificate_id, reason="after aggregation")
    r["EA_R04"] = {
        "report_survives_post_aggregation_revocation": observe(
            lambda: rep.formal_publication),
        "record_mutable_after_validation": observe(
            lambda: (setattr(dec, "semantic_verdict",
                             SemanticVerdict.INCORRECT)
                     or dec.semantic_verdict.value)),
        "revocation_history_retained": observe(
            lambda: len([c for c in store._certs.values()
                         if c.revoked_utc])),
        "reissue_equivalent_cert_immediately_valid": observe(
            lambda: eligible_for_semantic_statistics(
                ok_record(), _reissue(store)).eligible),
        "corrupted_registry_load": observe(
            lambda: CertificateStore(persist_to=_corrupt_registry())),
    }

    out = ROOT / "evidence" / "IJEVAL" / "EABC" / "red_reproduction.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(r, indent=1, default=str, ensure_ascii=False),
                   encoding="utf-8")
    print(json.dumps(r, indent=1, default=str))
    return 0


def _reissue(store):
    fresh = CertificateStore()
    fresh.issue(scope="semantic", dataset_id="d1", parser_version="p1",
                evaluator_version="v1", reference_evaluator_version="r")
    return fresh


def _corrupt_registry() -> pathlib.Path:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                      delete=False)
    tmp.write("{corrupt json")
    tmp.close()
    return pathlib.Path(tmp.name)


if __name__ == "__main__":
    raise SystemExit(main())
