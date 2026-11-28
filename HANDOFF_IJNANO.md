# HANDOFF — IJ-NANO-1.0 / IJ-NANO-1.1 / IJ-NANO-1.2

Read this first when resuming this mission. Last updated: 2026-11-27 (N1.2R).

If anything here disagrees with the machine or the remote, trust the machine,
fix this file, and say so in the commit.

## 1. Resume procedure

Work from this worktree root (the folder containing this file).

```powershell
git status --short --branch
git log --oneline | Select-Object -First 12
python scripts/tools/publish_check.py --staged   # fail-closed; before every commit
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

IJ-NANO-1.2 is active (orders: `docs/IJNANO_MISSION_ORDER_V1_2.md` +
N02R addendum, both committed verbatim).
Delivered under 1.1: **N00RR**, **N01**, **N06A-R**, **N05A** (all PASS).
Under 1.2: **N1.2R** (resume), **N05AR** (evaluator contract v2 gate
PASS), the fail-closed **publication check**, and **N02R** — gate
`N02R_MODEL_PROTOCOL_BEHAVIOR_CHARACTERIZED` **PASS**: corrected
experiment `ec5b95357e960f99` (2,184/2,184 unique logical slots,
identity-bound, netstat-verified, content-addressed artifacts), v1 screen
sealed as diagnostic evidence, integrity audit + disposition + integration
gate all delivered. Key N02R results: lazy-grammar/budget starvation
confirmed and removable; bounded reasoning budget (T2) the only
intervention ≥ default on all three models; model-specific protocol
candidates published for N03. Next lane: **N03** cognitive capability
atlas on evaluator contract v2 with the N02R protocol candidates.
Formal end-to-end business evaluation stays BLOCKED (IJN-B-002 narrowed).

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

## 5. Next steps, in order (IJ-NANO-1.2R closed 2026-11-28; N03 next)

IJ-NANO-1.2R delivered the offline-rescore integrity recovery: the N02R
rescore loader defect (all 1,397 rescored rows of `ec5b95357e960f99`
PARSE_INVALID regardless of content) was reproduced red, repaired, gated
(`N02R_OFFLINE_REPLAY_INTEGRITY_GO`) and the corpus re-scored offline
(replay identity `6701a6a6a08b34d9`; corrected headline 870/2,184 semantic
PASS; paired statistics; see
`reports/IJNANO_02RR_QUANTITATIVE_EVIDENCE_RECONCILIATION.md`). Use the
CORRECTED matrix (`evidence/IJNANO/N02RR/corrected_protocol_matrix.json`)
for N03 protocol candidates; do not freeze DSL/two-stage/thinking-policy
decisions from the superseded matrix. Original experiments and the
defective evidence remain sealed and untouched.

1. N05AR targeted evaluator corrections EV01–EV07 — reproduce each concern
   red first, then repair (gate
   `N05AR_COGNITIVE_EVALUATOR_INTEGRITY_GO`); stays separate from the
   business Oracle.
2. N02R protocol causal analysis under lease (gate
   `N02R_MODEL_PROTOCOL_BEHAVIOR_CHARACTERIZED`); preserve the raw S2
   `overall: FAIL` artifact unchanged; probe false-positive audit first
   (empty-content PASS, tool-call semantics, cancellation scope, SSE
   accounting).
3. N03 full cognitive profiling (C01–C32; 640 dev + 320 confirmation,
   CN+EN) and capability-to-Runtime mappings (gate
   `N03_COGNITIVE_CAPABILITY_PROFILES_AVAILABLE`).
4. Evidence-driven N06B/C layers and N04/N07 mechanism reproductions
   (reuse candidates recorded in
   `reports/IJNANO_OPEN_SOURCE_REUSE_DECISION.md`).
5. The 3,600-slot causal pilot once its prerequisites qualify.
6. Fail-closed publication check (scanner finding-count based) with a
   synthetic scanner control — mission order 1.2 §10.

## 6. Things that will trip you up

- Everything in HANDOFF.md §9 of the parent repository still applies (ugrep,
  `-I` flag, Git Bash pipelines, MSYS pids, PowerShell 5.1 quirks).
- `git fetch`/`push` to github.com may reset; retry or use `gh api` for reads.
- The IJSDK sibling worktree belongs to the stopped IJ-SDK-1.1 worker: read
  only, never write, never commit there.
- Never present gfx1151-era evidence (default-branch IJ-0.x reports) as this
  machine's results; this workstation is gfx1100.
- `scan_sensitive.py` has been observed to exit 0 even when it reports
  findings — use `python scripts/tools/publish_check.py [--staged]`,
  which decides from the parsed finding count (fail-closed; synthetic
  control in `tests/ij_nano/test_publish_check.py`).
- The pinned engine is llama.cpp **b12359**; any upgraded/patched engine is a
  separate experimental identity, never a silent replacement.
