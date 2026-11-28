# MISSION IJ-NANO-1.2R — Offline Rescore Integrity & Protocol Evidence Recovery

## 0. Mission Identity

- Repository: https://github.com/AIwork4me/Inclusive-JobBot
- Issue: #10
- Draft PR: #11
- Branch: `mission/ij-nano-1.0-slm-native-agentic-runtime`
- Audited HEAD: `26445d6f79949d51da7a9ce3f5669b032ab51efe`
- Current reported experiment: `ec5b95357e960f99`
- Offline-rescore source experiment: `7a1b9d7d160202d8`
- Original diagnostic experiment: `36bfed1d55a9987b`
- Current reported coverage: 2,184 logical slots, including 1,397 offline re-scores and 787 new physical trials.

Act as an independent Benchmark Scientist, Python Runtime Engineer, Statistical Reviewer and Evidence Integrity Auditor.

This is a narrowly scoped corrective continuation of IJ-NANO-1.2.

Do not restart the entire research mission.

Do not redesign NanoAgent.

Do not start N03 formal physical profiling using the current protocol rankings until the quantitative N02R evidence has been independently reconciled.

Preserve all original physical evidence and source-level causal findings.

---

## 1. Immediate verdict reconciliation

Temporarily reopen the quantitative comparison scope of:

`N02R_MODEL_PROTOCOL_BEHAVIOR_CHARACTERIZED`

Preserve independently valid scopes:

- Physical runtime identity.
- Source-level lazy-grammar investigation.
- Physical protocol counterfactual probes.
- N05AR evaluator qualification.
- Parser/evaluator integration qualification within its tested scope.
- Historical experiment evidence.

Do not invalidate a physical observation merely because a downstream analysis implementation is defective.

Maintain separate verdicts for:

- Physical execution coverage.
- Artifact integrity.
- Replay integrity.
- Semantic scoring integrity.
- Statistical comparison validity.
- Protocol recommendation eligibility.

---

## 2. RS01 — Reproduce the critical offline-rescore defect

Inspect:

`scripts/ij_nano/n02r_rescore.py`

The audited implementation contains:

```python
stage, path, http_json, http_error, latency = art["stages"][-1]
```

However, the actual response artifact represents each stage as a dictionary:

```python
{
    "stage": ...,
    "path": ...,
    "http": ...,
    "http_error": ...,
    "latency_s": ...
}
```

Python dictionary unpacking returns keys rather than values.

Consequently, the audited statement can assign:

```python
http_json = "http"
```

The subsequent type check then passes None into the parser.

### Mandatory red reproduction

Before changing the implementation:

1. Select an existing hash-verified artifact containing a valid model answer.
2. Execute the exact audited offline-rescore path.
3. Record the extracted stage, path, response, error and latency types.
4. Demonstrate whether the parser receives the original response or None.
5. Compare the resulting verdict against independently computed expected behavior.

Use the actual published artifact:

`evidence/IJNANO/N02R/runs/7a1b9d7d160202d8/responses/003abb9e2604141bd8b016ec.json`

and other positive and negative witnesses.

Determine the exact number of affected records among the 1,397 offline-rescored trials.

Do not assume the impact count without verifying the records.

### Repair

Read stage fields explicitly by key.

Validate the artifact schema before replay.

Reject:

- Missing fields.
- Incorrect field types.
- Unknown stage schemas.
- Inconsistent trial identities.
- Invalid artifact references.
- Hash mismatches.
- Invalid stage ordering.

Never silently convert an invalid artifact into an ordinary model failure.

Use a separately classified evidence-integrity failure.

---

## 3. RS02 — Replay complete multi-stage semantics

Audit P7S two-stage re-scoring.

The existing replay path appears to score only the final stage.

Reconstruct the full causal execution:

1. Original task.
2. Stage-one request.
3. Stage-one response.
4. Actual selected tool.
5. Stage-two request.
6. Stage-two response.
7. Final action.
8. Final semantic verdict.

Verify that the second-stage request is derived from the actual selected tool, not the expected tool.

A wrong stage-one selection must not be hidden by a correct-looking final response.

Measure total latency and tokens across both stages.

If the preserved artifacts are insufficient for complete reconstruction, classify the affected trial as EVIDENCE_INSUFFICIENT and selectively re-execute it.

---

## 4. Replay integration qualification

Create an end-to-end control suite:

