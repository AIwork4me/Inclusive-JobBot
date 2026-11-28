# Batch D (C25-C32) — decision and robustness

Consumer: IJ-EVAL-ASSURANCE (PR #13). Parser semantics, independent-oracle rules and mutation targets per primitive. Cross-cutting rules from the Batch A package (`../batch_a/parser_semantics.md`) apply unchanged (key-based access, no substring membership, EMPTY_OUTPUT separation, exception-masking immunity).

| Primitive | Parser surface | Oracle rule | Critical mutation targets |
|---|---|---|---|
| C25 | STOP or CONTINUE token | goal predicate over state | premature termination; unnecessary continuation |
| C26 | ACT or ASK + missing slot names | sufficiency vs required schema; invalid counts as missing | unnecessary clarification; missing clarification; optional confusion |
| C27 | ESCALATE + rule id, or PROCEED | threshold predicate evaluation over policy | threshold error; rule omission; spurious escalation |
| C28 | typed answer from the relevant span | target present in document; decoys differ | distractor capture; stale value; hallucination |
| C29 | id, or AMBIGUOUS + conflicting ids | candidate duplication rule (declared ambiguity) | silent disambiguation; over-flagging |
| C30 | canonical op string op:entity[:extra] | entity token verbatim; pair-consistent across languages | digit drift; language echo; canonical divergence |
| C31 | answer with per-claim citations | citations exist and cover required claims | uncited claim; phantom citation; contradiction |
| C32 | answer or ABSTAIN marker | declared sufficiency: fact present iff answerable | confident-wrong guess; over-abstention; marker misuse |

Plan-scoring rule (C19/C21): validity is established by simulating the emitted plan against the published preconditions/effects and evaluating the goal predicate — alternative valid plans are CORRECT; the reference plan is a witness, not an answer key.

No EA gate is granted by this package.
