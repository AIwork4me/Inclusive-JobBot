# IJ-NANO-1.3S — N03 Progressive Execution Plan (S0 deliverable)

Mission order: `docs/IJNANO_MISSION_ORDER_V1_3S.md` (verbatim preregistration,
SHA256 `c447831de2c4683c366fd0f7ae50ffda6d8660aea69961358d17900624d7e584`).
Machine state: `MISSION_STATE_IJNANO_N03_PROGRESSIVE.json`.

Reconciliation baseline (2026-11-28):

- IJ-NANO PR #11 remote HEAD `bc4555ecb6db989beefaeeba452c1c160283da2c` ==
  last audited IJ-NANO HEAD == local worktree HEAD (clean). Reused as-is.
- IJEVAL PR #13 remote HEAD `99639262e22ed5b59b42f28983c916f8b887b8b8` ==
  last audited IJEVAL HEAD. Local worktree additionally holds the Wave B/C
  preregistration commit (`672cdca`, unpushed) and in-flight EA-R01..EA-R04
  hardening owned by a concurrent IJEVAL session — NOT restarted or duplicated
  here; reconciliation deferred to that lane's own closeout.
- N02RR corrected research (replay `6701a6a6a08b34d9`, corrected headline
  870/2,184) is the only protocol evidence eligible for N03 design. The
  superseded N02R matrix must not feed N03 decisions.
- Business blockers IJE-B-004 (IJ-SDK D01–D03, their mission) and IJN-B-002
  (narrowed: formal business claims) remain OPEN. Pure cognitive evaluation
  proceeds independently.

## 1. Execution authorization levels (order §4)

| Level | Meaning | GPU | Entry condition |
|---|---|---|---|
| AUTH-0 | SOFTWARE_PREPARATION | no | None — active now |
| AUTH-1 | DIAGNOSTIC_SMOKE | yes, diagnostic only | dataset + production/reference evaluator + parser + evidence qualification, Continuous Canary, circuit-breaker integration, verified physical GPU identity |
| AUTH-2 | SCOPED_DEVELOPMENT_BENCHMARK | yes, formal dev | shared EAE core GO (§5), historical catastrophe regression, EA12 revalidation, EA14 shared-core acceptance, applicable EA13 + EA18, scope-bound certificates |
| AUTH-3 | SCOPED_CONFIRMATION_BENCHMARK | yes, protected | AUTH-2 + frozen model/protocol/parser/evaluator/analysis identities + protected roster + verified holdout separation |

Authorization decisions are issued by an executable controller
(`benchmarks/ij_nano/n03/authorization.py`, AUTH-0 task N03-B4) that consumes
EAE certificate state — never a hand-edited JSON status. Until that controller
exists, no level above AUTH-0 may be claimed.

## 2. Dependency graph (blocking edges)

```text
AUTH-0 Lane B                     Lane A (IJEVAL, PR #13)
---------------                   ------------------------
N03-B1 taxonomy C01-C32 ----+
N03-B2 dataset 640+320      |    EA-R01..R04 hardening (IN FLIGHT, other session)
N03-B3 dataset verification  |    EA03 dataset/GT -> EA04 parser -> EA05 dual-path
N03-B4 runner + authz        |    EA06 golden witness -> EA07 mutation
N03-B5 synthetic transport --+    EA08 evidence -> EA09 canary -> EA10 breaker
        |                        EA11 analyzer/publication (+ EA17 minimum
        |                        certificate issuance/verify/persist/revoke)
        v                        early catastrophe pilot -> EA12 revalidation
N03_DATASET_AND_RUNNER_          -> EA14 stress campaign -> EA18 acceptance
PREPARATION_READY                        |
        |                                v
        +----------> N03_SHARED_EVALUATION_ASSURANCE_CORE_GO
        |                                |
        +----------> N03_PHYSICAL_EVALUATION_INTEGRATION_GO  (S2 smoke, AUTH-1)
                        |                |
                        v                v
                 Batch A..D development (AUTH-2, per-batch EA13/EA18)
                        |
                        v
                 S7A/S7B/S7C research panels (AUTH-2 scopes)
                        |
                        v
                 Batch A..D confirmation (AUTH-3)
                        |
                        v
                 N03_COGNITIVE_CAPABILITY_ATLAS_GO
```

