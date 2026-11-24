# IJ-0.6 MiniCPM5 native parser root causes

The six original observations reproduced on both Windows GPU backends with the pinned b12359 binaries and Q8_0 model. The original fixture rubric remains 20/26 on each backend. The source-level probe reproduced the same output without loading model weights. A local P4 candidate rejects incomplete functions, duplicate XML parameters and malformed nested JSON before terminal mapping. P4b passed the scoped conformance suite through a static CPU server and a separate dynamic GPU build on Vulkan and ROCm/HIP.

## Six original cases

| Original fixture | Direct P0 observation and cause | Candidate and boundary results |
|---|---|---|
| `fx-valid-whitespace-between-tags` | Native parsing preserves the newline and spaces within the parameter. The fixture expected a trimmed identifier. The OpenBMB template requires CDATA for line breaks and has no rule that strips string contents. | Both candidates preserve content. v1.0.0 adds a separate template-conforming CDATA control with the same value. The padded value needs field-specific business validation, while free text retains its exact bytes. |
| `fx-invalid-duplicate-param` | The MiniCPM5 parameter repetition permits a second parameter of the same name. The PEG mapper appends JSON members without deduplication, so the raw arguments carry both values. Both P0 API modes preserve that evidence. | P4 checks AST parameter names per tool before terminal mapping. The strict JSON boundary rejects a duplicate at any nesting depth before object coercion. |
| `fx-invalid-missing-close-param` | The terminal parse enables LENIENT and accepts NEED_MORE_INPUT. The raw string parser has consumed the function's closing tag as value text while looking for a missing parameter closer. The mapper exposes incomplete JSON. | P4 requires complete terminal syntax and stops raw values at structural tag boundaries. The unchanged control with its parameter closer parses normally. |
| `fx-invalid-unclosed-function` | The parameter itself completes. The function parser reaches EOF waiting for its closer, but terminal mapping still emits a partial JSON object. | P4 rejects the incomplete function in the direct parser and produces terminal API errors for both modes on the CPU candidate. |
| `fx-invalid-enum-outside-schema` | Runtime PEG schema nodes delegate to their syntactic child. The mapper preserves the out-of-enum string. Grammar constraints during sampling and executable schema validation at the receiving boundary are independent. | P4 preserves the raw value and fixture-schema validation rejects it. Code must check the schema before a tool dispatch even when guided generation was enabled. |
| `fx-invalid-unclosed-cdata` | The CDATA branch does not find its terminator. LENIENT complete parsing maps the incomplete string node to an unterminated JSON string. | P4 rejects missing CDATA and parameter terminators. Completed CDATA, including a literal closing tag in its payload, remains intact. |

The direct probe calls the upstream C++ parser with the same declared tools as each fixed input. It uses both complete input and deterministic random UTF-8-safe input chunks, then reconstructs the upstream delta output. The live replay forces EOS through logit bias and checks token identity. For streaming, the documented llama-server `n_probs` extension records the sample because standard `logprobs` is unsupported with tools and streaming. Both API modes use `echo` so the assistant continuation is included in the protocol response. Terminal errors abort pending stream proposals.

See the original [Vulkan fixture evidence](../evidence/IJ0/protocol/parser_fixtures_strict_vulkan/fixtures.json), [ROCm fixture evidence](../evidence/IJ0/protocol/parser_fixtures_strict_rocm/fixtures.json) and [direct P0 observations](../evidence/IJ06/parser/p0-windows-direct.json).

## Upstream comparison

