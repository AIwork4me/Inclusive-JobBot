# P0-B SDK terminal-output compensation

The four-arm Qwen3.5-2B and Ministral-3-3B experiment is preregistered as `IJ-SLM11-P0B-ONLINE-OUTPUT/1.0`. The full 192-slot physical panel is `PASS` for capture and replay. D and F completed 96 slots each through the local Antigravity SDK and Radeon, with 96 and 120 provider requests respectively. This panel contributes zero formal core trials. [Capture runner](../benchmarks/slm10/online_compensation.py) · [Offline scorer](../benchmarks/slm10/online_compensation_score.py)

## Physical results

Each arm has 24 observations on 12 independent case units at two seeds. Counts below are PASS. Remaining observed assessments are FAIL. All 192 slots had a complete tool-free terminal stop.

| Model | Arm | Schema | Facts | Usable | Uncertainty | Median prompt / completion tokens | Requests per trial | Trial wall P50 / P95 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5 | Native | 24 | 10 | 10 | 16 | 156 / 31 | 1 | 3,242 / 3,773 ms |
| Qwen3.5 | Host normalization | 24 | 10 | 10 | 16 | 156 / 31 | 1 | 3,231 / 3,366 ms |
| Qwen3.5 | Grammar | 24 | 8 | 8 | 14 | 156 / 30 | 1 | 3,256 / 3,280 ms |
| Qwen3.5 | Bounded retry | 24 | 10 | 10 | 16 | 156 / 31 | 1 | 3,223 / 3,288 ms |
| Ministral | Native | 0 | 12 | 0 | 14 | 148 / 30 | 1 | 3,252 / 3,353 ms |
| Ministral | Host normalization | 24 | 12 | 12 | 14 | 148 / 30 | 1 | 3,252 / 4,288 ms |
| Ministral | Grammar | 24 | 12 | 12 | 14 | 148 / 30 | 1 | 3,258 / 3,753 ms |
| Ministral | Bounded retry | 0 | 16 | 0 | 16 | 321 / 60 | 2 | 6,512 / 7,060 ms |

- Qwen3.5 already satisfied the public shape in every native slot. Retry never triggered. The grammar lost correct facts in both repeats of one case. Neither host normalization nor bounded retry changed the usable outcome.
- Ministral gained 12 usable results across six cases under host normalization and under grammar, with all original fact outcomes preserved by each. Both met the preregistered descriptive threshold. Paired median trial-wall changes were +3.39 ms and +4.91 ms. Both arms used one provider request and the median paired token changes were zero.
- Ministral retry triggered in all 24 slots. Four observations across two cases gained correct facts. Usable output remained at zero because the terminal shape still failed. Median paired costs were an extra request, 173 prompt tokens, 31 completion tokens and 3,258 ms.
- The 1,596 historical counterfactual records cover a different task surface. All production and tool-backed compensation claims retain HYPOTHESIS. MiniCPM5 has a separate repeat and termination contract. [Historical replay](../atlas/slm/v1.0/tc-output-normalization-replay.json) · [MiniCPM5 retest](SLM11_MINICPM5_REPEAT_TERMINATION.md)

The portable publication retains the exact public provider requests and response bytes, projected observer records, per-trial dispositions and Radeon process samples. The exact raw SDK workspace messages, native prompt token IDs and complete private traces stay on the workstation under the recorded digests. Private replay verified both runs before export. Public replay independently recomputes the outcomes and resource summaries from the published projections. [Manifest](../evidence/IJSLM/online-compensation/manifest.json) · [Qwen3.5 scores](../evidence/IJSLM/online-compensation/D/score.json) · [Ministral scores](../evidence/IJSLM/online-compensation/F/score.json)

## Cohort and registration

The panel uses 12 newly authored synthetic inventory bulletins. Each of four strata contributes three prompts covering confirmed records, plausible decoys, incomplete or conflicting records, and quoted remarks. The panel contains English and Chinese prompts, a zero-count record, and four expected unknown dispositions. The cases were authored for this panel without selecting, editing, or repurposing a TC-V3 case, seal, model answer or expected value. Independent human validation remains pending.

Each model receives the same 12 prompts at seeds `11731` and `11743`. The four arms run in paired case and seed blocks with balanced arm positions and adjacent arm pairs at each seed. The second seed reverses case order. The roster has 96 slots per model, 192 total. The retry cap yields at most 120 provider requests per model and 240 in total. Temperature is zero, prompt caching and thinking are disabled, and each request has a 256-token completion ceiling. The two seeds repeat observations of the same cases. Treat the 24 per-arm observations as paired descriptive data with 12 distinct case units.

| Registered input | SHA256 |
| --- | --- |
| Public prompts and strata | `d4606f355296d3da14cc61cf46dcfc0233b614b604152a2f332f752313708160` |
| Ordered per-model roster | `663cc29ed4a75942a96ca3223f9d0bae81140c6011086f4139292059d070beb5` |
| System and retry instructions, schema, SDK wrapper and provider settings | `00e33d698a750abe25587829c85e00c8c1e6fa17321fcfffcd1fc6446695fea2` |
| Offline expected answer table | `03915fe47330dadd7c494abf4f9cdf3f5b97a6a6b1af3f2389ea9861fe4d128f` |

