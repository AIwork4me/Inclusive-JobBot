# LFM3-HA independent qualification

**Independent qualification BLOCKED.** The final holdout is unopened. The proposed contract below needs an independent registrar, business witness authors and reviewers with no role in development scoring. It records 720 proposed tasks, 48 proposed independent families, zero physical trials and zero repeated seeds. The completed 720 transfer trajectories and 6,600 TC-V3 compatibility trajectories retain their supplemental scope. [Measured compatibility](LFM3_HA_6600_TC_CAPABILITY_REPORT.md)

## Proposed freeze

| Item | Rule |
|---|---|
| Primary endpoint | Paired difference in exact scoped completion against Original under the same selected runtime. A pass requires the terminal business answer, legal execution, observation lineage, correct termination and matching persisted state where applicable. Estimate the difference from the task pairs and use family-clustered inference. |
| Task allocation | 48 independently sourced business families, 15 tasks each. English, Chinese and mixed-language inputs are balanced by assignment. One fixed seed per task with the same seed on each arm. A candidate and Original account for 1,440 trajectories across 720 pairs. A shared Original with three LoRAs accounts for at most 2,880 trajectories. |
| Effect and precision | Target an 8 percentage-point improvement. With 35% discordant pairs, a one-sided worst-case Bonferroni level of 0.05/3, and 80% power, the normal approximation requires about 483 pairs. A design effect of 1.35 from 15 tasks per family and assumed intrafamily correlation 0.025 raises this to about 652. Freeze 720 before release. Document actual family clustering and resulting uncertainty. |
| Quality and safety gates | Require at least 80% exact scoped completion and a multiplicity-adjusted one-sided lower bound above zero for improvement. Audit every safety sentinel. Any verified unauthorized execution, cross-scope disclosure or unauthorized persistent state change blocks selection. Any unresolved safety adjudication blocks selection. Report the observed safety denominator and interval separately. |
| Multiplicity | Family-clustered paired confidence intervals and Holm adjustment across at most three preregistered LoRA-versus-Original tests. Report unadjusted and adjusted results. Reserve subtype scores for descriptive analysis. |
| Indeterminate and missing trials | Preserve PASS, FAIL, BLOCKED and NOT_RUN. A complete prespecified pair requires two sealed and adjudicated results. Publish coverage by family and arm. Block selection when any required family is incomplete or a sensitivity analysis treating unresolved candidate trials as failures no longer clears the gate. |
| Candidate selection | Predeclare eligible weight and runtime identities before the registrar reveals tasks. Choose among configurations that meet the same quality and safety gates. Use matched per-success model requests, executed tools, tokens and p95 elapsed time as the ordered efficiency criteria. Improve throughput or cost only with a retained quality floor. No eligible configuration yields `NO_QUALIFIED_CONFIGURATION`. |

Each family must define a distinct business scenario and state transition or readback contract. A renamed reference or relabeled translation of an existing template belongs to the same family. The intake must cover typed parameters, dependent and parallel work, revised scope, recovery, clarification, authorization and stop behavior. Author the public user prompt and tool definitions independently from business expected state. The registrar seals the business witness and scorer contract before revealing the matched tasks, and separately signs task, world and witness identities.

The machine-readable prospective plan records the statistical assumptions and release gates for review before the final holdout opens. [Prospective plan](../configs/lfm3-ha-1.1/holdout-plan.json)

## Release gates and model coverage

| Work | Status | Prerequisite |
|---|---|---|
| Independent holdout measurement | NOT_RUN | Signed intake and freeze, then matched runtime and hardware dispatch credentials |
| Per-finalist MULTITOOL-V2, 1,500 per candidate | BLOCKED | Independent model selection, review, signed issuer authority and matching dispatcher |
| Per-finalist AGENTIC-PLAN-V2, 4,160 per candidate | BLOCKED | Independent Planning bundle, end-to-end runtime and evaluator release |
| JOB-V2, runtime specialization and quantization | NOT_RUN | Matched role-level comparisons and independent deployment credentials |
| Original five-model complex core, 28,300 reserved | BLOCKED | Existing release and dispatcher gates, including Gemma-4-E2B as P0 |

The 36,550 core denominator includes the 8,250 original seals and 28,300 remaining complex slots. Gemma retains its 1,650 sealed TC-V3 slots and full complex allocation. [Original allocation](../atlas/slm/v1.0/execution_plan.json) · [Independent release procedure](../atlas/slm/v1.0/release-review/RELEASE_WORKFLOW.md)
