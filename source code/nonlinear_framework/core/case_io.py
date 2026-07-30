# -*- coding: utf-8 -*-

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from core.mesh_spec import default_mesh_settings

CASE_SCHEMA_VERSION = "2.0"
CASE_UNITS = "m-kN-kPa"

AXIAL_FIELDS = {
    "API Sand": [("UNIT_WEIGHT", "gammaEff"), ("FRICTION_ANGLE", "phiDegree"), ("K", "K"), ("NQ", "Nq"), ("MAX_UNIT_SKIN_FRICTION", "max_unit_skin_friction"), ("MAX_UNIT_END_BEARING_RESISTANCE", "max_unit_end_bearing")],
    "API Clay": [("UNIT_WEIGHT", "gammaEff"), ("UNDRAINED_SHEAR_STRENGTH", "cu"), ("REMOLDED_SHEAR_STRENGTH", "cu_remolded"), ("MAX_UNIT_SKIN_FRICTION", "max_unit_skin_friction"), ("MAX_UNIT_END_BEARING_RESISTANCE", "max_unit_end_bearing")],
    "Drilled Sand": [("UNIT_WEIGHT", "gammaEff"), ("ULTIMATE_SHEAR_RESISTANCE", "max_unit_skin_friction"), ("ULTIMATE_END_BEARING_RESISTANCE", "max_unit_end_bearing")],
    "Drilled Clay": [("UNIT_WEIGHT", "gammaEff"), ("ULTIMATE_SHEAR_RESISTANCE", "max_unit_skin_friction"), ("ULTIMATE_END_BEARING_RESISTANCE", "max_unit_end_bearing")],
    "Elastic": [("KS", "ks"), ("KB", "kb")],
}

LATERAL_FIELDS = {
    "API Method for Sand": [("UNIT_WEIGHT", "gammaEff"), ("FRICTION_ANGLE", "phiDegree"), ("INITIAL_MODULUS_OF_SUBGRADE_REACTION", "k_modulus")],
    "Sand": [("UNIT_WEIGHT", "gammaEff"), ("FRICTION_ANGLE", "phiDegree"), ("KPY", "kpy")],
    "Soft Clay Soil": [("UNIT_WEIGHT", "gammaEff"), ("UNDRAINED_SHEAR_STRENGTH", "cu"), ("STRAIN_FACTOR", "eps50")],
    "Submerged Stiff Clay": [("UNIT_WEIGHT", "gammaEff"), ("UNDRAINED_SHEAR_STRENGTH", "cu"), ("STRAIN_FACTOR", "eps50"), ("KS", "k_modulus")],
    "Dry Stiff Clay": [("UNIT_WEIGHT", "gammaEff"), ("UNDRAINED_SHEAR_STRENGTH", "cu"), ("STRAIN_FACTOR", "eps50")],
    "Modified Stiff Clay without Free Water": [("UNIT_WEIGHT", "gammaEff"), ("UNDRAINED_SHEAR_STRENGTH", "cu"), ("STRAIN_FACTOR", "eps50"), ("INITIAL_STIFFNESS", "k_modulus")],
    "Weak Rock": [("UNIT_WEIGHT", "gammaEff"), ("UNIAXIAL_COMPRESSIVE_STRENGTH", "qu"), ("REACTION_MODULUS_OF_ROCK", "Eir"), ("RQD", "RQD"), ("KRM", "krm")],
    "Elastic": [("KH", "kh")],
}

AXIAL_ALIASES = {
    "UNIT_WEIGHT": "gammaEff", "FRICTION_ANGLE": "phiDegree", "K": "K", "NQ": "Nq",
    "MAX_UNIT_SKIN_FRICTION": "max_unit_skin_friction", "MAX_UNIT_END_BEARING_RESISTANCE": "max_unit_end_bearing",
    "ULTIMATE_SHEAR_RESISTANCE": "max_unit_skin_friction", "ULTIMATE_END_BEARING_RESISTANCE": "max_unit_end_bearing",
    "UNDRAINED_SHEAR_STRENGTH": "cu", "REMOLDED_SHEAR_STRENGTH": "cu_remolded", "KS": "ks", "KB": "kb",
}
LATERAL_ALIASES = {
    "UNIT_WEIGHT": "gammaEff", "FRICTION_ANGLE": "phiDegree", "INITIAL_MODULUS_OF_SUBGRADE_REACTION": "k_modulus",
    "KS": "k_modulus", "INITIAL_STIFFNESS": "k_modulus", "KPY": "kpy", "UNDRAINED_SHEAR_STRENGTH": "cu",
    "STRAIN_FACTOR": "eps50", "J": "J", "CA": "ca", "UNIAXIAL_COMPRESSIVE_STRENGTH": "qu",
    "REACTION_MODULUS_OF_ROCK": "Eir", "RQD": "RQD", "KRM": "krm", "KH": "kh",
}


