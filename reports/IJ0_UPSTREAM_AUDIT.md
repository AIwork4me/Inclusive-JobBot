# IJ-0.1 Upstream Source Audit

- Verified: 2026-11-24, live GitHub REST API and source at pinned commits
- Machine-readable evidence: `evidence/IJ0/upstream_source_manifest.json`
- Result: **PASS** - a stable llama.cpp release exists that contains a native
  MiniCPM5 parser and Windows builds for CPU, Vulkan and ROCm/HIP.

## The seven required checks

| # | Check | Result |
|---|---|---|
| 1 | Merge status of PR #24889 | **Merged** 2026-06-28, commit `c818263f2a5ddab028dea5f169ea2b2266421125`. |
| 2 | Where the parser is implemented | `common/parsers/minicpm5.cpp`, factory `common_chat_params_init_minicpm5`; selected in `common/chat.cpp`. |
| 3 | Does the stable release include it | **Yes.** `v1.0.0` ships binaries through `nightly-tag.txt`, which names build `b12359`, commit `b1b770d90`. That commit contains the parser merge (2,527 commits later). |
| 4 | 1B and 2B template and tool format consistency | **Wire protocol identical.** Templates differ only in replaying assistant messages that carry tool calls. |
| 5 | Later parser fixes or regressions | No MiniCPM5-specific fix after the stable build. PR #32746 (malformed-XML recovery) was **closed unmerged**; PR #29307 touches the parser with a two-line change after the build. |
| 6 | Windows Vulkan and ROCm/HIP release builds | **Available** for `b12359`: `win-cpu-x64`, `win-vulkan-x64`, `win-rocm-10.0-x64`. The ROCm target list includes `gfx1151`. |
| 7 | Antigravity SDK support for llama-server's API | SDK 0.1.24 has `LocalOpenAIAgentConfig(base_url=...)` for any OpenAI-compatible local server. **Not yet verified live**; done in the integration step. |

## Stable release and binary identity

`v1.0.0` (published 2026-11-13) is a release entry with a single asset,
`nightly-tag.txt`, containing `b12359`. The binaries are attached to the
`b12359` pre-release entry (38 assets, published one minute later).

The build commit is one commit behind the `v1.0.0` tag commit. The single
commit in between is `2d8a325029`, "CUDA: split the PAD_REFLECT_1D grid to stay
within the HIP grid limit (#32179)". It does not touch the CPU, Vulkan or chat
code paths.

| Asset | Size | SHA256 (GitHub asset digest) |
|---|---:|---|
| `llama-b12359-bin-win-cpu-x64.zip` | 25,097,509 | `837c1655e87df3b66989f4be33a792a1399c785bf259038dc75c900096683e69` |
| `llama-b12359-bin-win-vulkan-x64.zip` | 38,090,643 | `e8d18c6e4210cca87e7307c2ea78363ac8d158e4e1397358ec96ab70b53a0d5e` |
| `llama-b12359-bin-win-rocm-10.0-x64.zip` | 280,132,437 | `d5021cebbd3bd50a7cab3b9f121a887e45df76c360ecfa927940aac3bb64a982` |

All three were downloaded and matched their digests. None of the release
binaries is Authenticode-signed.

## How the parser works and when it is chosen

Selection is by template content. A template is routed to the MiniCPM5 parser
when its source contains all three of `Tool usage guidelines:`,
`<function name="` and `<param name="`. It does not depend on `<tool_sep>` or on
the model name, so the MiniCPM5-2B templates are routed there too.

The parser is not a string-splitting XML reader. For each request it builds a
parsing grammar from the declared tool schemas:

- only a declared tool name followed by declared parameter names can match;
- string parameters accept a plain value or a CDATA-wrapped value; other types
  are parsed by their own JSON schema;
- a lazy grammar constrains generation once `<function` is emitted;
- the message shape is: optional `<think>` block, optional content, then tool
  calls until the end of the output.

Consequences for qualification: unknown tools and unknown parameters cannot be
parsed as valid calls, but malformed model output (a missing `</param>`, text
between two calls) has no recovery path in this build, because PR #32746 was
not merged. The parser fixtures therefore include these cases and record the
observed behaviour instead of assuming it.

## The three MiniCPM5 templates

| Template | Length | SHA256 | `<tool_sep>` replay |
|---|---:|---|---|
| GGUF-embedded (identical in F16, Q8_0, Q4_K_M) | 9060 chars | `cc945752db555d60949b16989df4ccfeb52a313d6b4b5c5229dd786e2e9fcf1c` | yes |
| BF16 repository `chat_template.jinja` | 5435 bytes | `bc1f78ef8a86b6bdf64a056cf89dd0ac506db4f198ab363d85168e2500ab44dd` | no |
| MiniCPM5-1B `chat_template.jinja` | 9062 bytes | differs from the other two | yes |

The 1B file is byte-identical to the template bundled in llama.cpp
(`models/templates/openbmb-MiniCPM5-1B.jinja`). llama.cpp ships no 2B template;
for MiniCPM5-2B it uses the template embedded in the GGUF.

All three use the same wire protocol: ChatML framing, tool definitions as JSON
inside `<tools>`, calls as `<function name="..."><param name="...">`,
and tool results as `<tool_response>` in a user turn. The GGUF-embedded template
is the default; the repository template is kept for A/B comparison through
`--chat-template-file`. Templates are never edited.

## ROCm build needs extra runtime libraries

`win-rocm-10.0-x64.zip` is a complete build (56 entries). Besides the CPU
build it adds `ggml-hip.dll`, `amdhip64_7.dll`, `rocm_kpack.dll` and
`amd_comgr.dll`, but no hipBLAS, rocBLAS or hipBLASLt. The workflow comment
states that rocBLAS and hipBLASLt "resolve fine via PATH and are not copied". On
this machine
`ggml-hip.dll` fails to load because its import `hipblas.dll` is missing, so the
ROCm build reports no devices (`evidence/IJ0/rocm_pe_imports_before_fix.json`).
The libraries are supplied from the same source upstream CI uses, the ROCm
10.0.0 wheels, in an isolated virtual environment (see `BLOCKERS.md` B-003).
With them on `PATH` the build enumerates `ROCm0: AMD Radeon(TM) 8060S
Graphics (91612 MiB, 91452 MiB free)`; `rocblas.dll` and `libhipblaslt.dll`
contain `gfx1151` code objects.

## Antigravity SDK

| Item | Value |
|---|---|
| Package | `google-antigravity` 0.1.24, Apache-2.0, uploaded 2026-11-19 |
| Windows wheel | `google_antigravity-0.1.24-py3-none-win_amd64.whl` (42.8 MB) |
| Runtime binary | `localharness.exe`, not Authenticode-signed, starts on this machine |
| Local server config | `LocalOpenAIAgentConfig(model=..., base_url="http://127.0.0.1:<port>/v1")` |
| Default capabilities of that config | file reads, file writes, command execution, subagents and MCP are all **enabled** |

The last row matters: the production configuration must disable those
capabilities explicitly and add tool allow-list policies. `.lightweight()` is a
token-saving preset, not a security boundary.

## Open points

- Live check of the SDK against llama-server (step 7) is pending.
- The stable build predates PR #29307 and has none of the PR #32746 recovery
  logic. If fixtures or the benchmark show a parser defect, the response
  follows ECO-01 section 5.5: configure the official template, use a fixed
  release, adopt an upstream fix, write a minimal local patch with a
  reproduction, and only then consider an adapter.
