# JOB-V1 independent synthetic holdout

The frozen plan has 600 cases across document review, customer service and product information. Each job has 25 cases in each of eight predefined input cohorts. The text includes English, Chinese and mixed-language operator messages, delivery notes, customer chats, and warehouse requests. Each arm receives the same extracted text attachments and initial business state. No OCR or visual perception runs are included.

| Cohort | Cases | Task design |
|---|---:|---|
| Colloquial | 75 | Informal requests expressed in the operator's language |
| Implicit intent | 75 | Intended business action inferred from the request and setting |
| Multi-document | 75 | Evidence split across short text attachments |
| Missing field | 75 | Order or warehouse reference required before safe delivery |
| Conflicting evidence | 75 | Same-authority documents or messages disagree on the relevant resource |
| User follow-up | 75 | A subsequent user message changes the task to a different order or warehouse |
| Scope denied | 75 | The relevant record exists without a grant for this actor |
| Nonroutine | 75 | Quantity mismatch, overdue delivery or zero available stock |

The first three cohorts define the preassigned routine population. Expected outcomes include 350 successful business tasks, 25 correctly escalated document reviews with drafts, 150 clarification requests and 75 refusals. Each stores its expected disposition separately. These counts describe corpus composition.

## Pairing and treatment contract

The A–F identities and five contrasts follow ADR-003 and the existing JOB-V1 statistical contract. A is the general agent. B specializes tool schemas. C adds deterministic orchestration. D uses the purpose-built configuration with the small model. E uses D's configuration with the reference model. F is the deterministic, no-LLM workflow. Each treatment shares the authorization and audit boundary. Actual engine, model, SDK, prompt, tool and SOP versions belong in the measured experiment manifest.

`planned-cases.json` is accepted directly by the existing paired statistics CLI. Its per-case digest binds the category, routine cohort, initial prose and extracted attachments, scheduled follow-ups, common safety rules and budget, initial SQLite rows and permission scopes. Actual treatment-specific parameters stay in the run configuration. `repeat-selection.json` uses the existing proportional selector with 50 cases, selection seed 23001 and trial seeds 17, 31 and 83. This schedules 3,600 primary and 900 repeat records across the six arms.

## Integration and evidence

- Use `Case.input_initial()` for initial model or task input. Read the scoped world from `worlds.jsonl` only in the test host. Release the user event from the frozen tape as a separate message before final delivery or a draft write, and retain its identity as runtime evidence. The follow-up's text and the oracle stay outside the initial input.
- Feed the same natural input to F through its documented deterministic intake boundary. The benchmark fixture replay uses known-structured intake from a private oracle to exercise the existing skills. That replay cannot be counted as Arm F interpreting an unstructured request.
- Record the final answer as the arm-independent business decision, its authorized observed read resources and results, the delivered follow-up IDs, and trusted SQLite snapshots before and after. Supported read outputs include the exact resource, the current stock or status, and the requested business recommendation. The customer subject normalization accepts a fixed set of equivalent English and Chinese phrases. The oracle checks full persisted draft contents, source hashes, audit, terminal disposition and absence of effects on read-only or unresolved cases.
- Freeze separate raw telemetry for first-pass, automated recovery, human intervention, permission handling and total interactions. Use the prescribed JOB-V1 paired analysis for inference claims. The fixtures contain text and business record outcomes only. They do not establish the 99% correctness or 1/10 model-call targets.

`frozen/manifest.json` binds every frozen file by SHA-256. The data is generated from recurring synthetic templates in three business domains. Fixture verification covers reference business execution with known-structured inputs, checked access denials and authored terminal decisions. Natural-input Arm F has a separate measured result. OCR and Arms A–E remain `NOT_RUN`. [Arm F boundary](ARM_F.md) · [Measured results](../../../reports/IJ07_PURPOSE_BUILT_VALIDATION.md)

```powershell
$env:PYTHONPATH = 'src'
python -m benchmarks.job_productivity_v1.holdout.verify
python -m pytest tests/regression/ij07/test_job_v1_holdout.py tests/job_productivity tests/sop -q
```

Reproduce the bytes in a fresh directory with `python -m benchmarks.job_productivity_v1.holdout.generate --output <new-directory>`.