Non-blocking (must not delay qualified N03 work): EA15 cross-mission
integrations, EA16 RL reward integration, EA17 dashboard/general tooling
(beyond the minimum certificate functionality, which IS blocking), EA19
closure, IJ-SDK formal business Oracle, Harness Adapter training, NPU
deployment. Security/evidence-integrity dependencies are never deferred for
having a later task number.

## 3. Stage register

Each stage: gate, blocking dependencies, scope, resume. Commands listed
exist today; runner/controller commands are introduced by their own AUTH-0
tasks before use.

| ID | Stage | Gate | Blocking deps | Status | Resume (exact, existing) |
|---|---|---|---|---|---|
| S0 | Plan freeze | `N03_PROGRESSIVE_EXECUTION_PLAN_FROZEN` | order preregistered | **GRANTED (this commit)** | `git -C <IJNANO> log --oneline -3` |
| B1 | Taxonomy C01–C32 contracts (definitions, witnesses, boundaries, failure taxonomy, EAE deps per primitive) | `N03_TAXONOMY_CONTRACTS_FROZEN` | S0 | PENDING | `python -I scripts/ij_nano/n03/build_taxonomy.py --check` (after N03-B1) |
| B2 | Dataset build 640 dev + 320 confirmation, CN+EN, family splits | `N03_DATASET_FROZEN` | B1 | PENDING | generator + manifest under `evaluation/ij_nano/n03/` (after N03-B2) |
| B3 | Independent dataset verification (oracle replay, negative controls, leakage probes) | `N03_DATASET_VERIFIED` | B2 | PENDING | verification suite under `tests/ij_nano/n03/` (after N03-B3) |
| B4 | Runner (preflight/authorize/freeze/run/pause/resume/quarantine/replay/verify/analyze/publish) + authorization controller + synthetic transport | `N03_DATASET_AND_RUNNER_PREPARATION_READY` | B3, EA03/EA04 interfaces | PENDING | controller CLI under `benchmarks/ij_nano/n03/` (after N03-B4) |
| S2 | Physical integration smoke, 3 models × 16 dev cases = 48 slots + circuit-breaker demonstration | `N03_PHYSICAL_EVALUATION_INTEGRATION_GO` | B4, EA03–EA11 applicable, canary, breaker, GPU identity | PENDING | lease: `python benchmarks/root_cause/gpu_lease.py` (exists) |
| S3 | Batch A development (C01–C08, 480 slots) | `N03_BATCH_A_DEVELOPMENT_AUTHORIZED` | S2, shared-core GO, Batch A EA13 + EA18 | PENDING | — |
| S4 | Batch B development (C09–C16, 480 slots) | `N03_BATCH_B_DEVELOPMENT_AUTHORIZED` | same pattern, independently qualified | PENDING | — |
| S5 | Batch C development (C17–C24, 480 slots) | `N03_BATCH_C_DEVELOPMENT_AUTHORIZED` | same pattern | PENDING | — |
| S6 | Batch D development (C25–C32, 480 slots) | `N03_BATCH_D_DEVELOPMENT_AUTHORIZED` | same pattern | PENDING | — |
| S7A | Capability scaling curves (tool inventory 2–64, context, action complexity, planning depth, recovery) | scoped AUTH-2 | S3+ applicable batches | PENDING | — |
| S7B | Adaptive cognitive budgeting (T0/T1/T2-64..512; 3×6×60 = 1,080 slots) | scoped AUTH-2 | S3+ | PENDING | — |
| S7C | Larger-model reference panel (pinned 8B/14B) | scoped AUTH-2 | S3+ | PENDING | — |
| S7D | Protected confirmation, 4 × 240 = 960 slots | `N03_BATCH_<ID>_CONFIRMATION_AUTHORIZED` | frozen policies, AUTH-3 per batch | PENDING | — |
| S8A | Failure mechanism atlas | part of atlas gates | S3–S7D | PENDING | — |
| S8B | Capability→Runtime mapping | `IJNANO_CAPABILITY_TO_RUNTIME_MAPPING` | S8A | PENDING | — |
| S8C | Learnability atlas (non-blocking for closure) | — | S8A, development data only | PENDING | — |

