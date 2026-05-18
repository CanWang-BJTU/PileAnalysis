# -*- coding: utf-8 -*-

import math
from typing import Dict, List

from core.mesh_spec import build_mesh_positions
from core.parameter_collector import GroupInput, ParameterCollector

HAS_GROUP_SOLVER = True
GROUP_SOLVER_IMPORT_ERROR = None
try:
    from core.monolithic_group_solver import MonolithicGroupPileSolver
except Exception as exc:
    GROUP_SOLVER_IMPORT_ERROR = exc
    try:
        from nonlinear_framework.core.monolithic_group_solver import MonolithicGroupPileSolver
    except Exception as exc:
        GROUP_SOLVER_IMPORT_ERROR = exc
        HAS_GROUP_SOLVER = False
        MonolithicGroupPileSolver = None


class GroupExecutor:
    @staticmethod
    def _section_metadata(payload: Dict) -> Dict:
        pile_types = [
            dict(item) for item in (payload.get("pile_types", []) or [])
            if isinstance(item, dict)
        ]
        fiber_type_count = sum(
            1 for pile_type in pile_types
            if str(pile_type.get("section_mode", "elastic")) == "fiber"
        )
        fiber_library_count = sum(
            len(pile_type.get("fiber_section_library", []) or [])
            for pile_type in pile_types
        )
        fiber_segment_count = sum(
            len(pile_type.get("fiber_section_segments", []) or [])
            for pile_type in pile_types
        )
        return {
            "pile_type_count": len(pile_types),
            "fiber_pile_type_count": fiber_type_count,
            "fiber_section_count": fiber_library_count,
            "fiber_segment_count": fiber_segment_count,
        }

    @staticmethod
    def run(inp: GroupInput) -> Dict:
        if not HAS_GROUP_SOLVER:
            raise RuntimeError(
                "monolithic_group_solver is unavailable. "
                f"Import error: {GROUP_SOLVER_IMPORT_ERROR!r}"
            )

        payload = dict(inp.payload)
        solver = MonolithicGroupPileSolver(ele_size=payload.get("ele_size_m"))

        materials = {
            str(item.get("name", "")): dict(item)
            for item in payload.get("materials", [])
            if isinstance(item, dict)
        }

        for layer in payload.get("layers", []):
            if not isinstance(layer, dict):
                continue
            material = materials.get(str(layer.get("material_name", "")), {})
            z_top = abs(float(layer.get("z_top", 0.0)))
            z_bottom = abs(float(layer.get("z_bottom", 0.0)))
            z0 = min(z_top, z_bottom)
            z1 = max(z_top, z_bottom)
            solver.add_lateral_soil_layer(
                z0,
                z1,
                str(material.get("lateral_type", "Sand")),
                **dict(material.get("lateral_params", {})),
            )
            solver.add_axial_soil_layer(
                z0,
                z1,
                str(material.get("axial_type", "API Sand")),
                **dict(material.get("axial_params", {})),
            )

        if payload.get("layers"):
            last_layer = payload["layers"][-1]
            last_material = materials.get(str(last_layer.get("material_name", "")), {})
            solver.set_tip_soil(
                str(last_material.get("axial_type", "API Sand")),
                **dict(last_material.get("axial_params", {})),
            )

        pile_types = {
            str(item.get("name", "")): dict(item)
            for item in payload.get("pile_types", [])
            if isinstance(item, dict)
        }

        for row in payload.get("pile_layout", []):
            if not isinstance(row, dict):
                continue
            pile_index = len(solver.piles)
            pile_type = pile_types.get(str(row.get("pile_type_name", "")), {})
            top_z = float(row.get("top_z_m", pile_type.get("pile_top_z_m", 0.0)))
            bottom_z = float(row.get("bottom_z_m", pile_type.get("pile_bottom_z_m", -1.0)))
            total_length = abs(top_z - bottom_z)
            free_length = max(top_z, 0.0)
            embedded_length = max(total_length - free_length, 1.0e-4)
            if bottom_z < 0.0:
                embedded_length = max(abs(bottom_z), 1.0e-4)

            diameter = float(pile_type.get("pile_diameter_m", 1.0))
            thickness = float(pile_type.get("pile_thickness_m", 0.0))
            shape = str(pile_type.get("pile_shape", "Circle"))
            if shape == "Pipe":
                inner_d = max(diameter - 2.0 * thickness, 0.0)
                area = math.pi * (diameter * diameter - inner_d * inner_d) / 4.0
                inertia = math.pi * (diameter**4 - inner_d**4) / 64.0
            else:
                area = math.pi * diameter * diameter / 4.0
                inertia = math.pi * diameter**4 / 64.0

            mesh_key = f"Pile {pile_index + 1}"
            mesh_by_pile = payload.get("mesh_settings_by_pile", {})
            pile_mesh = (
                dict(mesh_by_pile.get(mesh_key, {}))
                if isinstance(mesh_by_pile, dict)
                else {}
            ) or payload.get("mesh_settings")
            mesh_positions = build_mesh_positions(total_length, pile_mesh)

            solver.add_pile(
                x=float(row.get("x_m", 0.0)),
                y=float(row.get("y_m", 0.0)),
                pile_length=embedded_length,
                pile_diameter=diameter,
                E_pile=float(pile_type.get("pile_E_kPa", 3.0e7)),
                I_pile=inertia,
                A_pile=area,
                free_length=free_length,
                head_elevation=top_z,
                mesh_positions=mesh_positions,
                head_connectivity=str(row.get("connectivity", "fixed")),
                section_mode=str(pile_type.get("section_mode", "elastic") or "elastic"),
                fiber_section_library=list(pile_type.get("fiber_section_library", []) or []),
                fiber_section_segments=list(pile_type.get("fiber_section_segments", []) or []),
                tip_area_m2=ParameterCollector._resolve_bottom_section_area(
                    str(pile_type.get("section_mode", "elastic") or "elastic"),
                    list(pile_type.get("fiber_section_library", []) or []),
                    list(pile_type.get("fiber_section_segments", []) or []),
                    total_length,
                ),
            )

        cap = dict(payload.get("cap", {}))
        cap_center_z = float(cap.get("center_z_m", 0.0))
        cap_reference = (0.0, 0.0, cap_center_z)

        fx_total = 0.0
        fy_total = 0.0
        fz_total = 0.0
        mx_total = 0.0
        my_total = 0.0
        mz_total = 0.0

        load_cases = payload.get("load_cases", [])
        if isinstance(load_cases, list) and load_cases:
            for row in load_cases:
                if not isinstance(row, dict):
                    continue
                x_m = float(row.get("x_m", 0.0))
                y_m = float(row.get("y_m", 0.0))
                fx = float(row.get("Fx", 0.0))
                fy = float(row.get("Fy", 0.0))
                fz = float(row.get("Fz", 0.0))
                mx = float(row.get("Mx", 0.0))
                my = float(row.get("My", 0.0))
                mz = float(row.get("Mz", 0.0))

                fx_total += fx
                fy_total += fy
                fz_total += fz
                mx_total += mx + y_m * fz
                my_total += my - x_m * fz
                mz_total += mz - y_m * fx + x_m * fy
        else:
            load_map = {key: {"value": 0.0, "x_m": 0.0, "y_m": 0.0} for key in ("Fx", "Fy", "Fz", "Mx", "My", "Mz")}
            for row in payload.get("loads", []):
                if not isinstance(row, dict):
                    continue
                load_type = str(row.get("type", "")).split()[0]
                if load_type in load_map:
                    load_map[load_type] = {
                        "value": float(row.get("value", 0.0)),
                        "x_m": float(row.get("x_m", 0.0)),
                        "y_m": float(row.get("y_m", 0.0)),
                    }

            fx_total = float(load_map["Fx"]["value"])
            fy_total = float(load_map["Fy"]["value"])
            fz_total = float(load_map["Fz"]["value"])
            mx_total = float(load_map["Mx"]["value"])
            my_total = float(load_map["My"]["value"])
            mz_total = float(load_map["Mz"]["value"])
            for force_key in ("Fx", "Fy", "Fz"):
                entry = load_map[force_key]
                value = float(entry.get("value", 0.0))
                x_m = float(entry.get("x_m", 0.0))
                y_m = float(entry.get("y_m", 0.0))
                if force_key == "Fx":
                    mz_total += -y_m * value
                elif force_key == "Fy":
                    mz_total += x_m * value
                elif force_key == "Fz":
                    mx_total += y_m * value
                    my_total += -x_m * value

        if abs(fx_total) > 1.0e-12 or abs(fy_total) > 1.0e-12:
            load_direction_deg = math.degrees(math.atan2(fy_total, fx_total))
        else:
            load_direction_deg = 0.0
        solver.auto_assign_pairwise_multipliers(load_direction_deg=load_direction_deg, combine="minimum")

        raw = solver.build_and_analyze(
            Fx=fx_total,
            Fy=fy_total,
            Fz=fz_total,
            Mx=mx_total,
            My=my_total,
            Mz=mz_total,
            n_steps=int(payload.get("steps", 40)),
            cap_fixity="3D",
            verbose=False,
            cap_reference=cap_reference,
            load_location=cap_reference,
        )

        pile_results = raw.get("piles", [])
        return {
            "raw": raw,
            "piles": pile_results,
            "section_definition": GroupExecutor._section_metadata(payload),
            "cap_disp_x_mm": float(raw.get("cap_disp_x_mm", 0.0)),
            "cap_disp_y_mm": float(raw.get("cap_disp_y_mm", 0.0)),
            "cap_disp_z_mm": float(raw.get("cap_disp_z_mm", 0.0)),
            "pile_count": len(pile_results),
            "max_abs_axial": max(
                (
                    max((abs(float(v)) for v in pile.get("axial_forces", [])), default=0.0)
                    for pile in pile_results
                ),
                default=0.0,
            ),
            "max_abs_shear": max(
                (
                    max(
                        max((abs(float(v)) for v in pile.get("rspile_shear_x", [])), default=0.0),
                        max((abs(float(v)) for v in pile.get("rspile_shear_y", [])), default=0.0),
                    )
                    for pile in pile_results
                ),
                default=0.0,
            ),
            "max_abs_moment": max(
                (
                    max(
                        max((abs(float(v)) for v in pile.get("rspile_moment_x", [])), default=0.0),
                        max((abs(float(v)) for v in pile.get("rspile_moment_y", [])), default=0.0),
                    )
                    for pile in pile_results
                ),
                default=0.0,
            ),
        }