| Arm | Source and determination | Runtime evidence status |
|---|---|---|
| P0 | Exact b12359 source `b1b770d90d94cad9e9ea5b993bdbc383a522fb28` and installed official Windows binaries. | FAIL on native rejection of 24 expanded structural cases. |
| P1 | Latest stable v1.0.0 targets `2d8a32502909ca065c41c4cf5f2fb1c427c047fc`. Exactly one file differs from the b12359 build commit, the CUDA pad operator. The relevant parser source is unchanged. | NOT_RUN as a distinct binary. |
| P2 | PR #32746 closed unmerged. Its changes recover malformed XML and modify Responses handling. PR #29307 later merged token-aware parsing. On reviewed master `a6ac41c757c066941766164439f6876f2deaab04` the MiniCPM5 string grammar uses `p.through` where b12359 uses `p.ac`. | NOT_RUN. Source review provides no independent evidence of terminal rejection or wire parity. |
| P3 | SGLang `88dc7501f58f026a18357b8ad4ef1f280e1fc2b4` and OpenBMB `f4293a1a7bde05d1acce99488235792615fc241b` full-call reference paths use XML with fallback extraction, duplicate-name checks and string trimming. Their streaming code has different buffering behavior. | NOT_RUN. Source-level semantic comparison only. |
| P4 | Pinned b12359 plus two small reviewable patches. The first patch scopes strict terminal parsing and per-function duplicate-name checks to MiniCPM5. The second rejects invalid nested JSON syntax by SAX validation before generic mapper normalization. | PASS on all applicable direct C++ and fixed-output API native cases on CPU, Vulkan and ROCm/HIP. |

Upstream #24889 introduced the native MiniCPM5 path and added template cases to `test-chat`. The older #23802 and recovery proposal #32746 closed unmerged. The official MiniCPM5 instructions follow the ModelScope templates and supply CDATA for markup, ampersands and newlines. General XML whitespace semantics preserve character data, while the template's wire format determines which markup the parser should interpret.

