# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Callable, Dict, List, Tuple, Union

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)
from language_manager import get_language
from ui_localization import translate_text


HelpPayload = Union[str, Tuple[str, str], Callable[[], Union[str, Tuple[str, str]]]]


AXIAL_SOIL_GUIDES: Dict[str, Dict[str, object]] = {
    "API Sand": {
        "scope": "Driven pile axial sand model for sands where shaft friction and tip resistance follow API-style correlations.",
        "parameters": [
            ("gammaEff", "Unit Weight (kN/m^3)", "Typical reference: 17 to 21."),
            ("phiDegree", "Friction Angle (deg)", "Official API/RSPile guide points are commonly checked at 15, 20, 25, 30, 35 deg."),
            ("K", "Coefficient of Lateral Earth Pressure", "Quick check: about 0.8 to 1.2."),
            ("Nq", "Bearing Capacity Factor", "Official guide anchors: phi 15/20/25/30/35 deg -> Nq 8/12/20/40/50."),
            ("max_unit_skin_friction", "Maximum Unit Skin Friction (kPa)", "Official guide anchors: phi 15/20/25/30/35 deg -> 47.8/67.0/81.3/95.7/114.8 kPa."),
            ("max_unit_end_bearing", "Maximum Unit End Bearing Resistance (kPa)", "Official guide anchors: phi 15/20/25/30/35 deg -> 1900/2900/4800/9600/12000 kPa."),
        ],
    },
    "API Clay": {
        "scope": "Driven pile axial clay model for undrained clay response and adhesion-style shaft resistance.",
        "parameters": [
            ("gammaEff", "Unit Weight (kN/m^3)", "Typical reference: 16 to 20."),
            ("cu", "Undrained Shear Strength (kPa)", "Typical reference: soft 15 to 40, medium 40 to 75, stiff 75 to 150+."),
            ("cu_remolded", "Remolded Shear Strength (kPa)", "Usually lower than intact cu; rough quick check about 40% to 90% of intact cu."),
            ("max_unit_skin_friction", "Maximum Unit Skin Friction (kPa)", "Use project or benchmark values directly."),
            ("max_unit_end_bearing", "Maximum Unit End Bearing Resistance (kPa)", "Use project or benchmark values directly."),
        ],
    },
    "Drilled Sand": {
        "scope": "Drilled shaft / bored pile axial sand model using ultimate shaft and tip capacities.",
        "parameters": [
            ("gammaEff", "Unit Weight (kN/m^3)", "Typical reference: 17 to 21."),
            ("max_unit_skin_friction", "Ultimate Shear Resistance (kPa)", "Use project or benchmark values directly."),
            ("max_unit_end_bearing", "Ultimate End Bearing Resistance (kPa)", "Use project or benchmark values directly."),
        ],
    },
    "Drilled Clay": {
        "scope": "Drilled shaft / bored pile axial clay model using ultimate shaft and tip capacities.",
        "parameters": [
            ("gammaEff", "Unit Weight (kN/m^3)", "Typical reference: 16 to 20."),
            ("max_unit_skin_friction", "Ultimate Shear Resistance (kPa)", "Use project or benchmark values directly."),
            ("max_unit_end_bearing", "Ultimate End Bearing Resistance (kPa)", "Use project or benchmark values directly."),
        ],
    },
    "Elastic": {
        "scope": "Simplified linear axial spring model for placeholder studies or calibration cases.",
        "parameters": [
            ("ks", "ks (Elastic)", "No universal range; use calibration or benchmark values."),
            ("kb", "kb (Elastic tip)", "No universal range; use calibration or benchmark values."),
        ],
    },
}


