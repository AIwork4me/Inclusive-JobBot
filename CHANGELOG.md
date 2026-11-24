# Changelog

Notable, evidenced changes to this project. Nothing below is a claim of
production readiness.

## [Unreleased]

### Added

- Mission ledger, working rules and decision record (ADR-001: llama.cpp is the
  primary inference engine).
- Windows hardware and software baseline with redacted evidence (M0).
- ModelScope import of MiniCPM5-2B at pinned revisions; 17 of 17 files match
  the published SHA256.
- Upstream audit of the llama.cpp MiniCPM5 parser and the three official chat
  templates.
- Install, launch, stop, check and GPU-counter scripts for the official
  llama.cpp build `b12359` (CPU, Vulkan, ROCm/HIP).
- ROCm 10.0.0 runtime wheels as the source of the hipBLAS the ROCm build
  imports.
- API check for llama-server: 9 of 9 on Vulkan with Q8_0.
- Engine qualification harness (`benchmarks/engine_qualification/`).

### Known limitations

- Smart App Control blocks the unsigned official binaries; the machine owner
  decides whether to turn it off.
- No real employee validation, no DEEPX DX-M2 hardware results.
