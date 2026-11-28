# IJ-NANO-48H Task Ledger

Mission: IJ-NANO-48H (`docs/IJNANO_48H_MISSION_ORDER.md`, SHA256
e9e52fc7f2ac380c5f139d9aa6e19a9786974d399c9a5870cbe126fe98542130).
Clock: started 2026-11-28T04:34:00Z, deadline 2026-11-30T04:34:00Z
(never restarted). Status values: PASS / FAIL / BLOCKED / NOT_RUN.

## P0 — Preregistration and reconciliation

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| S0 | 48H mission order committed verbatim | done | PASS | `docs/IJNANO_48H_MISSION_ORDER.md` |
| S0 | Campaign state frozen (hypotheses, arms, rosters, priorities, qualification requirements, metrics, analysis methods, time budget, resume semantics; 48h clock started) | done | PASS | `MISSION_STATE_IJNANO_48H.json` |
| S0 | Remote HEAD verification: IJNANO 58aa790 == remote; IJEVAL 3cdd066 == remote; IJ-SLM 79a805e remote current | done | PASS | reconciliation block in mission state |
| S0 | EAE release reconciliation: compat v1.1.1; AUTH-1 48-slot diagnostic (checksum 4a09f525…) + AUTH-2 480-slot Batch A dev (checksum a22bcc68…) released under certificate 512efb617a9cb4c8; AUTH-3 BLOCKED by design | done | PASS | `evidence/IJEVAL/AUTH{1,2}/release.json` (read-only, pinned rev) |
| S0 | Dataset reconciliation: EAE-pinned Batch A public dataset content-identical to local C01-C08 roster (240/240 records; authorization binds pinned bytes 045cf42f…) | done | PASS | mission state reconciliation block |
| S0 | LFM3-HA 1.1 evidence reconciled: 720/720 transfer panel on the OTHER host (gfx1151) under a different qualification scope -> separate comparative cohort, never pooled; priors recorded (Pi x phase-aware +15.5pp, direct Pi -1.7pp, NO_QUALIFIED_CONFIGURATION) | done | PASS | mission state `lfm3_ha_evidence_reconciliation` |
| S0 | Physical preconditions observed at init: RX 7900 XTX driver 32.0.21030.2001 present; engine exe sha256 38c5affb… == sealed N02R identity; weights S1/S2/S3 Q8_0 present; no llama-server running | done | PASS | mission state `physical_identity` |

## P1 — Physical admission and trusted EAE integration

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| P1 | EAE pinned snapshot at 3cdd066 (git archive of committed objects; 84-file digest manifest; dataset/expectations/roster/contract digests match the release bindings) | done | PASS | `runtime/eae_pin/3cdd066/` + `PIN_MANIFEST.json` |
| P1 | EAE bootstrap module: fail-closed pin verification (tamper refused), trusted ExecutionEvidence registration replicating the release scripts byte-for-byte, real-consumer provider re-pin | done | PASS (registration) / BLOCKED at issuance (48H-B-006) | `benchmarks/ij_nano/n03h/eae.py` |
| P1 | Consumer-side fail-closed verification: the pinned registry's drill revocation correctly refuses fresh issuance ("no applicable certificates"); 108/108 Batch A witnesses through the pinned dual-path; duplicate-identity rejection; renderer contracts; 276/276 suite | done | PASS | `tests/ij_nano/test_n03h_bootstrap.py` |
| P1 | Physical transport adapter + campaign controller (balanced blocks w/ model rotation, dispatch limits, per-dispatch revocation recheck, canary scheduler + persistent breaker, GPU lease, exact resume, seal/verify/replay) | done (software) | PASS (AUTH-0 scope; awaiting authorization to dispatch) | `benchmarks/ij_nano/n03h/{transport,campaign}.py` |
| P1 | Host-wide GPU lease + fresh admission hashes + llama-server session admission | not started | PENDING (dispatches with E0) | planned `runs/n03h/*/admission.json` |

## E0 — AUTH-1 physical smoke (48 slots) — BLOCKED (48H-B-006), superseded by AUTH-2B first-block verification

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| E0 | Execute 48-slot diagnostic roster (3 models x 16 representative dev tasks, chat protocol) under AUTH-1 with continuous canary + circuit breaker | not started | PENDING | planned `evidence/IJNANO/N03H/E0/` |
| E0 | Verify complete raw evidence, replay, actual evaluation, containment; smoke trials NEVER counted as formal benchmark observations | not started | PENDING | — |
| E0 | Gate `N03_PHYSICAL_EVALUATION_INTEGRATION_GO` (genuinely earned) | not started | PENDING | — |

## E1 — Cognitive capability atlas

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| E1-A | Batch A development 480 slots (3 models x 160 dev cases, chat protocol) under AUTH-2 | not started | PENDING (authorized after integration gate) | planned `evidence/IJNANO/N03H/E1A/` |
| E1-B | Batch B development 480 slots under AUTH-2B — blocks 0-1 EXECUTED (120 trials, C09+C10, sealed f19f0515→f1990515, 120/120 replays match); integration gate GRANTED; first findings recorded (S3 32/40 EMPTY via finish=length budget exhaustion — H2 signal) | blocks 2-7 pending | IN_PROGRESS | `runs/n03h/N03-AUTH2-DEVELOPMENT-BATCH-B-v1/`, `evidence/IJNANO/N03H/AUTH2B/` |
| E1-CD | Batches C/D development 960 slots | not started | BLOCKED (pending IJEVAL EA13-C/D releases) | — |
| E1-CONF | Protected confirmation 960 slots | not started | BLOCKED (AUTH-3 not registered; protection never weakened) | — |

## E2–E8 — see mission state experiment register

All P0/P1/P2 experiment scopes beyond E1-A are BLOCKED pending their
specific qualification releases and/or asset acquisition; CPU-side
preparation (E3 official task study, adapter asset pinning) proceeds
where independently executable. Rows are added when each scope activates.

## P2 — Adapter asset pinning (W1-W3)

| Phase | Task | Progress | Status | Evidence |
|---|---|---|---|---|
| P2 | Official Pi/OpenCode/Hermes F16 GGUF LoRAs acquired + digest-verified (sha256 == upstream LFS == ModelScope mirrors); rank/alpha/targets/license/training-data pinned; acquisition-endpoint deviation (hf-mirror; HF unreachable) documented | done | PASS | `evaluation/ij_nano/n03h/adapter_assets.json`, weights at `models/adapters/` (gitignored) |
| P2 | E3 official-sources study frozen (published deltas, task-set identities, verifier methodology, fidelity classification, Qwen super-adapter method) | done | PASS | `docs/IJNANO_48H_E3_OFFICIAL_SOURCES_STUDY.md` |
