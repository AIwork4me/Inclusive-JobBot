# IJ-0.6 Secure Model Gateway

## Windows software regression

The gateway and security suite passed **209/209**. The run includes local SQLite transactions, archived-wire replay, and loopback HTTP stand-ins. The exact per-case results and input SHA256 values are in the [Windows software regression](../evidence/IJ06/security/software_regression_windows.json). The test peer supplied synthetic response bodies for the HTTP adapter cases. It ran no model and used no GPU.

| Scope | Passed / executed |
|---|---:|
| Strict JSON and Unicode | 68/68 |
| OpenAI wire protocol and streaming | 56/56 |
| Strict nested schemas and exact numeric constraints | 11/11 |
| Loopback HTTP backend contract | 11/11 |
| Policy, confirmation, replay, faults, and transaction rollback | 45/45 |
| Draft-only persistence and ticket relationships | 6/6 |
| Six frozen parser failures replayed from each backend | 12/12 |

The source tree had pending edits during this software test. The evidence records that state and binds every test and production source in this suite to its byte digest. This evidence supports software regression and identifies the tested archived outputs. Native parser, full SDK, GPU and holdout qualification require their own runs.

## Captured parser outputs

The replay uses the original Vulkan and ROCm strict fixture files. All twelve replays stopped before a tool handler ran. The whitespace case is rejected by the order-identifier constraint. Free text preserves leading and trailing whitespace. The duplicate key, incomplete parameter, incomplete function and incomplete CDATA cases are rejected by strict raw-argument decoding. The nested enum violation is rejected by schema validation.

| Archived symptom | Gateway decision |
|---|---|
| Whitespace in the order identifier | SCHEMA_ERROR |
| Duplicate parameter names | PROTOCOL_ERROR |
| Missing parameter closure | PROTOCOL_ERROR |
| Missing function closure | PROTOCOL_ERROR |
| Out-of-enum nested field | SCHEMA_ERROR |
| Unclosed CDATA | PROTOCOL_ERROR |

The wire check retains each original arguments string. It requires a complete tool-call message, and streaming release requires the terminal choice and the SSE completion marker. An SDK adapter must invoke this check before SDK coercion and carry the validated proposal to the tool boundary. If future parser output discards native syntax evidence and emits an apparently valid argument object, wire-only validation cannot recover the lost information. Native conformance remains a separate gate.

## Execution effects

The gateway enforces explicit grants scoped by actor, role, tool, resource, read or write mode and trusted workflow state. The host supplies the session and operation identities. A human-reviewed submission has a confirmation bound to the exact tool argument bytes, actor, resource, session, role and workflow state. SQLite serializes concurrent write and replay attempts. The first authorized commit stores its receipt, approval consumption and audit event in the same transaction. A same-operation replay receives the original receipt.

A draft-only capability can insert only an unsubmitted review draft for its authorized resource. The audit entry reports DRAFTED. Formal submission uses a separate authorized operation with confirmation. Ticket creation persists subject, priority, tags, customer, optional order, references to verified business records, actor and status. The simulator checks that the selected order belongs to the customer before writing.

Each decision audit includes confirmation state, before/proposed/after business rows of the terminal attempt, transaction and operation identities, outcome and attempt count. Retry is limited to explicit transient faults inside SQLite savepoints. Cancellation and deadlines discard a write if signaled before commit. Trusted handlers have to cooperate at transaction checkpoints. They cannot be preempted mid-execution by the current synchronous adapter. The circuit breaker reports recovery exhaustion and stops additional attempts until cooldown.

The observation is zero unauthorized effects, unconfirmed formal commits and duplicate commits in the software regression scenarios that exercise those outcomes. Runtime callers must authenticate the supplied execution context and expose the confirmation entry point exclusively through a trusted review action. This implementation qualifies transaction-contained simulator tools. External business connectors need equivalent transactional safeguards and dedicated evidence.

## Reproduction

Run the suite in the repository virtual environment with pytest and the locked runtime dependencies installed.

    powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts/windows/run_ij06_security_tests.ps1

The script writes a redacted log and test summary under its chosen output directory. Use a fresh output directory to repeat the run. A completed run requested with the resume switch verifies input digests before returning its saved status.