Raw API artifact → Artifact loader → Stage reconstruction → Parser → Evaluator → Trial record → Analyzer.

Include at least:

- Correct chat JSON.
- Correct completion JSON.
- Correct native tool call.
- Valid DSL.
- Correct two-stage action.
- Incorrect first-stage selection.
- Empty final content.
- Actual HTTP error.
- Missing response.
- Malformed artifact.
- Duplicate JSON key.
- Unexpected tool argument.
- Invalid stage order.
- Hash mismatch.
- Wrong trial identity.
- Missing telemetry.
- Valid response stored in a dictionary.
- Incorrect dictionary-unpacking mutant.

Require positive controls to reach the parser as actual response dictionaries.

Do not merely test the comparator in isolation.

Add mutation tests that restore the audited dictionary-unpacking defect.

The qualification gate must reject the mutant.

Publish:

`N02R_OFFLINE_REPLAY_INTEGRITY_GO`

only after red-to-green evidence exists.

---

## 5. RS03 — Reconstruct the complete evidence chain

Independently verify all 2,184 current logical slots.

For every slot validate:

- Experiment identity.
- Trial identity.
- Expected roster membership.
- Model identity.
- Runtime identity.
- Backend.
- Source experiment identity.
- Source trial identity.
- Artifact path.
- Actual artifact SHA256.
- Artifact schema.
- Stage count.
- Semantic scoring.
- Physical session evidence where required.

Do not infer evidence validity merely from the presence of a hash field.

Distinguish:

- Hash field present.
- Artifact exists.
- Artifact hash verified.
- Artifact contents valid.
- Physical provenance verified.
- Replay semantics valid.

Check that the 1,397 reused trials retain valid original physical provenance.

Compare frozen source and destination experimental manifests.

Verify actual request identity, model identity, engine identity, server profile, backend and task identity.

Byte-identical request-renderer source is necessary but may not be sufficient for identical request behavior.

Require explicit evidence for any reused factor.

---

## 6. Re-score without unnecessary GPU execution

Preserve experiments:

- `36bfed1d55a9987b`
- `7a1b9d7d160202d8`
- `ec5b95357e960f99`

Do not overwrite their original records, manifests or seals.

Create a new immutable analysis/replay identity.

Re-score the complete affected corpus using the corrected artifact loader.

Where practical, independently re-score all 2,184 artifacts to verify consistency.

Produce a row-level reconciliation:

- Original verdict.
- Corrected verdict.
- Original parser output.
- Corrected parser output.
- Original failure reasons.
- Corrected failure reasons.
- Original telemetry.
- Corrected telemetry.
- Source evidence.
- Change classification.

Classify each trial:

- UNCHANGED_VALID
- CORRECTED_FALSE_NEGATIVE
- CORRECTED_FALSE_POSITIVE
- TELEMETRY_CORRECTED
- EVIDENCE_INSUFFICIENT
- PHYSICAL_REEXECUTION_REQUIRED

Only re-execute trials for which preserved evidence cannot establish a valid result.

Use the existing host-wide GPU lease for any necessary physical re-execution.

Do not spend additional GPU time on recoverable offline scoring errors.

---

## 7. RS04–RS08 — Statistical and telemetry reconciliation

### Paired comparisons

For each protocol comparison:

- Intersect the actual applicable task IDs.
- Compare identical model and task instances.
- Report paired sample size.
- Report discordant outcome counts.
- Use appropriate paired confidence intervals.
- Use McNemar testing or another justified paired method.
- Account for repeated task families and worlds where appropriate.

Do not compare P5A's 30-task aggregate directly against a 60-task aggregate and interpret the difference as a protocol effect.

### Protocol-specific comparisons

For P7S versus single-shot JSON, compare only the same structured-action tasks.

For P7 versus other representations, compare only its applicable task families.

Keep inapplicable combinations outside model failure denominators.

### Reasoning budget

Recalculate T0/T1/T2/T3/T3b results.

Distinguish observed point estimates from statistically supported improvements.

Do not claim that 256 tokens is optimal unless alternative reasoning budgets have actually been compared.

The existing total-generation-budget panel is not equivalent to a reasoning-budget sweep.

### Resource telemetry

Recover endpoint-specific telemetry from original artifacts, where actually available:

- Chat usage.prompt_tokens.
- Chat usage.completion_tokens.
- Completion tokens_evaluated.
- Completion tokens_predicted.
- Cached tokens.
- Timing records.
- Stop type.
- Truncation.
- Per-stage latency.
- Total task latency.

