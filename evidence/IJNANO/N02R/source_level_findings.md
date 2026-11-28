# N02R Source-Level Findings — llama.cpp b12359 (commit b1b770d90)

Investigation method: upstream sources fetched at the pinned commit
(`raw.githubusercontent.com/ggml-org/llama.cpp/b1b770d90/...`), key files
read and quoted verbatim; claims cross-checked against physical probe
behavior on S1/S2/S3 (this directory + `runs/*/probe_audit_*.json`).

## 1. Root cause of the chat-path structured-output failure (S2 observation)

**Mechanism (confirmed in source + physically replicated on S1 and S3, not
only S2):**

1. `common/chat.cpp` — `common_chat_session::apply_sampling` installs the
   grammar derived from `response_format.json_schema` as **lazy** with
   trigger tokens (`sampling.grammar_lazy = grammar_lazy;
   sampling.grammar_triggers = ...`). The jinja autoparser
   (`peg_generator::generate_parser`) sets `grammar_lazy` and attaches the
   template's `thinking_start_tag` / `thinking_end_tags`.
2. `common/sampling.cpp` — `grammar_should_apply()`:
   ```cpp
   if (gsmpl->params.grammar_lazy) {
       // if grammar is lazy, only apply when reasoning budget is not active
       const auto state = common_reasoning_budget_get_state(gsmpl->rbudget);
       return state == REASONING_BUDGET_IDLE || state == REASONING_BUDGET_DONE;
   }
   ```
   **The grammar is deliberately not applied while the model is inside its
   thinking block.**
3. The reasoning-budget sampler exists (`common_reasoning_budget_init`)
   but `reasoning_budget_tokens` defaults to unlimited unless the server is
   started with a reasoning budget / control armed
   (`--reasoning-budget`, `reasoning_control`). With the N02 launch flags
   (plain `--jinja`), nothing forces the thinking block to end.
4. `max_tokens` is a single budget for the whole completion — reasoning
   tokens and final-content tokens share it. There is no per-channel split
   in `usage` (no reasoning breakdown field in b12359), so exact
   reasoning-token attribution is UNAVAILABLE from the API; only the
   `reasoning_content` string channel is observable.

**Net effect:** thinking-capable chat template + json_schema → the model
reasons unconstrained until `max_tokens` is exhausted → empty
`message.content`, `finish_reason: length`. `/completion` requests carry no
chat session → the grammar is installed eagerly
(`llama_sampler_init_grammar`) from token 0 → constrained JSON immediately.
This is why Completion+GBNF and Completion+json_schema PASSed the N02 probe
while Chat+json_schema FAILed. **The failure is engine protocol semantics
(lazy grammar + unbounded default reasoning budget under a shared token
budget), not model weights.**

Interventions implied (tested by arms P2/budget panel): template-honored
thinking-disable; server-side reasoning budget; /completion-based
protocols; larger budgets.

## 2. Escaped-quote GBNF — engine record corrected

The N02 record stated "b12359 rejects escaped-quote GBNF literals (use ["]
char classes)". Source + physical reproduction refine this:

- `src/llama-grammar.cpp` `parse_char` **supports** `\"` (and `\t \r \n \x
  \u \U \\ \[ \] \-`): quoted literals may contain escaped quotes.
- Physical probes (all three models, same engine): the **minimal**
  escaped-quote grammar `root ::= "say \"hi\""` is **ACCEPTED**; the
  reconstructed N02 grammar string is **REJECTED** with
  `failed to parse grammar`. Decomposition probes (F4–F7) pin the exact
  invalid construct.

**Disposition: the N02 failure was incorrect grammar construction, not an
engine defect.** The engine-record note is corrected; char-class quotes
remain the robust style (and are what the N02R grammars use).

## 3. Chat template / thinking configuration

- `chat_template_kwargs` flow into the jinja context as `extra_context`
  (`common/chat.cpp`: `params.extra_context[el.first] =
  json::parse(el.second)`). **Unknown keys are silently ignored by jinja
  templates** — an accepted kwarg proves nothing; effectiveness must be
  verified by rendering diff (`/apply-template` with vs without) plus
  behavioral confirmation (no `reasoning_content`, non-empty content).
  N02R implements exactly this in `verify_thinking_kwarg`.
- `enable_thinking` is a first-class context variable
  (`{"enable_thinking", inputs.enable_thinking}`) honored by templates
  that branch on it (e.g. Qwen3-family); template support is probed via
  `common_chat_templates_support_enable_thinking`.
- Reasoning parsing: the autoparser derives `thinking_start_tag` /
  `thinking_end_tags` from the template analysis
  (`autoparser.reasoning.start/.end`), and `supports_thinking` is
  `reasoning.mode != NONE`.

## 4. JSON Schema conversion

Both request paths convert schema to GBNF through
`json_schema_to_grammar` (jinja path stores `params.json_schema`; legacy
path sets `params.grammar = json_schema_to_grammar(...)`). Grammar +
native tools cannot be combined (`"Cannot specify grammar with tools"`),
which is why P1 (schema) and P5 (native tools) are disjoint arms.

## 5. Token budget accounting

- One `n_predict`/`max_tokens` budget covers reasoning + content; the
  reasoning-budget sampler, when armed, can force the thinking block
  closed (`SERVER_CONTROL_ACTION_REASONING_END` →
  `common_sampler_reasoning_budget_force`) — an explicit server control
  channel that a Runtime could use.
- `usage` exposes prompt/completion/total only; reasoning-token counts are
  NOT exposed in b12359 (recorded as UNAVAILABLE in N02R trials; character
  counts of `reasoning_content` are never converted to token estimates,
  per the mission order).

## 6. Server request handling (cancellation, slots)

- Client-side abort: closing the stream cancels the task; the slot is
  released (SERVER_TASK_TYPE_CANCEL → `slot.release()`), and a follow-up
  generation completing with token accounting proves slot release (N02R
  probe audit distinguishes client abort vs server-side termination).
- `/apply-template` exists at b12359 (registered in `server.cpp`) and is
  used by N02R for rendered-prompt verification.

## Files inspected (pinned commit)

`src/llama-grammar.cpp`, `src/llama-chat.cpp`, `tools/server/server.cpp`,
`tools/server/server-chat.cpp`, `tools/server/server-context.cpp`,
`common/chat.cpp`, `common/sampling.cpp`.