The Antigravity harness adds the current time and workspace details to session messages. The boundary verifies that the SDK user message contains the complete registered prompt and preserves that raw SDK request. It then submits the same explicit system and user messages for all first attempts. The model sees only the bulletin, task and public output contract. The offline expected answer table is available only to the scoring entry point. The shared request adapter uses loopback, defines zero callable tools, denies all SDK tool policy, and disables the SDK's built-in retries. This terminal-only scope isolates output behavior after facts are available. Tool selection, real callbacks, downstream business writes, and the separate MiniCPM5 repeat and termination investigation fall outside this panel. [Compensation guide](SLM10_CAPABILITY_COMPENSATION_GUIDE.md)

## Intervention arms

| Arm | Online behavior |
| --- | --- |
| `MODEL_NATIVE` | One unconstrained request through the SDK. Deliver the raw SDK text after confirming a complete, tool-free terminal stop and equality with the captured provider text. |
| `HOST_NORMALIZED` | The same request. Extract only the exact object bytes inside one whole-answer JSON fence after the same terminal check. Preserve ambiguous wrappers, duplicate keys, and trailing prose as raw failures for assessment. |
| `RUNTIME_CONSTRAINED` | One request with llama.cpp's `response_format` JSON Schema path. The schema constrains public keys, types and state labels. It contains no per-case business facts. An unsupported provider request is retained as an arm failure when captured. |
| `RETRY_ASSISTED` | Start with the original request. After a validated terminal stop, permit one fresh SDK session if the raw result fails the public shape check. Append a fixed format-only reminder to the same prompt and keep both attempts. Scope, business facts and seed stay paired. A syntactically valid but wrong answer does not trigger a retry. |

## Offline assessment and evidence

The primary endpoint is usable output. It requires an exact bare JSON shape, exact literal facts, and a tool-free terminal path. Score these components separately so fenced-but-correct facts, wrong values in valid JSON, early stops, extra fields, and false certainty remain visible. Unknown cases require `state: unknown` and both value fields explicitly null. The report includes all four result dispositions and matched transitions from `MODEL_NATIVE` for every endpoint.

The bound for supporting a treatment on this panel is complete matched evidence, at least one original `FAIL` to treatment `PASS` transition for usable output, and zero original `PASS` to treatment `FAIL` transitions for usable output, facts, uncertainty or absence of tool proposals. Report each seed and case through the row-level evidence. Analyze D and F independently. The panel establishes a scoped effect estimate and its resource cost. Generalization to tool-backed production trajectories requires its own assessment.

The runner records per-attempt raw SDK request, provider request and SSE bytes, stop reason, SDK chunks and text, parsed response, native observer projection, request and token counts, and timing. It keeps original SDK text and delivered text independently. The scorer checks the request treatment, raw response digest and projection, and native observer linkage. It includes absolute and paired P50/P95 resource summaries for SDK and provider wall time, prompt and completion tokens, native prompt and decode time, trial wall time and host normalization time with observed and missing counts. Trial wall time includes the per-attempt capture write. Provider boundary wall time includes buffered wire validation, so this experiment has no time-to-first-token measurement. GPU counters attribute work to the server process across the candidate session. The panel has no per-arm GPU power, energy or cost measurement.

The private capture binds the run ID, Git SHA, source checksums, model repository, revision and GGUF hash, engine build and binary set, Vulkan backend, Radeon lease and GPU identity, SDK version and harness hash, public cohort and roster. Each attempt and completed slot has its own digest. The final run file binds the trial index, launch, GPU counters and native trace. Offline scoring binds its summary to the run file and scorer digests. Interrupted reserved slots are `BLOCKED`. Unreserved slots are `NOT_RUN`. Keep the interrupted capture directory for inspection and use a fresh run identity for any separately authorized repeat. Raw traces stay in the private runtime directory.

## Reproduce

Run `python -m benchmarks.slm10.online_compensation_report` to verify the portable publication without dispatch. The two registered entry points can also print their preregistration without dispatch. Run either physical command only after the workstation owner releases the AG-11 slot and the other frozen or diagnostic GPU queues have yielded. The explicit dispatch uses the existing shared Radeon lease and requires a fresh candidate-specific capture directory. No hardware or OS settings need to change.

```powershell
$assetRoot = (Resolve-Path ../..).Path
$python = Join-Path $assetRoot '.venv/Scripts/python.exe'
$env:PYTHONPATH = '.;src;benchmarks/tool_calling/runner'
& $python -m benchmarks.slm10.online_compensation
& $python -m benchmarks.slm10.online_compensation_score

$private = Join-Path $assetRoot '.runtime/ij-slm-1.0/online-compensation-v1'
$d = Join-Path $private 'D'
$f = Join-Path $private 'F'
& $python -m benchmarks.slm10.online_compensation --dispatch --candidate D --assets $assetRoot --output $d
& $python -m benchmarks.slm10.online_compensation --dispatch --candidate F --assets $assetRoot --output $f
& $python -m benchmarks.slm10.online_compensation_score --capture $d --output (Join-Path $private 'D-score.json')
& $python -m benchmarks.slm10.online_compensation_score --capture $f --output (Join-Path $private 'F-score.json')
```

The focused regression exercises the real Windows SDK against a scripted loopback SSE provider, plus software controls for matching, evidence integrity, normalization, retry, uncertainty and missing-resource attribution. The scripted loopback control is software evidence. The physical table above is derived from the separate checked Radeon archive. [Regression coverage](../tests/regression/slm10/test_online_compensation.py)
