# LFM3-HA-1.0 evaluation and handoff contract

This P0 extension uses the frozen IJ-SLM base and single Radeon lease. It
attributes zero trials to the existing 36,550 slots. The five original
TC-V3 seals, including all 1,650 Gemma trials, remain the core record.

## Admission panel

Use frozen LFM3 Q8_0, the existing Windows Vulkan observer and SDK 0.1.24.
Verify file and harness hashes before launch and the base hash again after
the panel. Use the shared GPU mutex and process-bound server launcher.
Check the incumbent controllers and owner-authorized AG-11 window before
taking the lease. Release the GPU between bounded sessions.

Use separate server launches for no LoRA and each registered adapter.
Keep runtime, model alias, prompt bytes, tokenization, seed, context and
decode settings fixed. Test scale 0 and scale 1 within an adapter launch.
Use native pre-sampling token log probabilities at identical token prefixes,
with greedy generation and a fresh request. The diagnostic launch disables
server-wide prompt cache and context checkpoints as well as request caching. Freeze
a 1e-5 absolute log-probability tolerance with identical token IDs and
ranking for no LoRA versus scale 0 and for same-arm replay. A scale 1
intervention requires a finite difference of at least 1e-3 on a token
present in both top-token sets on at least one fixed prefix, reproduced
by a second scale 1 request. Following a scale 1 request, a scale 0 request
must again match the baseline. Record native numerical evidence and
observed adapter allocation by backend. A separate loaded adapter must
produce its own isolated observations.

A missing adapter, wrong architecture and wrong tensor shape must be
rejected before readiness. Assert rejected model and adapter routing at the
project request boundary because native llama.cpp numeric adapter IDs are
server-local and do not encode the expected weight hash. Exercise direct
JSON, SSE, native tool parsing and Antigravity SDK callbacks on synthetic
cases. Record GPU engine activity and memory for the launched process,
along with offload and adapter placement. A missing signal yields an
explicit failed or blocked check. Keep physical and software-only controls
identifiable by run ID. Full M1 requires each of HA-O, HA-P and HA-H to pass
all admission checks.

## Subsequent experiment gates

| Stage | Planned scope | Release dependency |
|---|---|---|
| M2 author reproduction | 150 + 40 tasks per original harness, 1,140 trajectories per complete matched lane | Exact task roster, image digests, harness versions, scope isolation and minimal admission. Report BF16/vLLM and GGUF portability as separate lanes. Hermes 8K needs its own compatibility verdict. |
| M3 development | 60 case/world/seed pairs across W0-W3 and Direct/Original SDK, 480 trajectories | M1 admission and SDK transport/attribution controls. Preserve an original SDK arm when testing SDK_MATCHED_CONTEXT. |
| M4 historical | 1,650 physical trials per adapter, 4,950 total | Frozen TC-V3 extension enrollment. Run a new 1,650-trial base control on any changed pairing identity. |
| M4 independent | LFM3-HA-HOLDOUT-V1 with separate authoring and blind business expectations | Dev freeze, witnesses, negative controls, near-duplicate review and independent release. |
| M5 complexity | 1,500 MULTITOOL and 4,160 Planning trials per selected adapter | M4 quality-resource Pareto selection and scope-specific independent evaluator and dispatcher release. |
| M6-M8 transfer | A0-A7 runtime/weight factorial and 600 JOB-V2 tasks | Independent runtime component controls, NanoAgent provenance from PR #11, and a qualified business oracle. |
| M9 portability | Dynamic and merged precision matrix | High-precision merge identity checks and actual target runtime/operator support. DX-M2 physical stays NOT_RUN until measured. |
| M10-M12 research and handoff | Training design and versioned Capability Atlas | Independent training environments and observed transfer evidence. Export accepted, rejected and untested configurations with provenance. |

Before the final holdout, freeze the primary endpoint, sample size,
non-inferiority margin, allowed exclusions, thresholds and statistical
plan. Pair on task and world. Use exact McNemar for paired binary outcomes,
paired intervals and family- or task-clustered resampling as appropriate.
Treat repeat seeds as repeated observations within business tasks. Report
both jointly solved efficiency and full-cohort costs by outcome, including
retry and timeout overhead. Correct for multiple comparisons and apply
quality and safety constraints before Pareto selection.

Bind each milestone to its evidence digest, exact Git SHA, engine package,
base and adapter weights, GPU identity, tool policy, SDK, dataset and run
ID. Replay before publication and check CI at the published SHA.
