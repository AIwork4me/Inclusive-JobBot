"""N03 dataset package: Batch A family registry (C01-C08).

Each primitive has exactly three families: two development + one
confirmation, with disjoint family identities. Batches B-D extend this
registry (C09-C32) under the same contracts.
"""
from __future__ import annotations

from .families_a1 import (C01_FAMILIES, C02_FAMILIES, C03_FAMILIES,
                          C04_FAMILIES)
from .families_a2 import (C05_FAMILIES, C06_FAMILIES, C07_FAMILIES,
                          C08_FAMILIES)

ALL_BATCH_A = (C01_FAMILIES + C02_FAMILIES + C03_FAMILIES + C04_FAMILIES +
               C05_FAMILIES + C06_FAMILIES + C07_FAMILIES + C08_FAMILIES)

BATCH_A_FAMILIES: dict[str, list] = {}
for _f in ALL_BATCH_A:
    BATCH_A_FAMILIES.setdefault(_f.primitive, []).append(_f)

DEV_SEED = "ij-nano-1.3s/n03/dev-roster/v1"
CONF_SEED_FILE_NAME = "confirmation_seed.json"
