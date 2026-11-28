# Batch C (C17-C24) — state, planning and recovery

Consumer: IJ-EVAL-ASSURANCE (PR #13). Parser semantics, independent-oracle rules and mutation targets per primitive. Cross-cutting rules from the Batch A package (`../batch_a/parser_semantics.md`) apply unchanged (key-based access, no substring membership, EMPTY_OUTPUT separation, exception-masking immunity).

| Primitive | Parser surface | Oracle rule | Critical mutation targets |
|---|---|---|---|
| C17 | true/false per queried predicate id | predicate evaluation over the typed state | initial-state judgment after transitions; invented predicate |
| C18 | list of 'a before b' dependency edges | pre/eff intersection algebra (set equality) | spurious edge; missing edge; serialization bias |
| C19 | ordered action list | SIMULATION: preconditions hold per step and the goal predicate holds at the end - any valid plan is CORRECT, the reference plan is a witness, never the answer key | precondition violation; goal miss; hallucinated action |
| C20 | ids of holding branches only | condition evaluation over state; mutual exclusion | failed-condition branch; both exclusive branches |
| C21 | continuation plan from CURRENT state | simulation from current state reaches goal; no prefix re-execution | stale-plan persistence; prefix amnesia; goal drop |
| C22 | is_error boolean + catalog code | error-envelope rule (200 status never clears a body error) | masked error; false error; code confusion |
| C23 | corrected argument record | diff equals exactly the diagnosed field with the diagnosis-driven fix | no-op retry; over-correction; unrelated mutation |
| C24 | fallback id + action + arguments | first condition-holding declared fallback; template args | primary retry; condition-ignoring fallback; arg mismatch |

Plan-scoring rule (C19/C21): validity is established by simulating the emitted plan against the published preconditions/effects and evaluating the goal predicate — alternative valid plans are CORRECT; the reference plan is a witness, not an answer key.

No EA gate is granted by this package.
