# -*- coding: utf-8 -*-

from typing import Dict

from core.parameter_collector import AxialInput

HAS_AXIAL_SOLVER = True
AXIAL_SOLVER_IMPORT_ERROR = None
try:
    from core.axial_solver import AxialPileSolver
except Exception as exc:
    AXIAL_SOLVER_IMPORT_ERROR = exc
    try:
        from nonlinear_framework.core.axial_solver import AxialPileSolver
    except Exception as exc:
        AXIAL_SOLVER_IMPORT_ERROR = exc
        HAS_AXIAL_SOLVER = False
        AxialPileSolver = None


class AxialExecutor:
    """Execute axial solver using collected axial input."""

    @staticmethod
    def _section_metadata(inp: AxialInput) -> Dict:
        return {
            "section_mode": str(getattr(inp, "section_mode", "elastic")),
            "fiber_section_count": len(getattr(inp, "fiber_section_library", []) or []),
            "fiber_segment_count": len(getattr(inp, "fiber_section_segments", []) or []),
        }

    @staticmethod
    def run(inp: AxialInput) -> Dict:
        if not HAS_AXIAL_SOLVER:
            raise RuntimeError(
                "axial_solver is unavailable. "
                f"Import error: {AXIAL_SOLVER_IMPORT_ERROR!r}"
            )

        solver = AxialPileSolver(
            pile_length=inp.pile_length_m,
            pile_diameter=inp.pile_diameter_m,
            E_pile=inp.pile_E_kPa,
            A_pile=inp.pile_A_m2,
            ele_size=inp.ele_size_m,
            mesh_positions=inp.mesh_positions_m,
            section_mode=inp.section_mode,
            fiber_section_library=inp.fiber_section_library,
            fiber_section_segments=inp.fiber_section_segments,
        )

        for layer in inp.layers:
            solver.add_soil_layer(
                layer.z_top,
                layer.z_bottom,
                layer.soil_type,
                **layer.params,
            )

        solver.set_tip_soil(inp.tip_type, **inp.tip_params)

        kwargs = {"n_steps": inp.steps, "verbose": False}
        if inp.control_mode == "Displacement Control":
            kwargs["axial_disp"] = inp.axial_disp_m
            kwargs["axial_load"] = 0.0
        else:
            kwargs["axial_load"] = inp.axial_load_kN
            kwargs["axial_disp"] = None

        result = solver.analyze(**kwargs)
        if isinstance(result, dict):
            result["section_definition"] = AxialExecutor._section_metadata(inp)
        return result
