# HANDOFF — IJ-EVAL-ASSURANCE-1.0

## Where things stand (2026-11-28, Wave A complete)

Branch `mission/ij-eval-assurance-1.0-systemic-evaluation-integrity`
(worktree `<worktrees>/IJEVAL`) from audited IJ-NANO HEAD `bc4555e`.
Issue #12, Draft PR #13.

Wave A delivered (EA00 → EA01 → EA02, all gates claimed):
- EA00 (6d7b24e): 67-record historical defect inventory; §2.2 reproduction
  (R1/R2/R3; sealed corpus zero-risk rows — published 1.2R headline safe);
  cross-mission sweep incl. **unrepaired IJ-SDK D01/D02/D03** (new blocker
  IJE-B-004).
- EA01 (84c5ac2): 48-mode FMEA across all 27 layers, evidence-anchored.
- EA02 (e2467f4): typed contract v1.0.0 (`src/eval_assurance/contracts/`),
  central validator, `eligible_for_semantic_statistics`, fail-closed legacy
  adapters, N02RR adapter; 27/27 new tests + 213/213 ij_nano suite green.

Next: Wave B (EA03 dataset qualification → EA04 parser → EA05 dual-path →
EA06 golden witnesses → EA07 mutation → EA08 evidence integrity).

## Resume procedure

Worktree root below is the mission worktrees directory that contains the
sibling checkouts `IJNANO` (IJ-NANO mission) and `IJSDK` (read-only weights,
also hosts the Atlas lineage).

1. `cd <worktrees>/IJEVAL`, `git status` (expect clean).
2. Recreate untracked scaffolding on a fresh checkout:
   - `mkdir .runtime` (test scratch, gitignored)
   - `cmd /c mklink /J runtime\llama-cpp\vulkan <worktrees>/IJNANO/runtime/llama-cpp/vulkan`
3. Verify: `python -I -m unittest discover -s tests/ij_eval_assurance -q`
   and `python -I -m unittest discover -s tests/ij_nano -q` (213 OK).
4. Continue from `TASK_LEDGER_IJEVAL.md` first PENDING row (EA03).

## Pitfalls (carried over from IJ-NANO + new)

- Never edit sources of a running experiment; experiment identities hash them.
- Gate every commit with `python -I scripts/tools/publish_check.py --staged`
  run BARE (no `| tail` — the pipe masks the exit code and a BLOCKED verdict
  will slip through; bit once, see memory). After any redaction, `git add`
  AGAIN.
- Weights live in the read-only IJSDK sibling worktree; use
  `default_weights_root()` / `IJNANO_WEIGHTS_ROOT`, never hardcode user paths.
- Do not run `n02rr_analyze.main()` against patched REC paths — it rewrites
  `corrected_protocol_matrix.json` (sealed evidence).
- Repo test convention is stdlib `unittest`, NOT pytest (not installed).
- Do not modify the IJ-SDK mission branch (IJE-B-004 is theirs to repair).
- CPU-first: synthetic artifacts + offline replay; GPU only after EA13
  software qualification, via the host-wide `gpu_lease.py` protocol.

