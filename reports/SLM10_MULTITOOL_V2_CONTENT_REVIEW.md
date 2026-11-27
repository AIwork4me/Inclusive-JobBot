# MULTITOOL-V2 candidate 0.2 content review

The 600-case roster balance passes. An independent review implementation recovered the terminal facts, concrete tool arguments and dependency depths for all 600 synthetic cases. Content acceptance fails on observable prompt and evaluator discrepancies and on branch prediction from public identifiers. Independent ground-truth provenance remains **BLOCKED**. Formal freeze is **NOT_RUN**, formal dispatch is **BLOCKED**, and physical execution is **NOT_RUN** with zero attributed trials.

The reviewed artifact is candidate `MULTITOOL-V2/candidate-0.2`, manifest SHA-256 `720247005b4cae4ee0315aa91a570b272dd252886e420b5de89cb785808b5119`. A separate Codex reviewer who authored neither the candidate nor its witness examined all 24 instruction templates and ran an independent interpretation of the public data and raw fixture observations across the full panel. This was role-separated AI review of exposed source, with no blind human or organizational review. The review derived its interpretation before comparing it with the graph and never used the supplied witness for that derivation. It used the witness only to construct traces for the two route probes. [Candidate manifest](../atlas/slm/v1.0/multitool-v2-candidate-0.2/manifest.json) · [Independent review implementation](../scripts/tools/review_slm10_multitool_v2.py)

## Coverage and observed complexity

All five call-count bands (`2–3`, `4–5`, `6–10`, `11–15`, `16–20`) contain 120 cases. Each band contains five cases in each of the 24 category and language cells. There are 75 cases per category and 200 each in English, Chinese and mixed language. Each exact action count from 2 to 5 has 60 cases. Each count from 6 to 20 has 24. The 100 repeat cases cover 20 per band and 100 distinct band, category and language cells, with 33 English, 34 Chinese and 33 mixed-language cases. The five-model allocation remains 7,500 trials, made up of 600 Direct first, 600 SDK first and 300 SDK repeats per model. [Candidate roster](../atlas/slm/v1.0/multitool-v2-candidate-0.2/roster.json) · [Execution plan](../atlas/slm/v1.0/execution_plan.json)

| Category | Expected business facts from the public request and observations | Graph critical path | Route and content review |
| --- | --- | --- | --- |
| Parallel | Each named calibration or tolerance value under its requested reference | 1 | Calls are independent. The task supplies both the tool and the reference. The evidence measures execution of independent reads. |
| Serial | Label from the last signage record on the successor chain | 2–20 | Each next reference is data-dependent. Additional length adds links using the same small tool vocabulary. |
| Aggregation | Sum of live counts and the listed-order references where archived and live counts differ | 2 | There are 74 differing-count cases and one all-matching case. The prompts name `conflicts` and its order, and leave its item shape implicit. |
| Conditional | Destination reached from the observed open main path or closed-gate bypass | 2–20 | The fixture covers 39 main and 36 bypass paths. Public identifier parity predicts every branch. |
| Typed transfer | Preview identifier after transferring the exact caption objects and requested format | 2 | There are 36 SRT and 39 VTT cases. Payload order has observable coverage. Caption read order conflicts with the public instruction. |
| Recovery | Checksum reached from the one scheduled retry or the stated mirror | 2–20 | The fixture covers 40 retry and 35 mirror cases. Public identifier parity predicts every fault type. |
| Scope update | Replacement venue and features keyed only by its new references | 2 | All 75 cases supply replacement scope through a synthetic host event. The scorer matches that event and its route. The sandbox still serves obsolete records. |
| Authorization | Final consent decision and note from the permitted excerpt or the redaction guide | 2–20 | The fixture covers 40 permitted and 35 withheld cases. Public identifier parity predicts every decision. Tools only read. |

The four chain categories contribute 300 cases whose critical paths match their action counts. The other 300 have a critical path of one or two, with larger action counts increasing independent calls or the size of a batched payload. Ninety-six cases require more than 16 calls across the graph, with 12 per category. These are software-derived call counts and dependency depths. Model turns and effective concurrency under either physical transport are **NOT_RUN**.

## Acceptance findings

