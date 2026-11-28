# Batch B (C09-C16) — generation and extraction

Consumer: IJ-EVAL-ASSURANCE (PR #13). Parser semantics, independent-oracle rules and mutation targets per primitive. Cross-cutting rules from the Batch A package (`../batch_a/parser_semantics.md`) apply unchanged (key-based access, no substring membership, EMPTY_OUTPUT separation, exception-masking immunity).

| Primitive | Parser surface | Oracle rule | Critical mutation targets |
|---|---|---|---|
| C09 | flat JSON object per declared schema | record equals the public details after canonicalization | type mutation; dropped/extra field; duplicate key |
| C10 | nested JSON with exact array cardinality | document equals public details; array length equals declared | cardinality violation; level flattening; truncation |
| C11 | one DSL statement per line, declared tokens only | grammar-valid and step-count-consistent program | lowercased action token; missing argument; arity error |
| C12 | slot record with declared normalizations | slot values surface in the message; keys within schema | value corrupted; slot omitted without null; distractor fill |
| C13 | one candidate id (mention resolution) | unique attribute-agreement match per construction | recency-only resolution; non-unique match accepted |
| C14 | numeric JSON values, exact magnitude and sign | values appear in text (comma forms normalized) | rounding drift; string-typed number; field swap |
| C15 | value + canonical unit code | arithmetic recomputation from supplied factors | inverted factor; double conversion; unit mutation |
| C16 | grounded short answer | answer recomputable by query over the tool output | stale-note capture; ungrounded inference; field confusion |

Plan-scoring rule (C19/C21): validity is established by simulating the emitted plan against the published preconditions/effects and evaluating the goal predicate — alternative valid plans are CORRECT; the reference plan is a witness, not an answer key.

No EA gate is granted by this package.
