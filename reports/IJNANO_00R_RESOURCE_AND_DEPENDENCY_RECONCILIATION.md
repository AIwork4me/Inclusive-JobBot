# IJ-NANO-1.0 — N00R Resource and Dependency Reconciliation

- Generated: 2026-11-27T11:20:07Z
- Supplemental order: N00R (executed verbatim requirements; committed as
  `docs/IJNANO_MISSION_ORDER_N00R.md` (committed verbatim as docs/IJNANO_MISSION_ORDER_N00R.md); referenced from the
  mission tracking issue #10)
- Machine-readable evidence: `evidence/IJNANO/N00R/gpu_identity_comparison.json`,
  `evidence/IJNANO/N00R/lease_scope_decision.json`
- Preserves all N00 evidence; original N00 bytes remain in git history
  (`ee44482`) apart from the explicitly requested DEP-03 reference fix.

## 1. GPU lease scope correction — verdicts

| Verdict | Determination | Basis |
|---|---|---|
| `CROSS_HOST_GPU_LEASE_CONFLICT_RESOLVED` | IJ-SLM-1.0's lease binds to a **different physical GPU on a different host** | PR #9 @ `364c7ca` (live head, updated 10:23:34Z): `atlas/slm/v1.0/environment.json` → Radeon 8060S, **gfx1151**, driver 32.0.22018.5, AMD Ryzen AI MAX+ PRO 395; `evidence/IJ073/aeve/gpu_handoff.json` → host_sha256 `8c12b292...`, gpu_physical_sha256 `3d040bf5...`, lease_owner tc-v3-formal; sealed IJSLM tc-v3 manifest → Vulkan0 8060S, gfx1151, 25/25 layers, GPU execution PASS |
| `LOCAL_GPU_LEASE_AVAILABLE` | This workstation's GPU is free and coordinable | live PCI identity **RX 7900 XTX, gfx1100, `VEN_1002&DEV_744C&SUBSYS_0E3B1002&REV_C8`**, driver 32.0.21030.2001, i7-13700K/B760M — same host IJ-SDK P1 qualified; no llama/python/ollama processes; host-wide lease probe `ACQUIRED_FREE` + clean release at 11:20:07Z |
| `GPU_IDENTITY_VERIFIED` | both sides device-level verified | component-wise identity (GPU model, PCI ID, architecture, driver lineage, CPU/platform, host hashes) — distinct on every axis |

**The N00 interpretation is superseded**: N00 read "IJ-SLM-1.0 holds the
Radeon lease" from PR text without device-level identity binding; the sealed
run identities now show that mission executes on the earlier gfx1151
workstation. IJ-SLM's lease on that host is **not released, overridden or
modified** in any way.

## 2. Local coordination protocol (reused, not invented)

`benchmarks/root_cause/gpu_lease.py` (inherited via the Atlas lineage,
present in every worktree on this host) provides exactly the required
semantics: host-wide named kernel mutex `Global\InclusiveJobBotPhysicalGPU`
(visible across all checkouts, ports and queues), atomic acquisition
(non-blocking wait; refusal raises `BlockingIOError`), correct release in
`finally`, abandoned-owner recovery (WAIT_ABANDONED reacquires after an owner
crash), and no forced termination of other missions. **No mission-specific
mutex was created.** Every IJ-NANO physical session (N02+) wraps its whole
execution in `physical_gpu()` and maintains persistent, checkpoint-resumable
trial state under it, so an interrupted session resumes without duplicate
trials. If the resumed IJ-SDK-1.1 worker ever runs physical inference through
the same module, both missions coordinate correctly; if it does not, the
mutex still guarantees IJ-NANO never collides with any process using the
protocol.

## 3. Corrected dependency scope

The IJ-SDK `formal_gpu_matrix_authorized: false` statement is **scoped to
IJ-SDK's own unqualified benchmark and evaluator scopes** (P3/P4/P5 reopened
FAIL). It is not a repository-wide ban on physical model inference.

| Scope | Status after N00R |
|---|---|
| Physical runtime admission (N02: hashes, load, offload, generation, tool-call protocol, structured generation, grammar, streaming, cancellation, token accounting) | **PROCEED** under host-wide lease + own qualification; these are runtime/protocol tests, not business-correctness claims |
| Cognitive microbenchmarks (N03, 12 priority families) | **PROCEED** with deterministic controls and mutation tests per family |
| Protocol diagnostics / mechanism development (N04 tiers, N06/N07) | **PROCEED** (software now; physical validation under lease) |
| Formal end-to-end business performance evaluation | **BLOCKED** (qualified business oracle required) |
| Product qualification / reliability targets | **BLOCKED** until own prerequisites qualify |

Also corrected: the LFM3-1.7B license blocker is **IJN-B-003** (a DEP-03
reference in `evidence/IJNANO/N00/dependency_qualification.json` had wrongly
pointed at IJN-B-005; fixed with an inline correction note, original preserved
in history).

## 4. Shared evaluation architecture (adopted)

**One common business evaluation contract, multiple independently qualified
specialized evaluators.** IJ-NANO will not build a redundant full business
oracle if a qualified IJ-SDK P5R scope can be re-audited and reused; it will
not inherit the defective original P5 oracle. IJ-NANO-specific evaluator
scopes — C01–C32 cognitive primitives, context sufficiency/loss, tool
retrieval recall, dependency closure, dynamic action constraints, DSL
correctness, slot-binding provenance, typed state consistency, profile
effectiveness, recovery attribution, model×harness and cross-job transfer —
proceed **now**, each with deterministic controls, independent expected
results and mutation tests. Formal business evaluation waits for (A) a
qualified, re-audited P5R evaluator or (B) the minimum independently
implemented functionality satisfying the same business contract, with the
non-reuse reason documented.

## 5. Execution lanes (per the N00R directive)

- **Lane A — N01**: full R01–R09 primary-source verification, reuse decision.
- **Lane B — N05**: specialized cognitive/mechanism evaluator development.
- **Lane C — N06/N07**: minimum viable NanoAgent runtime, Layer A
  (execution integrity: authoritative budget controller, monotonic deadline,
  complete session reset, event correlation, typed state, safe gateway,
  checkpoint/cancellation — with D01–D07 regression tests), then Layers B/C.
- **Lane D — N02/N03**: physical runtime admission and cognitive
  microbenchmarks under the host-wide lease (fresh hash evidence; b12359 +
  Vulkan baseline retained; ROCm/HIP as separately identified comparator).
- **Lane E — N04**: research mechanism reproduction after N01.
- **Lane F**: SLM Harness Causal Pilot (arms A0–A9, 120 matched development
  cases per model per applicable arm, nominal max 3,600 trial slots,
  preregistered applicability/budgets/scoring; no winner declared from
  development results).

## 6. Gate assessment

`N00R_RESOURCE_AND_DEPENDENCY_RECONCILIATION_DELIVERED` — **PASS**: identity
comparison delivered (§1), lease scope decision delivered (§2–§3), dependency
matrix corrected (§3), state and blockers updated, verdicts recorded without
conflation. Original N00 evidence preserved.
