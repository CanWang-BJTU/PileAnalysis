# -*- coding: utf-8 -*-

import math
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtCore import Slot
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from core.mesh_spec import representative_element_size
from gui_modules.concrete_material_utils import (
    USER_DEFINED_CONCRETE,
    concrete_elastic_modulus_kpa,
    concrete_material_options,
    infer_concrete_material_from_E,
)
from gui_modules.fiber_section_widget import FiberSectionWidget
from gui_modules.help_system import (
    create_help_button,
    parameter_help,
    soil_model_help,
    wrap_widget_with_help,
)
from gui_modules.i18n_utils import tr
from gui_modules.interaction_utils import install_enter_navigation
from gui_modules.mesh_settings_widget import MeshSettingsWidget

from gui_modules.axial_panel import SOIL_TYPES, default_color_for_soil
from gui_modules.lateral_panel import LATERAL_SOIL_TYPES


def default_color_for_combined_lateral(soil_type: str) -> str:
    palette = {
        "API Method for Sand": "#f7e7a8",
        "Sand": "#fde2b8",
        "Soft Clay Soil": "#e8c7cf",
        "Submerged Stiff Clay": "#d9cde8",
        "Dry Stiff Clay": "#d6e8cf",
        "Modified Stiff Clay without Free Water": "#cfe1e8",
        "Weak Rock": "#dcd6cf",
        "Elastic": "#cfe6e8",
    }
    return palette.get(soil_type, "#dfe8d8")


