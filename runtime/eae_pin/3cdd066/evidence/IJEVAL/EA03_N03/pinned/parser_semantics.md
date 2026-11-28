# Batch A required Parser semantics (C01–C08) — for EA04 qualification

Consumer: IJ-EVAL-ASSURANCE (PR #13). Pinned inputs: the digests in
`package.json` at the pinned git revision. These are the MINIMUM parser
semantics the production Parser must implement and that EA04 must qualify
before any N03 physical trial. Parse failures must classify as
PARSER_SOFTWARE_ERROR (never model failure).

## Per-primitive accepted output surface

- **C01 Intent classification**: a bare label token OR a single-field JSON
  object (`{"intent": "<label>"}` / `{"label": "<label>"}`). The label must
  be a member of the case's `intent_catalog`. Multiple labels, free text,
  and labels outside the catalog are INCORRECT (not parse errors).
- **C02 Goal extraction**: a JSON object with exactly the five schema fields
  (`action, object, deadline, completion_criterion, unknown_flags`);
  `unknown_flags` is an object of booleans. Missing fields are parse-level
  defects for the contract only when the model emitted non-JSON.
- **C03 Single instruction**: family-dependent.
  - formatting: newline-separated plain-text lines (no bullets, no
    enumeration markers; leading/trailing whitespace tolerated, blank lines
    ignored);
  - formfill: single-field JSON `{"<field>": "<value>"}`;
  - oneedit: exactly one line of text (the edited record line).
- **C04 Multiple constraints**: comma- or newline-separated item ids; an
  empty result must surface as an explicit empty list (`[]`, empty content
  after canonicalization), never as a fallback guess. Ordering matters only
  when the instruction declares a sort.
- **C05 Boolean decision**: `TRUE`/`FALSE` (case-tolerant) or
  `{"decision": true|false}`. Narrated hedges are INCORRECT, not unparseable.
- **C06 Enumerated choice**: an option id (bare or `{"choice": "<id>"}`).
- **C07 NL action selection**: an action name from the catalog (bare or
  `{"action": "<name>"}`); verbatim catalog membership required.
- **C08 Tool-name selection**: a tool id from the candidate list (bare or
  `{"tool_id": "<id>"}`).

## Cross-cutting parser requirements (historical-immunity list applies)

- No positional unpacking of persisted stages (N02R root cause): key-based
  access only.
- JSON extraction must tolerate markdown fences; duplicate keys are a
  structural defect (C09 concern, already enforced here for single objects).
- Empty model output is EMPTY_OUTPUT (its own class), not a parse error and
  not INCORRECT.
- Substring matching is NEVER sufficient for label/id membership: exact
  token equality after trim/case-normalization.