1. **Public identifiers reveal the conditional outcomes.** The last hexadecimal digit of the model-facing gate, primary image reference, or initial consent reference predicts the branch in all 225 applicable cases. Even means main route, retry, or permitted, respectively. The evidence still enforces the expected read and later calls. The fixture cannot establish that selection depended on the observation. Each case has one fixed world. Use branch allocation independent of the visible identifier and replay paired worlds with the same public task and different branch observations. [Fixture authoring](../benchmarks/slm10/multitool_v2_cases.py) · [Parity derivation](../scripts/tools/review_slm10_multitool_v2.py)
2. **The scorer accepts a caption call sequence that the prompt disallows.** The three language templates direct the assistant to read the captions in the listed order. The graph makes the reads independent, with the preview depending on all of them. Reversing the chronological reads across distinct turns while preserving preview order returned `PASS` in all 68 cases with at least two captions. `MT2-C02-typed_transfer-03-en-0` provides a minimal reproduction. Clarify that reads may run in any order if the intent is to score only ordered transfer. Encode read-order edges if the wording reflects the required workflow. [Caption fixture](../benchmarks/slm10/multitool_v2_cases.py) · [Reverse-order replay](../scripts/tools/review_slm10_multitool_v2.py)
3. **Scope enforcement has evidence at the scorer, and the sandbox boundary remains open.** After delivering the trusted update, a direct simulator read against the old venue and its first obsolete reference returned `obsolete` in all 75 cases. `MT2-C02-scope_update-02-en-0` reproduces it using one stale read. The mismatch is an authorization and scope-delivery gap for a future matched runner. Enforce the new scope before executing access reads and verify that refused calls release no stale data. [Sandbox](../benchmarks/slm10/multitool_v2_witness.py) · [Stale-scope probe](../scripts/tools/review_slm10_multitool_v2.py)
4. **The candidate's business expectation shares the generator with the fixture.** `Author.add` writes the same authoring input to the graph and sandbox. Each category builder supplies `Author.finish` with its terminal answer. The witness separately reads the synthetic service and reconstructs the answer. This review independently matched that interpretation against all 600 cases, but the source for the business scenario and its expected answer remains a single generator. Publish separately authored business expectations that can reject plausible fixture-design errors, and resolve the `conflicts` element type explicitly in the public contract. [Case and oracle authoring](../benchmarks/slm10/multitool_v2_cases.py) · [Software witness](../benchmarks/slm10/multitool_v2_witness.py)
5. **The source demonstrates eight parameterized workflow families.** All 600 literal prompts are distinct, with 24 distinct instruction strings after removing the structured data. The earlier candidate calls the same eight builders. The corrected roster changes counts and identities within those families. The archived MULTITOOL-V1 prompts have no exact text match, while the archived eight-category rubric covers related workflow forms. The evidence supports the described template distribution. Its scope is insufficient to establish independent held-out business breadth or persisted approval handling. The separate stateful sandbox requires its own source-linked cases and evidence before it can contribute to the candidate's coverage. [Balanced generator](../benchmarks/slm10/multitool_v2_balanced.py) · [Archived V1 rubric](../benchmarks/multitool_v1/README.md) · [Stateful sandbox](../benchmarks/slm10/multitool_stateful.py)

## Reproduction

From the worktree with the repository Python environment, run the commands below. The candidate replay verifies the existing artifact bytes and returns `PASS 600 software witnesses`. The content review yields zero terminal, route or dependency mismatches and reproduces the acceptance findings. The focused candidate, balance and graph suite passed 10 tests.

```powershell
$env:PYTHONPATH = '.;src;benchmarks/tool_calling/runner'
python -m benchmarks.slm10.multitool_v2_balanced
python -m scripts.tools.review_slm10_multitool_v2
python -m pytest -q -o asyncio_mode= tests/regression/slm10/test_multitool_v2_candidate.py tests/regression/slm10/test_multitool_v2_balanced.py tests/regression/slm10/test_action_graph_v2.py
```

## 2026-11-27 re-review of candidate 0.3

The independent reviewer reproduced fixes for public-ID parity, caption reading order and stale access. The new manifest SHA-256 is `bc9daa18fb5c9dafc63945c5c791637c3b263b3a8d207e5b72dd3ac10264114c`. The roster SHA-256 is `7b7b54d2a151942dbe06fb639a5d67cca0431cde358dcf619439717c5e395a8a`, and the software certificate SHA-256 is `82899c42b35fb5e46fc74f6ccec856300fd9f9c546d82aa26749726c6929f4d8`. The earlier findings and hashes above describe candidate 0.2. [Revised manifest](../atlas/slm/v1.0/multitool-v2-candidate-0.3/manifest.json) · [Revised software certificate](../atlas/slm/v1.0/multitool-v2-candidate-0.3/software-qualification.json)

| Re-review check | Observed result |
| --- | --- |
| Re-derive terminal facts, concrete paths and dependency depths from public data and raw observations | **PASS** across 600 cases using the independent interpretation above. |
| Predict conditional, recovery or consent branches using public-ID parity | The old rule fails. Both outcomes occur for both parities in all three categories. For every one of the 225 cases, generate the two branch worlds with identical public inputs and test both traces against both worlds. Across the 450 world/trace pairs with matching paths and the 450 crossed pairs, all matching pairs pass and all crossed pairs fail. |
| Reverse caption reads across distinct turns with a correctly ordered preview, then reverse the preview payload too | All 68 valid reordered reads pass and all 68 reversed preview payloads fail. The 68 applicable English, Chinese and mixed prompts explicitly allow arbitrary read order. |
| Check venue access before event delivery, after delivery at the booking turn, in obsolete scope and with an old reference paired with the new venue | The sandbox denies all 75 cases for each probe. Current venue and reference succeed after event delivery in all 75 cases. |

The candidate and expected answers still share their generator. The 600 independently reproduced facts establish consistency with the existing worlds. The `conflicts` item shape remains implicit, the authorization category remains read-only, and broader business expectations still need separately authored evidence. The replay returns **PASS** for 600 software witnesses. Formal freeze and physical execution remain **NOT_RUN**, and dispatch remains **BLOCKED**. [Revised generator and evaluator](../benchmarks/slm10/multitool_v2_revised.py)

```powershell
$env:PYTHONPATH = '.;src;benchmarks/tool_calling/runner'
python -m benchmarks.slm10.multitool_v2_revised
python -m pytest -q -o asyncio_mode= tests/regression/slm10/test_multitool_v2_revised.py tests/regression/slm10/test_multitool_v2_balanced.py tests/regression/slm10/test_multitool_v2_candidate.py tests/regression/slm10/test_action_graph_v2.py
```

This focused suite passed 16 tests. The review probes used the revised module's public `candidate`, `build_case`, `witness`, `evaluate` and `Scenario` entry points and the separate expectation derivation in the review implementation. [Independent expectation derivation](../scripts/tools/review_slm10_multitool_v2.py)
