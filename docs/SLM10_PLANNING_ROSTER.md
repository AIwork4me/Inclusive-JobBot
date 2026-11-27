# Independent AGENTIC-PLAN-V2 roster

The Planning V2 allocation reserves 20,800 trials inside the 36,550-trial IJ-SLM-1.0 core. Each candidate uses the same 800 independent held-out tasks for four first-attempt tracks. These are Direct Plan-first, Direct Acting-first, SDK Plan-first and SDK Acting-first. Each track has 100 tasks per level from L0 to L7. The two SDK tracks also repeat the same 20 selected tasks per level at three fixed seeds, producing 960 repeat trials per candidate.

The roster uses seed `7107` for initial attempts and seeds `101`, `211` and `307` for repeats. The repeat selector cycles through language and authored variant strata after hashing case IDs within each stratum. Trial IDs bind the pinned source manifest, model slot, case, track, panel and seed. The physical evidence registry will separately bind runtime, model weights, SDK, backend, host, GPU and run identities.

## Source bundle

Supply an independently authored synthetic holdout in its own directory. Register its manifest SHA256 separately through the release review. Keep the control file and authoring proof outside the model-facing request path.

| File | Required content |
| --- | --- |
| `manifest.json` | Version `IJ-SLM-AGENTIC-PLAN-V2-INDEPENDENT-SOURCE/1.0`, mission `IJ-SLM-1.0`, suite `AGENTIC-PLAN-V2`, partition `sealed_holdout`, origin `independent_synthetic_authoring`, an `artifacts` map of filename to SHA256, and the `authoring_sources` map |
| `holdout-public.jsonl` | Exactly 100 cases per level. Each row includes `case_id`, `level`, `language`, `task`, `public`, `contract` and `limits`. IDs use `SLM-AP2-L<level>-<id>` and languages use `en`, `zh` or `mixed`. |
| `holdout-controls.jsonl` | Exactly one row per public case with `case_id`, `variant`, the independent version-2 `witness`, and `worlds` containing the expected calls, observations, terminal disposition and facts |
| Distinct authoring proof files | `authoring_sources` entries `public_authoring` and `world_and_witness_authoring` each supply a relative `path` and `sha256`. Review deliberate separation of the task-writing and proof assignments before accepting the manifest pin. |

The public contract uses `goal`, `tools`, `public_fields`, `event_fields` and `action_budget`, with optional `goal_options`. The public fields can omit information needed for clarification. Tool specs declare `inputs` and `outputs`, with optional `description` and local `input_schema`. Limits declare `tool_calls`, `model_requests`, `peak_context_tokens` and `retries`. World records supply `world_id`, `steps`, `disposition` and `facts`. Each step supplies `tool`, `args` and `result`. Additional keys can declare prerequisite step indices in `after`, `equivalent_tools`, a trusted host `event`, and `before` and `after_state` snapshots.

## Mechanical replay

The verifier uses the Planning V2 oracle to replay a single witness against every world for a task. It verifies call identities and resolved arguments, world dependencies, terminal facts, synthetic authorization and tool-call budgets. L0 controls have zero calls, L1 has a one-call path, L2 requires an independent two-call path, and L3 requires a bound dependency. L4 includes alternative executable paths under the same public contract. L5 exercises disruption or safe escalation. L6 includes an 11–20 call workflow with a verified synthetic draft. L7 includes both an approved synthetic commit and safe denial.

A scope update comes through the host event and must feed a later argument with a changed value. Removing that event must invalidate the replay of the original expected path. Restoring success at a recoverable failure must invalidate the original recovery witness path. The advanced levels need independent multi-route cases for both counterfactuals. Every world that includes a synthetic write supplies continuous state snapshots for reconciliation. The verifier checks exact known historical task matches even when a submitted case has a new ID. Source review is also required to detect reused or paraphrased history.

## Commands

Run from the worktree with the repository Python environment and `PYTHONPATH=.;src;benchmarks/tool_calling/runner`.

```powershell
python -m benchmarks.slm10.planning_roster --check-host
python -m benchmarks.slm10.planning_roster --bundle SOURCE_DIR --source-manifest-sha256 SOURCE_SHA256 --out FREEZE_DIR
python -m benchmarks.slm10.planning_roster --bundle SOURCE_DIR --source-manifest-sha256 SOURCE_SHA256 --out FREEZE_DIR --check
```

The first command verifies the existing GPU handoff against the live host and device without acquiring the lease. With no bundle, it reports the allocation, the pending source gate and zero new formal observations. Freezing an eligible bundle writes the roster and a source-linked mechanical replay manifest. `--check` verifies both outputs byte for byte.

The [source candidate](../atlas/slm/v1.0/planning-v2-source-candidate/manifest.json)
contains 800 tasks with separate AI authoring assignments for the public task
and the private worlds and witnesses. Both assignments used the public
contract. The [software replay certificate](../atlas/slm/v1.0/planning-v2-source-candidate/candidate-verification.json)
binds the source, the 2,000 synthetic worlds and the 20,800 reserved trial IDs.
Verify it with `python -m benchmarks.slm10.planning_source_candidate`.
Independent release review of the workload and provenance is pending.

The existing interactive SDK planning control is development evidence.
Archived IJ-0.7 and AEVE results contribute zero IJ-SLM Planning V2 coverage.
Formal dispatch requires the accepted source freeze, a matched runner,
candidate-specific runtime admission and the verified handoff at dispatch.
Strict qualification separately requires the applicable conditional-planning,
persisted-state, authorization and D25 credentials.
