# JOB-V1 Arm F software runner

Arm F runs the deterministic intake on the same frozen operator message, text attachments and separately delivered user follow-ups as the paired experiment. It recognizes explicit order and product references, a small warehouse vocabulary, one-line CNY delivery-note quantities and prices, and basic delivery-status language. A later user message changes the target only when it contains recognizable correction language and one identifiable target. Missing, unsupported or conflicting required fields cause the tool path to stop for clarification.

The current intake recognizes an explicit `receipt corrected to` order target, including a mixed-language follow-up. Multiple proposed correction targets still require clarification. Run this configuration in a fresh output directory and retain the original profile's archive under its recorded source identity.

The host seeds a fresh SQLite database from each case's shared world and uses the existing skills and Gateway grants for authorized reads. Document review may persist an unsubmitted review draft only when the frozen host permission grants that write. Customer service returns a ticket recommendation and product information returns available stock. Permission denials come from the Gateway. The intake has no access to the oracle, language and cohort tags, candidate database records, or case-specific answers. The independent oracle assesses the business answer, source evidence and persisted state after execution.

This is a bounded parser for the entities and commercial formats in the synthetic holdout. Its results do not establish general language understanding or performance across other document types. No rows, outcomes, policies or repetition identities in the frozen corpus were changed for this runner. The separate `verify` command still runs the existing baseline fixture checks using known inputs and supplies no Arm F treatment rows.

```powershell
$env:PYTHONPATH = 'src'
python -m benchmarks.job_productivity_v1.holdout.run_f --case JOB-DOC-001 --case JOB-DOC-076 --case JOB-DOC-151 --output .runtime/job-v1-f-diagnostic
python -m benchmarks.job_productivity_v1.holdout.run_f --output .runtime/job-v1-f-primary
python -m benchmarks.job_productivity_v1.holdout.run_f --panel repeat --output .runtime/job-v1-f-repeat
python -m pytest tests/regression/ij07/test_job_v1_arm_f.py -q
```

Use `--resume` with the same configuration and output directory after an interruption. Each case checkpoint preserves its original case and pairing digests, raw task input, delivered user messages, parsed intake, authorized read evidence, persisted state and task verdict. The run fingerprints source files and budgets. The runner binds each terminal JSON record and SQLite database by SHA-256. Repetition seeds are retained for pairing. Arm F has no stochastic model sampling.

Each observed row records zero model requests and tokens, actual elapsed machine time, intake decisions, Gateway transactions and safety counters. Argument counts describe normalized intake fields. Use that same measurement unit on the other arms before comparing argument accuracy. A confirmed correct refusal, clarification or escalated review is a successful semantic verdict with its own outcome and contributes no completed business task. A–E, cross-arm correctness and interaction-efficiency contrasts remain `NOT_RUN`.
