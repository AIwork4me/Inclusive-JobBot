# HANDOFF — IJ-NANO-1.0 / IJ-NANO-1.1

Read this first when resuming this mission. Last updated: 2026-11-27 (N00RR).

If anything here disagrees with the machine or the remote, trust the machine,
fix this file, and say so in the commit.

## 1. Resume procedure

Work from this worktree root (the folder containing this file).

```powershell
git status --short --branch
git log --oneline | Select-Object -First 12
python scripts/tools/scan_sensitive.py --staged   # before every commit; read the output
Get-Process llama-server -ErrorAction SilentlyContinue
python -I -m unittest discover -s tests/ij_nano -t .
```

Then read `MISSION_STATE_IJNANO.json` (phase/gate status),
`TASK_LEDGER_IJNANO.md` (task rows) and `BLOCKERS_IJNANO.md`.

## 2. Where the work is

Delivered and sealed: **N00** (audit/isolation), **N00R** (resource
reconciliation — cross-host GPU conflict resolved, `IJN-B-001` CLOSED, local
lease available), **N02** (physical runtime qualification PASS: identities,
admissions, protocol probes; S2 chat-path finding feeds N02R).

IJ-NANO-1.1 is active (order: `docs/IJNANO_MISSION_ORDER_V1_1.md`). Lanes:
N01 closure (reports), N06A-R integrity hardening (NA-D01..D08), N05A
cognitive evaluator, N02R protocol causal analysis (GPU, under lease),
then N03 profiling and the evidence-driven runtime work. Formal end-to-end
business evaluation stays BLOCKED (IJN-B-002 narrowed).

Branch: `mission/ij-nano-1.0-slm-native-agentic-runtime`, base `56c6c74b`
(PR #8 head at N00 audit), audited anchor `f3d5817f`. Never rebase onto
moving parents; never touch the PR #6 / PR #8 / PR #9 branches or other
missions' state files.

## 3. Mission-specific files

| File | Content |
|---|---|
| `docs/IJNANO_MISSION_ORDER.md` | IJ-NANO-1.0 verbatim mission order (preregistration) |
| `docs/IJNANO_MISSION_ORDER_V1_1.md` | IJ-NANO-1.1 verbatim mission order (continuation) |
| `docs/IJNANO_RESEARCH_PROTOCOL.md` | Operative protocol: hypotheses, integrity rules, gates |
| `MISSION_STATE_IJNANO.json` | Machine-readable phase/gate status, verdicts, recovery |
| `TASK_LEDGER_IJNANO.md` | Task rows with evidence paths |
| `BLOCKERS_IJNANO.md` | IJN-B-001..005 |
| `evidence/IJNANO/N00/` | baseline_manifest.json, dependency_qualification.json |
| `evidence/IJNANO/N02/` | identity, admission, protocol evidence + session record |
| `reports/IJNANO_02_PHYSICAL_RUNTIME_QUALIFICATION.md` | N02 report (incl. S2 chat-path finding) |

## 4. What is safe to do without the GPU

- N01 closure: license matrix + CN/EN landscape reports + reuse decision
  (raw sweeps: `evidence/IJNANO/N01/agent_reports/`, catalog committed).
- N06A-R adversarial hardening against Layer A (pure software, unittest).
- N05A cognitive evaluator contracts + controls + mutation tests.
- GPU work (N02R, N03) runs under the host-wide lease
  (`benchmarks/root_cause/gpu_lease.py`); check no other physical session
  is active first (`Get-Process llama-server`).
- Weights and engines are outside git. Record SHA256 evidence fresh at first
  use per session series; the committed manifest is an identity anchor.

## 5. Next steps, in order

1. N01 closure (gate `N01_RESEARCH_LANDSCAPE_VERIFIED`).
2. N06A-R hardening (gate `NANOAGENT_LAYER_A_SOFTWARE_INTEGRITY_GO`) —
   reproduce each NA-D concern red before repairing.
3. N05A evaluator qualification (gate `N05A_COGNITIVE_EVALUATOR_QUALIFIED`).
4. N02R protocol causal analysis under lease (gate
   `N02R_MODEL_PROTOCOL_BEHAVIOR_CHARACTERIZED`); preserve the raw S2
   `overall: FAIL` artifact unchanged.
5. N03 twelve priority cognitive families once N05A scopes qualify.

## 6. Things that will trip you up

- Everything in HANDOFF.md §9 of the parent repository still applies (ugrep,
  `-I` flag, Git Bash pipelines, MSYS pids, PowerShell 5.1 quirks).
- `git fetch`/`push` to github.com may reset; retry or use `gh api` for reads.
- The IJSDK sibling worktree belongs to the stopped IJ-SDK-1.1 worker: read
  only, never write, never commit there.
- Never present gfx1151-era evidence (default-branch IJ-0.x reports) as this
  machine's results; this workstation is gfx1100.
- `scan_sensitive.py` exits 0 even when it reports findings — read the output
  before every commit.
- The pinned engine is llama.cpp **b12359**; any upgraded/patched engine is a
  separate experimental identity, never a silent replacement.
