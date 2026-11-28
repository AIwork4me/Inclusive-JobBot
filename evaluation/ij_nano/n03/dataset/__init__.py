"""N03 dataset package: family registry for all four batches (C01-C32).

Each primitive has exactly three families: two development + one
confirmation, with disjoint family identities.
"""
from __future__ import annotations

from .families_a1 import (C01_FAMILIES, C02_FAMILIES, C03_FAMILIES,
                          C04_FAMILIES)
from .families_a2 import (C05_FAMILIES, C06_FAMILIES, C07_FAMILIES,
                          C08_FAMILIES)
from .families_b import (C09_FAMILIES, C10_FAMILIES, C11_FAMILIES,
                         C12_FAMILIES, C13_FAMILIES, C14_FAMILIES,
                         C15_FAMILIES, C16_FAMILIES)
from .families_c import (C17_FAMILIES, C18_FAMILIES, C19_FAMILIES,
                         C20_FAMILIES, C21_FAMILIES, C22_FAMILIES,
                         C23_FAMILIES, C24_FAMILIES)
from .families_d import (C25_FAMILIES, C26_FAMILIES, C27_FAMILIES,
                         C28_FAMILIES, C29_FAMILIES, C30_FAMILIES,
                         C31_FAMILIES, C32_FAMILIES)

ALL_FAMILIES = (C01_FAMILIES + C02_FAMILIES + C03_FAMILIES + C04_FAMILIES +
                C05_FAMILIES + C06_FAMILIES + C07_FAMILIES + C08_FAMILIES +
                C09_FAMILIES + C10_FAMILIES + C11_FAMILIES + C12_FAMILIES +
                C13_FAMILIES + C14_FAMILIES + C15_FAMILIES + C16_FAMILIES +
                C17_FAMILIES + C18_FAMILIES + C19_FAMILIES + C20_FAMILIES +
                C21_FAMILIES + C22_FAMILIES + C23_FAMILIES + C24_FAMILIES +
                C25_FAMILIES + C26_FAMILIES + C27_FAMILIES + C28_FAMILIES +
                C29_FAMILIES + C30_FAMILIES + C31_FAMILIES + C32_FAMILIES)

FAMILIES_BY_PRIMITIVE: dict[str, list] = {}
for _f in ALL_FAMILIES:
    FAMILIES_BY_PRIMITIVE.setdefault(_f.primitive, []).append(_f)

# backward-compatible name (Batch A only consumers)
BATCH_A_FAMILIES = {p: [f for f in fs if f.primitive <= "C08"]
                    for p, fs in FAMILIES_BY_PRIMITIVE.items()
                    if p <= "C08"}

DEV_SEED = "ij-nano-1.3s/n03/dev-roster/v1"
CONF_SEED_FILE_NAME = "confirmation_seed.json"
