# IJ-NANO-1.2 N02R — Experiment Integrity Audit (addendum PR-D01..PR-D10)

> **SCOPE NOTE (IJ-NANO-1.2R, 2026-11-28).** This audit remains valid for
> PR-D01..PR-D10. A later, separate defect — the offline re-score loader of
> `scripts/ij_nano/n02r_rescore.py` — was found outside this audit's scope
> and repaired under mission IJ-NANO-1.2R; see
> `reports/IJNANO_02RR_OFFLINE_RESCORE_ROOT_CAUSE.md` and the replay
> qualification gate `N02R_OFFLINE_REPLAY_INTEGRITY_GO`
> (`evidence/IJNANO/N02RR/replay_qualification.json`).


- Addendum order: `docs/IJNANO_MISSION_ORDER_V1_2_N02R_ADDENDUM.md`
- Audited implementation: `9b137f6` (experiment `36bfed1d55a9987b`)
- Reproduction evidence: `evidence/IJNANO/N02R/pr_concerns_red_run.txt`
  (13 red / 10 anchors against the audited implementation)
- Repairs: `benchmarks/ij_nano/n02r/{arms_v2,controller_v2}.py`
  (new modules; the audited v1 files are preserved untouched as the
  implementation-of-record for experiment `36bfed1d55a9987b`)
- Post-repair controls: `tests/ij_nano/test_n02r_pr_concerns.py` 24/24 OK
  (full `tests/ij_nano` suite: 206/206 OK)

## Concern-by-concern disposition

### PR-D01 — Information equivalence: REPRODUCED

Request-level manifest (`evidence/IJNANO/N02R/pr_d01_information_manifest.json`):
for `tool_selection` and `structured_action`, arms P0–P4 received **no tool
inventory in the prompt** (the model had to produce exact identifiers from
an unseen 8-tool space) while P5 rendered 8 tool definitions and P6/P7
listed candidates; schema/grammar enums constrained sampling but were never
prompt-visible. For `conditional_branch`/`stop_continue`, exact closed-vocab
labels were not listed for P0–P4. Cross-arm causal comparison under these
arms is confounded (candidate exposure vs constrained decoding).

**Repair:** information-matched arms `M-P0..M-P7` render the same
legitimate information block (tool names + descriptions + required
parameters; candidate lists; slot contracts) into every arm's prompt.
The original arms are retained as the **native-usability scope**
(default-rendering comparison), reported separately from the
**information-matched causal scope**.

### PR-D02 — P5 contract mismatch: REPRODUCED

The audited P5 for `structured_action` supplied `record_answer(args_json:
string)` while the parser required an actual business tool name — a
perfectly valid response per the supplied contract was structurally
rejected (red control `test_perfect_record_answer_response_not_rejected`).

**Repair:** P5 split into **P5A** (native business tools with real typed
parameter schemas; applicable families: tool_selection, slot_extraction,
structured_action) and **P5B** (declared `record_answer` with typed fields;
all families; explicitly labeled structured answer recording, never
business tool execution). Both carry single-vs-multiple tool-call checks,
expected-name verification, and complete argument preservation.

### PR-D03 — P7 applicability: REPRODUCED

P7 rendered a degenerate empty candidate list for `slot_extraction`
("Available answers:" with range "1-0") and had no meaningful enumeration
for `structured_action`.

**Repair:** preregistered applicability registry:
P7 applicable to tool_selection / enumerated_action / conditional_branch /
stop_continue; **inapplicable** for slot_extraction and structured_action
(enumerating would expose the hidden expected argument). `P7S` implements
the separately identified two-stage protocol (enumerated tool selection →
slot filling with the **stage-1-selected** tool; the expected tool is
never leaked). Inapplicable combinations raise at request-build time and
are counted INAPPLICABLE in the denominators, never as model failures.

### PR-D04/D05 — Parser/evaluator integration: REPRODUCED (6 red controls + 2 adjacent defects)

Red controls against the audited parser: contradictory final answer
accepted; multiple tool calls silently collapsed to the first; wrong
`record_answer` name accepted for closed families; unexpected tool
arguments discarded before the evaluator; incorrect DSL slot name
accepted; trailing contradictory DSL content accepted; parser results
carried no warnings/raw/normalization fields. Adjacent defects found
during reproduction: sentence punctuation blocked closed-set matching
(a tool name at end of sentence was unparseable), and ambiguity was
resolved by candidate-list ordering luck.