[Pinned MiniCPM5 parser](https://github.com/ggml-org/llama.cpp/blob/b1b770d90d94cad9e9ea5b993bdbc383a522fb28/common/parsers/minicpm5.cpp) · [Pinned terminal parser](https://github.com/ggml-org/llama.cpp/blob/b1b770d90d94cad9e9ea5b993bdbc383a522fb28/common/chat.cpp) · [Pinned PEG implementation](https://github.com/ggml-org/llama.cpp/blob/b1b770d90d94cad9e9ea5b993bdbc383a522fb28/common/peg-parser.cpp) · [Pinned mapper](https://github.com/ggml-org/llama.cpp/blob/b1b770d90d94cad9e9ea5b993bdbc383a522fb28/common/chat-peg-parser.cpp)

[Stable release comparison](https://github.com/ggml-org/llama.cpp/compare/b1b770d90d94cad9e9ea5b993bdbc383a522fb28...2d8a32502909ca065c41c4cf5f2fb1c427c047fc) · [#24889](https://github.com/ggml-org/llama.cpp/pull/24889) · [#23802](https://github.com/ggml-org/llama.cpp/pull/23802) · [#32746](https://github.com/ggml-org/llama.cpp/pull/32746) · [#29307](https://github.com/ggml-org/llama.cpp/pull/29307)

[SGLang detector](https://github.com/sgl-project/sglang/blob/88dc7501f58f026a18357b8ad4ef1f280e1fc2b4/python/sglang/srt/function_call/minicpm5_detector.py) · [OpenBMB reference detector](https://github.com/OpenBMB/MiniCPM/blob/f4293a1a7bde05d1acce99488235792615fc241b/tool_parsers/minicpm5xml_tool_parser.py) · [OpenBMB ModelScope GGUF](https://modelscope.cn/models/OpenBMB/MiniCPM5-2B-GGUF) · [XML 1.0 character data](https://www.w3.org/TR/xml/#sec-white-space)

## Layered regression counts

| Execution | Fixed cases | Native status | Strict arguments and schema | Stream parity | Combined Gateway wire and strict JSON acceptance |
|---|---:|---|---:|---:|---|
| P0 direct C++ | 130 | 79 PASS, 24 FAIL, 27 NOT_RUN | 130/130 | 130/130 | NOT_RUN |
| P0 Vulkan API | 130 | 79 PASS, 24 FAIL, 27 NOT_RUN | 130/130 | 130/130 | 98 PASS, 32 FAIL |
| P0 ROCm API | 130 | 79 PASS, 24 FAIL, 27 NOT_RUN | 130/130 | 130/130 | 98 PASS, 32 FAIL |
| P4a direct C++ | 130 | 103 PASS, 27 NOT_RUN | 130/130 | 130/130 | NOT_RUN |
| P4a CPU API | 130 | 103 PASS, 27 NOT_RUN | 130/130 | 130/130 | 122 PASS, 8 FAIL |
| P4a lexical expansion direct C++ | 146 | 111 PASS, 8 FAIL, 27 NOT_RUN | 138/146 | 146/146 | NOT_RUN |
| P4b lexical expansion direct C++ | 146 | 119 PASS, 27 NOT_RUN | 146/146 | 146/146 | NOT_RUN |
| P4b lexical expansion CPU API | 146 | 119 PASS, 27 NOT_RUN | 146/146 | 146/146 | 141 PASS, 5 FAIL |
| P4b lexical expansion Vulkan API | 146 | 119 PASS, 27 NOT_RUN | 146/146 | 146/146 | 141 PASS, 5 FAIL |
| P4b lexical expansion ROCm API | 146 | 119 PASS, 27 NOT_RUN | 146/146 | 146/146 | 141 PASS, 5 FAIL |

Native NOT_RUN entries are argument-only rejection fixtures outside the native conformance denominator. P4b passed all 78 valid exact fixtures and all 41 native rejection fixtures. In the P4a lexical experiment the generic mapper escaped eight raw control characters inside nested quoted strings. The already-transformed values passed strict Gateway checks, establishing the need to reject malformed source JSON before mapping. P4b rejects those originals and preserves each well-formed escaped control.

The combined decoder intentionally rejects the five P4b replies containing nested duplicate keys. The native parser preserves the raw nested text and the strict decoder rejects it before object construction. Under P0 the combined rejection class also contains incomplete XML mapped to invalid JSON, invalid Unicode and numeric overflow. A combined decoder failure can therefore be the intended outcome of a negative fixture. No fixed-input trial dispatches tools. End-to-end actual execution safety must be measured separately.

The original whitespace fixture still expects trimming under the v1 rubric. The added template-conforming variant and retained raw observation use exact whitespace expectations. The live server hashes the effective template without its trailing newline, `6e54652d84d698ebb3b7b2172204b6eeafd7f27533e006c8c1ebf8e743a7fd99`. The stored GGUF template used by the direct probe includes that newline, `cc945752db555d60949b16989df4ccfeb52a313d6b4b5c5229dd786e2e9fcf1c`.

[P0 direct](../evidence/IJ06/parser/p0-windows-direct.json) · [Vulkan wire](../evidence/IJ06/parser/p0-windows-vulkan-wire/summary.json) · [ROCm wire](../evidence/IJ06/parser/p0-windows-rocm-wire/summary.json) · [P4a lexical result](../evidence/IJ06/parser/p4a-windows-direct-lexical.json) · [P4b direct](../evidence/IJ06/parser/p4b-windows-direct.json) · [P4b CPU wire](../evidence/IJ06/parser/p4b-windows-cpu-wire/summary.json)

## Toolchain and qualification

Visual Studio Community 2026 supplies MSVC 19.52.37029, embedded CMake 4.3.1 and Ninja. Configuring through its developer command prompt activates only the local build process. The workspace captured exact pinned source, built the C++ probe and ran it on Windows. The pinned upstream `test-chat --template openbmb-MiniCPM5-1B` also exited 0 on Windows. The Linux workflow builds upstream `test-chat` and the probe without weights.

A private XML parser was unnecessary for the demonstrated repairs. The local patch keeps tool selection, CDATA and the PEG expression in llama.cpp. For the GPU runs the patched core loaded the byte-identical official b12359 GPU plugins from separate runtime directories. Both offloaded 43/43 layers and showed device-specific process memory and positive Compute/3D samples. `IJ06_NATIVE_PARSER_GO` is limited to this fixed conformance suite and P4b candidate. Its independent model holdout remains `NOT_RUN`. The five raw wire failures per backend remain in the original summaries and evidence, with their expected negative-test rejections confirmed by strict decoding.

[Build and process identity](../evidence/IJ06/parser/p4b-windows-dynamic-build.json) · [P4b Vulkan wire](../evidence/IJ06/parser/p4b-windows-vulkan-wire/summary.json) · [P4b ROCm wire](../evidence/IJ06/parser/p4b-windows-rocm-wire/summary.json) · [Pinned Windows test-chat](../evidence/IJ06/parser/p0-windows-upstream-test-chat.log)

[Reproduction](../benchmarks/tool_calling_v2/parser/README.md)
