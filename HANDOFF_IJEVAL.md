# HANDOFF — IJ-EVAL-ASSURANCE-1.0

## Where things stand (2026-11-28, EA02-R complete)

Branch `mission/ij-eval-assurance-1.0-systemic-evaluation-integrity`
(worktree `<worktrees>/IJEVAL`). Issue #12, Draft PR #13.

Delivered so far:
- Wave A (EA00 audit / EA01 threat model / EA02 typed contract) — see git
  history 0ab5c6b..e2467f4 and prior handoff in git.
- **EA02-R contract hardening** (addendum EA-D01..EA-D06, preregistered in
  `docs/IJEVAL_MISSION_ORDER_EA02R.md`): all six concerns reproduced red at
  `3fff135` then closed green — five certificate-gated fail-closed
  eligibility authorities; strict Boolean/enum typing (state-space battery:
  9,312 combos, 24/24 invariants, 0 escapes, 0 false rejections); evidence
  UNVERIFIED-by-default with VerifiedEvidence envelopes; qualified
  aggregation boundary proving the EA00 corruption containment at the real
  entry point (870 preserved, 2 NOT_EVALUABLE, 871/2186 unreachable);
  `pubgate.py` fail-closed publication gate (argv subprocess, finding-count
  verdict, staged-identity binding, receipts). Contract spec v1.1.0.
  Tests: ij_eval_assurance 68/68, ij_nano 213/213.

Also delivered (Wave B/C addendum `docs/IJEVAL_MISSION_ORDER_WAVE_BC.md`):
**EA-R01..EA-R04 trusted-boundary hardening** — QualificationAuthority
(digest-bound certificates, untrusted caller stores never authorize),
creation-keyed VerificationReceipts hashing actual artifact bytes,
immutable envelopes, hardened publication chain (scope certification,
roster reconciliation, critical-NOT_EVALUABLE blocking, explicit partial
scopes), snapshot-based publication-time revocation recheck. Tests 95/95 +
213/213. Evidence: `evidence/IJEVAL/EABC/`, report
`reports/IJEVAL_WAVEBC_HARDENING.md`.

Next: Wave B proper (EA03 independent ground truth → EA04/EA05 dual-path →
EA06/EA07 witnesses+mutation → EA08 end-to-end), then Wave C (EA09–EA11)
and the early catastrophe pilot. All Wave B qualifications must issue
through the QualificationAuthority.

## Resume procedure

Worktree root below is the mission worktrees directory that contains the
sibling checkouts `IJNANO` (IJ-NANO mission) and `IJSDK` (read-only weights,
also hosts the Atlas lineage).

1. `cd <worktrees>/IJEVAL`, `git status` (expect clean except possibly one
   untracked pubgate receipt — see pitfalls).
2. Recreate untracked scaffolding on a fresh checkout:
   - `mkdir .runtime` (test scratch, gitignored)
   - `cmd /c mklink /J runtime\llama-cpp\vulkan <worktrees>/IJNANO/runtime/llama-cpp/vulkan`
3. Verify: `python -m unittest discover -s tests/ij_eval_assurance -q`
   (95 OK) and `python -I -m unittest discover -s tests/ij_nano -q`
   (213 OK).
4. Continue from `TASK_LEDGER_IJEVAL.md` first PENDING row (EA03).

## Pitfalls (carried over + new)

- **Commit through the pubgate now**: `python -I
  scripts/ij_eval_assurance/pubgate.py commit -m "..."` — it runs the
  fail-closed gate (no pipes possible) and refuses while BLOCKED. The
  receipt for commit N is written before that commit and therefore lands in
  the NEXT commit (one-behind by design); the latest receipt may sit
  untracked — that is expected, document it.
- Never edit sources of a running experiment; experiment identities hash them.
- After any gate BLOCK + redaction, `git add` the file AGAIN before
  re-gating (staged-blob snapshot gotcha).
- Weights live in the read-only IJSDK sibling worktree; use
  `default_weights_root()` / `IJNANO_WEIGHTS_ROOT`, never hardcode user
  paths — and never hardcode a real local path even in test fixtures:
  build probe strings from `pathlib.Path.home()` at runtime (the scanner
  only flags real identities, but the SOURCE file must stay clean).
- `n02rr_analyze.py` is DIAGNOSTIC-ONLY now; formal aggregation goes through
  `eval_assurance.statistics.boundary.aggregate_semantic`.
- Repo test convention is stdlib `unittest`, NOT pytest (not installed).
- Receipt filenames must stay colon-free (Windows).
- Do not modify the IJ-SDK mission branch (IJE-B-004 is theirs to repair).
- CPU-first: synthetic artifacts + offline replay; GPU only after EA13
  software qualification, via the host-wide `gpu_lease.py` protocol.

