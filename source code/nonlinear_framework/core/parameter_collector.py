# -*- coding: utf-8 -*-

import math
from dataclasses import dataclass
from typing import Dict, List, Optional
from core.axial_param_processor import AxialParamProcessor
from core.mesh_spec import build_mesh_positions


@dataclass
class AxialLayer:
    z_top: float
    z_bottom: float
    soil_type: str
    params: Dict[str, float]


@dataclass
class AxialInput:
    pile_length_m: float
    pile_diameter_m: float
    pile_shape: str
    pile_thickness_m: float
    pile_E_kPa: float
    pile_A_m2: float
    ele_size_m: Optional[float]
    mesh_positions_m: Optional[List[float]]
    layers: List[AxialLayer]
    tip_type: str
    tip_params: Dict[str, float]
    control_mode: str
    axial_load_kN: float
    load_z_m: float
    axial_disp_m: float
    steps: int
    section_mode: str = "elastic"
    fiber_section_library: List[Dict] = None
    fiber_section_segments: List[Dict] = None


@dataclass
class LateralInput:
    pile_length_m: float
    pile_diameter_m: float
    pile_E_kPa: float
    pile_A_m2: float
    pile_I_m4: float
    ele_size_m: Optional[float]
    mesh_positions_m: Optional[List[float]]
    free_length_m: float
    layers: List[AxialLayer]
    loads: Dict[str, Dict[str, float]]
    control_mode: str
    lateral_load_kN: float
    lateral_disp_m: Optional[float]
    moment_load_kN_m: float
    steps: int
    section_mode: str = "elastic"
    fiber_section_library: List[Dict] = None
    fiber_section_segments: List[Dict] = None


@dataclass
class CombinedAxialLayer:
    z_top: float
    z_bottom: float
    soil_type: str
    params: Dict[str, float]


@dataclass
class CombinedLateralLayer:
    z_top: float
    z_bottom: float
    soil_type: str
    params: Dict[str, float]


@dataclass
class CombinedInput:
    pile_length_m: float
    pile_diameter_m: float
    pile_shape: str
    pile_thickness_m: float
    pile_E_kPa: float
    pile_A_m2: float
    pile_I_m4: float
    ele_size_m: Optional[float]
    mesh_positions_m: Optional[List[float]]
    free_length_m: float
    axial_layers: List[CombinedAxialLayer]
    lateral_layers: List[CombinedLateralLayer]
    tip_type: str
    tip_params: Dict[str, float]
    loads: Dict[str, Dict[str, float]]
    fx_kN: float
    fy_kN: float
    fz_kN: float
    mx_kN_m: float
    my_kN_m: float
    mz_kN_m: float
    axial_force_kN: float
    shear_force_kN: float
    moment_kN_m: float
    axial_depth_m: float
    shear_depth_m: float
    moment_depth_m: float
    steps: int
    section_mode: str = "elastic"
    fiber_section_library: List[Dict] = None
    fiber_section_segments: List[Dict] = None


@dataclass
class GroupInput:
    payload: Dict


