# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from openpyxl import Workbook

from core.mesh_spec import build_mesh_positions


def _load_solver(module_name: str, class_name: str):
    core_dir = str(Path(__file__).resolve().parent)
    if core_dir not in sys.path:
        sys.path.insert(0, core_dir)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def export_spring_parameters(mode_key: str, payload: Dict, results: Dict, file_path: str):
    sheets = build_spring_export(mode_key, payload, results)
    if not sheets:
        raise ValueError("No spring parameter data is available for export.")

    wb = Workbook()
    first = True
    for sheet_name, rows in sheets.items():
        ws = wb.active if first else wb.create_sheet(title=sheet_name[:31])
        first = False
        ws.title = sheet_name[:31]
        if rows:
            headers = list(rows[0].keys())
            ws.append(headers)
            for row in rows:
                ws.append([row.get(key, "") for key in headers])
        else:
            ws.append(["No data"])
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(file_path)


def build_spring_export(mode_key: str, payload: Dict, results: Dict) -> Dict[str, List[Dict]]:
    mode = str(mode_key or "").lower()
    if mode == "axial":
        return _build_axial_export(payload)
    if mode == "lateral":
        return _build_lateral_export(payload)
    if mode == "combined":
        return _build_combined_export(payload)
    if mode == "group":
        return _build_group_export(payload)
    return {}


def _build_axial_export(payload: Dict) -> Dict[str, List[Dict]]:
    AxialPileSolver = _load_solver("axial_solver", "AxialPileSolver")
    top_z = float(payload.get("pile_top_z_m", 0.0))
    bottom_z = float(payload.get("pile_bottom_z_m", 0.0))
    total_length = abs(top_z - bottom_z)
    mesh_positions = build_mesh_positions(total_length, payload.get("mesh_settings"))
    nodes = _single_pile_nodes(top_z, bottom_z, mesh_positions)

    solver = AxialPileSolver(
        pile_length=float(payload.get("pile_length_m", total_length)),
        pile_diameter=float(payload.get("pile_diameter_m", 1.0)),
        E_pile=float(payload.get("pile_E_kPa", 3.0e7)),
        A_pile=float(payload.get("pile_A_m2", 1.0)),
        ele_size=float(payload.get("ele_size_m", 0.1)),
        mesh_positions=mesh_positions,
        section_mode=str(payload.get("section_mode", "elastic")),
        fiber_section_library=list(payload.get("fiber_section_library", []) or []),
        fiber_section_segments=list(payload.get("fiber_section_segments", []) or []),
    )
    for layer in payload.get("layers", []):
        solver.add_soil_layer(
            float(layer.get("z_top", 0.0)),
            float(layer.get("z_bottom", 0.0)),
            str(layer.get("soil_type", "")),
            **dict(layer.get("params", {})),
        )
    solver.set_tip_soil(str(payload.get("tip_type", "")), **dict(payload.get("tip_params", {})))
    solver._precompute_sigma_v_array()

    tz_rows = []
    for idx, (s_i, s_j) in enumerate(_segment_pairs(mesh_positions), start=1):
        depth = 0.5 * (float(s_i) + float(s_j))
        i_x_m, i_y_m, i_z_m = _point_on_single_pile(top_z, bottom_z, float(s_i))
        j_x_m, j_y_m, j_z_m = _point_on_single_pile(top_z, bottom_z, float(s_j))
        tult, z50 = solver._get_tz_params(float(depth), seg_idx=idx - 1)
        tz_rows.append(
            {
                "pile_id": 1,
                "spring_id": idx,
                "i_node_id": idx,
                "j_node_id": idx + 1,
                "i_x_m": i_x_m,
                "i_y_m": i_y_m,
                "i_z_m": i_z_m,
                "j_x_m": j_x_m,
                "j_y_m": j_y_m,
                "j_z_m": j_z_m,
                "segment_top_from_head_m": float(s_i),
                "segment_bottom_from_head_m": float(s_j),
                "segment_mid_from_head_m": float(depth),
                "tult_kN": float(tult),
                "z50_m": _safe_number(z50),
            }
        )

    qult, q50 = solver._get_qz_params()
    qz_rows = [
        {
            "pile_id": 1,
            "spring_id": 1,
            "i_node_id": "soil_tip",
            "j_node_id": len(mesh_positions),
            "i_x_m": 0.0,
            "i_y_m": 0.0,
            "i_z_m": bottom_z,
            "j_x_m": 0.0,
            "j_y_m": 0.0,
            "j_z_m": bottom_z,
            "segment_top_from_head_m": total_length,
            "segment_bottom_from_head_m": total_length,
            "segment_mid_from_head_m": total_length,
            "qult_kN": float(qult),
            "z50_m": _safe_number(q50),
        }
    ]
    return {"nodes": nodes, "tz": tz_rows, "qz": qz_rows}


