# LFM3 original-harness reproduction status

UPSTREAM_REPRODUCTION is BLOCKED. Author scores, environments and the stated
split rules are recorded in the upstream audit. The available evidence
establishes aggregate denominators, with 150 SmolDataEnvs tasks and 40
trajectory-derived repository tasks per harness. Zero of the 190 task
identities have been tied to an exact historical run roster with image
digests. A current dataset checkout may contain candidates for these tasks.
The author score remains a reference until the roster is reconciled.
[Upstream audit](LFM3_HA01_UPSTREAM_RESEARCH.md) ·
[Live author dashboard](https://harness-hub-harness-adapters-rl.hf.space/)

This Windows workstation did not show Docker or Podman on PATH or a
configured WSL environment. The original harnesses need a verified
sandbox that excludes user directories, credentials, other worktrees
and external runtime egress. No job has been started in those harnesses.

| Lane | Configuration | Planned | Observed |
|---|---|---:|---:|
| Author-style | BF16/vLLM at matched upstream identity, or a separately labeled GGUF portability run with the original protocol, thinking, budget and timeout | 1,140 | 0 |
| Edge | Windows Radeon, frozen Q8_0 base, F16 adapter, 8K context, temperature 0, thinking disabled | 1,140 | 0 |

A minimal isolated admission must pin the OpenCode 1.19.5 build, Pi
Chat Completions provider, Hermes source version and each plugin and tool
definition. Exercise paired Original and LoRA under the same harness.
Hermes requires at least 64,000 tokens in its documented setup. Record
whether an 8K launch is supported as its own compatibility result before
attempting that edge arm. Keep unavailable trials and their causes in the
denominator report. Bind every scored trajectory to a frozen oracle, task
world, seed, base and adapter, runtime and hardware identity.
