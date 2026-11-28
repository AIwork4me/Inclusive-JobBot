# IJ-NANO-1.2R — Offline Re-score Root Cause (RS01)

- Mission order: `docs/IJNANO_MISSION_ORDER_V1_2R.md` §2
- Audited HEAD: `26445d6f79949d51da7a9ce3f5669b032ab51efe`
- Defective module: `scripts/ij_nano/n02r_rescore.py` (defect introduced at
  `8e87604`, symptom-masked at `b0d57e9`, both git-preserved)
- Affected experiment: `ec5b95357e960f99` — **all 1,397 offline-rescoreed
  rows** (of 2,184 total slots)
- Reproduction evidence: `evidence/IJNANO/N02RR/rs01_red_reproduction.json`
- Repair: `scripts/ij_nano/n02rr_replay_lib.py` (key-based, schema-validated
  loader) + rewritten `scripts/ij_nano/n02r_rescore.py`; regression gate
  `tests/ij_nano/test_n02rr_replay_qualification.py`
- Original experiments preserved read-only: `36bfed1d55a9987b`,
  `7a1b9d7d160202d8`, `ec5b95357e960f99` (seals intact; verified in
  `evidence/IJNANO/N02RR/evidence_verification.json`)

**Status: CLOSED — defect reproduced red on the published artifact, exact
impact measured (1,397/1,397), tool repaired, mutation-gated.**

## 1. The defect

The physical controller keeps per-stage records as in-memory tuples and
persists them as objects:

```python
# controller_v2._run_trial (physical path — CORRECT, tuple in memory)
stage_records.append((1, path, http_json, http_error, latency))
...
stage, path, http_json, http_error, latency = stage_records[-1]   # ok

# persisted artifact (controller_v2._run_trial)
{"stage": s, "path": p, "http": hj, "http_error": he, "latency_s": l}
```

The offline re-score tool re-used the positional unpacking against the
PERSISTED object:

```python
# n02r_rescore.py@26445d6 line 71 (DEFECT)
stage, path, http_json, http_error, latency = art["stages"][-1]
```

Iterating a dict yields its keys, so the audited statement assigned:

| variable | assigned value | intended value |
|---|---|---|
| `stage` | `"stage"` | `1` |
| `path` | `"/v1/chat/completions"` → `"path"` | the endpoint path |
| `http_json` | `"http"` | the response object |
| `http_error` | `"http_error"` | `None` or the error string |
| `latency` | `"latency_s"` | the measured latency |

The subsequent type check

```python
http_json if isinstance(http_json, dict) else None
```

then passed **`None`** into the parser, `http_ok` recorded `True`
(`"http" is not None`), and `http_error` recorded the literal string
`"http_error"`.

## 2. Why it was not caught (the masking chain)

1. **`8e87604`** — the tool was created already containing the defective
   line. With the then-current parser, `"http".get(...)` raised
   `AttributeError` and the tool crashed rather than producing evidence.
2. **`b0d57e9`** — instead of root-causing the crash, three guards were
   added that made the crash disappear:
   - `isinstance(http_json, dict) else None` before the parser;
   - `except Exception` around parse+score mapping every failure to
     `PARSE_INVALID` ("never lose a trial");
   - `_telemetry`/`_content_of` non-dict guards emitting
     `NOT_CAPTURED (non-object response body)`.
3. The masked run then sealed **1,397/1,397 rows as `PARSE_INVALID`** with
   `http_error="http_error"`, string latencies and erased telemetry, and the
   analyzer consumed them as ordinary model failures.

## 3. Red reproduction (published witness)

Artifact `evidence/IJNANO/N02R/runs/7a1b9d7d160202d8/responses/003abb9e2604141bd8b016ec.json`
(S2 / M-P2 / EA02 / budget 1024; SHA256 `519e66eb…` recorded and verified):