Batches are scheduling groups, not a new taxonomy. Groups may be reorganized
before formal outcomes are inspected only under order §7 constraints (all 32
primitives retained, identities preserved, dataset size preserved,
preregistered design intact). No cherry-picking by model performance.

## 4. Physical budget (primary)

| Batch | Primitives | Dev cases | Conf cases | 3-model dev slots | 3-model conf slots |
|---|---:|---:|---:|---:|---:|
| A | C01–C08 | 160 | 80 | 480 | 240 |
| B | C09–C16 | 160 | 80 | 480 | 240 |
| C | C17–C24 | 160 | 80 | 480 | 240 |
| D | C25–C32 | 160 | 80 | 480 | 240 |
| Total | 32 | 640 | 320 | 1,920 | 960 |

Primary total: 2,880 slots. Supplemental (S7A curves, S7B budgeting 1,080,
S7C reference, repeatability, learnability 1,440 nominal, smoke 48) are
accounted separately and never folded into the primary denominator.

## 5. Protocols (candidates, corrected N02RR basis)

- Common development baseline candidate: T2 Chat + bounded reasoning 256
  (`evidence/IJNANO/N02RR/corrected_protocol_matrix.json`). NOT proven
  optimal; reasoning-budget optimality is untested (budget panel varied
  TOTAL generation budget). Applicability and reasoning-budget enforcement
  must be physically verified before freezing (S3 preflight).
- Model-specific candidates (kept separate from common-protocol
  measurements; never changed in response to unfavorable results):
  - S1 MiniCPM5-2B: Chat+JSON Schema; Chat+bounded reasoning;
    thinking-disabled control; native function calling where applicable.
  - S2 LFM3-1.7B: Chat+JSON Schema; native business tool calling;
    Chat+bounded reasoning; thinking-disabled control; completion as
    negative-transfer comparator (bounded panel).
  - S3 Qwen3.5-2B: verified thinking-disabled Chat; Chat+bounded reasoning;
    default thinking as diagnostic comparator.
- Fixed weights (Q8_0, IJSDK sibling via `default_weights_root()`), pinned
  llama.cpp b12359, Vulkan backend, RX 7900 XTX gfx1100. No LoRA in the
  primary baseline (S8C records learnability candidates only).

## 6. Continuous protection (order §12–§14)

- Canary cadence (preregistered initial): before start; before model or
  protocol change; after every resume; every 25 trials or 5 minutes,
  whichever first; before sealing a batch; before publication. Rotating
  known-correct/known-incorrect witnesses appropriate to the active family
  and protocol. Canaries never count as benchmark observations; assurance
  overhead recorded separately.
- Dual-path evaluation on every formal primary trial: production
  (Parser→Evaluator) vs reference (Independent Interpreter→Reference
  Oracle); compared on semantic verdict, entity/tool identity, arguments,
  numeric values/units, predicate semantics, stage identity, planning
  dependencies, state transitions. Unresolved disagreement → NOT_EVALUABLE +
  investigation/quarantine — never ordinary model failure. Where full
  independent evaluation is impossible for a primitive, that primitive is
  BLOCKED or qualified to a narrower contract — no silent sampled checks.
- Historical failure immunity: permanent executable regression controls for
  the N02R dictionary-unpacking defect, exception masking, predicate
  substring false positives, unknown-argument filtering, entity collisions,
  unit inference, duplicate keys, multi-answer ambiguity, hidden wrong
  stage-one selections, unqualified evidence admission, Boolean coercion,
  empty-store publication, revoked-certificate reuse — plus every newly
  discovered defect.

## 7. Current status (2026-11-28)

- Lane A (IJEVAL): EA00–EA02-R delivered; EA-R01..R04 hardening in flight in
  a concurrent session on that worktree (red reproduction sealed at
  `evidence/IJEVAL/EABC/red_reproduction.json`); EA03+ not started. Wave B/C
  order preregistered in `docs/IJEVAL_MISSION_ORDER_WAVE_BC.md`.
- Lane B (IJNANO): this plan + mission state = first deliverables. Dataset
  and runner work starts under AUTH-0 immediately after this commit.
- No GPU work is authorized or scheduled until the S2 prerequisites qualify.

Scientific integrity first. Progressive execution second. GPU throughput
third.
