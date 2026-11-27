# IJ-NANO-1.1 N06A-R — NanoAgent Layer A Execution Integrity Hardening

Date: 2026-11-27. Scope: SOFTWARE_ONLY (unittest; no physical runtime, GPU or
engine involved). Audited source: `f3d5817f`. Mission order:
`docs/IJNANO_MISSION_ORDER_V1_1.md` §4. Verdict: **PASS** for the gate
`NANOAGENT_LAYER_A_SOFTWARE_INTEGRITY_GO` in its software scope. This is not
production transaction safety (see §7).

## 1. Method

Each of the eight defect classes (NA-D01..NA-D08) was reproduced against the
audited source before any repair: adversarial tests were written first from
the mission-order defect descriptions, the red run was captured verbatim
(`evidence/IJNANO/N06A-R/red_run.txt`), then the minimal justified repair was
applied per class and the suite rerun green
(`evidence/IJNANO/N06A-R/green_run.txt`). The IJ-SDK suite (93 tests) was
rerun as a cross-mission regression control: OK, unchanged. No files outside
`src/nanoagent/`, `tests/ij_nano/` and this mission's evidence/report/state
records were modified.

Red summary: 60 collected, 15 failures + 39 errors (54 red). Two adversarial
modules were import-blocked at red time because the repair APIs did not yet
exist (`CheckpointInvalid`, `validate_tool_schema`) — that absence is itself
red evidence. Six collected tests passed pre-repair; they are pre-existing
correct behaviors or negative controls, itemized per class in
`evidence/IJNANO/N06A-R/defect_ledger.json`.

Green summary: **119 tests OK** (83 adversarial + 36 Layer-A regression).

## 2. Confirmed defects and repairs

| ID | Class | Root cause (confirmed) | Minimal repair |
|---|---|---|---|
| NA-D01 | Transaction isolation | `dict(self._store)` shallow draft: nested dicts/lists aliased the store; rollback could not restore business state | deep-copy draft at `begin` and at `commit`; handlers only see the draft; concurrent calls run on isolated drafts with serialized commits |
| NA-D02 | Evidence integrity | hash envelope omitted `parent_id`/`ts_utc`; restore checked neither trial identity, uniqueness, parent existence, stage validity; payload shared nested references; no seal digest | canonical envelope covers all nine fields; `verify()` enforces stage/trial/uniqueness/parent/chain; payloads deep-copied; `seal()` digest anchors a separately trusted manifest; `verify_against_seal()` detects truncation |
| NA-D03 | Checkpoint integrity | checkpoint was a data record: no experiment id, budget spec, seal, idempotency, pending tx or integrity hash; restore validated nothing; monotonic-only deadlines; no atomic publication | schema-v2 checkpoint binds everything under one integrity hash; `restore()` raises `CheckpointInvalid` on any failure; atomic `save()` (temp + fsync + `os.replace`); `BudgetController.restore()` re-derives the deadline from the wall-clock anchor — a restart never grants a new budget; `Session.restore()` returns live, writable, fact-preserving state |
| NA-D04 | Budget integrity | `units=0` bypass, negative specs, no settlement semantics, no max_tokens binding, non-atomic reserve | units ≥ 1; spec validation; `settle(actual)` (release unused capacity, charge overrun), `settle_unknown()` (conservative full hold), explicit reservation states; `max_completion_tokens()`; RLock-atomic reserve/release |
| NA-D05 | Provenance integrity | any nonempty `source_event_id` string verified a Fact; no type/unit/entity validation; values stored by reference | Session binds trial + EventLog; source event must exist, belong to this trial, carry an authorized stage (`tool_call_finished`; model text never authorizes facts); fact validation incl. bool strictness; deep-copied values |
| NA-D06 | Epoch/cancellation | `state_epoch_getter` accepted but never enforced; late handlers committed after reset/cancel/deadline | boundary checks (epoch, cancellation, deadline) enforced pre-dispatch AND pre-commit; denials at stages `epoch`/`cancellation`/`deadline`; non-reversible tools must require approval (registration-time, fail closed) |
| NA-D07 | Approval/idempotency | bare reusable `call_key`; unbound effect keys; optional effect keys for idempotent tools; no in-flight detection; no export/restore | approval bound to tool + canonical-args hash + operation id + scope + expiry; effect keys mandatory and bound to (tool, canonical args); write-ahead pending mark denies in-flight duplicates; finalized atomically with commit; `export/load_idempotency()` binds into checkpoints (duplicate-after-restart denied) |
| NA-D08 | Schema validation | subset accepted keywords it did not enforce (bounds/length/pattern silently ignored); arrays unsupported; non-finite numbers passed; schemas never validated | explicit enforced keyword set; `validate_tool_schema()` rejects unknown keywords, invalid types, uncompilable patterns, non-finite bounds AT REGISTRATION; gateway validates every tool schema on construction; non-finite rejection anywhere in args; full array + arbitrary nesting support |