def _build_lateral_export(payload: Dict) -> Dict[str, List[Dict]]:
    LateralPileSolver = _load_solver("lateral_solver", "LateralPileSolver")
    top_z = float(payload.get("pile_top_z_m", 0.0))
    bottom_z = float(payload.get("pile_bottom_z_m", 0.0))
    total_length = abs(top_z - bottom_z)
    free_length = max(top_z, 0.0)
    mesh_positions = build_mesh_positions(total_length, payload.get("mesh_settings"))
    nodes = _single_pile_nodes(top_z, bottom_z, mesh_positions)

    solver = LateralPileSolver(
        pile_length=float(payload.get("pile_length_m", total_length)),
        pile_diameter=float(payload.get("pile_diameter_m", 1.0)),
        E_pile=float(payload.get("pile_E_kPa", 3.0e7)),
        I_pile=float(payload.get("pile_I_m4", 1.0)),
        A_pile=float(payload.get("pile_A_m2", 1.0)),
        ele_size=float(payload.get("ele_size_m", 0.1)),
        free_length=free_length,
        mesh_positions=mesh_positions,
        section_mode=str(payload.get("section_mode", "elastic")),
        fiber_section_library=list(payload.get("fiber_section_library", []) or []),
        fiber_section_segments=list(payload.get("fiber_section_segments", []) or []),
    )
    for layer in payload.get("layers", []):
        solver.add_soil_layer(
            float(layer.get("z_top", 0.0)),
            float(layer.get("z_bottom", 0.0)),
            str(layer.get("soil_type", "")),
            **dict(layer.get("params", {})),
        )
    try:
        solver._calc_georgiadis_depths()
    except Exception:
        pass

    py_rows = []
    for idx, (s_i, s_j) in enumerate(_segment_pairs(mesh_positions), start=1):
        s_mid = 0.5 * (float(s_i) + float(s_j))
        z_depth = s_mid - free_length
        if z_depth < 0.0:
            continue
        i_x_m, i_y_m, i_z_m = _point_on_single_pile(top_z, bottom_z, float(s_i))
        j_x_m, j_y_m, j_z_m = _point_on_single_pile(top_z, bottom_z, float(s_j))
        pult, y50 = solver._get_py_params(z_depth)
        py_rows.append(
            {
                "pile_id": 1,
                "spring_id": idx,
                "i_node_id": idx,
                "j_node_id": idx + 1,
                "i_x_m": i_x_m,
                "i_y_m": i_y_m,
                "i_z_m": i_z_m,
                "j_x_m": j_x_m,
                "j_y_m": j_y_m,
                "j_z_m": j_z_m,
                "segment_top_from_head_m": float(s_i),
                "segment_bottom_from_head_m": float(s_j),
                "segment_mid_from_head_m": float(s_mid),
                "embedded_depth_m": float(z_depth),
                "pult_kN_per_m": float(pult),
                "y50_m": _safe_number(y50),
                "pile_unit_weight_kN_m3": 25.0,
            }
        )
    return {"nodes": nodes, "py": py_rows}


