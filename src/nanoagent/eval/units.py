"""Closed unit registry shared by contracts (validation) and comparators
(semantic comparison). N05A-R EV05: a scalar value never silently inherits
a hidden expected unit; unit semantics live in one place only.
"""
from __future__ import annotations

# base unit per dimension and conversion factors into it
UNIT_REGISTRY: dict[str, tuple[str, float]] = {
    # length -> metre
    "mm": ("length", 0.001), "cm": ("length", 0.01), "m": ("length", 1.0),
    "km": ("length", 1000.0),
    # mass -> gram
    "g": ("mass", 1.0), "kg": ("mass", 1000.0), "t": ("mass", 1_000_000.0),
    # time -> second
    "s": ("time", 1.0), "min": ("time", 60.0), "h": ("time", 3600.0),
    "day": ("time", 86400.0),
    # money: currencies never convert into each other
    "CNY": ("money:CNY", 1.0), "USD": ("money:USD", 1.0), "EUR": ("money:EUR", 1.0),
    # count: dimensionless
    "": ("count", 1.0), "pcs": ("count", 1.0), "个": ("count", 1.0),
}

_EPS = 1e-9


def unit_registered(unit: str) -> bool:
    return unit in UNIT_REGISTRY


def dimension_of(unit: str) -> str | None:
    entry = UNIT_REGISTRY.get(unit)
    return entry[0] if entry else None


def to_base(value: float, unit: str) -> float:
    return float(value) * UNIT_REGISTRY[unit][1]


def values_equal(a: float, b: float) -> bool:
    return abs(a - b) <= _EPS * max(1.0, abs(b))