LATERAL_SOIL_GUIDES: Dict[str, Dict[str, object]] = {
    "API Method for Sand": {
        "scope": "Classic API sand p-y model for lateral response in sandy soil.",
        "parameters": [
            ("gammaEff", "Unit Weight (kN/m^3)", "Typical reference: 17 to 21."),
            ("phiDegree", "Friction Angle (deg)", "Typical reference: 28 to 42."),
            ("k_modulus", "Initial Modulus of Subgrade Reaction (kN/m^3)", "Tutorial-scale examples are often a few thousand."),
        ],
    },
    "Sand": {
        "scope": "Sand p-y model with explicit Kpy stiffness input.",
        "parameters": [
            ("gammaEff", "Unit Weight (kN/m^3)", "Typical reference: 17 to 21."),
            ("phiDegree", "Friction Angle (deg)", "Typical reference: 28 to 42."),
            ("kpy", "Kpy (kN/m^3)", "Common example-scale values range from thousands to tens of thousands."),
        ],
    },
    "Soft Clay Soil": {
        "scope": "Soft clay p-y model for low-strength undrained clay.",
        "parameters": [
            ("gammaEff", "Unit Weight (kN/m^3)", "Typical reference: 16 to 18."),
            ("cu", "Undrained Shear Strength (kPa)", "Typical reference: 15 to 40."),
            ("eps50", "Strain Factor", "Typical reference: 0.01 to 0.03."),
        ],
    },
    "Submerged Stiff Clay": {
        "scope": "Submerged stiff clay p-y model for undrained stiff clay below free water.",
        "parameters": [
            ("gammaEff", "Unit Weight (kN/m^3)", "Typical reference: 17 to 20."),
            ("cu", "Undrained Shear Strength (kPa)", "Typical reference: 75 to 150+."),
            ("eps50", "Strain Factor", "Typical reference: 0.003 to 0.01."),
            ("k_modulus", "Ks (kN/m^3)", "Usually much larger than soft-clay cases."),
        ],
    },
    "Dry Stiff Clay": {
        "scope": "Dry stiff clay p-y model for stiff clay without submerged conditions.",
        "parameters": [
            ("gammaEff", "Unit Weight (kN/m^3)", "Typical reference: 17 to 20."),
            ("cu", "Undrained Shear Strength (kPa)", "Typical reference: 75 to 150+."),
            ("eps50", "Strain Factor", "Typical reference: 0.003 to 0.01."),
        ],
    },
    "Modified Stiff Clay without Free Water": {
        "scope": "Modified stiff clay p-y model for stiff clay without free water using modified stiffness rules.",
        "parameters": [
            ("gammaEff", "Unit Weight (kN/m^3)", "Typical reference: 17 to 20."),
            ("cu", "Undrained Shear Strength (kPa)", "Typical reference: 75 to 150+."),
            ("eps50", "Strain Factor", "Typical reference: 0.003 to 0.01."),
            ("k_modulus", "Initial Stiffness (kN/m^3)", "Usually much larger than soft-clay cases."),
        ],
    },
    "Weak Rock": {
        "scope": "Weak rock p-y model for weathered or weak rock mass response.",
        "parameters": [
            ("gammaEff", "Unit Weight (kN/m^3)", "Typical reference: 18 to 24."),
            ("qu", "Uniaxial Compressive Strength (kPa)", "Usually starts from low thousands of kPa upward."),
            ("Eir", "Reaction Modulus of Rock (kPa)", "Usually much larger than soil stiffness values."),
            ("RQD", "Rock Quality Designation (RQD) (%)", "Reference scale: 0 to 100."),
            ("krm", "Constant Krm", "Small empirical constant; match the selected reference model."),
        ],
    },
    "Elastic": {
        "scope": "Simplified linear lateral spring model.",
        "parameters": [
            ("kh", "kh (Elastic)", "No universal range; use calibration or benchmark values."),
        ],
    },
}


LEGACY_HELP_TEXTS: Dict[str, str] = {
    "pile_shape": "Pile Shape\n\nChoose Circle for solid circular pile and Pipe for tubular pile.",
    "pile_diameter": "Pile Diameter\n\nOuter diameter used for section properties and spring calculations.",
    "pile_thickness": "Pile Thickness\n\nPipe wall thickness used when the pile shape is Pipe.",
    "pile_E": "Elastic Modulus E\n\nWhen a standard concrete grade is selected, E is filled automatically from the SectionMC concrete rule. Switch to User Define to edit it manually.",
    "pile_free_length": "Free Length\n\nUnsupported pile length above the embedded portion when applicable.",
    "pile_ele_size": "Element Size\n\nSet 0 for automatic discretization; smaller values increase fidelity and runtime.",
    "pile_geometry": "Pile Geometry\n\nLength is the controlling value. Changing top updates bottom; changing bottom updates top.",
    "cap_length_x": "Cap Length X\n\nPlan dimension in the global X direction.",
    "cap_length_y": "Cap Length Y\n\nPlan dimension in the global Y direction.",
    "cap_height": "Cap Height\n\nCap thickness / height.",
    "soil_layers": "Soil Layers\n\nDefine one layer per row. The first layer top is fixed at 0 and depths downward are negative in the GUI.",
    "axial_load_table": "Axial Load Input\n\nCompression is negative and tension is positive in global Z.",
    "lateral_load_table": "Lateral Load Input\n\nPure lateral analysis uses Fx, Fy, Mx and My only. Axial force belongs to combined analysis.",
    "combined_load_table": "Combined Load Input\n\nInput axial force, shear and moment in one table.",
    "group_load_table": "Group Load Input\n\nEach row is one load case. Enter cap-plane X and Y first, then fill the six global load components Fx, Fy, Fz, Mx, My and Mz for that row.",
    "pile_layout": "Pile Layout\n\nEach row defines one pile location, pile type and connectivity.",
    "connectivity": "Connectivity\n\nFixed is rotationally restrained, Pinned is released, Restrained is intermediate.",
}


