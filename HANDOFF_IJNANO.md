# HANDOFF — IJ-NANO-1.0

Read this first when resuming this mission. Last updated: 2026-11-27 (N00).

If anything here disagrees with the machine or the remote, trust the machine,
fix this file, and say so in the commit.

## 1. Resume procedure

Work from this worktree root (the folder containing this file).

```powershell
git status --short --branch
git log --oneline | Select-Object -First 12
python scripts/tools/scan_sensitive.py --staged   # before every commit; read the output
Get-Process llama-server -ErrorAction SilentlyContinue
```

Then read `MISSION_STATE_IJNANO.json` (phase/gate status),
`TASK_LEDGER_IJNANO.md` (task rows) and `BLOCKERS_IJNANO.md`.

## 2. Where the work is

N00 (repository audit and research isolation) is complete. The mission is
parked at the start of N01 (literature investigation) with all physical
phases BLOCKED: the Radeon GPU is leased to IJ-SLM-1.0 (PR #9), and no
qualified evaluator/harness/oracle is inheritable from IJ-SDK (P3/P4-core/P5
reopened FAIL; formal GPU matrix not authorized).

Branch: `mission/ij-nano-1.0-slm-native-agentic-runtime`, base `56c6c74b`
(PR #8 head at N00 audit). Never rebase onto moving parents; never touch the
PR #6 / PR #8 / PR #9 branches or other missions' state files.

## 3. Mission-specific files

| File | Content |
|---|---|
| `docs/IJNANO_MISSION_ORDER.md` | Verbatim mission order (preregistration) |
| `docs/IJNANO_RESEARCH_PROTOCOL.md` | Operative protocol: hypotheses, integrity rules, gates |
| `MISSION_STATE_IJNANO.json` | Machine-readable phase/gate status, verdicts, recovery |
| `TASK_LEDGER_IJNANO.md` | Task rows with evidence paths |
| `BLOCKERS_IJNANO.md` | IJN-B-001..005 |
| `evidence/IJNANO/N00/` | baseline_manifest.json, dependency_qualification.json |
| `reports/IJNANO_00_BASELINE_AND_DEPENDENCY_AUDIT.md` | N00 audit report |

## 4. What is safe to do without the GPU

- N01 literature verification (use `gh api` and web sources; see D-002).
- Research-protocol and statistical-analysis design (N08 skeleton, N05
  evaluator architecture, dataset generator design).
- Pure-software NanoAgent development (N06/N07 software tiers) with unit
  tests, labelled software-only. Study `tests/ij_sdk/` and the P4A harness
  code as REFERENCE_ONLY (defect classes D04-D07 are design requirements).
- On-disk weights (sibling IJ-SDK worktree) and engine installs exist; do not
  start llama-server for IJ-NANO purposes while IJN-B-001 is open.

## 5. Next steps, in order

1. N01: verify R01-R09 primary sources; write the landscape reports and the
   reuse decision (deliverables listed in the mission order §5).
2. Draft `docs/IJNANO_RESEARCH_PROTOCOL.md` additions: per-hypothesis
   experimental design (IV/DV/baseline/acceptance/falsification).
3. NanoAgent SDK skeleton (pure software, unit-tested).
4. When the GPU lease allows: N02 qualification protocol first, then model
   admissions re-verification (fresh SHA256 evidence), then physical runs.

## 6. Things that will trip you up

- Everything in HANDOFF.md §9 of the parent repository still applies (ugrep,
  `-I` flag, Git Bash pipelines, MSYS pids, PowerShell 5.1 quirks).
- `git fetch`/`push` to github.com may reset; retry or use `gh api` for reads.
- The IJSDK sibling worktree belongs to the stopped IJ-SDK-1.1 worker: read
  only, never write, never commit there.
- Never present gfx1151-era evidence (default-branch IJ-0.x reports) as this
  machine's results; this workstation is gfx1100.
- Weights and engines are outside git. Record SHA256 evidence fresh at first
  use; the committed manifest is an identity anchor, not disk proof.
