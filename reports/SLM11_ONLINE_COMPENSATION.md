# P0-B SDK terminal-output compensation

The four-arm Qwen3.5-2B and Ministral-3-3B experiment is preregistered as `IJ-SLM11-P0B-ONLINE-OUTPUT/1.0`. Software controls are `PASS`. Physical arms are `NOT_RUN` for both models. This panel contributes zero formal core trials. [Capture runner](../benchmarks/slm10/online_compensation.py) · [Offline scorer](../benchmarks/slm10/online_compensation_score.py)

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

Run the two no-dispatch commands from the linked worktree to verify the registration. Run either physical command only after the workstation owner releases the AG-11 slot and the other frozen or diagnostic GPU queues have yielded. The explicit dispatch uses the existing shared Radeon lease and requires a fresh candidate-specific capture directory. No hardware or OS settings need to change.

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

The focused regression exercises the real Windows SDK against a scripted loopback SSE provider, plus software controls for matching, evidence integrity, normalization, retry, uncertainty and missing-resource attribution. This is software evidence. The model and Radeon cells remain `NOT_RUN`. [Regression coverage](../tests/regression/slm10/test_online_compensation.py)