def default_case_document() -> Dict:
    return {
        "schema": CASE_SCHEMA_VERSION,
        "units": CASE_UNITS,
        "mode": "axial",
        "payloads": {
            "axial": {
                "pile_top_z_m": 0.0, "pile_bottom_z_m": -17.0, "pile_length_m": 17.0,
                "pile_diameter_m": 0.5, "pile_E_kPa": 2.0e8, "pile_shape": "Pipe", "pile_thickness_m": 0.02, "ele_size_m": 0.0, "mesh_settings": default_mesh_settings(), "section_mode": "elastic", "fiber_section_library": [], "fiber_section_segments": [],
                "soil_materials": [
                    {"name": "Material-1", "soil_type": "API Clay", "params": {"gammaEff": 17.0, "cu": 22.0, "cu_remolded": 15.0, "max_unit_skin_friction": 1.0e6, "max_unit_end_bearing": 1.0e6}, "bg_color": "#e8c7cf", "bg_alpha": 0.28},
                    {"name": "Material-2", "soil_type": "API Sand", "params": {"gammaEff": 20.0, "phiDegree": 35.0, "K": 1.0, "Nq": 40.0, "max_unit_skin_friction": 1.0e6, "max_unit_end_bearing": 1.0e6}, "bg_color": "#f7e7a8", "bg_alpha": 0.28},
                ],
                "layers": [
                    {"z_top": 0.0, "z_bottom": 10.0, "material_name": "Material-1", "soil_type": "API Clay"},
                    {"z_top": 10.0, "z_bottom": 20.0, "material_name": "Material-2", "soil_type": "API Sand"},
                ],
                "control_mode": "Load Control", "axial_load_kN": -100.0, "load_z_m": 0.0, "axial_disp_m": 0.0, "steps": 20,
            },
            "lateral": {
                "pile_top_z_m": 0.0, "pile_bottom_z_m": -19.0, "pile_length_m": 19.0,
                "pile_diameter_m": 0.5, "pile_E_kPa": 2.0e8, "pile_shape": "Pipe", "pile_thickness_m": 0.02, "ele_size_m": 0.0, "mesh_settings": default_mesh_settings(), "section_mode": "elastic", "fiber_section_library": [], "fiber_section_segments": [],
                "soil_materials": [
                    {"name": "SoftClay-1", "soil_type": "Soft Clay Soil", "params": {"gammaEff": 20.0, "cu": 25.0, "eps50": 0.02}, "bg_color": "#e8c7cf", "bg_alpha": 0.28},
                    {"name": "Sand-1", "soil_type": "Sand", "params": {"gammaEff": 20.0, "phiDegree": 30.0, "kpy": 6800.0}, "bg_color": "#fde2b8", "bg_alpha": 0.28},
                ],
                "layers": [
                    {"z_top": 0.0, "z_bottom": 10.0, "material_name": "SoftClay-1", "soil_type": "Soft Clay Soil"},
                    {"z_top": 10.0, "z_bottom": 19.0, "material_name": "Sand-1", "soil_type": "Sand"},
                ],
                "loads": [
                    {"type": "Fx", "value": 50.0, "depth_m": 0.0, "depth_ui": 0.0},
                    {"type": "Fy", "value": 0.0, "depth_m": 0.0, "depth_ui": 0.0},
                    {"type": "Mx", "value": 0.0, "depth_m": 0.0, "depth_ui": 0.0},
                    {"type": "My", "value": 100.0, "depth_m": 0.0, "depth_ui": 0.0},
                ],
                "control_mode": "Load Control", "lateral_load_kN": 50.0, "lateral_disp_m": 0.0, "moment_load_kN_m": 100.0, "shear_depth_m": 0.0, "moment_depth_m": 0.0, "steps": 50,
            },
            "combined": {
                "pile_shape": "Pipe", "pile_top_z_m": 0.0, "pile_bottom_z_m": -19.0, "pile_length_m": 19.0,
                "pile_diameter_m": 0.5, "pile_thickness_m": 0.02, "pile_E_kPa": 2.0e8, "ele_size_m": 0.0, "mesh_settings": default_mesh_settings(), "section_mode": "elastic", "fiber_section_library": [], "fiber_section_segments": [],
                "materials": [
                    {"name": "Layer-1", "bg_color": "#e8c7cf", "axial_type": "API Clay", "axial_params": {"gammaEff": 18.0, "cu": 80.0, "cu_remolded": 20.0, "max_unit_skin_friction": 1.0e6, "max_unit_end_bearing": 1.0e6}, "lateral_type": "Soft Clay Soil", "lateral_params": {"gammaEff": 20.0, "cu": 25.0, "eps50": 0.02}},
                    {"name": "Layer-2", "bg_color": "#f7e7a8", "axial_type": "API Sand", "axial_params": {"gammaEff": 18.0, "phiDegree": 30.0, "K": 0.8, "Nq": 20.0, "max_unit_skin_friction": 1.0e6, "max_unit_end_bearing": 1.0e6}, "lateral_type": "Sand", "lateral_params": {"gammaEff": 20.0, "phiDegree": 30.0, "kpy": 6800.0}},
                ],
                "layers": [{"z_top": 0.0, "z_bottom": 10.0, "material_name": "Layer-1"}, {"z_top": 10.0, "z_bottom": 19.0, "material_name": "Layer-2"}],
                "loads": [
                    {"type": "Fx", "value": 50.0, "depth_m": 0.0, "depth_ui": 0.0},
                    {"type": "Fy", "value": 0.0, "depth_m": 0.0, "depth_ui": 0.0},
                    {"type": "Fz", "value": -100.0, "depth_m": 0.0, "depth_ui": 0.0},
                    {"type": "Mx", "value": 0.0, "depth_m": 0.0, "depth_ui": 0.0},
                    {"type": "My", "value": 100.0, "depth_m": 0.0, "depth_ui": 0.0},
                    {"type": "Mz", "value": 0.0, "depth_m": 0.0, "depth_ui": 0.0},
                ],
            },
            "group": {
                "materials": [
                    {"name": "Material-1", "bg_color": "#e8c7cf", "bg_alpha": 0.28, "axial_type": "API Clay", "axial_params": {"gammaEff": 18.0, "cu": 25.0, "cu_remolded": 20.0, "max_unit_skin_friction": 1.0e6, "max_unit_end_bearing": 1.0e6}, "lateral_type": "Soft Clay Soil", "lateral_params": {"gammaEff": 20.0, "cu": 25.0, "eps50": 0.02}},
                    {"name": "Material-2", "bg_color": "#fde2b8", "bg_alpha": 0.28, "axial_type": "API Sand", "axial_params": {"gammaEff": 18.0, "phiDegree": 30.0, "K": 1.0, "Nq": 40.0, "max_unit_skin_friction": 1.0e6, "max_unit_end_bearing": 1.0e6}, "lateral_type": "Sand", "lateral_params": {"gammaEff": 20.0, "phiDegree": 30.0, "kpy": 6800.0}},
                ],
                "layers": [{"z_top": 0.0, "z_bottom": -10.0, "material_name": "Material-1"}, {"z_top": -10.0, "z_bottom": -27.0, "material_name": "Material-2"}],
                "pile_types": [{"name": "PileType-1", "pile_shape": "Circle", "pile_top_z_m": 0.0, "pile_bottom_z_m": -27.0, "pile_length_m": 27.0, "pile_diameter_m": 1.0, "pile_thickness_m": 0.04, "pile_E_kPa": 3.0e7, "ele_size_m": 0.0, "section_mode": "elastic", "fiber_section_library": [], "fiber_section_segments": []}],
                "cap": {"shape": "Rectangular", "length_x_m": 6.0, "length_y_m": 6.0, "height_m": 1.0, "center_z_m": 0.5, "bottom_z_m": 0.0},
                "pile_layout": [
                    {"x_m": -1.5, "y_m": -1.5, "top_z_m": 0.0, "bottom_z_m": -27.0, "pile_type_name": "PileType-1", "connectivity": "fixed"},
                    {"x_m": 1.5, "y_m": -1.5, "top_z_m": 0.0, "bottom_z_m": -27.0, "pile_type_name": "PileType-1", "connectivity": "fixed"},
                    {"x_m": -1.5, "y_m": 1.5, "top_z_m": 0.0, "bottom_z_m": -27.0, "pile_type_name": "PileType-1", "connectivity": "fixed"},
                    {"x_m": 1.5, "y_m": 1.5, "top_z_m": 0.0, "bottom_z_m": -27.0, "pile_type_name": "PileType-1", "connectivity": "fixed"},
                ],
                "load_cases": [{"load_no": 1, "x_m": 0.0, "y_m": 0.0, "Fx": 0.0, "Fy": 0.0, "Fz": 0.0, "Mx": 0.0, "My": 0.0, "Mz": 0.0}],
                "loads": [{"load_no": 1, "x_m": 0.0, "y_m": 0.0, "Fx": 0.0, "Fy": 0.0, "Fz": 0.0, "Mx": 0.0, "My": 0.0, "Mz": 0.0}],
                "mesh_settings": default_mesh_settings(),
                "mesh_settings_by_pile": {},
                "p_multiplier_mode": "automatic",
                "p_multiplier_manual": 1.0,
                "coordinate_origin": "cap_center", "analysis_type": "static_group_3d", "active_models": ["py", "tz", "qz"], "steps": 40,
            },
        },
    }


