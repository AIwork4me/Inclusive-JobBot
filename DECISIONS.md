# Decisions

Newest last. Each entry states what was decided, why, and what would reverse it.

## D-001 Keep everything reversible and inside the repository directory

Everything installed for this project lives under the repository folder:
`.venv`, `.tools`, `.runtime`, `models`, `runtime/llama-cpp`. No PATH, registry
or user-profile changes are made by project scripts. Settings are passed as
arguments or per-process environment variables.

Why: the original mission forbids unapproved system changes and asks for
application-level, reversible alternatives first.
Reverse: an explicit owner instruction to install a tool system-wide.

## D-002 Network workarounds keep end-to-end integrity

On this network `files.pythonhosted.org` resets TLS connections and
`raw.githubusercontent.com` is unreliable, while `pypi.org`, `api.github.com`
and `modelscope.cn` are reachable. GitHub release assets are throttled to about
100 KB/s per connection.

- Python packages come from the Tsinghua PyPI mirror through an explicit
  `-i` index argument. Hashes in `requirements.lock` are cross-checked against
  the official `pypi.org` metadata API, which is reachable.
- GitHub files are read through `gh api`.
- Large GitHub assets are fetched with `scripts/tools/parallel_fetch.py`, which
  uses parallel range requests and refuses any file whose SHA256 differs from
  the digest published by the project.

Why: no global pip or proxy configuration is touched, and the mirror is never
trusted on its own.
Reverse: the network changes; drop the mirror and the parallel fetcher.

## D-003 Commit identity

The repository-local git identity is `AIwork4me <AIwork4me@qq.com>`, matching
the identity already public in the owner's existing repositories. The global
git identity is not modified.

## D-004 llama.cpp replaces Ollama as primary engine

See `docs/decisions/ADR-001-LLAMA-CPP-PRIMARY-INFERENCE.md` (ECO-01).
Ollama's GPU discovery log is kept as control-group evidence and is not
relabeled.

## D-005 Smart App Control is never changed by the project; the owner decides

Windows Smart App Control initially blocked the unsigned official llama.cpp
release binaries on the qualification machine. The project did not touch the
setting and did not use any bypass; it recorded the blocker and continued with
work that did not depend on it. The machine owner then turned Smart App
Control off on 2026-11-24, so the official `b12359` build is the engine and
no alternative engine identity is needed.

Why: a one-way security setting belongs to the owner of the machine.
Reverse: if the owner turns the policy back on, record a new blocker; do not
substitute another engine silently.

## D-006 Model revisions are pinned and verified per file

MiniCPM5-2B weights come only from ModelScope at pinned head commits observed
on 2026-11-24: `OpenBMB/MiniCPM5-2B-GGUF` at `8cc1178b0a5c` and
`OpenBMB/MiniCPM5-2B` at `4e7a94716d45`. All 17 files matched the SHA256 and
size published by ModelScope (`evidence/IJ0/model_identity.json`).
Hugging Face is not used as a weight source.

## D-007 The GGUF-embedded chat template is the default

MiniCPM5-2B ships two official templates that differ only when replaying
assistant messages that contain tool calls: the GGUF-embedded template
(9060 characters, uses `<tool_sep>`) and `chat_template.jinja` from the BF16
repository (5435 bytes). Their wire protocol is identical.

Following ECO-01, the GGUF-embedded template is the default and templates are
never edited to hide model behaviour. The repository template is available
through `--chat-template-file` for A/B comparison, and both identities are
recorded in `evidence/IJ0/upstream_source_manifest.json`.

## D-008 Status vocabulary

Every test and gate uses only `PASS`, `FAIL`, `BLOCKED`, `NOT_RUN`. A result
with a workaround still states the workaround next to it.

## D-009 ROCm math libraries come from the same wheels as upstream CI

The official ROCm build of llama.cpp imports `hipblas.dll`, which the release
archive does not contain. The libraries are supplied by ROCm 10.0.0 wheels
(`rocm[libraries]==10.0.0`) installed into `runtime/llama-cpp/rocm-libs`, the
same source and version the upstream release workflow builds with. The
`amdhip64_7.dll` in the release archive and in the wheel are byte-identical.

The library directories are added to `PATH` for the llama-server process only.
No ROCm SDK is installed system-wide, and the driver-provided HIP runtime in
`System32` is left untouched.

Why: matches the build exactly and is fully reversible.
Reverse: a release that bundles the math libraries, or an owner-approved
system ROCm SDK; then drop the wheels.

## D-010 What counts as "running on the GPU"

A GPU run is accepted only when both hold:

1. the server answers `/health` and the listening socket belongs to the
   process the start script launched;
2. the server's own log reports `offloaded N/M layers to GPU` with `N > 0`
   when GPU layers were requested.

Verbosity level 4 is used because it is the lowest level that prints the
offload report and the buffer allocations. `ollama ps`, device enumeration or
model load success alone never count.

The offload line alone proves nothing: a CPU-only build prints
`offloaded 43/43 layers to GPU` for `-ngl 99` although it has no GPU backend
(observed during IJ-0.5). Launch scripts therefore request 0 GPU layers for a
build without GPU backend libraries, and a GPU arm additionally requires
Windows GPU counters to show engine activity and GPU memory for the server
process.

Why: a stale server on the same port once produced a false "ready" during
development; the rule now makes that impossible.

## D-011 Defects found by running the scripts, kept as regression notes

- Windows PowerShell 5.1 decodes BOM-less scripts in the local code page and
  corrupted a Chinese string in a `.ps1` file. Script files stay ASCII;
  non-ASCII text lives in UTF-8 JSON read with an explicit encoding.
- An unbound `[string]` parameter is an empty string, not `$null`, which sent
  a body with a GET. Test `$PSBoundParameters` instead.
- PowerShell variable names are case-insensitive: a `-Probe` switch and a
  `$probe` result were the same variable.
- .NET Framework `ExtractToDirectory` refuses to overwrite; archives are
  extracted entry by entry.
- `Join-Path` onto an already absolute path produced an invalid path;
  `Resolve-FullPath` handles both.
- A server started from a Git Bash pipeline inherits the pipe, so tools
  waiting for end-of-file never finish. Redirect script output to a file.
- `grep` on this machine is `ugrep`, whose backslash handling differs; a
  "no leak" check with it was a false negative. Leak checks use
  `scripts/tools/scan_sensitive.py` only.
- Processes started from Git Bash must be stopped by their Windows process id,
  never by the MSYS pid; manual probes once left two servers on port 8080.

## D-012 Benchmark datasets are generated, then frozen; tuning happens on the dev split only

Tool-calling cases come from a seeded generator
(`benchmarks/tool_calling/generators/generate_dataset.py`). It writes a 500-case
test set and a 120-case development set with different seeds, and
`generate_dataset.py --check` proves the committed files are what the
generator produces. Runners refuse a file whose SHA256 differs from the frozen
manifest and refuse to resume a run on a different dataset, engine or decode
setting.

Why: the frozen test set must stay independent from prompt and schema tuning.
Reverse: never for the 500-case set; a new generator version means a new
freeze and is recorded as such.

## D-013 The engine parity workload is strict and is not a business benchmark

`benchmarks/engine_qualification/workload.json` compares backends, so grading
is deliberately literal: an answer that ignores "output only the number" fails
even when the number is right. Its pass counts say nothing about job
productivity; they only have to be equal across backends. Thinking items are
reported as truncated when the think block uses up the token budget.
