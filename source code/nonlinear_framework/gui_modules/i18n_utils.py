# -*- coding: utf-8 -*-

from __future__ import annotations

from language_manager import get_language


_ZH_MAP = {
    "New Soil Material": "新建土层材料",
    "Material name:": "材料名称:",
    "Name Exists": "名称已存在",
    "Material name already exists.": "材料名称已存在。",
    "Cannot Delete": "无法删除",
    "At least one material must remain.": "至少需要保留一个材料。",
    "At least one soil material must remain.": "至少需要保留一个土层材料。",
    "Rename Soil Material": "重命名土层材料",
    "New Pile Type": "新建桩型",
    "Pile type name:": "桩型名称:",
    "Pile type name already exists.": "桩型名称已存在。",
    "At least one pile type must remain.": "至少需要保留一个桩型。",
    "Rename Pile Type": "重命名桩型",
    "Current Material:": "当前材料:",
    "Current Type:": "当前类型:",
    "New": "新建",
    "Delete": "删除",
    "Rename": "重命名",
    "Pick Layer Color": "选择层颜色",
    "Add Layer": "添加土层",
    "Delete Layer": "删除土层",
    "Add Pile": "添加桩",
    "Delete Pile": "删除桩",
    "Soil layers are referenced to the ground line. The first layer top is fixed at 0 m; enter negative values downward.": "土层以地面线为基准。首层顶面固定为 0 m，向下输入负值。",
    "Sign follows the global Z axis: downward compression is negative, upward tension is positive.": "符号遵循全局 Z 轴：向下受压为负，向上受拉为正。",
    "Depth is from the pile head. Enter negative values downward.": "深度以桩顶为基准，向下输入负值。",
    "The first layer top is fixed at 0. Enter negative values downward from the ground line.": "首层顶面固定为 0，向下相对地面线输入负值。",
    "The global coordinate origin is fixed at the cap center. Cap bottom follows the highest pile top elevation.": "全局坐标原点固定在承台中心。承台底面随最高桩顶高程自动调整。",
    "Coordinates are in the cap plane with the cap center as the origin.": "坐标位于承台平面内，并以承台中心为原点。",
    "Loads use the global X/Y/Z coordinate system. X and Y are the load coordinates on the cap plane.": "荷载采用全局 X/Y/Z 坐标系。X 和 Y 为承台平面内的加载坐标。",
}


_ZH_MAP.update(
    {
        "Load Case": "荷载工况",
        "Add Case": "添加工况",
        "Delete Case": "删除工况",
        "Case": "工况",
        "Load": "荷载",
        "X Coordinate (m)": "X 坐标 (m)",
        "Y Coordinate (m)": "Y 坐标 (m)",
        "Z (m)": "Z 坐标 (m)",
        "Axial Force N (kN)": "轴向力 N (kN)",
        "Fz (kN)": "Fz (kN)",
        "Fx (kN)": "Fx (kN)",
        "Fy (kN)": "Fy (kN)",
        "Mx (kN*m)": "Mx (kN*m)",
        "My (kN*m)": "My (kN*m)",
        "Mz (kN*m)": "Mz (kN*m)",
        "Nx (kN)": "Nx (kN)",
        "Ny (kN)": "Ny (kN)",
        "Nz (kN)": "Nz (kN)",
        "Pile": "桩",
    }
)


def tr(text: str) -> str:
    if get_language() != "zh":
        return text
    return _ZH_MAP.get(text, text)


_ZH_MAP.update(
    {
        "Material Parameters": "材料参数",
        "Soil model": "土模型",
        "Unit Weight (kN/m^3)": "重度 (kN/m^3)",
        "Friction Angle (deg)": "内摩擦角 (deg)",
        "Kpy (kN/m^3)": "Kpy (kN/m^3)",
        "Initial Modulus of Subgrade Reaction (kN/m^3)": "地基反力系数初值 (kN/m^3)",
        "Undrained Shear Strength (kPa)": "不排水抗剪强度 (kPa)",
        "Strain Factor": "应变系数",
        "Uniaxial Compressive Strength (kPa)": "单轴抗压强度 (kPa)",
        "Reaction Modulus of Rock (kPa)": "岩体反力模量 (kPa)",
        "Rock Quality Designation (RQD) (%)": "岩石质量指标 RQD (%)",
        "Constant Krm": "常数 Krm",
        "krm": "Krm",
        "kh (Elastic)": "kh（弹性）",
        "Initial Stiffness (kN/m^3)": "初始刚度 (kN/m^3)",
        "Ks (kN/m^3)": "Ks (kN/m^3)",
        "Soft Clay Soil": "软黏土",
        "Submerged Stiff Clay": "浸水硬黏土",
        "Dry Stiff Clay": "干硬黏土",
        "Modified Stiff Clay without Free Water": "无自由水修正硬黏土",
        "Weak Rock": "软弱岩层",
        "API Method for Sand": "API 砂土方法",
        "Sand": "砂土",
        "Elastic": "弹性",
    }
)