**Repair (parser v2 in `arms_v2.py`):** all-match closed-set search with
ambiguity and negation detection (28-char cue window); punctuation-tolerant
boundaries; strict duplicate-key JSON parsing (P1/P2/P3/P4 content and
P5 tool-call arguments); duplicate DSL keys flagged; wrong DSL slot names
kept visible to the evaluator; same-line and multi-line trailing
contradiction detection (recognized tokens scrubbed, remainder scanned
against the closed set); multiple tool calls flagged; supplied-contract
name verification; unknown fields always preserved into the evaluator
payload; results carry `{structural_ok, payload, warnings, raw_content,
normalizations}`. Integration gate:
`N02R_PARSER_EVALUATOR_INTEGRATION_GO` (below).

### PR-D06 — Experiment identity integrity: REPRODUCED (gap) → REPAIRED

The audited identity bound suite hash, arm labels, budgets, decoding,
cache policy, engine exe SHA and controller/arms/scorer hashes — but not
the chat template, engine DLLs, GPU identity, evaluator/parser modules,
or quantization. Resume could not detect a changed environment factor.

**Repair:** `controller_v2` identity binds model SHA256 + size +
quantization, chat-template fingerprint (rendered-prompt SHA via
`/apply-template`), llama-server exe SHA + every DLL SHA, backend, GPU
physical identity (name/driver/PNPDeviceID), evaluator implementation
(contracts/comparators/units), parser/renderer/suite/controller hashes,
budgets, decoding, cache policy, server profile, and the arm/applicability
registry. The resume guard refuses to append when the recomputed identity
differs from the frozen manifest; historical manifests are never
overwritten (session records are appended).

### PR-D07 — Physical GPU evidence: REPRODUCED (gap) → REPAIRED

`wait_ready()` recorded the launched PID as socket owner without
independent verification.

**Repair:** the OS-level LISTENING socket owner is resolved via netstat
and must equal the launched PID (fail-closed otherwise); GPU identity,
D-010 offload line, host-wide lease acquisition, server health and the
model file hash are recorded per session in the run manifest. A
successful HTTP request alone is never treated as GPU-execution proof.

### PR-D08/D09 — Response and resource evidence: REPRODUCED (gap) → REPAIRED

The audited trial record trimmed raw responses to 4,000 characters, did
not extract cached tokens/timings/stop types, and the SSE reconciliation
could not distinguish content vs reasoning channels.

**Repair:** endpoint-specific telemetry extraction for chat and completion
shapes — prompt/completion/total tokens, cached tokens
(`prompt_tokens_details`), finish reason / `stop_type`, truncation,
latency, timings when present, thinking-channel text, final-action text,
complete tool calls — with explicit `NOT_CAPTURED`/`UNAVAILABLE` markers
(missing usage is never treated as zero; reasoning-token attribution
recorded UNAVAILABLE per b12359). Complete untruncated responses are
stored per trial as content-addressed artifacts
(`runs/<id>/responses/<trial_id>.json`, SHA256 in the trial record).
Cancellation distinguishes: client connection closed, server cancellation
observed, original generation stopped, slot released (follow-up generation
completes with token accounting), subsequent generation completed.

### PR-D10 — Trial denominators: RECONCILED

Original plan arithmetic: 1,440 main + 720 panel − 144 overlap = **2,016
unique logical slots** (not 2,160). Corrected re-execution plan
(per applicability): 560 unique main slots per model
(M-arms on applicable families + P5A applicable + P5B all + P7S
structured + T2) × 3 = 1,680, plus panel extras (4 arms × 12 tasks ×
budgets 64–512) = 576 → **2,256 unique logical slots**; P7S trials make
two physical requests (selection + fill), so physical attempts exceed
logical slots. The analyzer reports planned/unique/reused/attempts/
evidence-valid/PASS/FAIL/BLOCKED/NOT_RUN/INAPPLICABLE; reused trials are
never counted as independent observations.

## Evidence disposition (summary; full file: `evidence_disposition.json`)

Experiment `36bfed1d55a9987b` is classified **development/diagnostic
evidence**: per-trial classes VALID_AS_IS / OFFLINE_RESCORE_POSSIBLE /
DIAGNOSTIC_ONLY / PHYSICAL_REEXECUTION_REQUIRED / EVIDENCE_INSUFFICIENT
are computed by `scripts/ij_nano/n02r_disposition.py` from the sealed
results; run-level caveats (PR-D06/D07/D08 gaps) apply to all trials at
formal scope. Original results are never modified; the corrected
comparisons execute under the new frozen identity from `controller_v2`.

## Integration gate

`N02R_PARSER_EVALUATOR_INTEGRITY_GO` is granted by
`evidence/IJNANO/N02R/parser_evaluator_qualification.json` when the
end-to-end control suite (raw response → parser → evaluator verdict,
mandatory negatives + preservation checks) is green against the frozen
parser+evaluator implementation hashes — see the qualification generator.