Validate the semantics of each engine field before using it.

Do not treat missing telemetry as zero.

Publish the measured sample count for every mean and percentile.

### Failure classification

Separate:

- True model semantic error.
- Structural generation error.
- Empty final output.
- Generation truncation.
- Legitimate tool-call-only output.
- Transport error.
- Parser error.
- Artifact error.
- Replay error.
- Unsupported telemetry.

Do not classify absent evidence as empty model output.

### Statistical claims

Do not infer statistical equivalence from overlapping marginal confidence intervals.

Use preregistered practical equivalence margins and appropriate paired analysis where an equivalence claim is required.

Otherwise report the evidence as inconclusive.

---

## 8. Scientific conclusion recovery

Re-evaluate every N02R scientific claim.

Explicitly answer:

1. How many records were affected by the rescore loader defect?
2. How many originally failed trials become correct after repair?
3. How many originally correct trials become incorrect?
4. What is the corrected semantic accuracy of each model/protocol?
5. What is the corrected structural validity?
6. What is the corrected empty-final-content rate?
7. Does bounded reasoning still improve all three models?
8. Does thinking-off still harm S2 and help S3?
9. Does DSL actually have zero semantic success?
10. Does two-stage execution remain inferior on matched tasks?
11. Does native function calling outperform structured-answer recording?
12. Which conclusions changed?
13. Which Runtime Profile recommendations remain justified?

Do not defend previous conclusions when corrected evidence contradicts them.

Preserve negative results.

The mission succeeds by recovering scientific truth.

---

## 9. Required deliverables

Publish:

- `reports/IJNANO_02RR_OFFLINE_RESCORE_ROOT_CAUSE.md`
- `reports/IJNANO_02RR_QUANTITATIVE_EVIDENCE_RECONCILIATION.md`
- `evidence/IJNANO/N02RR/replay_qualification.json`
- `evidence/IJNANO/N02RR/trial_reconciliation.jsonl`
- `evidence/IJNANO/N02RR/evidence_verification.json`
- `evidence/IJNANO/N02RR/corrected_protocol_matrix.json`
- Corrected model/protocol recommendation candidates.
- Red/green test evidence.
- Paired statistical comparison report.
- Update the existing N02R report with a clearly identified supersession notice.

Do not remove the original historical values.

Reconcile stale experiment identities, gate names, denominator descriptions and PR status.

Correct the PR description, which still primarily reflects IJ-NANO-1.1.

---

## 10. Acceptance gates

Grant:

`N02R_OFFLINE_REPLAY_INTEGRITY_GO`

when artifact loading and replay qualification are proven.

Grant:

`N02R_QUANTITATIVE_EVIDENCE_RECONCILED`

when all logical slots are accounted for, with valid evidence or explicit blocker classifications.

Re-grant:

`N02R_MODEL_PROTOCOL_BEHAVIOR_CHARACTERIZED`

only for the actual qualified comparison scopes.

Do not require every research hypothesis to be supported.

A corrected negative scientific result is acceptable.

---

## 11. Continue N03 immediately after scoped closure

Once the corrected N02R evidence is available, continue the existing N03 mission.

Preserve:

- C01–C32 taxonomy.
- 640 development cases.
- 320 reserved confirmation cases.
- S1/S2/S3 mandatory model arms.
- R1/R2 matched reference panels.
- Cognitive capability curves.
- Capability-to-Runtime mapping.

Use the corrected N02R results as development evidence.

For each cognitive family, independently qualify its actual dataset, parser and evaluator integration.

Do not rely only on a generic N05AR PASS.

Include a representative known-correct positive witness traversing the complete physical benchmark evidence path.

Do not freeze DSL, two-stage or thinking-policy decisions solely from the superseded matrix.

Continue N06B/C and the 3,600-slot causal pilot according to the original mission order.

Formal business claims remain subject to IJ-B-002.

---

## 12. Publication

Continue using Issue #10 and Draft PR #11.

Run all regression tests and the fail-closed publication check.

Record:

- Original experiment SHA.
- Corrected replay identity.
- Exact number of changed verdicts.
- Remaining blocked evidence.
- Revised scientific conclusions.
- Next N03 execution command.

Push normally and verify the remote SHA.

Do not merge or force-push.

Execute immediately, prioritizing offline evidence recovery over additional GPU experiments.
