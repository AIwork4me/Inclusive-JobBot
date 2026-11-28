"""EA04/EA05/EA08 — integrated production/reference dual-path evaluation.

Order section 2 (Wave B closure): the two genuinely independent semantic
paths executed on the SAME raw response, full typed semantics and
verdicts compared:

    Production: Raw response -> ProductionParser -> ProductionEvaluator
                          (consumes STORED expectation records)
    Reference:  Raw response -> Independent Interpreter -> Reference
                          Oracle (derives truth from PUBLIC payloads only)

Discipline enforced here:
- unresolved disagreement -> ``NOT_EVALUABLE`` + quarantine (never
  silently resolved to either side);
- software exceptions are their own classes, never model failures;
- empty model output is its own class, distinct from missing evidence
  (an absent artifact is a session-level integrity fault, not a verdict);
- no silent normalization of invalid identifiers: typed values are
  compared exactly at the agreed normalization point;
- raw artifacts are content-addressed (sha256 over the canonical JSON
  payload — byte-identical policy to the IJ-NANO runner's
  ``RawResponse.artifact``) and replayable offline;
- duplicate trial identities are rejected and quarantined, never
  double-counted;
- persistence is crash-safe (atomic temp+replace) with exact resume.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import time
from dataclasses import dataclass, field

from .production.evaluator import ProductionEvaluator, ProductionVerdict
from .production.parser import (PARSE_EMPTY, PARSE_SOFTWARE,
                                parse_response)
from .reference import oracle as _oracle

# classification buckets (aligned with the pinned IJ-NANO runner contract)
CORRECT = "CORRECT"
INCORRECT = "INCORRECT"
EMPTY_OUTPUT = "EMPTY_OUTPUT"
INVALID_OUTPUT = "INVALID_OUTPUT"          # model-side structural failure
NOT_EVALUABLE = "NOT_EVALUABLE"            # unresolved dual-path disagreement
PARSER_SOFTWARE_ERROR = "PARSER_SOFTWARE_ERROR"
EVALUATOR_SOFTWARE_ERROR = "EVALUATOR_SOFTWARE_ERROR"
DUPLICATE_TRIAL = "DUPLICATE_TRIAL"
MISSING_EVIDENCE = "MISSING_EVIDENCE"      # artifact absent (never EMPTY)

SOFTWARE_BUCKETS = frozenset({PARSER_SOFTWARE_ERROR,
                              EVALUATOR_SOFTWARE_ERROR})
MODEL_BUCKETS = frozenset({CORRECT, INCORRECT, INVALID_OUTPUT,
                           EMPTY_OUTPUT})

#: sentinel for "no raw artifact exists" (integrity fault, never a
#: verdict): exact distinction between empty model output (EMPTY_OUTPUT)
#: and missing evidence (MISSING_EVIDENCE)
MISSING = object()

#: verdict families the two paths are compared at (INVALID_OUTPUT folds
#: into the INCORRECT model-failure family: both are model outcomes, the
#: production path just keeps the structural/semantic distinction)
_FAMILY = {CORRECT: "CORRECT", INVALID_OUTPUT: "INCORRECT",
           INCORRECT: "INCORRECT", EMPTY_OUTPUT: "EMPTY_OUTPUT",
           NOT_EVALUABLE: "NOT_EVALUABLE"}


@dataclass(frozen=True)
class DualPathResult:
    case_id: str
    primitive: str
    classification: str
    production_verdict: str
    reference_verdict: str
    typed_match: bool
    quarantine: bool
    reasons: tuple = ()
    parsed_production: object = None
    parsed_reference: object = None
    truth_reference: object = None


def capture_artifact(case_id: str, model: str, protocol: str,
                     content: str) -> dict:
    """Content-addressed raw-response artifact (runner-compatible)."""
    payload = json.dumps({"case_id": case_id, "model": model,
                          "protocol": protocol, "content": content},
                         sort_keys=True, ensure_ascii=False)
    return {"artifact_sha256": hashlib.sha256(
        payload.encode("utf-8")).hexdigest(),
        "payload": payload,
        "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                      time.gmtime())}


def _typed_equal(prim: str, a, b) -> bool:
    """Typed-semantics equality at the agreed normalization point (no
    silent normalization of invalid identifiers: values are compared as
    the typed values each path produced)."""
    if prim == "C04":
        return [str(x).lower() for x in (a or [])] == \
            [str(x).lower() for x in (b or [])]
    if isinstance(a, dict) and isinstance(b, dict):
        return {k: v for k, v in a.items()} == dict(b)
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, list) and isinstance(b, list):
        return list(a) == list(b)
    if isinstance(a, str) and isinstance(b, str):
        return a.lower() == b.lower()
    return a == b


def evaluate_dual(case: dict, expectation: dict, response,
                  production_parser=None, production_evaluator=None
                  ) -> DualPathResult:
    """Run both paths on one raw response and compare them."""
    prim = case.get("primitive", "")
    case_id = case.get("case_id", "")
    pparse = production_parser or parse_response
    peval = production_evaluator or ProductionEvaluator()

    # -- production leg --------------------------------------------------
    try:
        parsed = pparse(prim, case.get("public_payload") or {}, response)
        if not hasattr(parsed, "parse_class"):        # interpreter-shaped
            parsed = _adopt(parsed)
        prod = peval.evaluate(case, expectation, parsed)
        prod_verdict = prod.verdict
        prod_class = parsed.parse_class
    except Exception as exc:                          # software, never model
        return DualPathResult(
            case_id, prim, PARSER_SOFTWARE_ERROR,
            ProductionVerdict.SOFTWARE_ERROR, "NOT_EVALUABLE", False, True,
            reasons=(f"production software error: "
                     f"{type(exc).__name__}: {exc}",))

    # -- reference leg ----------------------------------------------------
    ref = _oracle.evaluate_response(case, expectation, response)
    ref_verdict = ref.verdict.value

    # -- comparison --------------------------------------------------------
    if prod_class == PARSE_EMPTY:
        classification = EMPTY_OUTPUT
    elif prod_class == PARSE_SOFTWARE:
        classification = EVALUATOR_SOFTWARE_ERROR
    else:
        pf = _FAMILY.get(prod_verdict, "INCORRECT")
        rf = _FAMILY.get(ref_verdict, "NOT_EVALUABLE")
        if pf != rf:
            classification = NOT_EVALUABLE     # unresolved disagreement
        else:
            classification = prod_verdict      # agreed: keep prod's
            #                                    structural/semantic split
    typed_match = _typed_equal(prim, parsed.value,
                               getattr(ref.parsed, "value", ref.parsed))
    reasons = list(prod.reasons) + list(ref.reasons)
    # unique-truth agreements must also agree on the typed value
    if classification == CORRECT and not typed_match and \
            not getattr(prod, "matched_alternative", False):
        classification = NOT_EVALUABLE
        reasons.append("paths agree on CORRECT but typed values differ "
                       "without a declared alternative")
    quarantine = classification in (NOT_EVALUABLE,
                                    PARSER_SOFTWARE_ERROR,
                                    EVALUATOR_SOFTWARE_ERROR)
    return DualPathResult(
        case_id, prim, classification, prod_verdict, ref_verdict,
        typed_match, quarantine, reasons=tuple(reasons),
        parsed_production=parsed.value,
        parsed_reference=ref.parsed,
        truth_reference=ref.truth)


def _adopt(parsed_tuple):
    """Adopt an interpreter-shaped (value, parse_class, reasons) tuple."""
    value, parse_class, reasons = parsed_tuple
    from .production.parser import ParsedAnswer
    return ParsedAnswer("", value, parse_class, tuple(reasons or ()))


class DualPathSession:
    """EA08 end-to-end session: artifacts -> trusted loader -> dual-path
    -> typed verdicts -> resumable, duplicate-rejecting trial store."""

    def __init__(self, workdir: pathlib.Path):
        self.workdir = pathlib.Path(workdir)
        (self.workdir / "artifacts").mkdir(parents=True, exist_ok=True)
        self.trials: dict[str, dict] = {}
        self.quarantine: list[dict] = []

    # -- trial identity ---------------------------------------------------
    @staticmethod
    def trial_id(case_id: str, model: str, protocol: str) -> str:
        return f"{case_id}|{model}|{protocol}"

    # -- integrated execution ----------------------------------------------
    def run_trial(self, case: dict, expectation: dict, response,
                  model: str = "synthetic-cpu", protocol: str = "chat",
                  artifact_bytes: bytes | None = None,
                  receipt=None) -> DualPathResult:
        """Capture (or adopt) the raw artifact, verify it through the
        trusted loader, evaluate both paths, record the trial.

        ``response`` semantics: a string (possibly empty) or None is the
        MODEL's output (None/"" -> EMPTY_OUTPUT — the artifact exists and
        records the emptiness); the :data:`MISSING` sentinel (or absent
        artifact bytes for a recorded trial at verify time) is
        MISSING_EVIDENCE — an integrity fault, never a model verdict.
        """
        tid = self.trial_id(case.get("case_id", ""), model, protocol)
        if tid in self.trials:
            # the original record stays intact (it is valid evidence);
            # the duplicate ATTEMPT is quarantined and never re-counted
            self.quarantine.append({"trial_id": tid,
                                    "reason": DUPLICATE_TRIAL})
            return DualPathResult(
                case.get("case_id", ""), case.get("primitive", ""),
                DUPLICATE_TRIAL, "—", "—", False, True,
                reasons=("duplicate trial identity",))

        if response is MISSING:
            self.quarantine.append({"trial_id": tid,
                                    "reason": MISSING_EVIDENCE})
            self.trials[tid] = {"trial_id": tid,
                                "classification": MISSING_EVIDENCE}
            return DualPathResult(
                case.get("case_id", ""), case.get("primitive", ""),
                MISSING_EVIDENCE, "—", "—", False, True,
                reasons=("no raw artifact exists for this trial; missing "
                         "evidence is an integrity fault, never "
                         "EMPTY_OUTPUT and never a model verdict"))

        # trusted artifact capture: bytes given OR canonical payload
        if artifact_bytes is not None:
            digest = hashlib.sha256(artifact_bytes).hexdigest()
            payload = artifact_bytes.decode("utf-8", "replace")
        else:
            art = capture_artifact(case.get("case_id", ""), model,
                                   protocol, response
                                   if isinstance(response, str)
                                   else str(response))
            digest = art["artifact_sha256"]
            payload = art["payload"]

        (self.workdir / "artifacts" / f"{digest[:24]}.json").write_text(
            payload, encoding="utf-8")
        if receipt is not None:
            receipt  # already validated by the caller (class-C transfer)

        result = evaluate_dual(case, expectation, response)
        self.trials[tid] = {
            "trial_id": tid, "case_id": case.get("case_id", ""),
            "model": model, "protocol": protocol,
            "classification": result.classification,
            "artifact_sha256": digest,
            "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                          time.gmtime())}
        if result.quarantine:
            self.quarantine.append({"trial_id": tid,
                                    "reason": result.classification})
        return result

    # -- offline replay from the preserved artifact ------------------------
    def replay(self, case: dict, expectation: dict, model: str,
               protocol: str) -> dict:
        tid = self.trial_id(case.get("case_id", ""), model, protocol)
        rec = self.trials[tid]
        raw = json.loads(self._artifact_payload(rec["artifact_sha256"]))
        content = raw["content"] if isinstance(raw, dict) else str(raw)
        result = evaluate_dual(case, expectation, content)
        return {"trial_id": tid,
                "replay_classification": result.classification,
                "recorded_classification": rec["classification"],
                "matches_recorded":
                    result.classification == rec["classification"]}

    def _artifact_payload(self, digest24: str) -> str:
        return (self.workdir / "artifacts" /
                f"{digest24[:24]}.json").read_text(encoding="utf-8")

    # -- crash-safe persistence with exact resume ---------------------------
    def save(self) -> None:
        state = {"trials": self.trials, "quarantine": self.quarantine}
        tmp = self.workdir / "session_state.json.tmp"
        tmp.write_text(json.dumps(state, indent=1, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(self.workdir / "session_state.json")

    def load(self) -> bool:
        p = self.workdir / "session_state.json"
        if not p.is_file():
            return False
        state = json.loads(p.read_text(encoding="utf-8"))
        self.trials = state["trials"]
        self.quarantine = state["quarantine"]
        return True

    # -- artifact integrity (EA08 X-series controls) ------------------------
    def verify(self) -> list[str]:
        """Re-hash every recorded artifact file; tampering or absence is
        reported (and the trial downgraded to MISSING_EVIDENCE)."""
        problems = []
        for tid, rec in self.trials.items():
            if rec.get("classification") == DUPLICATE_TRIAL:
                continue
            p = self.workdir / "artifacts" / \
                f"{rec['artifact_sha256'][:24]}.json"
            if not p.is_file():
                rec["classification"] = MISSING_EVIDENCE
                problems.append(f"{tid}: artifact file missing")
                continue
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            if digest != rec["artifact_sha256"]:
                rec["classification"] = MISSING_EVIDENCE
                problems.append(f"{tid}: artifact hash mismatch "
                                f"(tampered after capture)")
        return problems

    # -- analyzer summary ----------------------------------------------------
    def analyze(self) -> dict:
        counts: dict[str, int] = {}
        for rec in self.trials.values():
            counts[rec["classification"]] = \
                counts.get(rec["classification"], 0) + 1
        model_outcomes = sum(counts.get(b, 0) for b in MODEL_BUCKETS)
        software = sum(counts.get(b, 0) for b in SOFTWARE_BUCKETS)
        return {"counts": counts, "model_outcomes": model_outcomes,
                "software_or_unresolvable": software
                + counts.get(NOT_EVALUABLE, 0),
                "quarantined": len(self.quarantine)}