def blank_case_document() -> Dict:
    return {
        "schema": CASE_SCHEMA_VERSION,
        "units": CASE_UNITS,
        "mode": "axial",
        "payloads": {
            "axial": {
                "pile_top_z_m": 0.0,
                "pile_bottom_z_m": 0.0,
                "pile_length_m": 0.0,
                "pile_diameter_m": 0.0,
                "pile_E_kPa": 0.0,
                "pile_shape": "Pipe",
                "pile_thickness_m": 0.0,
                "ele_size_m": 0.0,
                "mesh_settings": default_mesh_settings(),
                "section_mode": "elastic",
                "fiber_section_library": [],
                "fiber_section_segments": [],
                "soil_materials": [
                    {
                        "name": "Material-1",
                        "soil_type": "API Clay",
                        "params": {
                            "gammaEff": 0.0,
                            "cu": 0.0,
                            "cu_remolded": 0.0,
                            "max_unit_skin_friction": 0.0,
                            "max_unit_end_bearing": 0.0,
                        },
                        "bg_color": "#e8c7cf",
                        "bg_alpha": 0.28,
                    }
                ],
                "layers": [],
                "control_mode": "Load Control",
                "axial_load_kN": 0.0,
                "load_z_m": 0.0,
                "axial_disp_m": 0.0,
                "steps": 20,
            },
            "lateral": {
                "pile_top_z_m": 0.0,
                "pile_bottom_z_m": 0.0,
                "pile_length_m": 0.0,
                "pile_diameter_m": 0.0,
                "pile_E_kPa": 0.0,
                "pile_shape": "Pipe",
                "pile_thickness_m": 0.0,
                "ele_size_m": 0.0,
                "mesh_settings": default_mesh_settings(),
                "section_mode": "elastic",
                "fiber_section_library": [],
                "fiber_section_segments": [],
                "soil_materials": [
                    {
                        "name": "Material-1",
                        "soil_type": "Soft Clay Soil",
                        "params": {"gammaEff": 0.0, "cu": 0.0, "eps50": 0.0},
                        "bg_color": "#e8c7cf",
                        "bg_alpha": 0.28,
                    }
                ],
                "layers": [],
                "loads": [{"type": "Fx", "value": 0.0, "depth_m": 0.0, "depth_ui": 0.0}],
                "load_cases": [{"depth_m": 0.0, "depth_ui": 0.0, "Fx": 0.0, "Fy": 0.0, "Mx": 0.0, "My": 0.0}],
                "control_mode": "Load Control",
                "lateral_load_kN": 0.0,
                "lateral_disp_m": 0.0,
                "moment_load_kN_m": 0.0,
                "shear_depth_m": 0.0,
                "moment_depth_m": 0.0,
                "steps": 50,
            },
            "combined": {
                "pile_shape": "Pipe",
                "pile_top_z_m": 0.0,
                "pile_bottom_z_m": 0.0,
                "pile_length_m": 0.0,
                "pile_diameter_m": 0.0,
                "pile_thickness_m": 0.0,
                "pile_E_kPa": 0.0,
                "ele_size_m": 0.0,
                "mesh_settings": default_mesh_settings(),
                "section_mode": "elastic",
                "fiber_section_library": [],
                "fiber_section_segments": [],
                "materials": [
                    {
                        "name": "Material-1",
                        "bg_color": "#e8c7cf",
                        "axial_type": "API Clay",
                        "axial_params": {
                            "gammaEff": 0.0,
                            "cu": 0.0,
                            "cu_remolded": 0.0,
                            "max_unit_skin_friction": 0.0,
                            "max_unit_end_bearing": 0.0,
                        },
                        "lateral_type": "Soft Clay Soil",
                        "lateral_params": {"gammaEff": 0.0, "cu": 0.0, "eps50": 0.0},
                    }
                ],
                "layers": [],
                "loads": [
                    {"type": "Fx", "value": 0.0, "depth_m": 0.0, "depth_ui": 0.0},
                    {"type": "Fy", "value": 0.0, "depth_m": 0.0, "depth_ui": 0.0},
                    {"type": "Fz", "value": 0.0, "depth_m": 0.0, "depth_ui": 0.0},
                    {"type": "Mx", "value": 0.0, "depth_m": 0.0, "depth_ui": 0.0},
                    {"type": "My", "value": 0.0, "depth_m": 0.0, "depth_ui": 0.0},
                    {"type": "Mz", "value": 0.0, "depth_m": 0.0, "depth_ui": 0.0},
                ],
                "load_cases": [
                    {"depth_m": 0.0, "depth_ui": 0.0, "Fz": 0.0, "Fx": 0.0, "Fy": 0.0, "Mx": 0.0, "My": 0.0}
                ],
            },
            "group": {
                "materials": [
                    {
                        "name": "Material-1",
                        "bg_color": "#e8c7cf",
                        "bg_alpha": 0.28,
                        "axial_type": "API Clay",
                        "axial_params": {
                            "gammaEff": 0.0,
                            "cu": 0.0,
                            "cu_remolded": 0.0,
                            "max_unit_skin_friction": 0.0,
                            "max_unit_end_bearing": 0.0,
                        },
                        "lateral_type": "Soft Clay Soil",
                        "lateral_params": {"gammaEff": 0.0, "cu": 0.0, "eps50": 0.0},
                    }
                ],
                "layers": [],
                "pile_types": [
                    {
                        "name": "PileType-1",
                        "pile_shape": "Circle",
                        "pile_top_z_m": 0.0,
                        "pile_bottom_z_m": 0.0,
                        "pile_length_m": 0.0,
                        "pile_diameter_m": 0.0,
                        "pile_thickness_m": 0.0,
                        "pile_E_kPa": 0.0,
                        "ele_size_m": 0.0,
                        "section_mode": "elastic",
                        "fiber_section_library": [],
                        "fiber_section_segments": [],
                    }
                ],
                "cap": {"shape": "Rectangular", "length_x_m": 0.0, "length_y_m": 0.0, "height_m": 0.0, "center_z_m": 0.0, "bottom_z_m": 0.0},
                "pile_layout": [],
                "load_cases": [{"load_no": 1, "x_m": 0.0, "y_m": 0.0, "Fx": 0.0, "Fy": 0.0, "Fz": 0.0, "Mx": 0.0, "My": 0.0, "Mz": 0.0}],
                "loads": [{"load_no": 1, "x_m": 0.0, "y_m": 0.0, "Fx": 0.0, "Fy": 0.0, "Fz": 0.0, "Mx": 0.0, "My": 0.0, "Mz": 0.0}],
                "mesh_settings": default_mesh_settings(),
                "mesh_settings_by_pile": {},
                "p_multiplier_mode": "automatic",
                "p_multiplier_manual": 1.0,
                "coordinate_origin": "cap_center",
                "analysis_type": "static_group_3d",
                "active_models": ["py", "tz", "qz"],
                "steps": 40,
            },
        },
    }


def normalize_case_document(doc: Dict) -> Dict:
    out = copy.deepcopy(default_case_document())
    if isinstance(doc, dict):
        out["mode"] = str(doc.get("mode", out["mode"])).lower()
        payloads = doc.get("payloads", {})
        if isinstance(payloads, dict):
            for key in out["payloads"]:
                if isinstance(payloads.get(key), dict):
                    out["payloads"][key].update(payloads[key])
    return out


