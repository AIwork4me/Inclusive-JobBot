# HANDOFF — IJ-EVAL-ASSURANCE-1.0

## Where things stand (2026-11-28)

Wave A started. Branch `mission/ij-eval-assurance-1.0-systemic-evaluation-integrity`
(worktree `<worktrees>/IJEVAL`) from audited IJ-NANO HEAD `bc4555e`
(verified equal to PR #11 remote head at mission start). Issue #12, Draft PR #13.

Done:
- Mission order preregistered verbatim (`docs/IJEVAL_MISSION_ORDER.md`, commit 0ab5c6b).
- EA00 §2.2 residual audit COMPLETE (commit f081655): reproduction script
  `scripts/ij_eval_assurance/ea00_n02rr_residual_repro.py` +
  `evidence/IJEVAL/EA00/n02rr_residual_risk_reproduction.json`.
  Findings R1 (exception→semantic FAIL coercion), R2 (inconsistent stage-2
  retains True verdict), R3 (analyzer ingests both without eligibility filter,
  870/2184→871/2186 injected). Sealed corpus has zero such rows → published
  1.2R headline unaffected; risks structural.

In progress:
- EA00 §2.1 historical defect inventory (IJ-NANO families EV01–EV07,
  NA-D01–NA-D08, PR-D01–PR-D10, RS01–RS08 swept; Atlas/IJ-SLM/IJ-SDK sweep
  running at handoff time).
- Then: EA00 report → EA01 threat model → EA02 typed contract.

## Resume procedure

Worktree root below is the mission worktrees directory that contains the
sibling checkouts `IJNANO` (IJ-NANO mission) and `IJSDK` (read-only weights).

1. `cd <worktrees>/IJEVAL`, `git status` (expect clean).
2. Runtime junction (untracked, engine identity hashing only):
   `cmd /c mklink /J runtime\llama-cpp\vulkan <worktrees>/IJNANO/runtime/llama-cpp/vulkan`
3. Rerun the §2.2 reproducer: `python -I scripts/ij_eval_assurance/ea00_n02rr_residual_repro.py`
4. Continue from `TASK_LEDGER_IJEVAL.md` first IN_PROGRESS/PENDING row.

## Pitfalls (carried over from IJ-NANO + new)

- Never edit sources of a running experiment; experiment identities hash them.
- Gate every commit with `python -I scripts/tools/publish_check.py --staged`
  (finding-count based, NOT exit code). After any redaction, `git add` AGAIN.
- Weights live in the read-only IJSDK sibling worktree; use
  `default_weights_root()` / `IJNANO_WEIGHTS_ROOT`, never hardcode user paths.
- Do not run `n02rr_analyze.main()` against patched REC paths in exploratory
  work — it rewrites `corrected_protocol_matrix.json` (sealed evidence).
- CPU-first: synthetic artifacts + offline replay; GPU only after EA13
  software qualification, via the host-wide `gpu_lease.py` protocol.
