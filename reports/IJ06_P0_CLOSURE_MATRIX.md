# IJ-0.6 P0 closure matrix

| Work item | Original observation and evidence | Hypothesis or confirmed limitation | Discriminating test | Status |
|---|---|---|---|---|
| Native whitespace | Strict fixture `fx-valid-whitespace-between-tags` | HYPOTHESIS. The parser may preserve string data according to the format. | Compare fixed input bytes, official template and typed identifier policy. | NOT_RUN |
| Duplicate parameters | Strict fixture `fx-invalid-duplicate-param` | HYPOTHESIS. The parser serializes duplicate names into the arguments string. | Compare the raw native output and both wire forms before JSON decoding. | NOT_RUN |
| Missing parameter close | Strict fixture `fx-invalid-missing-close-param` | HYPOTHESIS. Partial parsing may leak into a terminal message. | Test the exact malformed input and a one-tag repair. | NOT_RUN |
| Missing function close | Strict fixture `fx-invalid-unclosed-function` | HYPOTHESIS. A terminal parser branch accepts an unfinished function. | Compare terminal and incremental behavior with the complete control. | NOT_RUN |
| Out-of-enum value | Strict fixture `fx-invalid-enum-outside-schema` | HYPOTHESIS. Parsing and schema enforcement are different stages. | Test raw wire value and schema rejection. | NOT_RUN |
| Unclosed CDATA | Strict fixture `fx-invalid-unclosed-cdata` | HYPOTHESIS. A quoted scalar is emitted for incomplete CDATA. | Compare the same value with and without the CDATA terminator. | NOT_RUN |
| Evaluator V2 | Both V1 diagnostic traces and the ticket audit | V1 compares first-step arguments only. Historical rows lack committed database state. | DAG replay, mutations for wrong later arguments and effects, explicit historical gaps. | NOT_RUN |
| Secure Model Gateway | Existing tool host and original parser fixtures | There is no reusable common execution boundary in the baseline. | Negative tests from protocol arrival through persistence, including the SDK path. | NOT_RUN |
| SDK checklist | B-008 and prior read-only transcripts | The owner supplied the twelve required gates. | Restore the document and test each gate independently on both backends. | PASS (document recovery) |
| Full SDK qualification | Prior read-only transcripts | UNVERIFIED. | Real SDK with validated wire input and isolated state and network evidence. | NOT_RUN |

Parser rows refer to `evidence/IJ0/protocol/parser_fixtures_strict_vulkan/fixtures.json` and the corresponding ROCm file. See the initial audit for the historical trace paths.