| | audited path | sealed destination row | corrected replay | source experiment |
|---|---|---|---|---|
| parser receives | `None` | — | response dict | response dict |
| `structural_ok` | False | False | **True** | True |
| payload | None | None | `{"intent": "A3"}` | `{"intent": "A3"}` |
| `reasons` | `["PARSE_INVALID"]` | `["PARSE_INVALID"]` | `["INTENT_MISMATCH"]` | `["INTENT_MISMATCH"]` |
| `http_error` field | `"http_error"` | `"http_error"` | `None` | `None` |
| `usage` | `NOT_CAPTURED (non-object response body)` | same | `{190, 11, 201, cached 1}` | same |
| latency | `"latency_s"` (string) | `source_stage_latency_s: "latency_s"` | `0.156` s | `0.156` s |

This witness is deliberately a **semantic false** trial (the model chose
A3; expected A4): under the defect it was indistinguishable from a crash,
an empty output, a transport error and every other failure.

## 4. Exact impact among the 1,397 offline re-scores

Executed the audited path and the corrected replay over all 1,397 source
rows (never writing to any sealed file):

- **affected records: 1,397 / 1,397** — every offline-rescored row carries
  the defect fingerprint (`http_error == "http_error"`,
  `reasons == ["PARSE_INVALID"]`, `structural_ok == false`) in the sealed
  destination;
- breakdown: **588 verdict flips — all false negatives** (originally
  semantic PASS sealed as FAIL); **306 structural-only** (verdict already
  FAIL, structural validity destroyed); **503 telemetry-only** (verdict and
  structure coincidentally unchanged, telemetry corrupted);
- **0 false positives** (the defect can only fail trials, never pass them);
- the 787 physically executed rows of `ec5b95357e960f99` are unaffected
  (the physical path unpacks in-memory tuples). Independent re-score of all
  787 artifacts reproduces their sealed verdicts exactly, payload-identical
  (`physical_consistency_verification: 787/787 match` in
  `evidence/IJNANO/N02RR/manifest.json`).

## 5. Repair

1. `scripts/ij_nano/n02rr_replay_lib.py` — corrected loader and replay
   engine:
   - stage fields read **explicitly by key**; positional unpacking of
     persisted artifacts is structurally impossible;
   - full schema validation before replay: required keys, types
     (`stage` int, `path` str, `http` object|null, `http_error` string|null,
     `latency_s` non-negative number), http/http_error exclusivity, stage
     ordering `1..n`, artifact trial identity, recorded SHA256;
   - integrity rejections raise `ArtifactIntegrityError` and are classified
     `EVIDENCE_INSUFFICIENT` — never silently converted into model
     failures;
   - the audited defective semantics are preserved verbatim as
     `mutant_unpack_last_stage()` for the red suite only.
2. `scripts/ij_nano/n02r_rescore.py` — rewritten fail-closed: delegates to
   the validated loader, refuses to append duplicate trial ids into an
   existing results file (the silent-append design is what let 1,397
   defective rows enter a sealed experiment), records integrity rejects
   separately in the manifest.
3. Qualification (mission §4): 19 end-to-end controls (raw artifact →
   loader → stage reconstruction → parser → evaluator → trial record →
   analyzer), including "valid response stored in a dictionary",
   "http field not object", "wrong trial identity", "hash mismatch",
   "invalid stage order", the two-stage hidden-wrong-selection case, and
   the dictionary-unpacking mutant itself. Red-to-green evidence:
   mutant rejected on every positive control; corrected loader passes
   19/19; published witness replays to its independently expected verdict.
   Gate `N02R_OFFLINE_REPLAY_INTEGRITY_GO` = **PASS**
   (`evidence/IJNANO/N02RR/replay_qualification.json`, regression tests
   `tests/ij_nano/test_n02rr_replay_qualification.py`).

## 6. What was NOT invalidated

Per mission §1, the physical observations stand: the 1,397 source trials
were physically executed under the sealed identity `7a1b9d7d160202d8` with
verified sessions, template fingerprints and hash-verified artifacts; the
787 physical trials of `ec5b95357e960f99` are valid as sealed. Only the
offline scoring layer (verdicts, failure reasons, telemetry) of the
rescored rows was defective. The corrected verdicts — not the physical
runs — are recovered in `evidence/IJNANO/N02RR/trial_reconciliation.jsonl`
(replay identity `6701a6a6a08b34d9`; binding hashes in
`evidence/IJNANO/N02RR/manifest.json`) and analyzed in
`reports/IJNANO_02RR_QUANTITATIVE_EVIDENCE_RECONCILIATION.md`.