def _format_value(value) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False) if (not value or any(ch.isspace() for ch in value) or value.startswith("#")) else value
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return str(value)


def _parse_value(text: str):
    text = text.strip()
    if not text:
        return ""
    if text[:1] in "\"'" and text[-1:] == text[:1]:
        return json.loads(text)
    try:
        return float(text) if any(ch in text for ch in ".eE") else int(text)
    except ValueError:
        return text


def _emit(lines: List[str], header: str, pairs: Iterable[Tuple[str, object]]):
    lines.append(f"[{header}]")
    for key, value in pairs:
        lines.append(f"{key} = {_format_value(value)}")
    lines.append("")


def _emit_material(lines: List[str], idx: int, material: Dict, mode: str):
    pairs = [("NAME", material.get("name", f"Material-{idx}")), ("COLOR", material.get("bg_color", "#dfe8d8"))]
    if mode == "axial":
        model = str(material.get("soil_type", "API Sand"))
        pairs.append(("MODEL", model))
        pairs.extend((label, dict(material.get("params", {})).get(key, 0.0)) for label, key in AXIAL_FIELDS.get(model, []))
    elif mode == "lateral":
        model = str(material.get("soil_type", "Sand"))
        pairs.append(("MODEL", model))
        pairs.extend((label, dict(material.get("params", {})).get(key, 0.0)) for label, key in LATERAL_FIELDS.get(model, []))
    else:
        a_model = str(material.get("axial_type", "API Sand"))
        l_model = str(material.get("lateral_type", "Sand"))
        pairs.append(("AXIAL_MODEL", a_model))
        pairs.extend((f"AXIAL_{label}", dict(material.get("axial_params", {})).get(key, 0.0)) for label, key in AXIAL_FIELDS.get(a_model, []))
        pairs.append(("LATERAL_MODEL", l_model))
        pairs.extend((f"LATERAL_{label}", dict(material.get("lateral_params", {})).get(key, 0.0)) for label, key in LATERAL_FIELDS.get(l_model, []))
    _emit(lines, f"MATERIAL {idx}", pairs)


def _emit_mesh(lines: List[str], mesh_settings: Dict | None):
    spec = default_mesh_settings()
    if isinstance(mesh_settings, dict):
        spec.update(mesh_settings)
    _emit(
        lines,
        "MESH_SETTING",
        [
            ("ADVANCED_ENABLED", bool(spec.get("advanced_enabled", False))),
            ("MESH_TYPE", spec.get("mesh_type", "element_number")),
            ("UNIFORM_ELEMENT_COUNT", spec.get("uniform_element_count", 400)),
            ("UNIFORM_ELEMENT_LENGTH", spec.get("uniform_element_length_m", 0.0)),
        ],
    )
    for idx, segment in enumerate(spec.get("segments", []), start=1):
        if not isinstance(segment, dict):
            continue
        _emit(
            lines,
            f"MESH_SEGMENT {idx}",
            [
                ("START", segment.get("start_m", 0.0)),
                ("END", segment.get("end_m", 0.0)),
                ("ELEMENT_COUNT", segment.get("element_count", 0)),
                ("TOP_LENGTH", segment.get("top_length_m", "")),
                ("BOTTOM_LENGTH", segment.get("bottom_length_m", "")),
            ],
        )


def _emit_mesh_for_pile(lines: List[str], pile_no: int, mesh_settings: Dict | None):
    spec = default_mesh_settings()
    if isinstance(mesh_settings, dict):
        spec.update(mesh_settings)
    _emit(
        lines,
        f"PILE_MESH {pile_no}",
        [
            ("PILE_NO", pile_no),
            ("ADVANCED_ENABLED", bool(spec.get("advanced_enabled", False))),
            ("MESH_TYPE", spec.get("mesh_type", "element_number")),
            ("UNIFORM_ELEMENT_COUNT", spec.get("uniform_element_count", 400)),
            ("UNIFORM_ELEMENT_LENGTH", spec.get("uniform_element_length_m", 0.0)),
        ],
    )
    for idx, segment in enumerate(spec.get("segments", []), start=1):
        if not isinstance(segment, dict):
            continue
        _emit(
            lines,
            f"PILE_MESH_SEGMENT {pile_no}-{idx}",
            [
                ("PILE_NO", pile_no),
                ("START", segment.get("start_m", 0.0)),
                ("END", segment.get("end_m", 0.0)),
                ("ELEMENT_COUNT", segment.get("element_count", 0)),
                ("TOP_LENGTH", segment.get("top_length_m", "")),
                ("BOTTOM_LENGTH", segment.get("bottom_length_m", "")),
            ],
        )


def _section_payload_from_payload(payload: Dict) -> Dict:
    return {
        "section_mode": str(payload.get("section_mode", "elastic") or "elastic"),
        "fiber_section_library": copy.deepcopy(list(payload.get("fiber_section_library", []) or [])),
        "fiber_section_segments": copy.deepcopy(list(payload.get("fiber_section_segments", []) or [])),
    }


def _emit_section_payload(lines: List[str], header: str, payload: Dict):
    section_payload = _section_payload_from_payload(payload)
    _emit(
        lines,
        header,
        [
            ("SECTION_MODE", section_payload["section_mode"]),
            ("FIBER_SECTION_COUNT", len(section_payload["fiber_section_library"])),
            ("FIBER_SEGMENT_COUNT", len(section_payload["fiber_section_segments"])),
            ("PAYLOAD_JSON", json.dumps(section_payload, ensure_ascii=False)),
        ],
    )


def _load_section_payload(block: Dict) -> Dict:
    payload_json = block.get("PAYLOAD_JSON", "")
    section_payload = {
        "section_mode": str(block.get("SECTION_MODE", "elastic") or "elastic"),
        "fiber_section_library": [],
        "fiber_section_segments": [],
    }
    if isinstance(payload_json, str) and payload_json.strip():
        try:
            parsed = json.loads(payload_json)
            if isinstance(parsed, dict):
                section_payload["section_mode"] = str(parsed.get("section_mode", section_payload["section_mode"]) or "elastic")
                section_payload["fiber_section_library"] = [
                    dict(item) for item in (parsed.get("fiber_section_library", []) or [])
                    if isinstance(item, dict)
                ]
                section_payload["fiber_section_segments"] = [
                    dict(item) for item in (parsed.get("fiber_section_segments", []) or [])
                    if isinstance(item, dict)
                ]
                return section_payload
        except Exception:
            pass
    return section_payload


