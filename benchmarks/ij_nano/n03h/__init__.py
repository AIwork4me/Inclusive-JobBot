"""IJ-NANO-48H physical campaign package (n03h).

Extends — never replaces — the N03 runner/authorization controller at
``benchmarks/ij_nano/n03/``. Physical dispatch goes exclusively through
the pinned EAE ExecutionAuthorization contract; evaluation goes
exclusively through the pinned EAE dual-path (ProductionParser +
ProductionEvaluator + Independent Interpreter + Reference Oracle).
"""