def _build_combined_export(payload: Dict) -> Dict[str, List[Dict]]:
    MonolithicGroupPileSolver = _load_solver("monolithic_group_solver", "MonolithicGroupPileSolver")
    top_z = float(payload.get("pile_top_z_m", 0.0))
    bottom_z = float(payload.get("pile_bottom_z_m", 0.0))
    total_length = abs(top_z - bottom_z)
    free_length = max(top_z, 0.0)
    mesh_positions = build_mesh_positions(total_length, payload.get("mesh_settings"))
    nodes = _single_pile_nodes(top_z, bottom_z, mesh_positions)

    solver = MonolithicGroupPileSolver(ele_size=float(payload.get("ele_size_m", 0.1)))
    for layer in payload.get("lateral_layers", []):
        solver.add_lateral_soil_layer(
            float(layer.get("z_top", 0.0)),
            float(layer.get("z_bottom", 0.0)),
            str(layer.get("soil_type", "")),
            **dict(layer.get("params", {})),
        )
    for layer in payload.get("axial_layers", []):
        solver.add_axial_soil_layer(
            float(layer.get("z_top", 0.0)),
            float(layer.get("z_bottom", 0.0)),
            str(layer.get("soil_type", "")),
            **dict(layer.get("params", {})),
        )
    solver.set_tip_soil(str(payload.get("tip_type", "")), **dict(payload.get("tip_params", {})))

    diameter = float(payload.get("pile_diameter_m", 1.0))
    py_rows = []
    tz_rows = []
    for idx, (s_i, s_j) in enumerate(_segment_pairs(mesh_positions), start=1):
        s_mid = 0.5 * (float(s_i) + float(s_j))
        z_depth = s_mid - free_length
        i_x_m, i_y_m, i_z_m = _point_on_single_pile(top_z, bottom_z, float(s_i))
        j_x_m, j_y_m, j_z_m = _point_on_single_pile(top_z, bottom_z, float(s_j))
        if z_depth >= 0.0:
            (pult, y50), _, _ = solver._get_py_at_depth(z_depth, diameter)
            py_rows.append(
                {
                    "pile_id": 1,
                    "spring_id": idx,
                    "i_node_id": idx,
                    "j_node_id": idx + 1,
                    "i_x_m": i_x_m,
                    "i_y_m": i_y_m,
                    "i_z_m": i_z_m,
                    "j_x_m": j_x_m,
                    "j_y_m": j_y_m,
                    "j_z_m": j_z_m,
                    "segment_top_from_head_m": float(s_i),
                    "segment_bottom_from_head_m": float(s_j),
                    "segment_mid_from_head_m": float(s_mid),
                    "embedded_depth_m": float(z_depth),
                    "pult_kN_per_m": float(pult),
                    "y50_m": _safe_number(y50),
                    "pile_unit_weight_kN_m3": 25.0,
                }
            )
            tult, z50 = solver._get_tz_params(z_depth, diameter, float(s_j) - float(s_i))
            tz_rows.append(
                {
                    "pile_id": 1,
                    "spring_id": idx,
                    "i_node_id": idx,
                    "j_node_id": idx + 1,
                    "i_x_m": i_x_m,
                    "i_y_m": i_y_m,
                    "i_z_m": i_z_m,
                    "j_x_m": j_x_m,
                    "j_y_m": j_y_m,
                    "j_z_m": j_z_m,
                    "segment_top_from_head_m": float(s_i),
                    "segment_bottom_from_head_m": float(s_j),
                    "segment_mid_from_head_m": float(s_mid),
                    "embedded_depth_m": float(z_depth),
                    "tult_kN": float(tult),
                    "z50_m": _safe_number(z50),
                }
            )

    qult, q50 = solver._get_qz_params(diameter, total_length)
    qz_rows = [
        {
            "pile_id": 1,
            "spring_id": 1,
            "i_node_id": "soil_tip",
            "j_node_id": len(mesh_positions),
            "i_x_m": 0.0,
            "i_y_m": 0.0,
            "i_z_m": bottom_z,
            "j_x_m": 0.0,
            "j_y_m": 0.0,
            "j_z_m": bottom_z,
            "segment_top_from_head_m": total_length,
            "segment_bottom_from_head_m": total_length,
            "segment_mid_from_head_m": total_length,
            "qult_kN": float(qult),
            "z50_m": _safe_number(q50),
        }
    ]
    return {"nodes": nodes, "py": py_rows, "tz": tz_rows, "qz": qz_rows}


