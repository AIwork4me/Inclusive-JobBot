# Matched quality and resource use

Each model uses its jointly evaluable case intersection across all first-attempt paths with complete token, provider-latency and session-memory telemetry. Median provider latency excludes SDK overhead.

| Model | Track | Matched cases | Scoped completions | Median tokens | Median provider ms | Frontier |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| A | direct_first | 400 | 372 | 915 | 956.933 | True |
| A | sdk_first | 400 | 2 | 4011 | 3350.385 | False |
| A | sdk_streaming | 400 | 2 | 4013 | 3066.425 | False |
| B | direct_first | 400 | 361 | 615 | 958.845 | True |
| B | sdk_first | 400 | 218 | 3509 | 1792.363 | False |
| B | sdk_streaming | 400 | 220 | 3503 | 1779.125 | False |
| D | direct_first | 400 | 272 | 1101 | 1489.674 | True |
| D | sdk_first | 400 | 80 | 3225 | 2455.71 | False |
| D | sdk_streaming | 400 | 78 | 3233 | 2443.823 | False |