def _guide_map(analysis_kind: str) -> Dict[str, Dict[str, object]]:
    return AXIAL_SOIL_GUIDES if analysis_kind == "axial" else LATERAL_SOIL_GUIDES


def _guide_parameters(analysis_kind: str, soil_type: str) -> List[Tuple[str, str, str]]:
    guide = _guide_map(analysis_kind).get(soil_type, {})
    params = guide.get("parameters", [])
    return list(params) if isinstance(params, list) else []


def soil_model_help(analysis_kind: str, soil_type: str) -> Tuple[str, str]:
    guide = _guide_map(analysis_kind).get(soil_type, {})
    if not guide:
        return ("Material Help", f"No help text has been prepared yet for {soil_type}.")
    lines = [soil_type, "", f"Applicable use\n{guide.get('scope', '')}", "", "Panel parameters"]
    for _key, label, reference in _guide_parameters(analysis_kind, soil_type):
        lines.append(f"- {label}: {reference}")
    return f"{soil_type} - {'Axial' if analysis_kind == 'axial' else 'Lateral'}", "\n".join(lines)


def parameter_help(analysis_kind: str, soil_type: str, param_key: str) -> Tuple[str, str]:
    for key, label, reference in _guide_parameters(analysis_kind, soil_type):
        if key == param_key:
            return (
                f"{label} - {soil_type}",
                (
                    f"{label}\n\n"
                    f"Current model\n{soil_type} ({'Axial' if analysis_kind == 'axial' else 'Lateral'})\n\n"
                    f"How it is used\n{_guide_map(analysis_kind).get(soil_type, {}).get('scope', '')}\n\n"
                    f"Reference notes\n{reference}"
                ),
            )
    return (
        f"{param_key} - {soil_type}",
        f"No parameter help has been prepared yet for {param_key} under {soil_type}.",
    )


def _resolve_help_payload(payload: HelpPayload) -> Tuple[str, str]:
    if callable(payload):
        resolved = payload()
        if isinstance(resolved, tuple):
            return resolved
        return "Help", str(resolved)
    if isinstance(payload, tuple):
        return payload
    return "Help", LEGACY_HELP_TEXTS.get(payload, "No help text has been prepared for this item yet.")


def show_help_message(parent: QWidget, payload: HelpPayload):
    title, text = _resolve_help_payload(payload)
    if get_language() == "zh":
        title = {
            "Help": "帮助",
            "Material Help": "材料帮助",
        }.get(title, title)
    QMessageBox.information(parent, title, text)


def create_help_button(parent: QWidget, payload: HelpPayload) -> QPushButton:
    button = QPushButton("?")
    button.setParent(parent)
    button.setFixedSize(18, 18)
    button.setStyleSheet(
        """
        QPushButton {
            background-color: #4b8fe2;
            color: white;
            border: 1px solid #3f7dca;
            border-radius: 9px;
            font-weight: bold;
            padding: 0px;
        }
        QPushButton:hover {
            background-color: #5a9af0;
        }
        """
    )
    button.setToolTip("显示帮助" if get_language() == "zh" else "Show help")
    button.clicked.connect(lambda: show_help_message(parent, payload))
    return button


def wrap_widget_with_help(parent: QWidget, widget: QWidget, payload: HelpPayload | None) -> QWidget:
    row = QWidget(parent)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    layout.addWidget(widget, 1)
    if payload is None:
        placeholder = QWidget(row)
        placeholder.setFixedSize(18, 18)
        placeholder.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addWidget(placeholder)
    else:
        layout.addWidget(create_help_button(parent, payload))
    return row