def _build_group_export(payload: Dict) -> Dict[str, List[Dict]]:
    MonolithicGroupPileSolver = _load_solver("monolithic_group_solver", "MonolithicGroupPileSolver")
    materials = {
        str(item.get("name", "")): dict(item)
        for item in payload.get("materials", [])
        if isinstance(item, dict)
    }
    pile_types = {
        str(item.get("name", "")): dict(item)
        for item in payload.get("pile_types", [])
        if isinstance(item, dict)
    }

    solver = MonolithicGroupPileSolver(ele_size=float(payload.get("ele_size_m", 0.1)))
    for layer in payload.get("layers", []):
        if not isinstance(layer, dict):
            continue
        material = materials.get(str(layer.get("material_name", "")), {})
        z_top = min(float(layer.get("z_top", 0.0)), float(layer.get("z_bottom", 0.0)))
        z_bottom = max(float(layer.get("z_top", 0.0)), float(layer.get("z_bottom", 0.0)))
        solver.add_lateral_soil_layer(
            z_top,
            z_bottom,
            str(material.get("lateral_type", "Sand")),
            **dict(material.get("lateral_params", {})),
        )
        solver.add_axial_soil_layer(
            z_top,
            z_bottom,
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

    nodes_rows: List[Dict] = []
    py_rows: List[Dict] = []
    tz_rows: List[Dict] = []
    qz_rows: List[Dict] = []

    for pile_id, row in enumerate(payload.get("pile_layout", []), start=1):
        if not isinstance(row, dict):
            continue
        pile_type = pile_types.get(str(row.get("pile_type_name", "")), {})
        top_z = float(row.get("top_z_m", pile_type.get("pile_top_z_m", 0.0)))
        bottom_z = float(row.get("bottom_z_m", pile_type.get("pile_bottom_z_m", -1.0)))
        total_length = abs(top_z - bottom_z)
        free_length = max(top_z, 0.0)
        mesh_key = f"Pile {pile_id}"
        mesh_settings = dict((payload.get("mesh_settings_by_pile") or {}).get(mesh_key, payload.get("mesh_settings", {})) or {})
        mesh_positions = build_mesh_positions(total_length, mesh_settings)
        x0 = float(row.get("x_m", 0.0))
        y0 = float(row.get("y_m", 0.0))
        diameter = float(pile_type.get("pile_diameter_m", 1.0))

        for node_id, s in enumerate(mesh_positions, start=1):
            _, _, z_m = _point_on_single_pile(top_z, bottom_z, float(s))
            nodes_rows.append(
                {
                    "pile_id": pile_id,
                    "node_id": node_id,
                    "x_m": x0,
                    "y_m": y0,
                    "z_m": z_m,
                    "depth_from_head_m": float(s),
                }
            )
        for spring_id, (s_i, s_j) in enumerate(_segment_pairs(mesh_positions), start=1):
            s_mid = 0.5 * (float(s_i) + float(s_j))
            z_depth = s_mid - free_length
            if z_depth < 0.0:
                continue
            i_x_m, i_y_m, i_z_m = _point_on_single_pile(top_z, bottom_z, float(s_i))
            j_x_m, j_y_m, j_z_m = _point_on_single_pile(top_z, bottom_z, float(s_j))
            (pult, y50), _, _ = solver._get_py_at_depth(z_depth, diameter)
            py_rows.append(
                {
                    "pile_id": pile_id,
                    "spring_id": spring_id,
                    "i_node_id": spring_id,
                    "j_node_id": spring_id + 1,
                    "i_x_m": x0 + i_x_m,
                    "i_y_m": y0 + i_y_m,
                    "i_z_m": i_z_m,
                    "j_x_m": x0 + j_x_m,
                    "j_y_m": y0 + j_y_m,
                    "j_z_m": j_z_m,
                    "segment_top_from_head_m": float(s_i),
                    "segment_bottom_from_head_m": float(s_j),
                    "segment_mid_from_head_m": float(s_mid),
                    "embedded_depth_m": float(z_depth),
                    "pult_kN_per_m": float(pult),
                    "y50_m": _safe_number(y50),
                    "pile_unit_weight_kN_m3": 25.0,
                }
            )
            tult, z50 = solver._get_tz_params(z_depth, diameter, float(s_j) - float(s_i))
            tz_rows.append(
                {
                    "pile_id": pile_id,
                    "spring_id": spring_id,
                    "i_node_id": spring_id,
                    "j_node_id": spring_id + 1,
                    "i_x_m": x0 + i_x_m,
                    "i_y_m": y0 + i_y_m,
                    "i_z_m": i_z_m,
                    "j_x_m": x0 + j_x_m,
                    "j_y_m": y0 + j_y_m,
                    "j_z_m": j_z_m,
                    "segment_top_from_head_m": float(s_i),
                    "segment_bottom_from_head_m": float(s_j),
                    "segment_mid_from_head_m": float(s_mid),
                    "embedded_depth_m": float(z_depth),
                    "tult_kN": float(tult),
                    "z50_m": _safe_number(z50),
                }
            )

        qult, q50 = solver._get_qz_params(diameter, total_length)
        qz_rows.append(
            {
                "pile_id": pile_id,
                "spring_id": 1,
                "i_node_id": "soil_tip",
                "j_node_id": len(mesh_positions),
                "i_x_m": x0,
                "i_y_m": y0,
                "i_z_m": bottom_z,
                "j_x_m": x0,
                "j_y_m": y0,
                "j_z_m": bottom_z,
                "segment_top_from_head_m": total_length,
                "segment_bottom_from_head_m": total_length,
                "segment_mid_from_head_m": total_length,
                "qult_kN": float(qult),
                "z50_m": _safe_number(q50),
            }
        )

    return {"nodes": nodes_rows, "py": py_rows, "tz": tz_rows, "qz": qz_rows}


def _single_pile_nodes(top_z: float, bottom_z: float, mesh_positions: Iterable[float]) -> List[Dict]:
    rows = []
    for node_id, s in enumerate(mesh_positions, start=1):
        x_m, y_m, z_m = _point_on_single_pile(top_z, bottom_z, float(s))
        rows.append(
            {
                "pile_id": 1,
                "node_id": node_id,
                "x_m": x_m,
                "y_m": y_m,
                "z_m": z_m,
                "depth_from_head_m": float(s),
            }
        )
    return rows


def _point_on_single_pile(top_z: float, bottom_z: float, arc_length: float) -> Tuple[float, float, float]:
    total_length = max(abs(top_z - bottom_z), 1.0e-9)
    ratio = min(max(float(arc_length) / total_length, 0.0), 1.0)
    z_m = top_z + (bottom_z - top_z) * ratio
    return 0.0, 0.0, float(z_m)


def _tributary_lengths(mesh_positions: Iterable[float]) -> List[float]:
    pts = [float(v) for v in mesh_positions]
    n = len(pts)
    if n <= 1:
        return [0.0]
    trib = [0.0] * n
    trib[0] = 0.5 * (pts[1] - pts[0])
    trib[-1] = 0.5 * (pts[-1] - pts[-2])
    for i in range(1, n - 1):
        trib[i] = 0.5 * (pts[i + 1] - pts[i - 1])
    return trib


def _safe_number(value):
    return "" if value is None else float(value)


def _segment_pairs(mesh_positions: Iterable[float]) -> List[Tuple[float, float]]:
    pts = [float(v) for v in mesh_positions]
    return [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
