"""EA-R02 — evidence verification from actual bytes.

The authoritative verification path: compute the artifact hash from the
file's actual bytes (or validate a receipt that was established that way).
Receipts bind the verification to the specific artifact, trial, execution
identity and verification implementation, and are immutable (private
creation key — they cannot be hand-forged like a bare digest pair).

Evidence classes distinguished (addendum EA-R02):
A. Claimed evidence    — a bare digest pair from an untrusted caller
                         (verify_evidence; proves string equality only).
B. Actually verified   — sha256 computed from bytes here and now
                         (issue_verification_receipt).
C. Qualified transfer  — a VerificationReceipt previously established by a
                         trusted loader, re-validated at transfer time
                         (validate_receipt_for).
"""
from __future__ import annotations

import hashlib
import pathlib
from dataclasses import dataclass

from .contracts.core import validate_sha256_digest

_RECEIPT_CREATE_KEY = object()
RECEIPT_SCHEMA_VERSION = "1.0.0"
VERIFIER_IDENTITY = "eval_assurance.evidence@1"


def sha256_of_file(path: pathlib.Path | str) -> str:
    """Compute the artifact hash from actual bytes (64 lowercase hex)."""
    p = pathlib.Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True, init=False)
class VerificationReceipt:
    """Immutable record that a specific artifact's bytes were hashed and
    matched the expected digest, bound to trial + execution identity and the
    verification implementation."""
    _create_key: object
    schema_version: str
    artifact_path: str
    artifact_sha256: str
    artifact_bytes: int
    trial_id: str
    experiment_id: str
    verifier: str

    def __init__(self, _create_key=None, *, schema_version=None,
                 artifact_path=None, artifact_sha256=None,
                 artifact_bytes=None, trial_id=None, experiment_id=None,
                 verifier=None):
        if _create_key is not _RECEIPT_CREATE_KEY:
            raise PermissionError(
                "VerificationReceipt cannot be constructed directly; use "
                "issue_verification_receipt() (EA-R02)")
        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(self, "artifact_path", str(artifact_path))
        object.__setattr__(
            self, "artifact_sha256",
            validate_sha256_digest(artifact_sha256,
                                   field_name="receipt sha256"))
        object.__setattr__(self, "artifact_bytes", int(artifact_bytes))
        object.__setattr__(self, "trial_id", str(trial_id))
        object.__setattr__(self, "experiment_id", str(experiment_id))
        object.__setattr__(self, "verifier", str(verifier))

    def envelope_kwargs(self) -> dict:
        """Feed for verify_evidence() with basis documenting the receipt."""
        return {"artifact_sha256_computed": self.artifact_sha256,
                "artifact_sha256_expected": self.artifact_sha256,
                "schema_validated": True,
                "trial_identity_match": True,
                "basis": f"verification_receipt:{self.verifier}"}


def issue_verification_receipt(artifact_path, *, expected_sha256: str,
                               trial_id: str, experiment_id: str,
                               verifier: str = VERIFIER_IDENTITY
                               ) -> VerificationReceipt:
    """Class-B verification: hash the ACTUAL bytes and compare to the
    expected digest. Any mismatch (or unreadable artifact, or bad digest
    syntax) fails closed with ValueError."""
    expected = validate_sha256_digest(expected_sha256,
                                      field_name="expected sha256")
    p = pathlib.Path(artifact_path)
    computed = sha256_of_file(p)     # raises OSError if unreadable
    if computed != expected:
        raise ValueError(
            f"verification failed for {p.name}: computed {computed[:12]}... "
            f"!= expected {expected[:12]}...")
    return VerificationReceipt(
        _create_key=_RECEIPT_CREATE_KEY,
        schema_version=RECEIPT_SCHEMA_VERSION,
        artifact_path=str(p),
        artifact_sha256=computed,
        artifact_bytes=p.stat().st_size,
        trial_id=trial_id,
        experiment_id=experiment_id,
        verifier=verifier)


def validate_receipt_for(receipt: VerificationReceipt, *, trial_id: str,
                         experiment_id: str) -> VerificationReceipt:
    """Class-C transfer: bind a previously established receipt to the exact
    trial/execution identity about to consume it. Identity mismatch fails
    closed (a receipt from one trial can never verify another)."""
    if not isinstance(receipt, VerificationReceipt):
        raise ValueError("not a VerificationReceipt")
    if receipt.trial_id != trial_id or receipt.experiment_id != experiment_id:
        raise ValueError(
            f"receipt identity mismatch: receipt is for "
            f"{receipt.experiment_id}/{receipt.trial_id}, requested "
            f"{experiment_id}/{trial_id}")
    return receipt
