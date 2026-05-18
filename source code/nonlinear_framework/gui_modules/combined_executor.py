# -*- coding: utf-8 -*-

from typing import Dict

from core.parameter_collector import CombinedInput

HAS_COMBINED_SOLVER = True
COMBINED_SOLVER_IMPORT_ERROR = None
try:
    from core.monolithic_group_solver import MonolithicGroupPileSolver
except Exception as exc:
    COMBINED_SOLVER_IMPORT_ERROR = exc
    try:
        from nonlinear_framework.core.monolithic_group_solver import MonolithicGroupPileSolver
    except Exception as exc:
        COMBINED_SOLVER_IMPORT_ERROR = exc
        HAS_COMBINED_SOLVER = False
        MonolithicGroupPileSolver = None


class CombinedExecutor:
    """Single-pile 3D coupled executor based on the monolithic solver."""

    @staticmethod
    def _section_metadata(inp: CombinedInput) -> Dict:
        return {
            "section_mode": str(getattr(inp, "section_mode", "elastic")),
            "fiber_section_count": len(getattr(inp, "fiber_section_library", []) or []),
            "fiber_segment_count": len(getattr(inp, "fiber_section_segments", []) or []),
        }

    @staticmethod
    def run(inp: CombinedInput) -> Dict:
        if not HAS_COMBINED_SOLVER:
            raise RuntimeError(
                "monolithic_group_solver is unavailable. "
                f"Import error: {COMBINED_SOLVER_IMPORT_ERROR!r}"
            )

        solver = MonolithicGroupPileSolver(ele_size=inp.ele_size_m)
        solver.add_pile(
            x=0.0,
            y=0.0,
            pile_length=inp.pile_length_m,
            pile_diameter=inp.pile_diameter_m,
            E_pile=inp.pile_E_kPa,
            I_pile=inp.pile_I_m4,
            A_pile=inp.pile_A_m2,
            free_length=inp.free_length_m,
            head_connectivity="fixed",
            mesh_positions=inp.mesh_positions_m,
            section_mode=inp.section_mode,
            fiber_section_library=inp.fiber_section_library,
            fiber_section_segments=inp.fiber_section_segments,
        )

        for layer in inp.lateral_layers:
            solver.add_lateral_soil_layer(
                layer.z_top,
                layer.z_bottom,
                layer.soil_type,
                **layer.params,
            )

        for layer in inp.axial_layers:
            solver.add_axial_soil_layer(
                layer.z_top,
                layer.z_bottom,
                layer.soil_type,
                **layer.params,
            )

        solver.set_tip_soil(inp.tip_type, **inp.tip_params)
        raw = solver.build_and_analyze(
            Fx=inp.fx_kN,
            Fy=inp.fy_kN,
            Fz=inp.fz_kN,
            Mx=inp.mx_kN_m,
            My=inp.my_kN_m,
            Mz=inp.mz_kN_m,
            n_steps=inp.steps,
            cap_fixity="3D",
            verbose=False,
        )

        pile = raw.get("piles", [{}])[0] if raw.get("piles") else {}
        return {
            "raw": raw,
            "pile": pile,
            "section_definition": CombinedExecutor._section_metadata(inp),
            "cap_disp": raw.get("cap_disp", [0.0] * 6),
            "head_disp_x_mm": float(raw.get("cap_disp_x_mm", 0.0)),
            "head_disp_y_mm": float(raw.get("cap_disp_y_mm", 0.0)),
            "head_disp_z_mm": float(raw.get("cap_disp_z_mm", 0.0)),
            "depths": pile.get("depths_from_head", []),
            "depths_ele": pile.get("depths_ele_from_head", []),
            "displacements_x": pile.get("disps_dx", []),
            "displacements_y": pile.get("disps_dy", []),
            "displacements_z": pile.get("disps_dz", []),
            "axial_forces": pile.get("axial_forces", []),
            "shears": [-float(v) for v in pile.get("rspile_shear_x", [])],
            "shears_y": [-float(v) for v in pile.get("rspile_shear_y", [])],
            "moments": pile.get("rspile_moment_y", []),
            "moments_x": pile.get("rspile_moment_x", []),
            "section_shears": [-float(v) for v in pile.get("section_rspile_shear_x", [])],
            "section_shears_y": [-float(v) for v in pile.get("section_rspile_shear_y", [])],
            "section_moments": pile.get("section_rspile_moment_y", []),
            "section_moments_x": pile.get("section_rspile_moment_x", []),
            "section_depths": pile.get("section_depths_from_head", []),
            "max_abs_moment": max((abs(float(v)) for v in pile.get("rspile_moment_y", [])), default=0.0),
            "max_abs_axial": max((abs(float(v)) for v in pile.get("axial_forces", [])), default=0.0),
        }
