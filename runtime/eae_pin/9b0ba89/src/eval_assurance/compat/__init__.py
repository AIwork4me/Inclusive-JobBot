"""EAE-runner compatibility: versioned contract registry and machine-
readable runner authorization (N03 critical path)."""
from .authorization import RunnerAuthorization, authorize_runner
from .contract import (CONTRACT_VERSION, N03_BATCH_A, Interface,
                       REGISTRY, contract_summary, verify_contract)

__all__ = ["CONTRACT_VERSION", "N03_BATCH_A", "Interface", "REGISTRY",
           "contract_summary", "verify_contract", "RunnerAuthorization",
           "authorize_runner"]
