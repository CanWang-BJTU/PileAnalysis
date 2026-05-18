# -*- coding: utf-8 -*-

import math
from typing import List


CONCRETE_GRADE_OPTIONS: List[str] = [
    "C10",
    "C15",
    "C20",
    "C25",
    "C30",
    "C35",
    "C40",
    "C45",
    "C50",
    "C55",
    "C60",
    "C65",
    "C70",
    "C75",
    "C80",
]

USER_DEFINED_CONCRETE = "User Define"


def concrete_material_options() -> List[str]:
    return [*CONCRETE_GRADE_OPTIONS, USER_DEFINED_CONCRETE]


def concrete_cover_strength_kpa(grade: str) -> float:
    digits = "".join(ch for ch in str(grade) if ch.isdigit())
    if not digits:
        raise ValueError(f"Invalid concrete grade: {grade}")
    strength = float(digits)

    def factor1(r: float) -> float:
        if r <= 50.0:
            return 0.76
        if r == 80.0:
            return 0.82
        return 0.76 + 0.06 * (r - 50.0) / 30.0

    def factor2(r: float) -> float:
        if r < 40.0:
            return 1.0
        if r == 80.0:
            return 0.87
        return 1.0 - 0.13 * (r - 40.0) / 40.0

    return -strength * 0.88 * factor1(strength) * factor2(strength) * 1000.0


def concrete_elastic_modulus_kpa(grade: str) -> float:
    fc_kpa = concrete_cover_strength_kpa(grade)
    return math.sqrt(-fc_kpa / 1000.0) * 5.0e6


def infer_concrete_material_from_E(E_kpa: float, rel_tol: float = 1.0e-6) -> str:
    try:
        target = float(E_kpa)
    except Exception:
        return USER_DEFINED_CONCRETE
    for grade in CONCRETE_GRADE_OPTIONS:
        ref = concrete_elastic_modulus_kpa(grade)
        if math.isclose(target, ref, rel_tol=rel_tol, abs_tol=1.0):
            return grade
    return USER_DEFINED_CONCRETE
