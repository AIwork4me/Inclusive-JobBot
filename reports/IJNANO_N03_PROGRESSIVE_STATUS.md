# N03 Progressive Status

Generated 2026-11-27T23:58:26Z from `MISSION_STATE_IJNANO_N03_PROGRESSIVE.json` (deterministic render of the machine state; do not hand-edit).

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
| `N03_DATASET_FROZEN` | PENDING |
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

| ID | Capability | Batch | Dataset | Cert | Dev auth | Conf auth | Dev slots (exec/plan) | Conf slots (exec/plan) |
|---|---|---|---|---|---|---|---|---|
| C01 | Intent classification | A | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C02 | Goal extraction | A | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C03 | Single instruction understanding | A | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C04 | Multiple constraint understanding | A | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C05 | Boolean decision | A | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C06 | Enumerated choice | A | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C07 | Natural-language action selection | A | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C08 | Tool-name selection | A | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C09 | JSON structural generation | B | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C10 | Nested schema generation | B | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C11 | Compact DSL generation | B | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C12 | Slot extraction | B | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C13 | Entity reference resolution | B | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C14 | Numerical extraction | B | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C15 | Unit and currency understanding | B | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C16 | Tool result comprehension | B | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C17 | State interpretation | C | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C18 | Action dependency recognition | C | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C19 | Short-horizon planning | C | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C20 | Conditional branching | C | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C21 | Dynamic replanning | C | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C22 | Error recognition | C | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C23 | Argument correction | C | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C24 | Alternative action recovery | C | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C25 | Stop versus continue decision | D | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C26 | Clarification decision | D | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C27 | Escalation decision | D | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C28 | Context interference resistance | D | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C29 | Instruction ambiguity robustness | D | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C30 | Multilingual semantic consistency | D | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C31 | Grounded answer generation | D | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |
| C32 | Uncertainty and abstention behavior | D | frozen-contract | - | BLOCKED | BLOCKED | 0/30 | 0/15 |

Planned primary slots: 960 dev + 480 confirmation = 1440 (target 2880; three-model slot accounting begins at B4 runner integration).

## Preserved blockers

- IJE-B-004: OPEN (IJ-SDK D01-D03, owned by that mission)
- IJN-B-002: OPEN narrowed (formal business claims only)

Next task: N03-B2 dataset build (AUTH-0)
