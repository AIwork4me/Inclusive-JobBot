# IJ-0.6 Evaluator V2

**Evaluator regression status PASS.** On the local Python runtime, all 42 deterministic evaluator checks passed. They cover synthetic calls and snapshots, including two checks against a reopened SQLite database after real Gateway transactions. The cases exercise incorrect later arguments, wrong stored fields and associations, fabricated completion, unauthorized and unconfirmed effects, duplicate writes and IDs, missing calls and effects, a dangerous extra call, reordered and parallel reads, mismatched source results, nested schema mismatches and audit tampering. The mutation evidence lists the checks individually. See [mutation results](../evidence/IJ06/evaluator_v2/mutations.json).

## Scoring contract

The workflow contract defines an authored order for the strict SOP score and a dependency graph for the semantic score. An independent node can move or share a turn. A dependent node needs the correct prior result and must land on a later turn. A dynamic argument reference names its source node and result path. The evaluator binds the source to the expected resource and checks returned data against independently defined results before accepting dependent actions.

The denominator counts all required top-level arguments across authored nodes, including required nodes the trace never reaches. A nested object or array counts as one complete field. Its contents are compared recursively and must pass schema validation. Unexpected arguments and calls fail the trace even when they add no units to this denominator. The scorer keeps JSON types distinct and uses exact decimal comparisons. An unordered collection requires explicit authorization in the rubric.

The persisted oracle compares complete initial and final domain snapshots, including approval records, and checks audit rows for unauthorized, unconfirmed, extra or duplicate committed effects. It binds a write to a verified call ID and checks validated arguments and before/proposed/after records. A case can require a draft as a separate effect from a confirmed submission. The final structured answer is compared with independent expected fields. A correctly escalated case can have an explicit escalation outcome and no expected write.

Historical evaluation leaves the business-state facet BLOCKED when an expected write or a historical execution receipt lacks persistent evidence. A provable trace error still produces an overall FAIL. Read-only diagnostic rows are graded on calls and available answer facts, with the historical state facet NOT_RUN. For V1 free text, the answer check covers specified facts and contradictions. It cannot establish correctness of every incidental claim.

## Reproduction

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/evaluator
.\.venv\Scripts\python.exe -m benchmarks.tool_calling_v2.rescore --check
```

To regenerate for inspection, run the module with `--output .scratch/ij06-rescoring` and verify that directory using the same argument and `--check`. The runner binds both original runs and outputs to content digests and verifies exact case order, IDs, backend, original run IDs and V1 counts. See the [historical analysis](IJ06_BASELINE_RESCORING.md).