def add_form_row_with_help(
    form: QFormLayout,
    parent: QWidget,
    label_text: str,
    widget: QWidget,
    payload: HelpPayload,
) -> QWidget:
    row = wrap_widget_with_help(parent, widget, payload)
    form.addRow(label_text, row)
    return row


class HelpManualDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Soil Material Help")
        self.resize(980, 700)
        layout = QVBoxLayout(self)
        mode_tabs = QTabWidget()
        layout.addWidget(mode_tabs)
        mode_tabs.addTab(self._build_soil_mode_tabs("axial", AXIAL_SOIL_GUIDES), "Axial")
        mode_tabs.addTab(self._build_soil_mode_tabs("lateral", LATERAL_SOIL_GUIDES), "Lateral")

    def _build_soil_mode_tabs(self, analysis_kind: str, guides: Dict[str, Dict[str, object]]) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        soil_tabs = QTabWidget()
        layout.addWidget(soil_tabs)
        for soil_type in guides:
            html = self._soil_html(analysis_kind, soil_type)
            soil_tabs.addTab(self._build_html_page(html), soil_type)
        return page

    def _soil_html(self, analysis_kind: str, soil_type: str) -> str:
        guide = _guide_map(analysis_kind)[soil_type]
        items = "".join(
            f"<li><b>{label}</b>: {reference}</li>"
            for _key, label, reference in _guide_parameters(analysis_kind, soil_type)
        )
        return (
            f"<h2>{soil_type}</h2>"
            f"<p><b>Applicable use:</b> {guide.get('scope', '')}</p>"
            f"<h3>Panel Parameters</h3>"
            f"<ul>{items}</ul>"
        )

    def _build_html_page(self, html: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(html)
        layout.addWidget(browser)
        return page


def show_help_message(parent: QWidget, payload: HelpPayload):
    title, text = _resolve_help_payload(payload)
    language = get_language()
    if language == "zh":
        title = str(translate_text(title, language))
        text = str(translate_text(text, language))
    QMessageBox.information(parent, title, text)


def create_help_button(parent: QWidget, payload: HelpPayload) -> QPushButton:
    button = QPushButton("?")
    button.setParent(parent)
    button.setFixedSize(18, 18)
    button.setStyleSheet(
        """
        QPushButton {
            background-color: #4b8fe2;
            color: white;
            border: 1px solid #3f7dca;
            border-radius: 9px;
            font-weight: bold;
            padding: 0px;
        }
        QPushButton:hover {
            background-color: #5a9af0;
        }
        """
    )
    button.setToolTip(str(translate_text("Show help", get_language())))
    button.clicked.connect(lambda: show_help_message(parent, payload))
    return button


def show_help_manual(parent: QWidget | None = None):
    dialog = HelpManualDialog(parent)
    dialog.exec()


def build_reference_html() -> str:
    return (
        f"<h3>{translate_text('Soil Material Help', get_language())}</h3>"
        f"<p>{translate_text('Use the Help menu to open the soil material manual.', get_language())}</p>"
    )


_ORIGINAL_HELP_INIT = HelpManualDialog.__init__
_ORIGINAL_SOIL_HTML = HelpManualDialog._soil_html


def _localized_help_init(self, parent: QWidget | None = None):
    _ORIGINAL_HELP_INIT(self, parent)
    language = get_language()
    self.setWindowTitle(str(translate_text("Soil Material Help", language)))
    tabs = self.findChildren(QTabWidget)
    if tabs:
        mode_tabs = tabs[0]
        if mode_tabs.count() >= 2:
            mode_tabs.setTabText(0, str(translate_text("Axial", language)))
            mode_tabs.setTabText(1, str(translate_text("Lateral", language)))


def _localized_soil_html(self, analysis_kind: str, soil_type: str) -> str:
    html = _ORIGINAL_SOIL_HTML(self, analysis_kind, soil_type)
    language = get_language()
    return str(translate_text(html, language))


HelpManualDialog.__init__ = _localized_help_init
HelpManualDialog._soil_html = _localized_soil_html


_ZH_SOIL_GUIDES: Dict[str, Dict[str, Dict[str, object]]] = {
    "axial": {
        "API Sand": {
            "scope": "用于砂土中打入桩轴向分析，侧摩阻和端阻按 API 风格相关公式计算。",
            "parameters": [
                ("gammaEff", "土有效重度 (kN/m^3)", "常用参考范围：17 到 21。"),
                ("phiDegree", "内摩擦角 (deg)", "常按 15、20、25、30、35 度等典型值校核。"),
                ("K", "侧向土压力系数", "可先按约 0.8 到 1.2 进行快速估计。"),
                ("Nq", "端承力系数 Nq", "典型参考：phi=15/20/25/30/35 度时，Nq 约为 8/12/20/40/50。"),
                ("max_unit_skin_friction", "极限单位侧摩阻 (kPa)", "典型参考：phi=15/20/25/30/35 度时，约为 47.8/67.0/81.3/95.7/114.8 kPa。"),
                ("max_unit_end_bearing", "极限单位端阻力 (kPa)", "典型参考：phi=15/20/25/30/35 度时，约为 1900/2900/4800/9600/12000 kPa。"),
            ],
        },
        "API Clay": {
            "scope": "用于黏土中打入桩轴向分析，考虑不排水抗剪强度与黏附型侧阻。",
            "parameters": [
                ("gammaEff", "土有效重度 (kN/m^3)", "常用参考范围：16 到 20。"),
                ("cu", "不排水抗剪强度 cu (kPa)", "常用参考：软土 15 到 40，中等 40 到 75，硬塑到坚硬 75 到 150 以上。"),
                ("cu_remolded", "重塑不排水抗剪强度 (kPa)", "通常小于原状 cu，可粗略取原状值的 40% 到 90%。"),
                ("max_unit_skin_friction", "极限单位侧摩阻 (kPa)", "建议直接采用项目经验值、试验值或对标值。"),
                ("max_unit_end_bearing", "极限单位端阻力 (kPa)", "建议直接采用项目经验值、试验值或对标值。"),
            ],
        },
        "Drilled Sand": {
            "scope": "用于砂土中钻孔灌注桩轴向分析，直接输入极限侧阻与端阻。",
            "parameters": [
                ("gammaEff", "土有效重度 (kN/m^3)", "常用参考范围：17 到 21。"),
                ("max_unit_skin_friction", "极限侧阻 (kPa)", "建议直接采用项目经验值、试验值或对标值。"),
                ("max_unit_end_bearing", "极限端阻 (kPa)", "建议直接采用项目经验值、试验值或对标值。"),
            ],
        },
        "Drilled Clay": {
            "scope": "用于黏土中钻孔灌注桩轴向分析，直接输入极限侧阻与端阻。",
            "parameters": [
                ("gammaEff", "土有效重度 (kN/m^3)", "常用参考范围：16 到 20。"),
                ("max_unit_skin_friction", "极限侧阻 (kPa)", "建议直接采用项目经验值、试验值或对标值。"),
                ("max_unit_end_bearing", "极限端阻 (kPa)", "建议直接采用项目经验值、试验值或对标值。"),
            ],
        },
        "Elastic": {
            "scope": "用于占位分析、参数标定或对比分析的简化线弹性轴向弹簧模型。",
            "parameters": [
                ("ks", "ks（弹性）", "无统一推荐值，建议依据标定结果或对标算例确定。"),
                ("kb", "kb（桩端弹性）", "无统一推荐值，建议依据标定结果或对标算例确定。"),
            ],
        },
    },
    "lateral": {
        "API Method for Sand": {
            "scope": "经典 API 砂土 p-y 模型，用于砂土中桩的横向响应分析。",
            "parameters": [
                ("gammaEff", "土有效重度 (kN/m^3)", "常用参考范围：17 到 21。"),
                ("phiDegree", "内摩擦角 (deg)", "常用参考范围：28 到 42。"),
                ("k_modulus", "地基反力初始模量 (kN/m^3)", "教程或示例中通常为几千量级起步。"),
            ],
        },
        "Sand": {
            "scope": "显式输入 Kpy 刚度参数的砂土 p-y 模型。",
            "parameters": [
                ("gammaEff", "土有效重度 (kN/m^3)", "常用参考范围：17 到 21。"),
                ("phiDegree", "内摩擦角 (deg)", "常用参考范围：28 到 42。"),
                ("kpy", "Kpy (kN/m^3)", "常见示例值范围从几千到几万不等。"),
            ],
        },
        "Soft Clay Soil": {
            "scope": "用于低强度不排水软黏土的横向 p-y 模型。",
            "parameters": [
                ("gammaEff", "土有效重度 (kN/m^3)", "常用参考范围：16 到 18。"),
                ("cu", "不排水抗剪强度 cu (kPa)", "常用参考范围：15 到 40。"),
                ("eps50", "应变系数 eps50", "常用参考范围：0.01 到 0.03。"),
            ],
        },
        "Submerged Stiff Clay": {
            "scope": "用于地下水位以下硬黏土的不排水横向 p-y 模型。",
            "parameters": [
                ("gammaEff", "土有效重度 (kN/m^3)", "常用参考范围：17 到 20。"),
                ("cu", "不排水抗剪强度 cu (kPa)", "常用参考范围：75 到 150 以上。"),
                ("eps50", "应变系数 eps50", "常用参考范围：0.003 到 0.01。"),
                ("k_modulus", "Ks (kN/m^3)", "通常显著大于软黏土工况。"),
            ],
        },
        "Dry Stiff Clay": {
            "scope": "用于非浸水条件下硬黏土的横向 p-y 模型。",
            "parameters": [
                ("gammaEff", "土有效重度 (kN/m^3)", "常用参考范围：17 到 20。"),
                ("cu", "不排水抗剪强度 cu (kPa)", "常用参考范围：75 到 150 以上。"),
                ("eps50", "应变系数 eps50", "常用参考范围：0.003 到 0.01。"),
            ],
        },
        "Modified Stiff Clay without Free Water": {
            "scope": "用于无自由水条件下硬黏土的修正刚度 p-y 模型。",
            "parameters": [
                ("gammaEff", "土有效重度 (kN/m^3)", "常用参考范围：17 到 20。"),
                ("cu", "不排水抗剪强度 cu (kPa)", "常用参考范围：75 到 150 以上。"),
                ("eps50", "应变系数 eps50", "常用参考范围：0.003 到 0.01。"),
                ("k_modulus", "初始刚度 (kN/m^3)", "通常显著大于软黏土工况。"),
            ],
        },
        "Weak Rock": {
            "scope": "用于风化岩或弱岩岩体响应的横向 p-y 模型。",
            "parameters": [
                ("gammaEff", "土有效重度 (kN/m^3)", "常用参考范围：18 到 24。"),
                ("qu", "单轴抗压强度 qu (kPa)", "通常从数千 kPa 起步，并随岩性增加。"),
                ("Eir", "岩体反力模量 Eir (kPa)", "通常远大于一般土层刚度。"),
                ("RQD", "岩石质量指标 RQD (%)", "取值范围通常为 0 到 100。"),
                ("krm", "经验常数 Krm", "属于较小经验参数，建议与所选模型保持一致。"),
            ],
        },
        "Elastic": {
            "scope": "简化线弹性横向弹簧模型。",
            "parameters": [
                ("kh", "kh（弹性）", "无统一推荐值，建议依据标定结果或对标算例确定。"),
            ],
        },
    },
}


_ZH_LEGACY_HELP_TEXTS: Dict[str, str] = {
    "pile_shape": "桩截面形状\n\nCircle 表示实心圆桩，Pipe 表示空心管桩。",
    "pile_diameter": "桩径\n\n外径参数，用于截面性质和弹簧刚度计算。",
    "pile_thickness": "壁厚\n\n当桩形为 Pipe 时，需要输入管壁厚度。",
    "pile_E": "弹性模量 E\n\n当选择标准混凝土等级时，E 会按 SectionMC 的混凝土规则自动填写；切换到 User Define 后可手动修改。",
    "pile_free_length": "自由段长度\n\n表示埋置段以上的无侧向约束桩长。",
    "pile_ele_size": "单元尺寸\n\n输入 0 表示自动离散；数值越小，计算精度通常越高，但计算时间也会增加。",
    "pile_geometry": "桩几何参数\n\n桩长是控制量。修改桩顶标高会联动更新桩底，修改桩底也会反向更新桩顶。",
    "cap_length_x": "承台 X 向尺寸\n\n承台在全局 X 方向上的平面尺寸。",
    "cap_length_y": "承台 Y 向尺寸\n\n承台在全局 Y 方向上的平面尺寸。",
    "cap_height": "承台高度\n\n承台厚度或高度。",
    "soil_layers": "土层设置\n\n每一行表示一层土。首层顶面固定为 0，界面中向下深度用负值输入。",
    "axial_load_table": "轴向荷载输入\n\n全局 Z 方向中，受压为负，受拉为正。",
    "lateral_load_table": "横向荷载输入\n\n纯横向分析通常只使用 Fx、Fy、Mx、My；轴力应放在组合分析中输入。",
    "combined_load_table": "组合荷载输入\n\n在同一张表中输入轴力、剪力与弯矩。",
    "group_load_table": "群桩荷载输入\n\n每一行对应一个荷载工况。先输入承台平面内的 X、Y 坐标，再填写 Fx、Fy、Fz、Mx、My、Mz 六个全局荷载分量。",
    "pile_layout": "桩位布置\n\n每一行定义一根桩的位置、桩型以及连接方式。",
    "connectivity": "连接方式\n\nFixed 表示转动约束，Pinned 表示铰接释放，Restrained 表示部分约束。",
}


_ORIGINAL_SOIL_MODEL_HELP = soil_model_help
_ORIGINAL_PARAMETER_HELP = parameter_help
_ORIGINAL_RESOLVE_HELP_PAYLOAD = _resolve_help_payload


def _zh_guide(analysis_kind: str, soil_type: str) -> Dict[str, object]:
    return _ZH_SOIL_GUIDES.get(analysis_kind, {}).get(soil_type, {})


def _localized_soil_model_help(analysis_kind: str, soil_type: str) -> Tuple[str, str]:
    if get_language() != "zh":
        return _ORIGINAL_SOIL_MODEL_HELP(analysis_kind, soil_type)
    guide = _zh_guide(analysis_kind, soil_type)
    if not guide:
        return ("材料帮助", f"尚未为 {soil_type} 准备帮助内容。")
    lines = [soil_type, "", f"适用范围\n{guide.get('scope', '')}", "", "面板参数"]
    for _key, label, reference in guide.get("parameters", []):
        lines.append(f"- {label}: {reference}")
    return f"{soil_type} - {'轴向' if analysis_kind == 'axial' else '横向'}", "\n".join(lines)


def _localized_parameter_help(analysis_kind: str, soil_type: str, param_key: str) -> Tuple[str, str]:
    if get_language() != "zh":
        return _ORIGINAL_PARAMETER_HELP(analysis_kind, soil_type, param_key)
    guide = _zh_guide(analysis_kind, soil_type)
    for key, label, reference in guide.get("parameters", []):
        if key == param_key:
            return (
                f"{label} - {soil_type}",
                (
                    f"{label}\n\n"
                    f"当前模型\n{soil_type}（{'轴向' if analysis_kind == 'axial' else '横向'}）\n\n"
                    f"用途说明\n{guide.get('scope', '')}\n\n"
                    f"参考说明\n{reference}"
                ),
            )
    return (f"{param_key} - {soil_type}", f"尚未为 {soil_type} 模型下的参数 {param_key} 准备帮助内容。")


def _localized_resolve_help_payload(payload: HelpPayload) -> Tuple[str, str]:
    if get_language() != "zh":
        return _ORIGINAL_RESOLVE_HELP_PAYLOAD(payload)
    if callable(payload):
        resolved = payload()
        if isinstance(resolved, tuple):
            return resolved
        return "帮助", str(resolved)
    if isinstance(payload, tuple):
        return payload
    return "帮助", _ZH_LEGACY_HELP_TEXTS.get(payload, "该项帮助内容尚未准备。")


def _localized_soil_html(self, analysis_kind: str, soil_type: str) -> str:
    if get_language() != "zh":
        return _ORIGINAL_SOIL_HTML(self, analysis_kind, soil_type)
    guide = _zh_guide(analysis_kind, soil_type)
    if not guide:
        return f"<h2>{soil_type}</h2><p>该土模型的中文说明尚未准备。</p>"
    items = "".join(
        f"<li><b>{label}</b>: {reference}</li>"
        for _key, label, reference in guide.get("parameters", [])
    )
    return (
        f"<h2>{soil_type}</h2>"
        f"<p><b>适用范围：</b>{guide.get('scope', '')}</p>"
        f"<h3>面板参数</h3>"
        f"<ul>{items}</ul>"
    )


soil_model_help = _localized_soil_model_help
parameter_help = _localized_parameter_help
_resolve_help_payload = _localized_resolve_help_payload
HelpManualDialog._soil_html = _localized_soil_html