def save_case(file_path: str, doc: Dict):
    doc = normalize_case_document(doc)
    mode = str(doc.get("mode", "axial")).lower()
    payload = doc["payloads"][mode]
    lines: List[str] = []
    if mode == "group":
        _emit(lines, "CONTROL", [("SCOPE", "GROUP")])
        lines.extend(["[SOIL_PROPERTIES]", f"COUNT = {len(payload.get('materials', []))}", ""])
        for idx, material in enumerate(payload.get("materials", []), start=1):
            _emit_material(lines, idx, material, "combined")
        lines.extend(["[SOIL_LAYOUT]", f"COUNT = {len(payload.get('layers', []))}", ""])
        for idx, layer in enumerate(payload.get("layers", []), start=1):
            _emit(lines, f"LAYER {idx}", [("TOP", layer.get("z_top", 0.0)), ("BOTTOM", layer.get("z_bottom", -1.0)), ("MATERIAL", layer.get("material_name", ""))])
        lines.extend(["[PILE_DEFINITION]", f"COUNT = {len(payload.get('pile_types', []))}", ""])
        for idx, pile_type in enumerate(payload.get("pile_types", []), start=1):
            _emit(lines, f"PILE_TYPE {idx}", [("NAME", pile_type.get("name", f"PileType-{idx}")), ("PILE_SHAPE", pile_type.get("pile_shape", "Circle")), ("PILE_TOP_Z", pile_type.get("pile_top_z_m", 0.0)), ("PILE_BOTTOM_Z", pile_type.get("pile_bottom_z_m", -27.0)), ("PILE_LENGTH", pile_type.get("pile_length_m", 27.0)), ("PILE_DIAMETER", pile_type.get("pile_diameter_m", 1.0)), ("PILE_THICKNESS", pile_type.get("pile_thickness_m", 0.04)), ("PILE_E", pile_type.get("pile_E_kPa", 3.0e7)), ("ELEMENT_SIZE", pile_type.get("ele_size_m", 0.0))])
            _emit_section_payload(lines, f"PILE_TYPE_SECTION_PAYLOAD {idx}", pile_type)
        cap = dict(payload.get("cap", {}))
        _emit(lines, "CAP_DEFINITION", [
            ("CAP_LENGTH_X", cap.get("length_x_m", 6.0)),
            ("CAP_LENGTH_Y", cap.get("length_y_m", 6.0)),
            ("CAP_HEIGHT", cap.get("height_m", 1.0)),
            ("CAP_CENTER_Z", cap.get("center_z_m", 0.0)),
            ("CAP_BOTTOM_Z", cap.get("bottom_z_m", 0.0)),
        ])
        _emit(lines, "P_MULTIPLIER", [
            ("MODE", payload.get("p_multiplier_mode", "automatic")),
            ("MANUAL_VALUE", payload.get("p_multiplier_manual", 1.0)),
        ])
        lines.extend(["[PILE_LAYOUT]", f"COUNT = {len(payload.get('pile_layout', []))}", ""])
        for idx, row in enumerate(payload.get("pile_layout", []), start=1):
            _emit(lines, f"PILE {idx}", [("X", row.get("x_m", 0.0)), ("Y", row.get("y_m", 0.0)), ("TOP_Z", row.get("top_z_m", 0.0)), ("BOTTOM_Z", row.get("bottom_z_m", -27.0)), ("PILE_TYPE", row.get("pile_type_name", "")), ("CONNECTIVITY", row.get("connectivity", "fixed")), ("P_MULTIPLIER", row.get("p_multiplier_manual", payload.get("p_multiplier_manual", 1.0)))])
        load_cases = payload.get("load_cases", payload.get("loads", []))
        lines.extend(["[LOAD_SETTING]", f"COUNT = {len(load_cases)}", ""])
        for idx, row in enumerate(load_cases, start=1):
            _emit(lines, f"LOAD {idx}", [("X", row.get("x_m", 0.0)), ("Y", row.get("y_m", 0.0)), ("FX", row.get("Fx", 0.0)), ("FY", row.get("Fy", 0.0)), ("FZ", row.get("Fz", 0.0)), ("MX", row.get("Mx", 0.0)), ("MY", row.get("My", 0.0)), ("MZ", row.get("Mz", 0.0))])
        _emit_mesh(lines, payload.get("mesh_settings"))
        mesh_by_pile = payload.get("mesh_settings_by_pile", {})
        if isinstance(mesh_by_pile, dict):
            for idx in range(len(payload.get("pile_layout", []))):
                key = f"Pile {idx + 1}"
                if isinstance(mesh_by_pile.get(key), dict):
                    _emit_mesh_for_pile(lines, idx + 1, mesh_by_pile.get(key))
    else:
        _emit(lines, "CONTROL", [("SCOPE", "SINGLE"), ("MODE", {"axial": 1, "lateral": 2, "combined": 3}[mode])])
        materials = payload.get("soil_materials", []) if mode in ("axial", "lateral") else payload.get("materials", [])
        lines.extend(["[SOIL_PROPERTIES]", f"COUNT = {len(materials)}", ""])
        for idx, material in enumerate(materials, start=1):
            _emit_material(lines, idx, material, mode if mode != "combined" else "combined")
        lines.extend(["[SOIL_LAYOUT]", f"COUNT = {len(payload.get('layers', []))}", ""])
        for idx, layer in enumerate(payload.get("layers", []), start=1):
            _emit(lines, f"LAYER {idx}", [("TOP", layer.get("z_top", 0.0)), ("BOTTOM", layer.get("z_bottom", 1.0)), ("MATERIAL", layer.get("material_name", ""))])
        pile_pairs = [("PILE_SHAPE", payload.get("pile_shape", "Pipe")), ("PILE_TOP_Z", payload.get("pile_top_z_m", 0.0)), ("PILE_BOTTOM_Z", payload.get("pile_bottom_z_m", -17.0)), ("PILE_LENGTH", payload.get("pile_length_m", 17.0)), ("PILE_DIAMETER", payload.get("pile_diameter_m", 0.5)), ("PILE_THICKNESS", payload.get("pile_thickness_m", 0.02)), ("PILE_E", payload.get("pile_E_kPa", 2.0e8))]
        _emit(lines, "PILE_DEFINITION", pile_pairs)
        _emit_section_payload(lines, "SECTION_PAYLOAD", payload)
        if mode == "axial":
            _emit(lines, "LOAD_SETTING", [("AXIAL_LOAD", payload.get("axial_load_kN", 0.0)), ("LOAD_Z", payload.get("load_z_m", 0.0))])
        elif mode == "lateral":
            loads = payload.get("loads", [])
            if isinstance(loads, list) and loads:
                lines.extend(["[LOAD_SETTING]", f"COUNT = {len(loads)}", ""])
                for idx, row in enumerate(loads, start=1):
                    _emit(lines, f"LOAD {idx}", [("TYPE", row.get("type", "")), ("VALUE", row.get("value", 0.0)), ("Z", row.get("depth_m", row.get("z_m", 0.0)))])
            else:
                _emit(lines, "LOAD_SETTING", [("LATERAL_LOAD", payload.get("lateral_load_kN", 0.0)), ("LATERAL_LOAD_Z", payload.get("shear_depth_m", 0.0)), ("MOMENT", payload.get("moment_load_kN_m", 0.0)), ("MOMENT_Z", payload.get("moment_depth_m", 0.0))])
        else:
            loads = payload.get("loads", [])
            lines.extend(["[LOAD_SETTING]", f"COUNT = {len(loads)}", ""])
            for idx, row in enumerate(loads, start=1):
                _emit(lines, f"LOAD {idx}", [("TYPE", row.get("type", "")), ("VALUE", row.get("value", 0.0)), ("Z", row.get("depth_m", row.get("z_m", 0.0)))])
        _emit_mesh(lines, payload.get("mesh_settings"))
    Path(file_path).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def load_case(file_path: str) -> Dict:
    path = Path(file_path)
    text = None
    last_error = None
    for encoding in ("utf-8", "utf-8-sig", "gbk", "cp936"):
        try:
            text = path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError as exc:
            last_error = exc
    if text is None:
        raise last_error if last_error is not None else ValueError(f"Unable to read case file: {file_path}")
    if text.lstrip().startswith("{"):
        raise ValueError("Old JSON case files are no longer supported. Please use the new structured .dat format.")

    blocks: List[Tuple[str, Dict]] = []
    current_header = None
    current: Dict[str, object] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            if current_header is not None:
                blocks.append((current_header, current))
            current_header = line[1:-1].strip()
            current = {}
            continue
        if "=" in line and current_header is not None:
            key, value = line.split("=", 1)
            current[key.strip()] = _parse_value(value)
    if current_header is not None:
        blocks.append((current_header, current))

    doc = default_case_document()
    control = next((block for header, block in blocks if header == "CONTROL"), {})
    scope = str(control.get("SCOPE", "SINGLE")).upper()
    if scope == "GROUP":
        doc["mode"] = "group"
        payload = copy.deepcopy(doc["payloads"]["group"])
        payload["materials"] = []
        payload["layers"] = []
        payload["pile_types"] = []
        payload["pile_layout"] = []
        payload["load_cases"] = []
        payload["loads"] = []
        payload["mesh_settings"] = default_mesh_settings()
        payload["mesh_settings_by_pile"] = {}
        payload["p_multiplier_mode"] = "automatic"
        payload["p_multiplier_manual"] = 1.0
        pile_type_sections: Dict[int, Dict] = {}
        cap_bottom_from_file = False
        for header, block in blocks:
            if header.startswith("MATERIAL "):
                payload["materials"].append({"name": str(block.get("NAME", "Material-1")), "bg_color": str(block.get("COLOR", "#dfe8d8")), "bg_alpha": 0.28, "axial_type": str(block.get("AXIAL_MODEL", "API Sand")), "axial_params": {AXIAL_ALIASES[k[6:]]: float(v) for k, v in block.items() if k.startswith("AXIAL_") and k[6:] in AXIAL_ALIASES and k != "AXIAL_MODEL"}, "lateral_type": str(block.get("LATERAL_MODEL", "Sand")), "lateral_params": {LATERAL_ALIASES[k[8:]]: float(v) for k, v in block.items() if k.startswith("LATERAL_") and k[8:] in LATERAL_ALIASES and k != "LATERAL_MODEL"}})
            elif header.startswith("LAYER "):
                payload["layers"].append({"z_top": float(block.get("TOP", 0.0)), "z_bottom": float(block.get("BOTTOM", -1.0)), "material_name": str(block.get("MATERIAL", ""))})
            elif header.startswith("PILE_TYPE "):
                payload["pile_types"].append({"name": str(block.get("NAME", "PileType-1")), "pile_shape": str(block.get("PILE_SHAPE", "Circle")), "pile_top_z_m": float(block.get("PILE_TOP_Z", 0.0)), "pile_bottom_z_m": float(block.get("PILE_BOTTOM_Z", -27.0)), "pile_length_m": float(block.get("PILE_LENGTH", 27.0)), "pile_diameter_m": float(block.get("PILE_DIAMETER", 1.0)), "pile_thickness_m": float(block.get("PILE_THICKNESS", 0.04)), "pile_E_kPa": float(block.get("PILE_E", 3.0e7)), "ele_size_m": float(block.get("ELEMENT_SIZE", 0.0)), "section_mode": "elastic", "fiber_section_library": [], "fiber_section_segments": []})
            elif header.startswith("PILE_TYPE_SECTION_PAYLOAD "):
                pile_idx = int(str(header).split()[-1])
                pile_type_sections[pile_idx] = _load_section_payload(block)
            elif header == "CAP_DEFINITION":
                cap_height = float(block.get("CAP_HEIGHT", 1.0))
                cap_bottom_from_file = "CAP_BOTTOM_Z" in block
                cap_bottom = float(block.get("CAP_BOTTOM_Z", 0.0))
                payload["cap"].update({
                    "length_x_m": float(block.get("CAP_LENGTH_X", 6.0)),
                    "length_y_m": float(block.get("CAP_LENGTH_Y", 6.0)),
                    "height_m": cap_height,
                    "center_z_m": float(block.get("CAP_CENTER_Z", cap_bottom + 0.5 * cap_height)),
                    "bottom_z_m": cap_bottom,
                })
            elif header == "P_MULTIPLIER":
                mode_value = str(block.get("MODE", "automatic")).lower()
                payload["p_multiplier_mode"] = "manual" if mode_value == "manual" else "automatic"
                payload["p_multiplier_manual"] = float(block.get("MANUAL_VALUE", 1.0))
            elif header.startswith("PILE "):
                payload["pile_layout"].append({"x_m": float(block.get("X", 0.0)), "y_m": float(block.get("Y", 0.0)), "top_z_m": float(block.get("TOP_Z", 0.0)), "bottom_z_m": float(block.get("BOTTOM_Z", -27.0)), "pile_type_name": str(block.get("PILE_TYPE", "")), "connectivity": str(block.get("CONNECTIVITY", "fixed")).lower(), "p_multiplier_manual": float(block.get("P_MULTIPLIER", payload.get("p_multiplier_manual", 1.0)))})
            elif header.startswith("LOAD "):
                if any(key in block for key in ("FX", "FY", "FZ", "MX", "MY", "MZ")):
                    payload["load_cases"].append({
                        "load_no": len(payload["load_cases"]) + 1,
                        "x_m": float(block.get("X", 0.0)),
                        "y_m": float(block.get("Y", 0.0)),
                        "Fx": float(block.get("FX", 0.0)),
                        "Fy": float(block.get("FY", 0.0)),
                        "Fz": float(block.get("FZ", 0.0)),
                        "Mx": float(block.get("MX", 0.0)),
                        "My": float(block.get("MY", 0.0)),
                        "Mz": float(block.get("MZ", 0.0)),
                    })
                else:
                    payload["loads"].append({"type": str(block.get("TYPE", "")), "value": float(block.get("VALUE", 0.0)), "x_m": float(block.get("X", 0.0)), "y_m": float(block.get("Y", 0.0))})
            elif header == "MESH_SETTING":
                payload["mesh_settings"] = {
                    "advanced_enabled": str(block.get("ADVANCED_ENABLED", "False")).lower() in {"1", "true", "yes", "on"},
                    "mesh_type": str(block.get("MESH_TYPE", "element_number")).lower(),
                    "uniform_element_count": int(block.get("UNIFORM_ELEMENT_COUNT", 400)),
                    "uniform_element_length_m": float(block.get("UNIFORM_ELEMENT_LENGTH", 0.0)),
                    "segments": [],
                }
            elif header.startswith("MESH_SEGMENT "):
                payload.setdefault("mesh_settings", default_mesh_settings())
                payload["mesh_settings"].setdefault("segments", []).append(
                    {
                        "start_m": float(block.get("START", 0.0)),
                        "end_m": float(block.get("END", 0.0)),
                        "element_count": int(block.get("ELEMENT_COUNT", 0)),
                        "top_length_m": None if block.get("TOP_LENGTH", "") in ("", None) else float(block.get("TOP_LENGTH", 0.0)),
                        "bottom_length_m": None if block.get("BOTTOM_LENGTH", "") in ("", None) else float(block.get("BOTTOM_LENGTH", 0.0)),
                    }
                )
            elif header.startswith("PILE_MESH "):
                pile_no = int(block.get("PILE_NO", str(header).split()[-1]))
                payload.setdefault("mesh_settings_by_pile", {})
                payload["mesh_settings_by_pile"][f"Pile {pile_no}"] = {
                    "advanced_enabled": str(block.get("ADVANCED_ENABLED", "False")).lower() in {"1", "true", "yes", "on"},
                    "mesh_type": str(block.get("MESH_TYPE", "element_number")).lower(),
                    "uniform_element_count": int(block.get("UNIFORM_ELEMENT_COUNT", 400)),
                    "uniform_element_length_m": float(block.get("UNIFORM_ELEMENT_LENGTH", 0.0)),
                    "segments": [],
                }
            elif header.startswith("PILE_MESH_SEGMENT "):
                pile_no = int(block.get("PILE_NO", 1))
                payload.setdefault("mesh_settings_by_pile", {})
                payload["mesh_settings_by_pile"].setdefault(
                    f"Pile {pile_no}",
                    {
                        "advanced_enabled": False,
                        "mesh_type": "element_number",
                        "uniform_element_count": 400,
                        "uniform_element_length_m": 0.0,
                        "segments": [],
                    },
                )
                payload["mesh_settings_by_pile"][f"Pile {pile_no}"].setdefault("segments", []).append(
                    {
                        "start_m": float(block.get("START", 0.0)),
                        "end_m": float(block.get("END", 0.0)),
                        "element_count": int(block.get("ELEMENT_COUNT", 0)),
                        "top_length_m": None if block.get("TOP_LENGTH", "") in ("", None) else float(block.get("TOP_LENGTH", 0.0)),
                        "bottom_length_m": None if block.get("BOTTOM_LENGTH", "") in ("", None) else float(block.get("BOTTOM_LENGTH", 0.0)),
                    }
                )
        for idx, pile_type in enumerate(payload["pile_types"], start=1):
            pile_type.update(pile_type_sections.get(idx, {}))
        if not cap_bottom_from_file:
            pile_tops = [
                float(row.get("top_z_m", 0.0))
                for row in payload.get("pile_layout", [])
                if isinstance(row, dict)
            ]
            if not pile_tops:
                pile_tops = [
                    float(row.get("pile_top_z_m", 0.0))
                    for row in payload.get("pile_types", [])
                    if isinstance(row, dict)
                ]
            cap_bottom = max(pile_tops) if pile_tops else float(payload["cap"].get("bottom_z_m", 0.0))
            cap_height = float(payload["cap"].get("height_m", 1.0))
            payload["cap"]["bottom_z_m"] = cap_bottom
            payload["cap"]["center_z_m"] = cap_bottom + 0.5 * cap_height
        if not payload["load_cases"] and payload["loads"]:
            merged = {"load_no": 1, "x_m": 0.0, "y_m": 0.0, "Fx": 0.0, "Fy": 0.0, "Fz": 0.0, "Mx": 0.0, "My": 0.0, "Mz": 0.0}
            for row in payload["loads"]:
                if not isinstance(row, dict):
                    continue
                load_type = str(row.get("type", "")).split()[0]
                if load_type in merged:
                    merged[load_type] = float(row.get("value", 0.0))
                    merged["x_m"] = float(row.get("x_m", merged["x_m"]))
                    merged["y_m"] = float(row.get("y_m", merged["y_m"]))
            payload["load_cases"] = [merged]
        doc["payloads"]["group"] = payload
        return doc

    mode = {1: "axial", 2: "lateral", 3: "combined"}.get(int(control.get("MODE", 1)), "axial")
    doc["mode"] = mode
    payload = copy.deepcopy(doc["payloads"][mode])
    if mode in ("axial", "lateral"):
        payload["soil_materials"] = []
    else:
        payload["materials"] = []
    payload["layers"] = []
    if mode == "lateral":
        payload["loads"] = []
    elif mode == "combined":
        payload["loads"] = []
    payload["mesh_settings"] = default_mesh_settings()
    section_payload = None
    for header, block in blocks:
        if header.startswith("MATERIAL "):
            if mode == "axial":
                payload["soil_materials"].append({"name": str(block.get("NAME", "Material-1")), "soil_type": str(block.get("MODEL", "API Sand")), "params": {AXIAL_ALIASES[k]: float(v) for k, v in block.items() if k in AXIAL_ALIASES}, "bg_color": str(block.get("COLOR", "#dfe8d8")), "bg_alpha": 0.28})
            elif mode == "lateral":
                payload["soil_materials"].append({"name": str(block.get("NAME", "Material-1")), "soil_type": str(block.get("MODEL", "Sand")), "params": {LATERAL_ALIASES[k]: float(v) for k, v in block.items() if k in LATERAL_ALIASES}, "bg_color": str(block.get("COLOR", "#dfe8d8")), "bg_alpha": 0.28})
            else:
                payload["materials"].append({"name": str(block.get("NAME", "Layer-1")), "bg_color": str(block.get("COLOR", "#dfe8d8")), "axial_type": str(block.get("AXIAL_MODEL", "API Sand")), "axial_params": {AXIAL_ALIASES[k[6:]]: float(v) for k, v in block.items() if k.startswith("AXIAL_") and k[6:] in AXIAL_ALIASES and k != "AXIAL_MODEL"}, "lateral_type": str(block.get("LATERAL_MODEL", "Sand")), "lateral_params": {LATERAL_ALIASES[k[8:]]: float(v) for k, v in block.items() if k.startswith("LATERAL_") and k[8:] in LATERAL_ALIASES and k != "LATERAL_MODEL"}})
        elif header.startswith("LAYER "):
            payload["layers"].append({"z_top": float(block.get("TOP", 0.0)), "z_bottom": float(block.get("BOTTOM", 1.0)), "material_name": str(block.get("MATERIAL", ""))})
        elif header == "PILE_DEFINITION":
            payload.update({"pile_shape": str(block.get("PILE_SHAPE", payload.get("pile_shape", "Pipe"))), "pile_top_z_m": float(block.get("PILE_TOP_Z", payload.get("pile_top_z_m", 0.0))), "pile_bottom_z_m": float(block.get("PILE_BOTTOM_Z", payload.get("pile_bottom_z_m", -17.0))), "pile_length_m": float(block.get("PILE_LENGTH", payload.get("pile_length_m", 17.0))), "pile_diameter_m": float(block.get("PILE_DIAMETER", payload.get("pile_diameter_m", 0.5))), "pile_thickness_m": float(block.get("PILE_THICKNESS", payload.get("pile_thickness_m", 0.02))), "pile_E_kPa": float(block.get("PILE_E", payload.get("pile_E_kPa", 2.0e8))), "ele_size_m": float(block.get("ELEMENT_SIZE", payload.get("ele_size_m", 0.0)))})
            if mode in ("lateral", "combined"):
                payload["free_length_m"] = float(block.get("FREE_LENGTH", payload.get("free_length_m", 0.0)))
        elif header == "SECTION_PAYLOAD":
            section_payload = _load_section_payload(block)
        elif header == "LOAD_SETTING":
            if mode == "axial":
                payload["axial_load_kN"] = float(block.get("AXIAL_LOAD", payload.get("axial_load_kN", 0.0)))
                payload["load_z_m"] = float(block.get("LOAD_Z", payload.get("load_z_m", 0.0)))
            elif mode == "lateral":
                if "LATERAL_LOAD" in block or "MOMENT" in block:
                    payload["lateral_load_kN"] = float(block.get("LATERAL_LOAD", payload.get("lateral_load_kN", 0.0)))
                    payload["shear_depth_m"] = float(block.get("LATERAL_LOAD_Z", payload.get("shear_depth_m", 0.0)))
                    payload["moment_load_kN_m"] = float(block.get("MOMENT", payload.get("moment_load_kN_m", 0.0)))
                    payload["moment_depth_m"] = float(block.get("MOMENT_Z", payload.get("moment_depth_m", 0.0)))
                if not payload.get("loads") and ("LATERAL_LOAD" in block or "MOMENT" in block):
                    payload["loads"] = [
                        {"type": "Fx", "value": payload["lateral_load_kN"], "depth_m": payload["shear_depth_m"], "depth_ui": -payload["shear_depth_m"]},
                        {"type": "Fy", "value": 0.0, "depth_m": 0.0, "depth_ui": 0.0},
                        {"type": "Fz", "value": 0.0, "depth_m": 0.0, "depth_ui": 0.0},
                        {"type": "Mx", "value": 0.0, "depth_m": 0.0, "depth_ui": 0.0},
                        {"type": "My", "value": payload["moment_load_kN_m"], "depth_m": payload["moment_depth_m"], "depth_ui": -payload["moment_depth_m"]},
                        {"type": "Mz", "value": 0.0, "depth_m": 0.0, "depth_ui": 0.0},
                    ]
            else:
                if ("AXIAL_FORCE" in block or "SHEAR_HX" in block or "MOMENT_MY" in block) and not payload.get("loads"):
                    payload["loads"] = [
                        {"type": "Fx", "value": float(block.get("SHEAR_HX", 0.0)), "depth_m": float(block.get("SHEAR_HX_Z", 0.0)), "depth_ui": -float(block.get("SHEAR_HX_Z", 0.0))},
                        {"type": "Fy", "value": 0.0, "depth_m": 0.0, "depth_ui": 0.0},
                        {"type": "Fz", "value": float(block.get("AXIAL_FORCE", 0.0)), "depth_m": float(block.get("AXIAL_FORCE_Z", 0.0)), "depth_ui": -float(block.get("AXIAL_FORCE_Z", 0.0))},
                        {"type": "Mx", "value": 0.0, "depth_m": 0.0, "depth_ui": 0.0},
                        {"type": "My", "value": float(block.get("MOMENT_MY", 0.0)), "depth_m": float(block.get("MOMENT_MY_Z", 0.0)), "depth_ui": -float(block.get("MOMENT_MY_Z", 0.0))},
                        {"type": "Mz", "value": 0.0, "depth_m": 0.0, "depth_ui": 0.0},
                    ]
        elif mode == "lateral" and header.startswith("LOAD "):
            payload.setdefault("loads", []).append(
                {
                    "type": str(block.get("TYPE", "")),
                    "value": float(block.get("VALUE", 0.0)),
                    "depth_m": float(block.get("Z", 0.0)),
                    "depth_ui": -float(block.get("Z", 0.0)),
                }
            )
        elif mode == "combined" and header.startswith("LOAD "):
            payload.setdefault("loads", []).append(
                {
                    "type": str(block.get("TYPE", "")),
                    "value": float(block.get("VALUE", 0.0)),
                    "depth_m": float(block.get("Z", 0.0)),
                    "depth_ui": -float(block.get("Z", 0.0)),
                }
            )
        elif header == "MESH_SETTING":
            payload["mesh_settings"] = {
                "advanced_enabled": str(block.get("ADVANCED_ENABLED", "False")).lower() in {"1", "true", "yes", "on"},
                "mesh_type": str(block.get("MESH_TYPE", "element_number")).lower(),
                "uniform_element_count": int(block.get("UNIFORM_ELEMENT_COUNT", 400)),
                "uniform_element_length_m": float(block.get("UNIFORM_ELEMENT_LENGTH", 0.0)),
                "segments": [],
            }
        elif header.startswith("MESH_SEGMENT "):
            payload.setdefault("mesh_settings", default_mesh_settings())
            payload["mesh_settings"].setdefault("segments", []).append(
                {
                    "start_m": float(block.get("START", 0.0)),
                    "end_m": float(block.get("END", 0.0)),
                    "element_count": int(block.get("ELEMENT_COUNT", 0)),
                    "top_length_m": None if block.get("TOP_LENGTH", "") in ("", None) else float(block.get("TOP_LENGTH", 0.0)),
                    "bottom_length_m": None if block.get("BOTTOM_LENGTH", "") in ("", None) else float(block.get("BOTTOM_LENGTH", 0.0)),
                }
            )
    if mode == "lateral" and payload.get("loads"):
        load_map = {str(row.get("type", "")): row for row in payload.get("loads", []) if isinstance(row, dict)}
        payload["lateral_load_kN"] = float(load_map.get("Fx", {}).get("value", 0.0))
        payload["shear_depth_m"] = float(load_map.get("Fx", {}).get("depth_m", 0.0))
        payload["moment_load_kN_m"] = float(load_map.get("My", {}).get("value", 0.0))
        payload["moment_depth_m"] = float(load_map.get("My", {}).get("depth_m", 0.0))
    if mode in ("axial", "lateral"):
        material_map = {
            str(mat.get("name", "")): dict(mat)
            for mat in payload.get("soil_materials", [])
            if isinstance(mat, dict)
        }
        enriched_layers = []
        for row in payload.get("layers", []):
            if not isinstance(row, dict):
                continue
            layer = dict(row)
            material = material_map.get(str(layer.get("material_name", "")), {})
            if material:
                layer["soil_type"] = str(layer.get("soil_type", material.get("soil_type", "")))
                layer["params"] = dict(layer.get("params", material.get("params", {})) or {})
            else:
                layer.setdefault("soil_type", "")
                layer.setdefault("params", {})
            enriched_layers.append(layer)
        payload["layers"] = enriched_layers
    if mode == "combined" and payload.get("loads"):
        legacy_map = {
            "Axial Force N (kN)": "Fz",
            "Shear Hx (kN)": "Fx",
            "Moment My (kN*m)": "My",
        }
        normalized = []
        for row in payload.get("loads", []):
            if isinstance(row, dict):
                item = dict(row)
                item["type"] = legacy_map.get(str(item.get("type", "")), str(item.get("type", "")))
                normalized.append(item)
        payload["loads"] = normalized
    if isinstance(section_payload, dict):
        payload.update(section_payload)
    doc["payloads"][mode] = payload
    return doc
