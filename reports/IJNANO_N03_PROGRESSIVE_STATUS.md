# N03 Progressive Status

Generated 2026-11-28T01:21:32Z from `MISSION_STATE_IJNANO_N03_PROGRESSIVE.json` (deterministic render of the machine state; do not hand-edit).

- Mission order: `docs/IJNANO_MISSION_ORDER_V1_3S.md` (SHA256 `c447831de2c4683c...`)
- Execution plan: `docs/IJNANO_N03_PROGRESSIVE_EXECUTION_PLAN.md`
- Taxonomy: `evaluation/ij_nano/n03/taxonomy.json` (SHA256 `cb800bce6efc0172...`, frozen 2026-11-28T08:40:00Z)

## Authorization

- **AUTH-0_SOFTWARE_PREPARATION**: ACTIVE
- **AUTH-1_DIAGNOSTIC_SMOKE**: inactive (diagnostic only)
- **AUTH-2_SCOPED_DEVELOPMENT_BENCHMARK**: inactive
- **AUTH-3_SCOPED_CONFIRMATION_BENCHMARK**: inactive
- Authorization controller: `benchmarks/ij_nano/n03/authorization.py` — NOT_IMPLEMENTED

## Gates

| Gate | Status |
|---|---|
| `N03_PROGRESSIVE_EXECUTION_PLAN_FROZEN` | GRANTED |
| `N03_TAXONOMY_CONTRACTS_FROZEN` | GRANTED |
| `N03_DATASET_FROZEN` | PENDING (Batch A built+verified; Batches B-D outstanding) |
| `N03_DATASET_VERIFIED` | PENDING |
| `N03_DATASET_AND_RUNNER_PREPARATION_READY` | PENDING |
| `N03_SHARED_EVALUATION_ASSURANCE_CORE_GO` | PENDING (owned by IJEVAL PR #13) |
| `N03_PHYSICAL_EVALUATION_INTEGRATION_GO` | PENDING |
| `N03_BATCH_A_DEVELOPMENT_AUTHORIZED` | PENDING |
| `N03_BATCH_B_DEVELOPMENT_AUTHORIZED` | PENDING |
| `N03_BATCH_C_DEVELOPMENT_AUTHORIZED` | PENDING |
| `N03_BATCH_D_DEVELOPMENT_AUTHORIZED` | PENDING |
| `N03_ALL_32_COGNITIVE_PRIMITIVES_QUALIFIED` | PENDING |
| `N03_PRIMARY_PHYSICAL_BENCHMARK_COMPLETE` | PENDING |
| `N03_COGNITIVE_CAPABILITY_ATLAS_GO` | PENDING |

## EAE dependencies (Lane A, PR #13)

- Lane A status: EA00/EA01/EA02/EA02-R delivered; EA-R01..R04 trusted-boundary hardening delivered by concurrent IJEVAL session (commit 67af3dd, red at 9963926 -> green, 95/95 + 213/213); next: EA03 dataset/ground-truth qualification (Wave B)
- Blocking: EA03, EA04, EA05, EA06, EA07, EA08, EA09, EA10, EA11, EA12, EA13, EA14, EA18, early catastrophe prevention pilot, EA17-minimum certificate issuance/verification/persistence/revocation

## Progress measures (kept separate by design)

| Measure | Value |
|---|---|
| A. Engineering readiness (primitives with qualified evaluation contracts) | 0/32 |
| B. Physical execution coverage (authorized slots with physical evidence) | 0 of 2880 primary (0 dev + 0 confirmation executed) |
| C. Evaluation coverage (applicable planned slots with qualified evaluable outcomes) | 0 |
| D. Semantic accuracy (qualified evaluable, semantically correct) | not yet measurable (0 qualified slots) |

No single blended progress percentage is reported.

## Per-primitive matrix

| ID | Capability | Batch | Roster | Cert | Dev auth | Conf auth | Dev slots (plan) | Conf slots (plan) |
|---|---|---|---|---|---|---|---|---|
| C01 | Intent classification | A | BUILT_VERIFIED | - | BLOCKED | BLOCKED | 60 | 30 |
| C02 | Goal extraction | A | BUILT_VERIFIED | - | BLOCKED | BLOCKED | 60 | 30 |
| C03 | Single instruction understanding | A | BUILT_VERIFIED | - | BLOCKED | BLOCKED | 60 | 30 |
| C04 | Multiple constraint understanding | A | BUILT_VERIFIED | - | BLOCKED | BLOCKED | 60 | 30 |
| C05 | Boolean decision | A | BUILT_VERIFIED | - | BLOCKED | BLOCKED | 60 | 30 |
| C06 | Enumerated choice | A | BUILT_VERIFIED | - | BLOCKED | BLOCKED | 60 | 30 |
| C07 | Natural-language action selection | A | BUILT_VERIFIED | - | BLOCKED | BLOCKED | 60 | 30 |
| C08 | Tool-name selection | A | BUILT_VERIFIED | - | BLOCKED | BLOCKED | 60 | 30 |
| C09 | JSON structural generation | B | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C10 | Nested schema generation | B | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C11 | Compact DSL generation | B | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C12 | Slot extraction | B | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C13 | Entity reference resolution | B | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C14 | Numerical extraction | B | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C15 | Unit and currency understanding | B | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C16 | Tool result comprehension | B | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C17 | State interpretation | C | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C18 | Action dependency recognition | C | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C19 | Short-horizon planning | C | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C20 | Conditional branching | C | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C21 | Dynamic replanning | C | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C22 | Error recognition | C | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C23 | Argument correction | C | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C24 | Alternative action recovery | C | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C25 | Stop versus continue decision | D | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C26 | Clarification decision | D | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C27 | Escalation decision | D | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C28 | Context interference resistance | D | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C29 | Instruction ambiguity robustness | D | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C30 | Multilingual semantic consistency | D | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C31 | Grounded answer generation | D | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |
| C32 | Uncertainty and abstention behavior | D | NOT_STARTED | - | BLOCKED | BLOCKED | - | - |

Planned primary slots (roster-derived): 480 dev + 240 confirmation = 720 (target when complete 2880; executed/qualified accounting activates with the B4 runner).

## Preserved blockers

- IJE-B-004: OPEN (IJ-SDK D01-D03, owned by that mission)
- IJN-B-002: OPEN narrowed (formal business claims only)

Next task: N03-B2 Batches B/C/D families (C09-C32)
