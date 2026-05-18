# -*- coding: utf-8 -*-

from typing import Dict

from core.parameter_collector import LateralInput

HAS_LATERAL_SOLVER = True
LATERAL_SOLVER_IMPORT_ERROR = None
try:
    from core.lateral_solver import LateralPileSolver
except Exception as exc:
    LATERAL_SOLVER_IMPORT_ERROR = exc
    try:
        from nonlinear_framework.core.lateral_solver import LateralPileSolver
    except Exception as exc:
        LATERAL_SOLVER_IMPORT_ERROR = exc
        HAS_LATERAL_SOLVER = False
        LateralPileSolver = None


class LateralExecutor:
    """Execute lateral solver using collected lateral input."""

    @staticmethod
    def _section_metadata(inp: LateralInput) -> Dict:
        return {
            "section_mode": str(getattr(inp, "section_mode", "elastic")),
            "fiber_section_count": len(getattr(inp, "fiber_section_library", []) or []),
            "fiber_segment_count": len(getattr(inp, "fiber_section_segments", []) or []),
        }

    @staticmethod
    def run(inp: LateralInput) -> Dict:
        if not HAS_LATERAL_SOLVER:
            raise RuntimeError(
                "lateral_solver is unavailable. "
                f"Import error: {LATERAL_SOLVER_IMPORT_ERROR!r}"
            )

        solver = LateralPileSolver(
            pile_length=inp.pile_length_m,
            pile_diameter=inp.pile_diameter_m,
            E_pile=inp.pile_E_kPa,
            I_pile=inp.pile_I_m4,
            A_pile=inp.pile_A_m2,
            ele_size=inp.ele_size_m,
            free_length=inp.free_length_m,
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

        kwargs = {
            "top_bc": "free",
            "bottom_bc": "free",
            "n_steps": inp.steps,
            "verbose": False,
        }
        if inp.control_mode == "Displacement Control":
            kwargs["lateral_disp"] = inp.lateral_disp_m
        else:
            kwargs["lateral_disp"] = None
        result = solver.analyze_6dof(
            Fx=float(inp.loads.get("Fx", {}).get("value", 0.0)),
            Fy=float(inp.loads.get("Fy", {}).get("value", 0.0)),
            Fz=float(inp.loads.get("Fz", {}).get("value", 0.0)),
            Mx=float(inp.loads.get("Mx", {}).get("value", 0.0)),
            My=float(inp.loads.get("My", {}).get("value", 0.0)),
            Mz=float(inp.loads.get("Mz", {}).get("value", 0.0)),
            z_Fx=float(inp.loads.get("Fx", {}).get("z_m", 0.0)),
            z_Fy=float(inp.loads.get("Fy", {}).get("z_m", 0.0)),
            z_Fz=float(inp.loads.get("Fz", {}).get("z_m", 0.0)),
            z_Mx=float(inp.loads.get("Mx", {}).get("z_m", 0.0)),
            z_My=float(inp.loads.get("My", {}).get("z_m", 0.0)),
            z_Mz=float(inp.loads.get("Mz", {}).get("z_m", 0.0)),
            **kwargs,
        )
        if isinstance(result, dict):
            result["section_definition"] = LateralExecutor._section_metadata(inp)
        return result