class CombinedPanel:
    """Shared soil-layer GUI for 2D single-pile combined analysis.

    Current design:
    - One shared soil material list (name + color per layer material)
    - One shared soil-layer arrangement page
    - Axial / Lateral tabs only hold their own parameter definitions
    """

    def __init__(self):
        self._loading = False
        self._pile_geometry_loading = False
        self._change_callback: Optional[Callable[[], None]] = None
        self.materials: List[Dict] = []

        self.page_soil_material = self._create_soil_material_page()
        self.page_soil_layers = self._create_soil_layers_page()
        self.page_pile = self._create_pile_page()
        self.page_load = self._create_load_page()

        self._init_default_materials()
        self._add_layer_row(0.0, -10.0, "Layer-1")
        self._add_layer_row(-10.0, -19.0, "Layer-2")
        self._update_section()

    def set_change_callback(self, callback: Optional[Callable[[], None]]):
        self._change_callback = callback

    def _notify_changed(self):
        if self._loading:
            return
        if callable(self._change_callback):
            try:
                self._change_callback()
            except Exception:
                pass

    def mount_to_tabs(self, tabs: QTabWidget):
        tabs.clear()
        tabs.addTab(self._wrap_scroll_page(self.page_soil_material), "Soil Material")
        tabs.addTab(self._wrap_scroll_page(self.page_soil_layers), "Soil Layers")
        tabs.addTab(self._wrap_scroll_page(self.page_pile), "Pile Definition")
        tabs.addTab(self._wrap_scroll_page(self.page_load), "Load Input")

    def _wrap_scroll_page(self, page: QWidget) -> QWidget:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        area.setWidget(page)
        return area

    def _placeholder_page(self, text: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet("color: #909090; font-size: 17px;")
        layout.addStretch()
        layout.addWidget(label)
        layout.addStretch()
        return page

    def _spin(self, value: float, vmin: float, vmax: float, decimals: int = 3) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setDecimals(decimals)
        box.setRange(vmin, vmax)
        box.setValue(value)
        return box

    def _default_axial_params(self, soil_type: str) -> Dict[str, float]:
        if soil_type == "API Sand":
            return {"gammaEff": 18.0, "phiDegree": 30.0, "K": 0.8, "Nq": 20.0}
        if soil_type in ("API Clay", "Drilled Clay"):
            return {"gammaEff": 18.0, "cu": 80.0}
        if soil_type == "Drilled Sand":
            return {"gammaEff": 18.0, "phiDegree": 30.0, "Nq": 20.0}
        return {"ks": 100000.0, "kb": 100000.0}

    def _default_lateral_params(self, soil_type: str) -> Dict[str, float]:
        if soil_type == "API Method for Sand":
            return {"gammaEff": 20.0, "phiDegree": 30.0, "k_modulus": 5400.0}
        if soil_type == "Sand":
            return {"gammaEff": 20.0, "phiDegree": 30.0, "kpy": 6800.0}
        if soil_type == "Soft Clay Soil":
            return {"gammaEff": 20.0, "cu": 25.0, "eps50": 0.02}
        if soil_type == "Submerged Stiff Clay":
            return {"gammaEff": 20.0, "cu": 100.0, "eps50": 0.005, "k_modulus": 135000.0}
        if soil_type == "Dry Stiff Clay":
            return {"gammaEff": 20.0, "cu": 100.0, "eps50": 0.005}
        if soil_type == "Modified Stiff Clay without Free Water":
            return {"gammaEff": 20.0, "cu": 100.0, "eps50": 0.005, "k_modulus": 200000.0}
        if soil_type == "Weak Rock":
            return {"gammaEff": 20.0, "qu": 3450.0, "Eir": 7240000.0, "RQD": 0.0, "krm": 0.0005}
        return {"kh": 10000.0}

    def _init_default_materials(self):
        self.materials = [
            {
                "name": "Layer-1",
                "bg_color": "#e8c7cf",
                "axial_type": "API Clay",
                "axial_params": self._default_axial_params("API Clay"),
                "lateral_type": "Soft Clay Soil",
                "lateral_params": self._default_lateral_params("Soft Clay Soil"),
            },
            {
                "name": "Layer-2",
                "bg_color": "#f7e7a8",
                "axial_type": "API Sand",
                "axial_params": self._default_axial_params("API Sand"),
                "lateral_type": "Sand",
                "lateral_params": self._default_lateral_params("Sand"),
            },
        ]
        self._refresh_material_selector()
        self.material_selector.setCurrentIndex(0)
        self._load_material(0)

    def _material_names(self) -> List[str]:
        return [str(m.get("name", "")) for m in self.materials]

    def _create_soil_material_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        manager_group = QGroupBox("Soil Material Management")
        manager_layout = QVBoxLayout(manager_group)
        manager_layout.setContentsMargins(6, 6, 6, 6)
        manager_layout.setSpacing(6)

        top = QHBoxLayout()
        top.addWidget(QLabel(tr("Current Material:")))
        self.material_selector = QComboBox()
        top.addWidget(self.material_selector, 1)
        self.btn_pick_color = QPushButton(tr("Pick Layer Color"))
        self.color_preview = QLabel()
        self.color_preview.setMinimumHeight(24)
        self.color_preview.setMinimumWidth(90)
        self.color_preview.setMaximumWidth(110)
        top.addWidget(self.btn_pick_color)
        top.addWidget(self.color_preview)
        self.btn_new = QPushButton(tr("New"))
        self.btn_delete = QPushButton(tr("Delete"))
        self.btn_rename = QPushButton(tr("Rename"))
        top.addWidget(self.btn_new)
        top.addWidget(self.btn_delete)
        top.addWidget(self.btn_rename)
        manager_layout.addLayout(top)

        self.material_tabs = QTabWidget()
        self.material_tabs.addTab(self._create_axial_material_tab(), "Axial")
        self.material_tabs.addTab(self._create_lateral_material_tab(), "Lateral")
        manager_layout.addWidget(self.material_tabs)

        root.addWidget(manager_group)
        root.addStretch()

        self.material_selector.currentIndexChanged.connect(self._load_material)
        self.btn_pick_color.clicked.connect(self._pick_color)
        self.btn_new.clicked.connect(self._new_material)
        self.btn_delete.clicked.connect(self._delete_material)
        self.btn_rename.clicked.connect(self._rename_material)
        self.axial_type.currentTextChanged.connect(self._on_axial_type_changed)
        self.lateral_type.currentTextChanged.connect(self._on_lateral_type_changed)

        for widget in [
            self.ax_gamma,
            self.ax_phi,
            self.ax_cu,
            self.ax_K,
            self.ax_ks,
            self.ax_kb,
            self.ax_Nq,
            self.lt_gamma,
            self.lt_phi,
            self.lt_kpy,
            self.lt_kmod,
            self.lt_cu,
            self.lt_eps50,
            self.lt_J,
            self.lt_ca,
            self.lt_qu,
            self.lt_Eir,
            self.lt_RQD,
            self.lt_krm,
            self.lt_kh,
        ]:
            widget.valueChanged.connect(self._on_param_changed)

        return page

    def _create_axial_material_tab(self) -> QWidget:
        page = QWidget()
        self.axial_form = QFormLayout(page)
        self.axial_type = QComboBox()
        self.axial_type.addItems(SOIL_TYPES)
        self.axial_form.addRow(
            tr("Soil model"),
            wrap_widget_with_help(page, self.axial_type, lambda: soil_model_help("axial", self.axial_type.currentText())),
        )

        self.ax_gamma = self._spin(18.0, 0.0, 1000.0, 3)
        self.ax_phi = self._spin(30.0, 0.0, 80.0, 3)
        self.ax_cu = self._spin(80.0, 0.0, 50000.0, 3)
        self.ax_cu_remolded = self._spin(20.0, 0.0, 50000.0, 3)
        self.ax_K = self._spin(0.8, 0.0, 100.0, 3)
        self.ax_ks = self._spin(100000.0, 0.0, 1.0e9, 3)
        self.ax_kb = self._spin(100000.0, 0.0, 1.0e9, 3)
        self.ax_Nq = self._spin(20.0, 0.0, 500.0, 3)
        self.ax_max_skin = self._spin(1000000.0, 0.0, 1.0e9, 3)
        self.ax_max_tip = self._spin(1000000.0, 0.0, 1.0e9, 3)

        self._ax_rows: Dict[str, Dict] = {}

        def add_ax(key: str, label: str, widget: QWidget, types: List[str]):
            row = QWidget()
            lay = QHBoxLayout(row)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(widget)
            help_map = {
                "gammaEff": "unit_weight",
                "phiDegree": "phi",
                "cu": "cu",
                "cu_remolded": "cu_remolded",
                "K": "K_api_sand",
                "ks": "k_modulus",
                "kb": "max_tip",
                "Nq": "Nq",
                "max_unit_skin_friction": "max_skin",
                "max_unit_end_bearing": "max_tip",
            }
            lay.addWidget(
                create_help_button(
                    page,
                    lambda key=key: parameter_help("axial", self.axial_type.currentText(), key),
                )
            )
            row_index = self.axial_form.rowCount()
            self.axial_form.addRow(tr(label), row)
            self._ax_rows[key] = {"row": row, "row_index": row_index, "types": set(types), "label": label}

        add_ax("gammaEff", "Unit Weight (kN/m^3)", self.ax_gamma, ["API Sand", "API Clay", "Drilled Sand", "Drilled Clay"])
        add_ax("phiDegree", "Friction Angle (deg)", self.ax_phi, ["API Sand"])
        add_ax("cu", "Undrained Shear Strength (kPa)", self.ax_cu, ["API Clay"])
        add_ax("cu_remolded", "Remolded Shear Strength (kPa)", self.ax_cu_remolded, ["API Clay"])
        add_ax("K", "Coefficient of Lateral Earth Pressure", self.ax_K, ["API Sand"])
        add_ax("ks", "ks (Elastic)", self.ax_ks, ["Elastic"])
        add_ax("kb", "kb (Elastic tip)", self.ax_kb, ["Elastic"])
        add_ax("Nq", "Bearing Capacity Factor", self.ax_Nq, ["API Sand"])
        add_ax("max_unit_skin_friction", "Maximum Unit Skin Friction (kPa)", self.ax_max_skin, ["API Sand", "API Clay", "Drilled Sand", "Drilled Clay"])
        add_ax("max_unit_end_bearing", "Maximum Unit End Bearing Resistance (kPa)", self.ax_max_tip, ["API Sand", "API Clay", "Drilled Sand", "Drilled Clay"])
        return page

    def _create_lateral_material_tab(self) -> QWidget:
        page = QWidget()
        self.lateral_form = QFormLayout(page)
        self.lateral_type = QComboBox()
        self.lateral_type.addItems(LATERAL_SOIL_TYPES)
        self.lateral_form.addRow(
            tr("Soil model"),
            wrap_widget_with_help(page, self.lateral_type, lambda: soil_model_help("lateral", self.lateral_type.currentText())),
        )

        self.lt_gamma = self._spin(18.0, 0.0, 1000.0, 3)
        self.lt_phi = self._spin(35.0, 0.0, 80.0, 3)
        self.lt_kpy = self._spin(16300.0, 0.0, 1.0e8, 3)
        self.lt_kmod = self._spin(0.0, 0.0, 1.0e8, 3)
        self.lt_cu = self._spin(32.0, 0.0, 50000.0, 3)
        self.lt_eps50 = self._spin(0.02, 0.0, 1.0, 5)
        self.lt_J = self._spin(0.5, 0.0, 10.0, 4)
        self.lt_ca = self._spin(100.0, 0.0, 50000.0, 3)
        self.lt_qu = self._spin(1000.0, 0.0, 1.0e8, 3)
        self.lt_Eir = self._spin(7240000.0, 0.0, 1.0e10, 3)
        self.lt_RQD = self._spin(0.0, 0.0, 100.0, 3)
        self.lt_krm = self._spin(0.0005, 0.0, 100.0, 6)
        self.lt_kh = self._spin(10000.0, 0.0, 1.0e9, 3)

        self._lt_rows: Dict[str, Dict] = {}

        def add_lt(key: str, label: str, widget: QWidget, types: List[str]):
            row = QWidget()
            lay = QHBoxLayout(row)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(widget)
            help_map = {
                "gammaEff": "unit_weight",
                "phiDegree": "phi",
                "kpy": "kpy",
                "k_modulus": "k_modulus",
                "cu": "cu",
                "eps50": "eps50",
                "qu": "qu",
                "Eir": "Eir",
                "RQD": "RQD",
                "krm": "krm",
                "kh": "k_modulus",
            }
            lay.addWidget(
                create_help_button(
                    page,
                    lambda key=key: parameter_help("lateral", self.lateral_type.currentText(), key),
                )
            )
            row_index = self.lateral_form.rowCount()
            self.lateral_form.addRow(tr(label), row)
            self._lt_rows[key] = {
                "row": row,
                "row_index": row_index,
                "types": set(types),
                "label": self.lateral_form.labelForField(row),
                "default_label": label,
            }

        non_elastic = [
            "API Method for Sand",
            "Sand",
            "Soft Clay Soil",
            "Submerged Stiff Clay",
            "Dry Stiff Clay",
            "Modified Stiff Clay without Free Water",
            "Weak Rock",
        ]
        add_lt("gammaEff", "Unit Weight (kN/m^3)", self.lt_gamma, non_elastic)
        add_lt("phiDegree", "Friction Angle (deg)", self.lt_phi, ["API Method for Sand", "Sand"])
        add_lt("kpy", "Kpy (kN/m^3)", self.lt_kpy, ["Sand"])
        add_lt("k_modulus", "Initial Modulus of Subgrade Reaction (kN/m^3)", self.lt_kmod, ["API Method for Sand", "Submerged Stiff Clay", "Modified Stiff Clay without Free Water"])
        add_lt("cu", "Undrained Shear Strength (kPa)", self.lt_cu, ["Soft Clay Soil", "Submerged Stiff Clay", "Dry Stiff Clay", "Modified Stiff Clay without Free Water"])
        add_lt("eps50", "Strain Factor", self.lt_eps50, ["Soft Clay Soil", "Submerged Stiff Clay", "Dry Stiff Clay", "Modified Stiff Clay without Free Water"])
        add_lt("J", "J", self.lt_J, [])
        add_lt("ca", "ca (kPa)", self.lt_ca, [])
        add_lt("qu", "Uniaxial Compressive Strength (kPa)", self.lt_qu, ["Weak Rock"])
        add_lt("Eir", "Reaction Modulus of Rock (kPa)", self.lt_Eir, ["Weak Rock"])
        add_lt("RQD", "Rock Quality Designation (RQD) (%)", self.lt_RQD, ["Weak Rock"])
        add_lt("krm", "Constant Krm", self.lt_krm, ["Weak Rock"])
        add_lt("kh", "kh (Elastic)", self.lt_kh, ["Elastic"])
        return page

    def _create_soil_layers_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        self.layer_table = QTableWidget(0, 3)
        self.layer_table.setHorizontalHeaderLabels(["Top z (-m)", "Bottom z (-m)", "Soil Material"])
        self.layer_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.layer_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.layer_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.layer_table)
        install_enter_navigation(self.layer_table, [0, 1], add_row_fn=lambda: self._add_layer_row())
        tool_row = QHBoxLayout()
        tool_row.addWidget(create_help_button(page, "soil_layers"))
        tool_row.addStretch()
        root.addLayout(tool_row)

        hint = QLabel(tr("Tip: Press Enter to jump between depth cells."))
        hint.setStyleSheet("color: #2980b9; font-size: 9pt; padding: 2px 0;")
        hint.setWordWrap(True)
        root.addWidget(hint)
        note = QLabel(tr("The first layer top is fixed at 0. Enter negative values downward from the ground line."))
        note.setStyleSheet("color: #808080;")
        root.addWidget(note)

        btns = QHBoxLayout()
        self.btn_add_layer = QPushButton(tr("Add Layer"))
        self.btn_delete_layer = QPushButton(tr("Delete Layer"))
        btns.addWidget(self.btn_add_layer)
        btns.addWidget(self.btn_delete_layer)
        btns.addStretch()
        root.addLayout(btns)

        self.btn_add_layer.clicked.connect(lambda: self._add_layer_row())
        self.btn_delete_layer.clicked.connect(self._delete_layer_row)
        self.layer_table.itemChanged.connect(self._on_layer_item_changed)
        return page

    def _create_pile_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.fiber_section_widget = FiberSectionWidget(page)
        self.fiber_section_widget.set_total_length_provider(lambda: self.pile_len.value())
        self.fiber_section_widget.set_change_callback(self._notify_changed)
        root.addWidget(self.fiber_section_widget, 0, Qt.AlignmentFlag.AlignTop)

        form_host = QGroupBox("Elastic Section Parameters")
        self.elastic_section_box = form_host
        form = QFormLayout(form_host)
        self.pile_form = form
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        self.pile_shape = QComboBox()
        self.pile_shape.addItems(["Pipe", "Circle"])
        self.pile_shape.setCurrentText("Pipe")
        self.pile_top_z = self._spin(0.0, -1000.0, 1000.0, 4)
        self.pile_bottom_z = self._spin(-19.0, -1000.0, 1000.0, 4)
        self.pile_len = self._spin(19.0, 0.1, 1000.0, 4)
        self.pile_d = self._spin(0.5, 0.01, 20.0, 4)
        self.pile_t = self._spin(0.02, 0.001, 5.0, 4)
        self.pile_concrete_material = QComboBox()
        self.pile_concrete_material.addItems(concrete_material_options())
        self.pile_E = self._spin(2.0e8, 1.0, 1.0e12, 3)
        self.geometry_table = QTableWidget(1, 3)
        self.geometry_table.setHorizontalHeaderLabels(["Pile top z (m)", "Pile bottom z (m)", "Length (m)"])
        self.geometry_table.verticalHeader().setVisible(False)
        self.geometry_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.geometry_table.setCellWidget(0, 0, self.pile_top_z)
        self.geometry_table.setCellWidget(0, 1, self.pile_bottom_z)
        self.geometry_table.setCellWidget(0, 2, self.pile_len)
        self.geometry_table.setFixedHeight(44)
        self.geometry_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._set_pile_editor_widths(
            [
                self.pile_shape,
                self.pile_d,
                self.pile_t,
                self.pile_concrete_material,
                self.pile_E,
                self.pile_top_z,
                self.pile_bottom_z,
                self.pile_len,
            ]
        )

        self.pile_shape_row = wrap_widget_with_help(page, self.pile_shape, "pile_shape")
        self.pile_d_row = wrap_widget_with_help(page, self.pile_d, "pile_diameter")
        self.pile_t_row = wrap_widget_with_help(page, self.pile_t, "pile_thickness")
        form.addRow("Pile shape", self.pile_shape_row)
        form.addRow("Diameter (m)", self.pile_d_row)
        self.pile_t_row_index = form.rowCount()
        form.addRow("Thickness (m, pipe)", self.pile_t_row)
        form.addRow("Concrete material", wrap_widget_with_help(page, self.pile_concrete_material, None))
        form.addRow("Elastic modulus E (kPa)", wrap_widget_with_help(page, self.pile_E, "pile_E"))
        self.fiber_section_widget.set_external_elastic_widget(form_host)

        geometry_box = QGroupBox("Pile Geometry")
        geometry_layout = QFormLayout(geometry_box)
        geometry_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        geometry_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        geometry_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        geometry_layout.setHorizontalSpacing(10)
        geometry_layout.setVerticalSpacing(8)
        geometry_layout.addRow("Pile geometry", self.geometry_table)
        root.addWidget(geometry_box, 0, Qt.AlignmentFlag.AlignTop)
        root.addStretch(1)

        self.pile_top_z.valueChanged.connect(self._sync_pile_bottom_from_top)
        self.pile_bottom_z.valueChanged.connect(self._sync_pile_top_from_bottom)
        self.pile_len.valueChanged.connect(self._sync_pile_bottom_from_length)
        self.pile_top_z.editingFinished.connect(self._sync_pile_bottom_from_top)
        self.pile_bottom_z.editingFinished.connect(self._sync_pile_top_from_bottom)
        self.pile_len.editingFinished.connect(self._sync_pile_bottom_from_length)
        self.pile_shape.currentTextChanged.connect(self._update_section)
        self.pile_d.valueChanged.connect(self._update_section)
        self.pile_t.valueChanged.connect(self._update_section)
        self.pile_top_z.valueChanged.connect(lambda *_: self._notify_changed())
        self.pile_bottom_z.valueChanged.connect(lambda *_: self._notify_changed())
        self.pile_shape.currentTextChanged.connect(lambda *_: self._notify_changed())
        self.pile_len.valueChanged.connect(lambda *_: self._notify_changed())
        self.pile_len.valueChanged.connect(lambda *_: self.fiber_section_widget.refresh_external_constraints())
        self.fiber_section_widget.changed.connect(self._sync_section_model_visibility)
        self.pile_d.valueChanged.connect(lambda *_: self._notify_changed())
        self.pile_t.valueChanged.connect(lambda *_: self._notify_changed())
        self.pile_concrete_material.currentTextChanged.connect(self._on_pile_concrete_material_changed)
        self.pile_E.valueChanged.connect(lambda *_: self._notify_changed())
        self._sync_pile_concrete_material_from_E(self.pile_E.value())
        self._sync_section_model_visibility()
        return page

    def _sync_section_model_visibility(self):
        if hasattr(self, "elastic_section_box"):
            self.elastic_section_box.setVisible(True)

    def _apply_pile_concrete_material(self, material_name: str):
        is_user_defined = str(material_name) == USER_DEFINED_CONCRETE
        self.pile_E.setReadOnly(not is_user_defined)
        self.pile_E.setButtonSymbols(
            QDoubleSpinBox.ButtonSymbols.UpDownArrows
            if is_user_defined
            else QDoubleSpinBox.ButtonSymbols.NoButtons
        )
        if not is_user_defined:
            self.pile_E.blockSignals(True)
            self.pile_E.setValue(concrete_elastic_modulus_kpa(str(material_name)))
            self.pile_E.blockSignals(False)

    def _sync_pile_concrete_material_from_E(self, E_kpa: float):
        material_name = infer_concrete_material_from_E(E_kpa)
        self.pile_concrete_material.blockSignals(True)
        idx = self.pile_concrete_material.findText(material_name)
        if idx >= 0:
            self.pile_concrete_material.setCurrentIndex(idx)
        self.pile_concrete_material.blockSignals(False)
        self._apply_pile_concrete_material(material_name)

    @Slot(str)
    def _on_pile_concrete_material_changed(self, material_name: str):
        self._apply_pile_concrete_material(material_name)
        self._notify_changed()

    def _set_pile_editor_widths(self, widgets: List[QWidget]):
        for widget in widgets:
            widget.setMinimumWidth(180)
            widget.setMaximumWidth(340)
        self.geometry_table.setMinimumWidth(420)
        self.geometry_table.setMaximumWidth(620)
        self.geometry_table.setFixedHeight(44)

    def _create_load_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.load_table = QTableWidget(0, 5)
        self.load_table.horizontalHeader().setVisible(False)
        for col in range(5):
            self.load_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        self.load_table.verticalHeader().setVisible(False)
        self.load_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.load_table)
        tool_row = QHBoxLayout()
        tool_row.addWidget(create_help_button(page, "combined_load_table"))
        tool_row.addStretch()
        layout.addLayout(tool_row)
        btn_row = QHBoxLayout()
        self.btn_add_load_case = QPushButton(tr("Add Case"))
        self.btn_delete_load_case = QPushButton(tr("Delete Case"))
        btn_row.addWidget(self.btn_add_load_case)
        btn_row.addWidget(self.btn_delete_load_case)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        self.mesh_settings_widget = MeshSettingsWidget(page)
        self.mesh_settings_widget.set_total_length_provider(lambda: self.pile_len.value())
        self.mesh_settings_widget.set_change_callback(self._notify_changed)
        layout.addWidget(self.mesh_settings_widget)
        self.btn_add_load_case.clicked.connect(lambda: self._add_load_case_row())
        self.btn_delete_load_case.clicked.connect(self._delete_load_case_row)
        self.load_table.itemChanged.connect(lambda *_: self._notify_changed())
        self._add_load_case_row()
        return page

    def _make_readonly_item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setBackground(QBrush(QColor("#f5f5f5")))
        font = QFont()
        font.setBold(True)
        item.setFont(font)
        return item

    def _make_value_item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    def _add_load_case_row(
        self,
        depth_ui: float = 0.0,
        fz: float = -100.0,
        fx: float = 50.0,
        fy: float = 0.0,
        mx: float = 0.0,
        my: float = 100.0,
    ):
        base = self.load_table.rowCount()
        for _ in range(4):
            self.load_table.insertRow(self.load_table.rowCount())
        self.load_table.setRowHeight(base, 24)
        self.load_table.setRowHeight(base + 1, 30)
        self.load_table.setRowHeight(base + 2, 24)
        self.load_table.setRowHeight(base + 3, 30)

        self.load_table.setItem(base, 0, self._make_readonly_item(tr("Load Case")))
        self.load_table.setSpan(base, 0, 1, 2)
        self.load_table.setItem(base, 2, self._make_readonly_item(tr("Z (m)")))
        self.load_table.setSpan(base, 2, 1, 3)

        case_item = self._make_readonly_item(f"{tr('Case')} {(base // 4) + 1}")
        self.load_table.setItem(base + 1, 0, case_item)
        self.load_table.setSpan(base + 1, 0, 1, 2)
        self.load_table.setItem(base + 1, 2, self._make_value_item(f"{float(depth_ui):.3f}"))
        self.load_table.setSpan(base + 1, 2, 1, 3)

        for col, text in enumerate(["Fz (kN)", "Fx (kN)", "Fy (kN)", "Mx (kN*m)", "My (kN*m)"]):
            self.load_table.setItem(base + 2, col, self._make_readonly_item(tr(text)))
        for col, value in enumerate([fz, fx, fy, mx, my]):
            self.load_table.setItem(base + 3, col, self._make_value_item(f"{float(value):.3f}"))
        self._update_load_table_height()

    @Slot()
    def _delete_load_case_row(self):
        current_row = self.load_table.currentRow()
        row_count = self.load_table.rowCount()
        if row_count < 4:
            return
        base = row_count - 4 if current_row < 0 else (current_row // 4) * 4
        for _ in range(4):
            self.load_table.removeRow(base)
        for base_row in range(0, self.load_table.rowCount(), 4):
            item = self.load_table.item(base_row + 1, 0)
            if item is None:
                item = self._make_readonly_item("")
                self.load_table.setItem(base_row + 1, 0, item)
            item.setText(f"{tr('Case')} {(base_row // 4) + 1}")
            self.load_table.setSpan(base_row + 1, 0, 1, 2)
            self.load_table.setSpan(base_row + 1, 2, 1, 3)
        if self.load_table.rowCount() == 0:
            self._add_load_case_row()
        self._update_load_table_height()
        self._notify_changed()

    def _update_load_table_height(self):
        if self.load_table.rowCount() == 0:
            self.load_table.setFixedHeight(120)
            return
        total_h = sum(self.load_table.rowHeight(row) or 28 for row in range(self.load_table.rowCount())) + 6
        self.load_table.setFixedHeight(min(max(total_h, 120), 260))

    def _refresh_material_selector(self):
        names = self._material_names()
        current = self.material_selector.currentText()
        self.material_selector.blockSignals(True)
        self.material_selector.clear()
        self.material_selector.addItems(names)
        if current in names:
            self.material_selector.setCurrentText(current)
        self.material_selector.blockSignals(False)

        for row in range(self.layer_table.rowCount()):
            combo = self.layer_table.cellWidget(row, 2)
            if not isinstance(combo, QComboBox):
                continue
            chosen = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(names)
            if chosen in names:
                combo.setCurrentText(chosen)
            elif names:
                combo.setCurrentIndex(0)
            combo.blockSignals(False)

    def _set_color_preview(self, color_hex: str):
        self.color_preview.setStyleSheet(f"border: 1px solid #aaaaaa; background-color: {color_hex};")

    def _set_row_visible(self, form: QFormLayout, row_index: int, row_widget: QWidget, visible: bool):
        if hasattr(form, "setRowVisible"):
            form.setRowVisible(row_index, visible)
        else:
            row_widget.setVisible(visible)

    def _refresh_axial_visibility(self, soil_type: str):
        for key, info in self._ax_rows.items():
            self._set_row_visible(self.axial_form, info["row_index"], info["row"], soil_type in info["types"])
            label_widget = self.axial_form.labelForField(info["row"])
            if label_widget is not None:
                if key == "max_unit_skin_friction" and soil_type in {"Drilled Sand", "Drilled Clay"}:
                    label_widget.setText(tr("Ultimate Shear Resistance (kPa)"))
                elif key == "max_unit_end_bearing" and soil_type in {"Drilled Sand", "Drilled Clay"}:
                    label_widget.setText(tr("Ultimate End Bearing Resistance (kPa)"))
                else:
                    label_widget.setText(tr(info["label"]))

    def _refresh_lateral_visibility(self, soil_type: str):
        label_overrides = {
            ("k_modulus", "API Method for Sand"): "Initial Modulus of Subgrade Reaction (kN/m^3)",
            ("k_modulus", "Submerged Stiff Clay"): "Ks (kN/m^3)",
            ("k_modulus", "Modified Stiff Clay without Free Water"): "Initial Stiffness (kN/m^3)",
            ("krm", "Weak Rock"): "Constant Krm",
        }
        for info in self._lt_rows.values():
            self._set_row_visible(self.lateral_form, info["row_index"], info["row"], soil_type in info["types"])
            label_widget = info.get("label")
            if label_widget is not None:
                key = next((k for k, v in self._lt_rows.items() if v is info), None)
                label_widget.setText(tr(label_overrides.get((key, soil_type), info["default_label"])))

    def _axial_params_from_editor(self, soil_type: str) -> Dict[str, float]:
        p: Dict[str, float] = {}
        if soil_type in ("API Sand", "API Clay", "Drilled Sand", "Drilled Clay"):
            p["gammaEff"] = self.ax_gamma.value()
        if soil_type == "API Sand":
            p["phiDegree"] = self.ax_phi.value()
            p["Nq"] = self.ax_Nq.value()
            p["K"] = self.ax_K.value()
            p["max_unit_skin_friction"] = self.ax_max_skin.value()
            p["max_unit_end_bearing"] = self.ax_max_tip.value()
        if soil_type == "API Clay":
            p["cu"] = self.ax_cu.value()
            p["cu_remolded"] = self.ax_cu_remolded.value()
            p["max_unit_skin_friction"] = self.ax_max_skin.value()
            p["max_unit_end_bearing"] = self.ax_max_tip.value()
        if soil_type in ("Drilled Sand", "Drilled Clay"):
            p["max_unit_skin_friction"] = self.ax_max_skin.value()
            p["max_unit_end_bearing"] = self.ax_max_tip.value()
        if soil_type == "Elastic":
            p["ks"] = self.ax_ks.value()
            p["kb"] = self.ax_kb.value()
        return p

    def _lateral_params_from_editor(self, soil_type: str) -> Dict[str, float]:
        p: Dict[str, float] = {}
        if soil_type in ("API Method for Sand", "Sand", "Soft Clay Soil", "Submerged Stiff Clay", "Dry Stiff Clay", "Modified Stiff Clay without Free Water", "Weak Rock"):
            p["gammaEff"] = self.lt_gamma.value()
        if soil_type in ("API Method for Sand", "Sand"):
            p["phiDegree"] = self.lt_phi.value()
        if soil_type == "Sand":
            p["kpy"] = self.lt_kpy.value()
        if soil_type == "API Method for Sand":
            p["k_modulus"] = self.lt_kmod.value()
        if soil_type in ("Soft Clay Soil", "Submerged Stiff Clay", "Dry Stiff Clay", "Modified Stiff Clay without Free Water"):
            p["cu"] = self.lt_cu.value()
            p["eps50"] = self.lt_eps50.value()
        if soil_type == "Submerged Stiff Clay":
            p["k_modulus"] = self.lt_kmod.value()
        if soil_type == "Modified Stiff Clay without Free Water":
            p["k_modulus"] = self.lt_kmod.value()
        if soil_type == "Weak Rock":
            p["qu"] = self.lt_qu.value()
            p["Eir"] = self.lt_Eir.value()
            p["RQD"] = self.lt_RQD.value()
            p["krm"] = self.lt_krm.value()
        if soil_type == "Elastic":
            p["kh"] = self.lt_kh.value()
        return p

    @Slot(int)
    def _load_material(self, index: int):
        if index < 0 or index >= len(self.materials):
            return
        mat = self.materials[index]
        self._loading = True
        self._set_color_preview(str(mat.get("bg_color", "#f7e7a8")))

        axial_type = str(mat.get("axial_type", "API Sand"))
        self.axial_type.setCurrentText(axial_type)
        ax = dict(mat.get("axial_params", {}))
        self.ax_gamma.setValue(float(ax.get("gammaEff", 18.0)))
        self.ax_phi.setValue(float(ax.get("phiDegree", 30.0)))
        self.ax_cu.setValue(float(ax.get("cu", 80.0)))
        self.ax_cu_remolded.setValue(float(ax.get("cu_remolded", 20.0)))
        self.ax_K.setValue(float(ax.get("K", 0.8)))
        self.ax_ks.setValue(float(ax.get("ks", 100000.0)))
        self.ax_kb.setValue(float(ax.get("kb", 100000.0)))
        self.ax_Nq.setValue(float(ax.get("Nq", 20.0)))
        self.ax_max_skin.setValue(float(ax.get("max_unit_skin_friction", 1000000.0)))
        self.ax_max_tip.setValue(float(ax.get("max_unit_end_bearing", 1000000.0)))
        self._refresh_axial_visibility(axial_type)

        lateral_type = str(mat.get("lateral_type", "Sand"))
        self.lateral_type.setCurrentText(lateral_type)
        lt = dict(mat.get("lateral_params", {}))
        self.lt_gamma.setValue(float(lt.get("gammaEff", 18.0)))
        self.lt_phi.setValue(float(lt.get("phiDegree", 35.0)))
        self.lt_kpy.setValue(float(lt.get("kpy", 16300.0)))
        self.lt_kmod.setValue(float(lt.get("k_modulus", 0.0)))
        self.lt_cu.setValue(float(lt.get("cu", 32.0)))
        self.lt_eps50.setValue(float(lt.get("eps50", 0.02)))
        self.lt_J.setValue(float(lt.get("J", 0.5)))
        self.lt_ca.setValue(float(lt.get("ca", 100.0)))
        self.lt_qu.setValue(float(lt.get("qu", 1000.0)))
        self.lt_Eir.setValue(float(lt.get("Eir", 7240000.0)))
        self.lt_RQD.setValue(float(lt.get("RQD", 0.0)))
        self.lt_krm.setValue(float(lt.get("krm", 0.0005)))
        self.lt_kh.setValue(float(lt.get("kh", 10000.0)))
        self._refresh_lateral_visibility(lateral_type)

        self._loading = False

    @Slot(str)
    def _on_axial_type_changed(self, soil_type: str):
        if self._loading:
            return
        idx = self.material_selector.currentIndex()
        if idx < 0:
            return
        self.materials[idx]["axial_type"] = soil_type
        self.materials[idx]["axial_params"] = self._default_axial_params(soil_type)
        current_color = str(self.materials[idx].get("bg_color", "")).strip()
        if not current_color:
            self.materials[idx]["bg_color"] = default_color_for_soil(soil_type)
        self._load_material(idx)

    @Slot(str)
    def _on_lateral_type_changed(self, soil_type: str):
        if self._loading:
            return
        idx = self.material_selector.currentIndex()
        if idx < 0:
            return
        self.materials[idx]["lateral_type"] = soil_type
        self.materials[idx]["lateral_params"] = self._default_lateral_params(soil_type)
        current_color = str(self.materials[idx].get("bg_color", "")).strip()
        if not current_color:
            self.materials[idx]["bg_color"] = default_color_for_combined_lateral(soil_type)
        self._load_material(idx)

    @Slot()
    def _on_param_changed(self):
        if self._loading:
            return
        idx = self.material_selector.currentIndex()
        if idx < 0:
            return
        axial_type = self.axial_type.currentText()
        lateral_type = self.lateral_type.currentText()
        self.materials[idx]["axial_type"] = axial_type
        self.materials[idx]["axial_params"] = self._axial_params_from_editor(axial_type)
        self.materials[idx]["lateral_type"] = lateral_type
        self.materials[idx]["lateral_params"] = self._lateral_params_from_editor(lateral_type)
        self._notify_changed()

    @Slot()
    def _pick_color(self):
        idx = self.material_selector.currentIndex()
        if idx < 0:
            return
        color = QColorDialog.getColor()
        if color.isValid():
            self.materials[idx]["bg_color"] = color.name()
            self._set_color_preview(color.name())
            self._notify_changed()

    @Slot()
    def _new_material(self):
        names = set(self._material_names())
        i = 1
        while f"Material-{i}" in names:
            i += 1
        name, ok = QInputDialog.getText(self.page_soil_material, tr("New Soil Material"), tr("Material name:"), text=f"Material-{i}")
        name = name.strip()
        if not ok or not name:
            return
        if name in names:
            QMessageBox.warning(self.page_soil_material, tr("Name Exists"), tr("Material name already exists."))
            return
        self.materials.append(
            {
                "name": name,
                "bg_color": "#dfe8d8",
                "axial_type": "API Sand",
                "axial_params": self._default_axial_params("API Sand"),
                "lateral_type": "Sand",
                "lateral_params": self._default_lateral_params("Sand"),
            }
        )
        self._refresh_material_selector()
        self.material_selector.setCurrentText(name)
        self._load_material(self.material_selector.currentIndex())
        self._notify_changed()

    @Slot()
    def _delete_material(self):
        if len(self.materials) <= 1:
            QMessageBox.warning(self.page_soil_material, tr("Cannot Delete"), tr("At least one material must remain."))
            return
        idx = self.material_selector.currentIndex()
        if idx < 0:
            return
        removed_name = self.materials[idx]["name"]
        del self.materials[idx]
        self._refresh_material_selector()
        self.material_selector.setCurrentIndex(0)
        self._load_material(0)
        for row in range(self.layer_table.rowCount()):
            combo = self.layer_table.cellWidget(row, 2)
            if isinstance(combo, QComboBox) and combo.currentText() == removed_name:
                combo.setCurrentIndex(0)
        self._notify_changed()

    @Slot()
    def _rename_material(self):
        idx = self.material_selector.currentIndex()
        if idx < 0:
            return
        old_name = str(self.materials[idx]["name"])
        name, ok = QInputDialog.getText(self.page_soil_material, tr("Rename Soil Material"), tr("Material name:"), text=old_name)
        name = name.strip()
        if not ok or not name or name == old_name:
            return
        names = set(self._material_names())
        names.discard(old_name)
        if name in names:
            QMessageBox.warning(self.page_soil_material, tr("Name Exists"), tr("Material name already exists."))
            return
        self.materials[idx]["name"] = name
        self._refresh_material_selector()
        self.material_selector.setCurrentText(name)
        self._notify_changed()

    def _add_layer_row(self, top: Optional[float] = None, bottom: Optional[float] = None, material_name: Optional[str] = None):
        row = self.layer_table.rowCount()
        self.layer_table.insertRow(row)
        top_item = QTableWidgetItem(f"{0.0 if top is None else top:.4f}")
        if row == 0:
            top_item.setFlags(top_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.layer_table.setItem(row, 0, top_item)
        self.layer_table.setItem(row, 1, QTableWidgetItem(f"{-1.0 if bottom is None else bottom:.4f}"))
        combo = QComboBox()
        combo.addItems(self._material_names())
        if material_name and material_name in self._material_names():
            combo.setCurrentText(material_name)
        combo.currentTextChanged.connect(lambda *_: self._notify_changed())
        self.layer_table.setCellWidget(row, 2, combo)
        self._notify_changed()

    @Slot()
    def _delete_layer_row(self):
        row = self.layer_table.currentRow()
        if row >= 0:
            self.layer_table.removeRow(row)
            if self.layer_table.rowCount() > 0:
                item = self.layer_table.item(0, 0)
                if item is not None:
                    item.setText("0.0000")
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._notify_changed()

    @Slot()
    def _on_layer_item_changed(self):
        if self._loading:
            return
        if self.layer_table.rowCount() > 0:
            item = self.layer_table.item(0, 0)
            if item is not None and item.text() != "0.0000":
                item.setText("0.0000")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._notify_changed()

    @Slot()
    def _update_section(self):
        if not hasattr(self, "pile_form") or not hasattr(self, "pile_t_row"):
            return
        d = self.pile_d.value()
        if self.pile_shape.currentText() == "Circle":
            self.pile_t.setEnabled(False)
            self._set_row_visible(self.pile_form, self.pile_t_row_index, self.pile_t_row, False)
        else:
            self.pile_t.setEnabled(True)
            self._set_row_visible(self.pile_form, self.pile_t_row_index, self.pile_t_row, True)

    @Slot()
    def _sync_pile_bottom_from_top(self):
        if self._pile_geometry_loading:
            return
        self._pile_geometry_loading = True
        length = max(self.pile_len.value(), 0.0001)
        self.pile_bottom_z.setValue(self.pile_top_z.value() - length)
        self._pile_geometry_loading = False

    @Slot()
    def _sync_pile_top_from_bottom(self):
        if self._pile_geometry_loading:
            return
        self._pile_geometry_loading = True
        length = max(self.pile_len.value(), 0.0001)
        self.pile_top_z.setValue(self.pile_bottom_z.value() + length)
        self._pile_geometry_loading = False

    @Slot()
    def _sync_pile_bottom_from_length(self):
        if self._pile_geometry_loading:
            return
        self._pile_geometry_loading = True
        self.pile_bottom_z.setValue(self.pile_top_z.value() - self.pile_len.value())
        self._pile_geometry_loading = False

    def _ui_depth_to_internal(self, value: float) -> float:
        return abs(float(value))

    def collect_payload(self) -> Dict:
        layers: List[Dict] = []
        prev_bottom = None
        for row in range(self.layer_table.rowCount()):
            top_item = self.layer_table.item(row, 0)
            bottom_item = self.layer_table.item(row, 1)
            if top_item is None or bottom_item is None:
                continue
            z_top_ui = float(top_item.text())
            z_bottom_ui = float(bottom_item.text())
            z_top = self._ui_depth_to_internal(z_top_ui)
            z_bottom = self._ui_depth_to_internal(z_bottom_ui)
            if row == 0 and z_top > 1.0e-8:
                raise ValueError("First layer top depth is fixed at 0.0 m.")
            if z_bottom <= z_top:
                raise ValueError(f"Layer row {row + 1}: bottom depth must be larger than top depth.")
            if prev_bottom is not None and z_top < prev_bottom - 1.0e-8:
                raise ValueError("Soil layers must be sorted and non-overlapping.")
            prev_bottom = z_bottom
            combo = self.layer_table.cellWidget(row, 2)
            mat_name = combo.currentText() if isinstance(combo, QComboBox) else ""
            mat = next((m for m in self.materials if str(m.get("name")) == mat_name), None)
            if mat is None:
                continue
            layers.append(
                {
                    "z_top": z_top,
                    "z_bottom": z_bottom,
                    "material_name": mat_name,
                    "bg_color": str(mat.get("bg_color", "#dfe8d8")),
                    "axial": {
                        "soil_type": str(mat.get("axial_type", "API Sand")),
                        "params": dict(mat.get("axial_params", {})),
                    },
                    "lateral": {
                        "soil_type": str(mat.get("lateral_type", "Sand")),
                        "params": dict(mat.get("lateral_params", {})),
                    },
                }
            )

        load_cases = []
        for base in range(0, self.load_table.rowCount(), 4):
            depth_item = self.load_table.item(base + 1, 2)
            value_items = [self.load_table.item(base + 3, col) for col in range(5)]
            if depth_item is None or any(item is None for item in value_items):
                continue
            depth_ui = float(depth_item.text() or 0.0)
            load_cases.append(
                {
                    "case_no": (base // 4) + 1,
                    "depth_ui": depth_ui,
                    "depth_m": self._ui_depth_to_internal(depth_ui),
                    "Fz": float(value_items[0].text() or 0.0),
                    "Fx": float(value_items[1].text() or 0.0),
                    "Fy": float(value_items[2].text() or 0.0),
                    "Mx": float(value_items[3].text() or 0.0),
                    "My": float(value_items[4].text() or 0.0),
                }
            )
        load_rows = []
        for row in load_cases:
            for load_type in ("Fz", "Fx", "Fy", "Mx", "My"):
                load_rows.append(
                    {
                        "type": load_type,
                        "value": float(row.get(load_type, 0.0)),
                        "depth_ui": float(row.get("depth_ui", 0.0)),
                        "depth_m": float(row.get("depth_m", 0.0)),
                    }
                )

        d = self.pile_d.value()
        if self.pile_shape.currentText() == "Circle":
            area = math.pi * d * d / 4.0
            inertia = math.pi * d**4 / 64.0
        else:
            t = self.pile_t.value()
            di = max(d - 2.0 * t, 0.0)
            area = math.pi * (d * d - di * di) / 4.0
            inertia = math.pi * (d**4 - di**4) / 64.0

        mesh_error = self.mesh_settings_widget.validate_custom_segments()
        if mesh_error:
            raise ValueError(mesh_error)
        mesh_settings = self.mesh_settings_widget.get_settings()
        rep_ele_size = representative_element_size(self.pile_len.value(), mesh_settings) or 0.0

        return {
            "pile_shape": self.pile_shape.currentText(),
            "pile_top_z_m": self.pile_top_z.value(),
            "pile_bottom_z_m": self.pile_bottom_z.value(),
            "pile_length_m": self.pile_len.value(),
            "pile_diameter_m": d,
            "pile_thickness_m": self.pile_t.value(),
            "pile_concrete_material": self.pile_concrete_material.currentText(),
            "pile_E_kPa": self.pile_E.value(),
            "pile_A_m2": area,
            "pile_I_m4": inertia,
            "free_length_m": max(self.pile_top_z.value(), 0.0),
            "ele_size_m": rep_ele_size,
            "mesh_settings": mesh_settings,
            "materials": [
                {
                    "name": str(m.get("name", "")),
                    "bg_color": str(m.get("bg_color", "#dfe8d8")),
                    "axial_type": str(m.get("axial_type", "API Sand")),
                    "axial_params": dict(m.get("axial_params", {})),
                    "lateral_type": str(m.get("lateral_type", "Sand")),
                    "lateral_params": dict(m.get("lateral_params", {})),
                }
                for m in self.materials
            ],
            "layers": layers,
            "load_cases": load_cases,
            "loads": load_rows,
            **self.fiber_section_widget.get_payload(),
        }

    def set_payload(self, payload: Dict):
        self._loading = True
        self._pile_geometry_loading = True
        if "pile_shape" in payload:
            idx = self.pile_shape.findText(str(payload["pile_shape"]))
            if idx >= 0:
                self.pile_shape.setCurrentIndex(idx)
        if "pile_top_z_m" in payload:
            self.pile_top_z.setValue(float(payload["pile_top_z_m"]))
        if "pile_bottom_z_m" in payload:
            self.pile_bottom_z.setValue(float(payload["pile_bottom_z_m"]))
        if "pile_length_m" in payload:
            self.pile_len.setValue(float(payload["pile_length_m"]))
        if "pile_bottom_z_m" not in payload and "pile_length_m" in payload:
            self.pile_bottom_z.setValue(self.pile_top_z.value() - float(payload["pile_length_m"]))
        if "pile_diameter_m" in payload:
            self.pile_d.setValue(float(payload["pile_diameter_m"]))
        if "pile_thickness_m" in payload:
            self.pile_t.setValue(float(payload["pile_thickness_m"]))
        pile_material = str(payload.get("pile_concrete_material", "") or "")
        if pile_material not in concrete_material_options():
            pile_material = infer_concrete_material_from_E(float(payload.get("pile_E_kPa", self.pile_E.value())))
        self.pile_concrete_material.setCurrentText(pile_material)
        if pile_material == USER_DEFINED_CONCRETE and "pile_E_kPa" in payload:
            self.pile_E.setValue(float(payload["pile_E_kPa"]))
        else:
            self._apply_pile_concrete_material(self.pile_concrete_material.currentText())
        self._pile_geometry_loading = False
        self.fiber_section_widget.set_payload(payload)
        self.mesh_settings_widget.set_settings(payload.get("mesh_settings"))
        materials = payload.get("materials")
        if isinstance(materials, list) and materials:
            self.materials = [
                {
                    "name": str(m.get("name", f"Material-{i + 1}")),
                    "bg_color": str(m.get("bg_color", "#dfe8d8")),
                    "axial_type": str(m.get("axial_type", "API Sand")),
                    "axial_params": dict(m.get("axial_params", {})),
                    "lateral_type": str(m.get("lateral_type", "Sand")),
                    "lateral_params": dict(m.get("lateral_params", {})),
                }
                for i, m in enumerate(materials)
            ]
        self._refresh_material_selector()
        if self.materials:
            self.material_selector.setCurrentIndex(0)
            self._load_material(0)

        self.layer_table.setRowCount(0)
        for layer in payload.get("layers", []):
            self._add_layer_row(
                -float(layer.get("z_top", 0.0)),
                -float(layer.get("z_bottom", 1.0)),
                str(layer.get("material_name", self.material_selector.currentText())),
            )

        self.load_table.setRowCount(0)
        load_cases = payload.get("load_cases", [])
        if isinstance(load_cases, list) and load_cases:
            for row in load_cases:
                if not isinstance(row, dict):
                    continue
                self._add_load_case_row(
                    depth_ui=float(row.get("depth_ui", -float(row.get("depth_m", 0.0)))),
                    fz=float(row.get("Fz", 0.0)),
                    fx=float(row.get("Fx", 0.0)),
                    fy=float(row.get("Fy", 0.0)),
                    mx=float(row.get("Mx", 0.0)),
                    my=float(row.get("My", 0.0)),
                )
        else:
            loads = payload.get("loads", [])
            if isinstance(loads, list):
                legacy_map = {
                    "Axial Force N (kN)": "Fz",
                    "Shear Hx (kN)": "Fx",
                    "Moment My (kN*m)": "My",
                }
                load_lookup = {}
                for entry in loads:
                    if isinstance(entry, dict):
                        load_lookup[legacy_map.get(str(entry.get("type", "")), str(entry.get("type", "")))] = entry
                depth_ui = 0.0
                for load_type in ("Fz", "Fx", "Fy", "Mx", "My"):
                    entry = load_lookup.get(load_type, {})
                    if "depth_ui" in entry:
                        depth_ui = float(entry.get("depth_ui", depth_ui))
                        break
                    if "depth_m" in entry:
                        depth_ui = -float(entry.get("depth_m", 0.0))
                        break
                self._add_load_case_row(
                    depth_ui=float(depth_ui),
                    fz=float(load_lookup.get("Fz", {}).get("value", 0.0)),
                    fx=float(load_lookup.get("Fx", {}).get("value", 0.0)),
                    fy=float(load_lookup.get("Fy", {}).get("value", 0.0)),
                    mx=float(load_lookup.get("Mx", {}).get("value", 0.0)),
                    my=float(load_lookup.get("My", {}).get("value", 0.0)),
                )

        self._loading = False
        self._update_section()
        self._notify_changed()
