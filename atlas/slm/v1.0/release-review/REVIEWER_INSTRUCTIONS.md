# Independent benchmark review

Use the [MULTITOOL-V2 candidate 0.3 packet](MULTITOOL_V2_BLIND_REVIEW_PACKET/PACKET_MANIFEST.json) and the [Planning V2 candidate 0.4 packet](PLANNING_V2_BLIND_REVIEW_PACKET/candidate-0.4-review-v3/PACKET_MANIFEST.json) for active review. The Planning packet includes the two alternate-denial variants and the cross-level fixture separation. Earlier Planning packets are retained for audit. Use the current packet digest when requesting an independent review. Each verdict binds only its exact packet digest.

## Blind phase

1. Choose reviewers independent of the candidate authors, witness authors and automated reviewers. Give a reviewer only this guide, the relevant schemas, and the active packet's permitted manifest and input records. Keep the original oracle, witness, candidate outputs, prior scored results and other reviewers' judgments out of the review materials.
2. For Planning 0.4, send only the manifest and `REVIEW_INPUTS.jsonl` with the guide, schema and blank [first-phase form](RELEASE_WORKFLOW.md#first-phase-planning-expectations). Derive permissible branches and dependencies, conditional outcomes, authority requirements, and semantic duplicate findings from the request and tool contract. Use symbolic values for observations that will be revealed later. First-phase expectations use case IDs and conditional rules. Scenario IDs arrive with the second phase. The registrar signs the first-phase receipt before sharing any scenario data.
3. In the second Planning phase, share `SCENARIO_INPUTS.jsonl`. It contains projected synthetic service replies and trusted event metadata, including unsigned confirmation replies. The projection omits tool order, call arguments, witness plans and final expected answers. The reviewer checks applicability and terminal facts against these observations. Preserve any difference from the first-phase expectations as a discrepancy. Handle missing information as BLOCKED. The final submission includes the issuer-recorded `phase_one_expectations_sha256`.
4. MULTITOOL reviewers can use service records and trusted events in the initial packet. Record permissible sequences or dependencies, expected input and output facts, forbidden calls, and legitimate alternative orderings. Identify semantic duplicate candidates and name their case families.
5. Treat the Planning service observations as unordered. Check binding and temporal constraints independently. Use symbolic references for actual runtime-generated IDs. An external grant flag is eligible only with an authenticated event for the exact draft and current scope. Any uncertainty about origin or intended ordering is a review finding.
6. MULTITOOL reviewers should verify business consequences of conditional branches, repeated requests, denials, dependency order, scope revisions, and typed argument transfer. Planning reviewers should cover L0–L7, including denial after scope revision, staged-action provenance, stale observations, and unauthorized or duplicate commits.
7. Mark PASS when the independent expectation is supported by the supplied inputs. Mark FAIL for a clear contradiction, unsafe consequence, wrong dependency or material partition overlap. Mark BLOCKED if information or authoring provenance is insufficient. Use NOT_RUN for work still unreviewed.
8. Submit a UTF-8 verdict JSON document privately to benchmark engineering using `review-verdict.schema.json`. Use the manifest digest, an assigned pseudonymous reviewer ID, the review date and a digest of the finalized independent expectations. The issuer records reviewer independence and receipt privately. Submit no real approval values, usernames, account names or private business data.

## Intake verification

The issuer records the exact UTF-8 submission digest at receipt. The repository verifier checks that digest, the pinned packet and scenario roster, the independent-expectation digest, and duplicate or missing verdicts. The expectation digest is SHA256 over the canonical JSON array of `case_id`, `scenario_id` and `independent_expectation` from each returned finding, sorted by case and scenario ID.

```powershell
$env:PYTHONPATH = 'src'
python -m benchmarks.slm10.blind_review_receipt --packet '<repository-packet-directory>' --verdict '<private-verdict.json>' --received-sha256 '<issuer-recorded-sha256>'
```

For Planning 0.4 supply `--phase-one-file '<private-phase-one.json>'` and `--phase-one-sha256 '<registrar-recorded-canonical-sha256>'`. The verifier returns counts and digests suitable for reconciliation. The registrar checks reviewer independence and authority against its private assignment record and signs the intake. Retain the submitted files and exact review scope outside the repository until approved for publication. [Authenticated release workflow](RELEASE_WORKFLOW.md)

## Reconciliation and sign-off

Freeze and hash the independent expectation before the source oracle is opened. A separate reconciler joins candidate inputs, independent expectation, oracle and witness using the pinned candidate digest and case/scenario IDs. Record both expectations, counterevidence, impact, affected scope and whether the defect is in the prompt, world, witness, evaluator, or partition. Preserve every original discrepancy. Reissue affected content as a new candidate digest and assign blind re-review to an independent reviewer. Keep disagreement BLOCKED until the accountable review owner records its resolution.

Review returns an evidence input for the credential issuer. The issuer must independently bind the exact candidate, roster, runner, runtime, hardware and evaluator scope. A completed packet does not by itself authorize dispatch. Release dispositions remain separate for read-only mechanical, stateful, affirmative write and strict end-to-end scopes.
