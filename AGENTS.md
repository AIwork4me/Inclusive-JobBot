# AGENTS.md

Working rules for any engineer or agent continuing this repository.

## Read first

1. `HANDOFF.md` - where the work stopped and how to resume.
2. `MISSION_STATE.json` - machine-readable mission and gate status.
3. `BLOCKERS.md` - open blockers, with the owner of each decision.
4. `DECISIONS.md` and `docs/decisions/` - why the technical route looks as it does.
5. `TASK_LEDGER.md` - every task, its status and its evidence path.

## Mission structure

- `IJ-0` (change order ECO-01): qualify llama.cpp as the primary inference
  engine for MiniCPM5-2B on Windows AMD Radeon gfx1151, including the native
  MiniCPM5 tool-calling parser, a 500-case tool-calling benchmark and the
  Antigravity SDK end-to-end loop. Gates G0-G14.
- `IJ-1.0`: three production-shaped JobBots, accessible workstation, 3,000-case
  productivity benchmark, security, offline and soak qualification, DX-M2
  migration package, open-source release. Missions M0-M10.

IJ-0 is the P0 prerequisite: do not start large-scale job development or the
3,000-case benchmark before the IJ-0 gates pass.

## Non-negotiable rules

- Every test result is one of `PASS`, `FAIL`, `BLOCKED`, `NOT_RUN`. Never merge
  these, never upgrade a result without evidence.
- Never present a mock, a fixture or a CPU run as real model or GPU evidence.
  Mock-based CI is labelled as mock.
- Evidence binds to exact identities: git SHA, engine build, binary SHA256,
  ModelScope revision, model SHA256, backend, GPU identity, dataset SHA256,
  SDK version, run ID.
- No silent fallback between engines, backends or model versions.
- The model proposes; deterministic rules, schema validation, permission checks
  and human confirmation decide. Fail closed on business writes and approvals.
- Production runtime is local: no cloud LLM, no Gemini API key, no external
  agent service. The runtime may reach the network only during install and
  download.

## Changes that need the machine owner

Do not do any of these on your own; record the need in `BLOCKERS.md` instead.

- Changing Windows security settings, including Smart App Control.
- Updating Windows, BIOS, GPU drivers, or installing system-wide software.
- Disabling the machine's network or interfering with the remote session.
- Force-pushing, rewriting history, or deleting existing work.
- Submitting issues or pull requests to upstream projects.
- Publishing anything that contains credentials, real names, usernames, host
  names, serial numbers, internal addresses or private business data.

Prefer application-level, process-level and reversible alternatives: keep
tools, models and state inside the repository directory and pass settings as
arguments or per-process environment variables.

## Before every commit

- Redact local identities from evidence: user directory names, host names,
  account names, tokens. Run `python scripts/tools/scan_sensitive.py`.
- Update `TASK_LEDGER.md` and `MISSION_STATE.json` for the work you finished.
- Run the regression tests that cover the code you changed.
- Commit in small logical units and push normally, never with force.

## Evidence layout

- `evidence/M0/` - Windows hardware and software baseline.
- `evidence/IJ0/` - upstream audit, model identity, GPU qualification,
  protocol traces, Antigravity integration, performance.
- `evidence/M*/` - later IJ-1.0 missions.
- `reports/` - human-readable reports that cite the evidence.

Large model weights and engine binaries stay out of git; `models/model_manifest.json`
and `runtime/llama-cpp/README.md` describe how scripts obtain them.