class ParameterCollector:
    """Unified mode-aware parameter collector.

    Today only axial path is fully implemented.
    """

    @staticmethod
    def collect(mode_index: int, payload: Dict):
        if mode_index == 0:
            return ParameterCollector.collect_axial(payload)
        if mode_index == 1:
            return ParameterCollector.collect_lateral(payload)
        if mode_index == 2:
            return ParameterCollector.collect_combined(payload)
        if mode_index == 3:
            return ParameterCollector.collect_group(payload)
        raise ValueError(f"Unsupported mode index: {mode_index}")

    @staticmethod
    def _derive_single_pile_geometry(payload: Dict):
        total_length = float(payload.get("pile_length_m", 0.0))
        pile_top_z = float(payload.get("pile_top_z_m", 0.0))
        pile_bottom_z = float(payload.get("pile_bottom_z_m", pile_top_z - total_length))
        free_length = max(pile_top_z, 0.0)
        embedded_length = max(total_length - free_length, 0.0001)
        if pile_bottom_z < 0.0:
            embedded_length = max(abs(pile_bottom_z), 0.0001)
        soil_shift_from_head = max(pile_top_z, 0.0)
        return total_length, embedded_length, free_length, soil_shift_from_head

    @staticmethod
    def _collect_section_payload(payload: Dict):
        return {
            "section_mode": str(payload.get("section_mode", "elastic") or "elastic"),
            "fiber_section_library": [
                dict(item) for item in (payload.get("fiber_section_library", []) or [])
                if isinstance(item, dict)
            ],
            "fiber_section_segments": [
                dict(item) for item in (payload.get("fiber_section_segments", []) or [])
                if isinstance(item, dict)
            ],
        }

    @staticmethod
    def _resolve_bottom_section_area(section_mode: str, fiber_section_library: List[Dict], fiber_section_segments: List[Dict], total_length: float) -> Optional[float]:
        if str(section_mode or "elastic") != "fiber":
            return None
        sections = {
            str(item.get("name", "")): dict(item)
            for item in (fiber_section_library or [])
            if isinstance(item, dict)
        }
        segments = [
            dict(item) for item in (fiber_section_segments or [])
            if isinstance(item, dict)
        ]
        if not sections or not segments:
            return None

        selected = None
        for seg in segments:
            top = float(seg.get("top_m", 0.0))
            bottom = float(seg.get("bottom_m", top))
            low = min(top, bottom)
            high = max(top, bottom)
            if low - 1.0e-8 <= total_length <= high + 1.0e-8:
                selected = seg
                break
        if selected is None:
            selected = max(
                segments,
                key=lambda seg: max(float(seg.get("top_m", 0.0)), float(seg.get("bottom_m", 0.0))),
            )

        section_name = str(selected.get("section_name", ""))
        section = sections.get(section_name)
        if not section:
            return None
        summary = dict(section.get("summary", {}) or {})
        area = summary.get("area_m2")
        if area in (None, "", "None"):
            return None
        area_val = float(area)
        return area_val if area_val > 0.0 else None

    @staticmethod
    def collect_axial(payload: Dict) -> AxialInput:
        payload = AxialParamProcessor.normalize(payload)
        total_length, _, _, soil_shift = ParameterCollector._derive_single_pile_geometry(payload)
        section_payload = ParameterCollector._collect_section_payload(payload)
        bottom_section_area = ParameterCollector._resolve_bottom_section_area(
            section_payload["section_mode"],
            section_payload["fiber_section_library"],
            section_payload["fiber_section_segments"],
            total_length,
        )
        mesh_positions = build_mesh_positions(total_length, payload.get("mesh_settings"))
        layers: List[AxialLayer] = []
        for row in payload.get("layers", []):
            layers.append(
                AxialLayer(
                    z_top=float(row["z_top"]) + soil_shift,
                    z_bottom=float(row["z_bottom"]) + soil_shift,
                    soil_type=str(row["soil_type"]),
                    params=dict(row["params"]),
                )
            )

        d = float(payload["pile_diameter_m"])
        shape = str(payload.get("pile_shape", "Circle"))
        t = float(payload.get("pile_thickness_m", 0.0))
        area = payload.get("pile_A_m2")
        if area is None:
            if shape == "Pipe":
                di = max(d - 2.0 * t, 0.0)
                area = math.pi * (d * d - di * di) / 4.0
            else:
                area = math.pi * d * d / 4.0

        ele_size = payload.get("ele_size_m")
        tip_params = dict(payload["tip_params"])
        if bottom_section_area is not None:
            tip_params["A_base"] = bottom_section_area
            tip_params["A_tip"] = bottom_section_area
        return AxialInput(
            pile_length_m=total_length,
            pile_diameter_m=d,
            pile_shape=shape,
            pile_thickness_m=t,
            pile_E_kPa=float(payload["pile_E_kPa"]),
            pile_A_m2=float(area),
            ele_size_m=(None if ele_size in (None, 0, 0.0) else float(ele_size)),
            mesh_positions_m=mesh_positions,
            layers=layers,
            tip_type=str(payload["tip_type"]),
            tip_params=tip_params,
            control_mode=str(payload["control_mode"]),
            # User-facing payload follows the global Z-axis sign convention:
            # downward compression is negative. The current axial solver expects
            # positive compression downward, so we flip the sign here.
            axial_load_kN=-float(payload["axial_load_kN"]),
            load_z_m=float(payload.get("load_z_m", 0.0)),
            axial_disp_m=float(payload["axial_disp_m"]),
            steps=int(payload["steps"]),
            section_mode=section_payload["section_mode"],
            fiber_section_library=section_payload["fiber_section_library"],
            fiber_section_segments=section_payload["fiber_section_segments"],
        )

    @staticmethod
    def collect_lateral(payload: Dict) -> LateralInput:
        total_length, embedded_length, derived_free_length, _ = ParameterCollector._derive_single_pile_geometry(payload)
        section_payload = ParameterCollector._collect_section_payload(payload)
        mesh_positions = build_mesh_positions(total_length, payload.get("mesh_settings"))
        layers: List[AxialLayer] = []
        for row in payload.get("layers", []):
            layers.append(
                AxialLayer(
                    z_top=float(row["z_top"]),
                    z_bottom=float(row["z_bottom"]),
                    soil_type=str(row["soil_type"]),
                    params=dict(row["params"]),
                )
            )

        d = float(payload["pile_diameter_m"])
        shape = str(payload.get("pile_shape", "Circle"))
        t = float(payload.get("pile_thickness_m", 0.0))

        area = payload.get("pile_A_m2")
        inertia = payload.get("pile_I_m4")
        if area is None or inertia is None:
            if shape == "Pipe":
                di = max(d - 2.0 * t, 0.0)
                area_calc = math.pi * (d * d - di * di) / 4.0
                i_calc = math.pi * (d**4 - di**4) / 64.0
            else:
                area_calc = math.pi * d * d / 4.0
                i_calc = math.pi * d**4 / 64.0
            if area is None:
                area = area_calc
            if inertia is None:
                inertia = i_calc

        control_mode = str(payload.get("control_mode", "Load Control"))
        lateral_disp = payload.get("lateral_disp_m")
        if control_mode == "Displacement Control":
            lateral_disp = 0.0 if lateral_disp is None else float(lateral_disp)
        else:
            lateral_disp = None

        loads = {}
        for key in ("Fx", "Fy", "Fz", "Mx", "My", "Mz"):
            loads[key] = {"value": 0.0, "z_m": 0.0}
        load_cases = payload.get("load_cases", [])
        if isinstance(load_cases, list) and load_cases:
            fx_total = fy_total = mx_total = my_total = 0.0
            for row in load_cases:
                if not isinstance(row, dict):
                    continue
                z_m = float(row.get("depth_m", row.get("z_m", 0.0)))
                fx = float(row.get("Fx", 0.0))
                fy = float(row.get("Fy", 0.0))
                mx = float(row.get("Mx", 0.0))
                my = float(row.get("My", 0.0))
                fx_total += fx
                fy_total += fy
                mx_total += mx + fy * z_m
                my_total += my - fx * z_m
            loads["Fx"] = {"value": fx_total, "z_m": 0.0}
            loads["Fy"] = {"value": fy_total, "z_m": 0.0}
            loads["Mx"] = {"value": mx_total, "z_m": 0.0}
            loads["My"] = {"value": my_total, "z_m": 0.0}
        elif isinstance(payload.get("loads"), list):
            for row in payload.get("loads", []):
                if not isinstance(row, dict):
                    continue
                load_type = str(row.get("type", "")).strip()
                if load_type in loads:
                    loads[load_type] = {
                        "value": float(row.get("value", 0.0)),
                        "z_m": float(row.get("depth_m", row.get("z_m", 0.0))),
                    }
        else:
            loads["Fx"] = {"value": float(payload.get("lateral_load_kN", payload.get("load", {}).get("lateral_kN", 0.0))), "z_m": float(payload.get("shear_depth_m", 0.0))}
            loads["My"] = {"value": float(payload.get("moment_load_kN_m", payload.get("load", {}).get("moment_kN_m", 0.0))), "z_m": float(payload.get("moment_depth_m", 0.0))}

        lateral_load = float(loads["Fx"]["value"])
        moment_load = float(loads["My"]["value"])

        ele_size = payload.get("ele_size_m")
        return LateralInput(
            pile_length_m=embedded_length,
            pile_diameter_m=d,
            pile_E_kPa=float(payload["pile_E_kPa"]),
            pile_A_m2=float(area),
            pile_I_m4=float(inertia),
            ele_size_m=(None if ele_size in (None, 0, 0.0) else float(ele_size)),
            mesh_positions_m=mesh_positions,
            free_length_m=derived_free_length,
            layers=layers,
            loads=loads,
            control_mode=control_mode,
            lateral_load_kN=lateral_load,
            lateral_disp_m=lateral_disp,
            moment_load_kN_m=moment_load,
            steps=int(payload.get("steps", 50)),
            section_mode=section_payload["section_mode"],
            fiber_section_library=section_payload["fiber_section_library"],
            fiber_section_segments=section_payload["fiber_section_segments"],
        )

    @staticmethod
    def collect_combined(payload: Dict) -> CombinedInput:
        total_length, embedded_length, derived_free_length, _ = ParameterCollector._derive_single_pile_geometry(payload)
        section_payload = ParameterCollector._collect_section_payload(payload)
        bottom_section_area = ParameterCollector._resolve_bottom_section_area(
            section_payload["section_mode"],
            section_payload["fiber_section_library"],
            section_payload["fiber_section_segments"],
            total_length,
        )
        mesh_positions = build_mesh_positions(total_length, payload.get("mesh_settings"))
        axial_layers: List[CombinedAxialLayer] = []
        lateral_layers: List[CombinedLateralLayer] = []
        material_map = {
            str(mat.get("name", "")): dict(mat)
            for mat in payload.get("materials", [])
            if isinstance(mat, dict)
        }
        for row in payload.get("layers", []):
            row_material = material_map.get(str(row.get("material_name", "")), {})
            axial = dict(row.get("axial", {}))
            lateral = dict(row.get("lateral", {}))
            if not axial and row_material:
                axial = {
                    "soil_type": row_material.get("axial_type", "API Sand"),
                    "params": dict(row_material.get("axial_params", {})),
                }
            if not lateral and row_material:
                lateral = {
                    "soil_type": row_material.get("lateral_type", "Sand"),
                    "params": dict(row_material.get("lateral_params", {})),
                }
            z_top_raw = float(row["z_top"])
            z_bottom_raw = float(row["z_bottom"])
            z_top = min(abs(z_top_raw), abs(z_bottom_raw))
            z_bottom = max(abs(z_top_raw), abs(z_bottom_raw))
            axial_layers.append(
                CombinedAxialLayer(
                    z_top=z_top,
                    z_bottom=z_bottom,
                    soil_type=str(axial.get("soil_type", "API Sand")),
                    params=dict(axial.get("params", {})),
                )
            )
            lateral_layers.append(
                CombinedLateralLayer(
                    z_top=z_top,
                    z_bottom=z_bottom,
                    soil_type=str(lateral.get("soil_type", "Sand")),
                    params=dict(lateral.get("params", {})),
                )
            )

        d = float(payload["pile_diameter_m"])
        shape = str(payload.get("pile_shape", "Circle"))
        t = float(payload.get("pile_thickness_m", 0.0))
        area = payload.get("pile_A_m2")
        inertia = payload.get("pile_I_m4")
        if area is None or inertia is None:
            if shape == "Pipe":
                di = max(d - 2.0 * t, 0.0)
                area_calc = math.pi * (d * d - di * di) / 4.0
                i_calc = math.pi * (d**4 - di**4) / 64.0
            else:
                area_calc = math.pi * d * d / 4.0
                i_calc = math.pi * d**4 / 64.0
            if area is None:
                area = area_calc
            if inertia is None:
                inertia = i_calc

        loads = payload.get("loads", [])
        load_map = {key: {"value": 0.0, "depth_m": 0.0} for key in ("Fx", "Fy", "Fz", "Mx", "My", "Mz")}
        load_cases = payload.get("load_cases", [])
        if isinstance(load_cases, list) and load_cases:
            fx = fy = fz = mx = my = mz = 0.0
            for row in load_cases:
                if not isinstance(row, dict):
                    continue
                z_m = float(row.get("depth_m", row.get("z_m", 0.0)))
                fx_i = float(row.get("Fx", 0.0))
                fy_i = float(row.get("Fy", 0.0))
                fz_i = float(row.get("Fz", 0.0))
                mx_i = float(row.get("Mx", 0.0))
                my_i = float(row.get("My", 0.0))
                mz_i = float(row.get("Mz", 0.0))
                fx += fx_i
                fy += fy_i
                fz += fz_i
                mx += mx_i + fy_i * z_m
                my += my_i - fx_i * z_m
                mz += mz_i
            load_map["Fx"] = {"value": fx, "depth_m": 0.0}
            load_map["Fy"] = {"value": fy, "depth_m": 0.0}
            load_map["Fz"] = {"value": fz, "depth_m": 0.0}
            load_map["Mx"] = {"value": mx, "depth_m": 0.0}
            load_map["My"] = {"value": my, "depth_m": 0.0}
            load_map["Mz"] = {"value": mz, "depth_m": 0.0}
        elif isinstance(loads, list):
            for row in loads:
                if not isinstance(row, dict):
                    continue
                load_type = str(row.get("type", ""))
                if load_type in load_map:
                    load_map[load_type] = {
                        "value": float(row.get("value", 0.0)),
                        "depth_m": float(row.get("depth_m", row.get("z_m", 0.0))),
                    }
        else:
            load_map["Fz"] = {"value": float(payload.get("axial_force_kN", 0.0)), "depth_m": float(payload.get("axial_depth_m", 0.0))}
            load_map["Fx"] = {"value": float(payload.get("shear_force_kN", 0.0)), "depth_m": float(payload.get("shear_depth_m", 0.0))}
            load_map["My"] = {"value": float(payload.get("moment_kN_m", 0.0)), "depth_m": float(payload.get("moment_depth_m", 0.0))}

        fx = float(load_map["Fx"]["value"])
        fy = float(load_map["Fy"]["value"])
        fz = float(load_map["Fz"]["value"])
        mx = float(load_map["Mx"]["value"]) + fy * float(load_map["Fy"]["depth_m"])
        my = float(load_map["My"]["value"]) - fx * float(load_map["Fx"]["depth_m"])
        mz = float(load_map["Mz"]["value"])

        pile_length = total_length
        tip_depth = embedded_length
        tip_layer = None
        for row in payload.get("layers", []):
            top = abs(float(row.get("z_top", 0.0)))
            bottom = abs(float(row.get("z_bottom", 0.0)))
            upper = max(top, bottom)
            lower = min(top, bottom)
            if lower <= tip_depth <= upper:
                tip_layer = row
                break
        if tip_layer is None and payload.get("layers"):
            tip_layer = payload["layers"][-1]
        tip_material = material_map.get(str((tip_layer or {}).get("material_name", "")), {})
        tip_axial = dict((tip_layer or {}).get("axial", {}))
        if not tip_axial and tip_material:
            tip_axial = {
                "soil_type": tip_material.get("axial_type", "API Sand"),
                "params": dict(tip_material.get("axial_params", {})),
            }

        ele_size = payload.get("ele_size_m")
        tip_params = dict(tip_axial.get("params", {}))
        if bottom_section_area is not None:
            tip_params["A_base"] = bottom_section_area
            tip_params["A_tip"] = bottom_section_area
        return CombinedInput(
            pile_length_m=embedded_length,
            pile_diameter_m=d,
            pile_shape=shape,
            pile_thickness_m=t,
            pile_E_kPa=float(payload["pile_E_kPa"]),
            pile_A_m2=float(area),
            pile_I_m4=float(inertia),
            ele_size_m=(None if ele_size in (None, 0, 0.0) else float(ele_size)),
            mesh_positions_m=mesh_positions,
            free_length_m=derived_free_length,
            axial_layers=axial_layers,
            lateral_layers=lateral_layers,
            tip_type=str(tip_axial.get("soil_type", "API Sand")),
            tip_params=tip_params,
            loads=load_map,
            fx_kN=fx,
            fy_kN=fy,
            fz_kN=fz,
            mx_kN_m=mx,
            my_kN_m=my,
            mz_kN_m=mz,
            axial_force_kN=fz,
            shear_force_kN=fx,
            moment_kN_m=my,
            axial_depth_m=float(load_map.get("Fz", {}).get("depth_m", 0.0)),
            shear_depth_m=float(load_map.get("Fx", {}).get("depth_m", 0.0)),
            moment_depth_m=float(load_map.get("My", {}).get("depth_m", 0.0)),
            steps=int(payload.get("steps", 40)),
            section_mode=section_payload["section_mode"],
            fiber_section_library=section_payload["fiber_section_library"],
            fiber_section_segments=section_payload["fiber_section_segments"],
        )

    @staticmethod
    def collect_group(payload: Dict) -> GroupInput:
        return GroupInput(payload=dict(payload))
