# -*- coding: utf-8 -*-

from typing import Dict

from core.parameter_collector import AxialInput, CombinedInput, GroupInput, LateralInput
from language_manager import get_language


def _is_zh() -> bool:
    return get_language() == "zh"


class ResultFormatter:
    """Format solver outputs into summary and raw text blocks."""

    @staticmethod
    def _safe_sequence(value):
        if value is None:
            return []
        try:
            return list(value)
        except TypeError:
            return []

    @staticmethod
    def axial_z_mm_for_display(value_mm: float) -> float:
        return -float(value_mm)

    @staticmethod
    def global_z_mm_for_display(value_mm: float) -> float:
        return float(value_mm)

    @staticmethod
    def _control_mode_label(value: str) -> str:
        mode = str(value or "")
        if _is_zh():
            mapping = {
                "Load Control": "荷载控制",
                "Displacement Control": "位移控制",
            }
            return mapping.get(mode, mode)
        return mode

    @staticmethod
    def _analysis_label(key: str) -> str:
        if _is_zh():
            mapping = {
                "axial": "轴向分析",
                "lateral": "横向分析",
                "combined": "组合分析",
                "group": "群桩分析",
            }
            return mapping.get(key, key)
        mapping = {
            "axial": "Axial Analysis",
            "lateral": "Lateral Analysis",
            "combined": "Combined Analysis",
            "group": "Group Pile Analysis",
        }
        return mapping.get(key, key)

    @staticmethod
    def _build_summary(title: str, basic_lines, response_lines) -> str:
        if _is_zh():
            basic_title = "-------第一部分 基础信息-------"
            response_title = "-------第二部分 相关响应-------"
        else:
            basic_title = "-------Part 1 Basic Information-------"
            response_title = "-------Part 2 Response-------"
        return "\n".join(
            [title, "", basic_title, *basic_lines, "", response_title, *response_lines]
        )

    @staticmethod
    def _axial_load_location_label(load_z_m: float, pile_length_m: float) -> str:
        load_z = float(load_z_m or 0.0)
        pile_length = max(float(pile_length_m or 0.0), 0.0)
        if _is_zh():
            if abs(load_z) <= 1.0e-8:
                return "桩顶"
            if pile_length > 1.0e-8 and abs(load_z - pile_length) <= 1.0e-8:
                return "桩端"
            return f"距桩顶深度 {load_z:.4f} m"
        if abs(load_z) <= 1.0e-8:
            return "pile head"
        if pile_length > 1.0e-8 and abs(load_z - pile_length) <= 1.0e-8:
            return "pile tip"
        return f"depth {load_z:.4f} m from pile head"

    @staticmethod
    def _format_group_load_lines(payload: Dict):
        load_cases = payload.get("load_cases", [])
        if not isinstance(load_cases, list) or not load_cases:
            if _is_zh():
                return ["荷载数量: 0"]
            return ["Load case count: 0"]

        lines = []
        if _is_zh():
            lines.append(f"荷载工况数量: {len(load_cases)}")
        else:
            lines.append(f"Load case count: {len(load_cases)}")

        preview_cases = load_cases[:5]
        for idx, row in enumerate(preview_cases, start=1):
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
            if _is_zh():
                lines.append(
                    f"荷载工况 {idx} 作用点 (x, y) = ({x_m:.4f}, {y_m:.4f}) m: "
                    f"Fx={fx:.4f}, Fy={fy:.4f}, Fz={fz:.4f} kN; "
                    f"Mx={mx:.4f}, My={my:.4f}, Mz={mz:.4f} kN*m"
                )
            else:
                lines.append(
                    f"Load case {idx} at (x, y) = ({x_m:.4f}, {y_m:.4f}) m: "
                    f"Fx={fx:.4f}, Fy={fy:.4f}, Fz={fz:.4f} kN; "
                    f"Mx={mx:.4f}, My={my:.4f}, Mz={mz:.4f} kN*m"
                )
        if len(load_cases) > len(preview_cases):
            remaining = len(load_cases) - len(preview_cases)
            if _is_zh():
                lines.append(f"其余荷载工况: {remaining}")
            else:
                lines.append(f"Additional load cases: {remaining}")
        return lines

    @staticmethod
    def _node_count(results: Dict, depth_key: str = "depths") -> int:
        return len(ResultFormatter._safe_sequence(results.get(depth_key)))

    @staticmethod
    def _element_count(results: Dict, depth_key: str = "depths_ele", node_key: str = "depths") -> int:
        depths_ele = ResultFormatter._safe_sequence(results.get(depth_key))
        if len(depths_ele) > 0:
            return len(depths_ele)
        return max(ResultFormatter._node_count(results, node_key) - 1, 0)

    @staticmethod
    def _first_pile(results: Dict) -> Dict:
        piles = ResultFormatter._safe_sequence(results.get("piles"))
        if len(piles) > 0:
            first = piles[0]
            if isinstance(first, dict):
                return first
        return {}

    @staticmethod
    def axial_summary(inp: AxialInput, r: Dict) -> str:
        element_count = ResultFormatter._element_count(r, node_key="depths")
        node_count = ResultFormatter._node_count(r, "depths")
        if _is_zh():
            basic_lines = [
                "单位: m, kN, kPa",
                f"分析模式: {ResultFormatter._analysis_label('axial')}",
                f"控制模式: {ResultFormatter._control_mode_label(inp.control_mode)}",
                f"桩长 (m): {inp.pile_length_m:.6f}",
                f"桩径 (m): {inp.pile_diameter_m:.6f}",
                f"桩型: {inp.pile_shape}",
                f"桩截面积 (m^2): {inp.pile_A_m2:.8f}",
                f"桩弹性模量 (kPa): {inp.pile_E_kPa:.6f}",
                f"土层数量: {len(inp.layers)}",
                f"荷载作用位置: {ResultFormatter._axial_load_location_label(getattr(inp, 'load_z_m', 0.0), inp.pile_length_m)}",
            ]
            if inp.control_mode == "Displacement Control":
                basic_lines.append(f"施加桩顶 Z 位移 (mm): {float(inp.axial_disp_m) * 1000.0:.8f}")
            else:
                basic_lines.append(f"施加轴向荷载 Fz (kN): {-float(inp.axial_load_kN):.8f}")
            response_lines = [
                f"桩顶 Z 位移 (mm, +up/-down): {ResultFormatter.axial_z_mm_for_display(float(r.get('pile_top_disp', 0.0))):.8f}",
                f"桩端 Z 位移 (mm, +up/-down): {ResultFormatter.axial_z_mm_for_display(float(r.get('pile_tip_disp', 0.0))):.8f}",
                f"总侧摩阻累计值 (kN): {float(r.get('total_skin_friction', 0.0)):.8f}",
                f"端阻力 Z (kN): {float(r.get('end_bearing', 0.0)):.8f}",
                f"网格数/单元数: {element_count}",
                f"节点数: {node_count}",
            ]
            return ResultFormatter._build_summary(
                "轴向分析结果摘要",
                basic_lines,
                response_lines,
            )
        basic_lines = [
            "Units: m, kN, kPa",
            f"Analysis mode: {ResultFormatter._analysis_label('axial')}",
            f"Control mode: {ResultFormatter._control_mode_label(inp.control_mode)}",
            f"Pile Length (m): {inp.pile_length_m:.6f}",
            f"Pile Diameter (m): {inp.pile_diameter_m:.6f}",
            f"Pile Area Used (m^2): {float(r.get('debug_pile_area_m2', inp.pile_A_m2)):.8f}",
            f"Tip Area Used (m^2): {float(r.get('debug_tip_area_m2', 0.0) or 0.0):.8f}",
            f"Section Mode: {r.get('debug_section_mode', getattr(inp, 'section_mode', 'elastic'))}",
            f"Elastic EA (kN): {float(r.get('debug_elastic_EA_kN', 0.0) or 0.0):.8f}",
            f"Fiber Initial EA (kN): {float(r.get('debug_fiber_initial_EA_kN', 0.0) or 0.0):.8f}",
            f"Soil Layer Count: {len(inp.layers)}",
            f"Load location: {ResultFormatter._axial_load_location_label(getattr(inp, 'load_z_m', 0.0), inp.pile_length_m)}",
        ]
        if inp.control_mode == "Displacement Control":
            basic_lines.append(f"Applied head displacement Z (mm): {float(inp.axial_disp_m) * 1000.0:.8f}")
        else:
            basic_lines.append(f"Applied axial load Fz (kN): {-float(inp.axial_load_kN):.8f}")
        response_lines = [
            f"Top displacement Z (mm, +up/-down): {ResultFormatter.axial_z_mm_for_display(float(r.get('pile_top_disp', 0.0))):.8f}",
            f"Tip displacement Z (mm, +up/-down): {ResultFormatter.axial_z_mm_for_display(float(r.get('pile_tip_disp', 0.0))):.8f}",
            f"Total skin friction accumulated (kN): {float(r.get('total_skin_friction', 0.0)):.8f}",
            f"End bearing Z (kN): {float(r.get('end_bearing', 0.0)):.8f}",
            f"q-z qult (kN): {float(r.get('debug_qz_qult_kN', 0.0) or 0.0):.8f}",
            f"q-z z50 (m): {float(r.get('debug_qz_z50_m', 0.0) or 0.0):.8f}",
            f"Mesh element count: {element_count}",
            f"Node count: {node_count}",
        ]
        return ResultFormatter._build_summary(
            "Axial Analysis Summary",
            basic_lines,
            response_lines,
        )

    @staticmethod
    def axial_raw(r: Dict) -> str:
        depths = r.get("depths", [])
        disps_mm = r.get("displacements", [])
        axial = r.get("axial_forces", [])
        skin = r.get("skin_frictions", [])
        ult_skin = r.get("ult_skin_frictions", [])
        header = (
            "index,depth_m,disp_z_mm_global,axial_force_z_kN,skin_friction_z_kN,"
            "ult_skin_friction_z_kN,soil_stiffness_kN_per_m"
        )
        lines = [header]
        n = min(len(depths), len(disps_mm), len(axial), len(skin), len(ult_skin))
        for i in range(n):
            disp_m = float(disps_mm[i]) / 1000.0
            k = 0.0 if abs(disp_m) < 1.0e-12 else float(skin[i]) / disp_m
            lines.append(
                f"{i},{float(depths[i]):.8f},{-float(disps_mm[i]):.8f},{float(axial[i]):.8f},"
                f"{-float(skin[i]):.8f},{-float(ult_skin[i]):.8f},{k:.8f}"
            )
        return "\n".join(lines)

    @staticmethod
    def lateral_summary(inp: LateralInput, r: Dict) -> str:
        element_count = ResultFormatter._element_count(r, depth_key="depths_ele", node_key="depths")
        node_count = ResultFormatter._node_count(r, "depths")
        if _is_zh():
            basic_lines = [
                "单位: m, kN, kPa",
                f"分析模式: {ResultFormatter._analysis_label('lateral')}",
                f"控制模式: {ResultFormatter._control_mode_label(inp.control_mode)}",
                f"桩长 (m): {inp.pile_length_m:.6f}",
                f"桩径 (m): {inp.pile_diameter_m:.6f}",
                f"桩截面积 (m^2): {inp.pile_A_m2:.8f}",
                f"桩惯性矩 (m^4): {inp.pile_I_m4:.10f}",
                f"桩弹性模量 (kPa): {inp.pile_E_kPa:.6f}",
                f"土层数量: {len(inp.layers)}",
                f"Fx 作用深度 (m): {float(inp.loads.get('Fx', {}).get('z_m', 0.0)):.8f}",
                f"My 作用深度 (m): {float(inp.loads.get('My', {}).get('z_m', 0.0)):.8f}",
                f"等效横向荷载 (kN): {float(r.get('effective_lateral_load_kN', inp.lateral_load_kN)):.8f}",
                f"等效弯矩 (kN*m): {float(r.get('effective_moment_kN_m', inp.moment_load_kN_m)):.8f}",
                f"分析方向角 (deg): {float(r.get('analysis_angle_deg', 0.0)):.8f}",
            ]
            response_lines = [
                f"桩顶位移 (mm): {float(r.get('pile_top_disp', 0.0)):.8f}",
                f"桩顶 X 位移 (mm): {float(r.get('pile_top_disp_x_mm', 0.0)):.8f}",
                f"桩顶 Y 位移 (mm): {float(r.get('pile_top_disp_y_mm', 0.0)):.8f}",
                f"最大弯矩 (kN*m): {float(r.get('max_moment', 0.0)):.8f}",
                f"最大弯矩深度 (m): {float(r.get('max_moment_depth', 0.0)):.8f}",
                f"网格数/单元数: {element_count}",
                f"节点数: {node_count}",
            ]
            return ResultFormatter._build_summary(
                "横向分析结果摘要",
                basic_lines,
                response_lines,
            )
        basic_lines = [
            "Units: m, kN, kPa",
            f"Analysis mode: {ResultFormatter._analysis_label('lateral')}",
            f"Control mode: {ResultFormatter._control_mode_label(inp.control_mode)}",
            f"Pile Length (m): {inp.pile_length_m:.6f}",
            f"Pile Diameter (m): {inp.pile_diameter_m:.6f}",
            f"Pile Area Used (m^2): {float(r.get('debug_pile_area_m2', inp.pile_A_m2)):.8f}",
            f"Pile Inertia Used (m^4): {float(r.get('debug_pile_inertia_m4', inp.pile_I_m4)):.10f}",
            f"Section Mode: {r.get('debug_section_mode', getattr(inp, 'section_mode', 'elastic'))}",
            f"Elastic EI (kN*m^2): {float(r.get('debug_elastic_EI_kN_m2', 0.0) or 0.0):.8f}",
            f"Fiber Initial EIy (kN*m^2): {float(r.get('debug_fiber_initial_EIy_kN_m2', 0.0) or 0.0):.8f}",
            f"Fiber Initial EIz (kN*m^2): {float(r.get('debug_fiber_initial_EIz_kN_m2', 0.0) or 0.0):.8f}",
            f"Soil Layer Count: {len(inp.layers)}",
            f"Fx load depth (m): {float(inp.loads.get('Fx', {}).get('z_m', 0.0)):.8f}",
            f"My load depth (m): {float(inp.loads.get('My', {}).get('z_m', 0.0)):.8f}",
            f"Effective lateral load (kN): {float(r.get('effective_lateral_load_kN', inp.lateral_load_kN)):.8f}",
            f"Effective moment (kN*m): {float(r.get('effective_moment_kN_m', inp.moment_load_kN_m)):.8f}",
        ]
        response_lines = [
            f"Top displacement (mm): {float(r.get('pile_top_disp', 0.0)):.8f}",
            f"Top displacement X (mm): {float(r.get('pile_top_disp_x_mm', 0.0)):.8f}",
            f"Top displacement Y (mm): {float(r.get('pile_top_disp_y_mm', 0.0)):.8f}",
            f"Max moment (kN*m): {float(r.get('max_moment', 0.0)):.8f}",
            f"Max moment depth (m): {float(r.get('max_moment_depth', 0.0)):.8f}",
            f"Mesh element count: {element_count}",
            f"Node count: {node_count}",
        ]
        return ResultFormatter._build_summary(
            "Lateral Analysis Summary",
            basic_lines,
            response_lines,
        )

    @staticmethod
    def lateral_raw(r: Dict) -> str:
        depths = r.get("depths", [])
        disps = r.get("displacements", [])
        rots = r.get("rotations", [])
        soil_rxn = r.get("soil_reactions", [])
        soil_rxn_per_m = r.get("soil_reactions_per_m", [])
        depths_ele = r.get("depths_ele", [])
        moments = r.get("moments", [])
        shears = r.get("shears", [])

        header = (
            "index,depth_m,disp_mm,rotation_rad,soil_reaction_kN,soil_reaction_per_m_kNpm,"
            "ele_depth_m,moment_kNm,shear_kN"
        )
        lines = [header]
        n = max(len(depths), len(depths_ele))
        for i in range(n):
            d = float(depths[i]) if i < len(depths) else 0.0
            u = float(disps[i]) if i < len(disps) else 0.0
            rt = float(rots[i]) if i < len(rots) else 0.0
            sr = float(soil_rxn[i]) if i < len(soil_rxn) else 0.0
            sk = float(soil_rxn_per_m[i]) if i < len(soil_rxn_per_m) else 0.0
            de = float(depths_ele[i]) if i < len(depths_ele) else 0.0
            mm = float(moments[i]) if i < len(moments) else 0.0
            sh = float(shears[i]) if i < len(shears) else 0.0
            lines.append(f"{i},{d:.8f},{u:.8f},{rt:.8f},{sr:.8f},{sk:.8f},{de:.8f},{mm:.8f},{sh:.8f}")
        return "\n".join(lines)

    @staticmethod
    def combined_summary(inp: CombinedInput, r: Dict) -> str:
        element_count = ResultFormatter._element_count(r, depth_key="depths_ele", node_key="depths")
        node_count = ResultFormatter._node_count(r, "depths")
        if _is_zh():
            basic_lines = [
                "单位: m, kN, kPa",
                f"分析模式: {ResultFormatter._analysis_label('combined')}",
                f"桩长 (m): {inp.pile_length_m:.6f}",
                f"桩径 (m): {inp.pile_diameter_m:.6f}",
                f"桩型: {inp.pile_shape}",
                f"桩截面积 (m^2): {inp.pile_A_m2:.8f}",
                f"桩惯性矩 (m^4): {inp.pile_I_m4:.10f}",
                f"桩弹性模量 (kPa): {inp.pile_E_kPa:.6f}",
                f"轴向土层数量: {len(inp.axial_layers)}",
                f"横向土层数量: {len(inp.lateral_layers)}",
                f"Fz 作用深度 (m): {float(inp.loads.get('Fz', {}).get('depth_m', 0.0)):.8f}",
                f"Fx 作用深度 (m): {float(inp.loads.get('Fx', {}).get('depth_m', 0.0)):.8f}",
                f"My 作用深度 (m): {float(inp.loads.get('My', {}).get('depth_m', 0.0)):.8f}",
                f"Fz (kN, +上/-下): {float(inp.fz_kN):.8f}",
                f"Fx (kN): {float(inp.fx_kN):.8f}",
                f"Fy (kN): {float(inp.fy_kN):.8f}",
                f"Mx (kN*m): {float(inp.mx_kN_m):.8f}",
                f"My (kN*m): {float(inp.my_kN_m):.8f}",
                f"Mz (kN*m): {float(inp.mz_kN_m):.8f}",
            ]
            response_lines = [
                f"桩头 X 位移 (mm): {float(r.get('head_disp_x_mm', 0.0)):.8f}",
                f"桩头 Y 位移 (mm): {float(r.get('head_disp_y_mm', 0.0)):.8f}",
                f"桩头 Z 位移 (mm, +up/-down): {ResultFormatter.global_z_mm_for_display(float(r.get('head_disp_z_mm', 0.0))):.8f}",
                f"最大轴力绝对值 (kN): {float(r.get('max_abs_axial', 0.0)):.8f}",
                f"最大弯矩绝对值 (kN*m): {float(r.get('max_abs_moment', 0.0)):.8f}",
                f"网格数/单元数: {element_count}",
                f"节点数: {node_count}",
            ]
            return ResultFormatter._build_summary(
                "组合分析结果摘要",
                basic_lines,
                response_lines,
            )
        basic_lines = [
            "Units: m, kN, kPa",
            f"Analysis mode: {ResultFormatter._analysis_label('combined')}",
            f"Pile Length (m): {inp.pile_length_m:.6f}",
            f"Pile Diameter (m): {inp.pile_diameter_m:.6f}",
            f"Axial Layer Count: {len(inp.axial_layers)}",
            f"Lateral Layer Count: {len(inp.lateral_layers)}",
            f"Fz load depth (m): {float(inp.loads.get('Fz', {}).get('depth_m', 0.0)):.8f}",
            f"Fx load depth (m): {float(inp.loads.get('Fx', {}).get('depth_m', 0.0)):.8f}",
            f"My load depth (m): {float(inp.loads.get('My', {}).get('depth_m', 0.0)):.8f}",
            f"Fz (kN, +up/-down): {float(inp.fz_kN):.8f}",
            f"Fx (kN): {float(inp.fx_kN):.8f}",
            f"Fy (kN): {float(inp.fy_kN):.8f}",
            f"Mx (kN*m): {float(inp.mx_kN_m):.8f}",
            f"My (kN*m): {float(inp.my_kN_m):.8f}",
            f"Mz (kN*m): {float(inp.mz_kN_m):.8f}",
        ]
        response_lines = [
            f"Head displacement X (mm): {float(r.get('head_disp_x_mm', 0.0)):.8f}",
            f"Head displacement Y (mm): {float(r.get('head_disp_y_mm', 0.0)):.8f}",
            f"Head displacement Z (mm, +up/-down): {ResultFormatter.global_z_mm_for_display(float(r.get('head_disp_z_mm', 0.0))):.8f}",
            f"Max |axial force| (kN): {float(r.get('max_abs_axial', 0.0)):.8f}",
            f"Max |moment| (kN*m): {float(r.get('max_abs_moment', 0.0)):.8f}",
            f"Mesh element count: {element_count}",
            f"Node count: {node_count}",
        ]
        return ResultFormatter._build_summary(
            "Combined Analysis Summary",
            basic_lines,
            response_lines,
        )

    @staticmethod
    def group_summary(inp: GroupInput, r: Dict) -> str:
        payload = dict(inp.payload)
        first_pile = ResultFormatter._first_pile(r)
        ref_element_count = ResultFormatter._element_count(first_pile, depth_key="depths_ele_from_head", node_key="depths_from_head")
        ref_node_count = ResultFormatter._node_count(first_pile, "depths_from_head")
        if _is_zh():
            basic_lines = [
                "单位: m, kN, kPa",
                f"分析模式: {ResultFormatter._analysis_label('group')}",
                f"桩数: {int(r.get('pile_count', len(r.get('piles', []))))}",
                f"土层数量: {len(payload.get('layers', []))}",
                *ResultFormatter._format_group_load_lines(payload),
            ]
            response_lines = [
                f"承台 X 位移 (mm): {float(r.get('cap_disp_x_mm', 0.0)):.8f}",
                f"承台 Y 位移 (mm): {float(r.get('cap_disp_y_mm', 0.0)):.8f}",
                f"承台 Z 位移 (mm, +up/-down): {ResultFormatter.global_z_mm_for_display(float(r.get('cap_disp_z_mm', 0.0))):.8f}",
                f"最大轴力绝对值 (kN): {float(r.get('max_abs_axial', 0.0)):.8f}",
                f"最大弯矩绝对值 (kN*m): {float(r.get('max_abs_moment', 0.0)):.8f}",
                f"参考网格数/单元数: {ref_element_count}",
                f"参考节点数: {ref_node_count}",
            ]
            return ResultFormatter._build_summary(
                "群桩分析结果摘要",
                basic_lines,
                response_lines,
            )
        basic_lines = [
            "Units: m, kN, kPa",
            f"Analysis mode: {ResultFormatter._analysis_label('group')}",
            f"Pile count: {int(r.get('pile_count', len(r.get('piles', []))))}",
            f"Soil layer count: {len(payload.get('layers', []))}",
            *ResultFormatter._format_group_load_lines(payload),
        ]
        response_lines = [
            f"Cap displacement X (mm): {float(r.get('cap_disp_x_mm', 0.0)):.8f}",
            f"Cap displacement Y (mm): {float(r.get('cap_disp_y_mm', 0.0)):.8f}",
            f"Cap displacement Z (mm, +up/-down): {ResultFormatter.global_z_mm_for_display(float(r.get('cap_disp_z_mm', 0.0))):.8f}",
            f"Max |axial force| (kN): {float(r.get('max_abs_axial', 0.0)):.8f}",
            f"Max |shear| (kN): {float(r.get('max_abs_shear', 0.0)):.8f}",
            f"Max |moment| (kN*m): {float(r.get('max_abs_moment', 0.0)):.8f}",
            f"Reference mesh element count: {ref_element_count}",
            f"Reference node count: {ref_node_count}",
        ]
        return ResultFormatter._build_summary(
            "Group Pile Analysis Summary",
            basic_lines,
            response_lines,
        )