Full detail, per-class red/green itemization and scope limits:
`evidence/IJNANO/N06A-R/defect_ledger.json`.

## 3. Justified contract changes (recorded, not silent)

1. `apply_verified` now requires a bound EventLog and a real authorized
   source event (NA-D05). Existing tests that used bare id strings encoded
   the defective contract and were updated.
2. `approve()` now binds tool/args/operation (NA-D07); the old one-argument
   form was the defect.
3. Arrays are now a supported, validated type (NA-D08); the old
   blanket-rejection test was updated to use a genuinely unsupported type.
4. The event hash envelope changed (NA-D02). No persisted logs exist from
   the audited source (the event log was software-scope only), so nothing
   needs migration; logs from the audited source would not verify under the
   new envelope, by design.

## 4. Dependency decision (NA-D08)

A trusted standard validator (`jsonschema` 4.26.0, MIT) is listed in
`requirements.lock` but is **not installed** in this runtime environment
(verified `ModuleNotFoundError`). Per the mission order, the
limited-validator branch applies: explicit subset, fail closed at
registration. Switching to `jsonschema` later is a one-line decision gated
on the package being present in the pinned environment; recorded in the
defect ledger.

## 5. Deadline and budget recovery (NA-D03/D04 joint demonstration)

`BudgetController` now anchors the wall-clock deadline at start. Checkpoints
carry the anchor; `BudgetController.restore()` rebuilds exact counters and
re-derives the live deadline from the anchor: if the anchored deadline has
passed, the first post-restart deadline check raises — a restart never
silently grants a new budget. Demonstrated in
`test_na_d03_checkpoint.py::test_deadline_survives_restart_without_new_budget`
and `::test_budget_counters_recovered_exactly`, with executable-state
recovery (live writable session, continuing event chain) in
`::test_executable_state_recovered`.

## 6. Non-reversible external actions (NA-D06 policy)

The gateway enforces epoch/cancellation/deadline checks **before dispatch**
and refuses to register non-reversible tools without the approval contract.
An effect already dispatched to the outside world cannot be rolled back by
an in-memory store: tool packages declaring `non_reversible=True` own their
pre-dispatch verification and compensation policy. This is documented in the
gateway module contract; implementing compensation registries is Layer B/C
work, out of this gate's scope.

## 7. Explicit scope limits (never claimed beyond)

- Software qualification under unittest only — no physical runtime, GPU,
  engine or model involvement.
- Deep-copy isolation qualifies the transaction boundary for the synthetic
  in-memory store; durable transactional storage for persistent job worlds
  is explicitly future work (mission order NA-D01).
- Single-process hash chain and dict idempotency are not adversarial
  persistence; the seal digest gives an anchor value, but anchoring it in a
  separately trusted manifest is a procedure, not a property of this code.
- Concurrency support is serialized commits over isolated drafts, not
  parallel transactional commits.
- **No production transaction safety is claimed from this qualification.**

## 8. Evidence manifest

- `evidence/IJNANO/N06A-R/red_run.txt` — verbatim red run (audited source)
- `evidence/IJNANO/N06A-R/green_run.txt` — verbatim green run + IJ-SDK control
- `evidence/IJNANO/N06A-R/defect_ledger.json` — per-class reproduction,
  root cause, repair, itemization
- `evidence/IJNANO/N06A-R/regression_results.json` — machine-readable summary
- Tests: `tests/ij_nano/test_na_d01_transaction.py` … `test_na_d08_schema.py`

Rerun: `python -I -m unittest discover -s tests/ij_nano -t .`
