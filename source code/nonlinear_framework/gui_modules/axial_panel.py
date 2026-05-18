# -*- coding: utf-8 -*-

import math
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QColorDialog,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)
from core.mesh_spec import representative_element_size
from gui_modules.help_system import (
    add_form_row_with_help,
    create_help_button,
    parameter_help,
    soil_model_help,
    wrap_widget_with_help,
)
from gui_modules.fiber_section_widget import FiberSectionWidget
from gui_modules.concrete_material_utils import (
    USER_DEFINED_CONCRETE,
    concrete_elastic_modulus_kpa,
    concrete_material_options,
    infer_concrete_material_from_E,
)
from gui_modules.i18n_utils import tr
from gui_modules.interaction_utils import configure_table_interaction, install_enter_navigation, soften_button_focus
from gui_modules.mesh_settings_widget import MeshSettingsWidget


SOIL_TYPES = ["API Sand", "API Clay", "Drilled Sand", "Drilled Clay", "Elastic"]


def default_color_for_soil(soil_type: str) -> str:
    palette = {
        "API Sand": "#f7e7a8",
        "API Clay": "#e8c7cf",
        "Drilled Sand": "#fde2b8",
        "Drilled Clay": "#d9cde8",
        "Elastic": "#cfe6e8",
    }
    return palette.get(soil_type, "#dfe8d8")


class AxialPanel:
    """Axial mode parameter UI builder and collector.

    Design aligns with RSPile-style workflow:
    1) Define soil materials
    2) Assign soil materials to layers and tip
    3) Solver maps selected material to t-z / q-z inputs automatically
    """

    def __init__(self):
        self._material_loading = False
        self._pile_geometry_loading = False
        self._change_callback: Optional[Callable[[], None]] = None
        self.soil_materials: List[Dict] = []

        self.page_soil_material = self._create_soil_material_page()
        self.page_soil_layers = self._create_soil_layers_page()
        self.page_pile = self._create_pile_page()
        self.page_load = self._create_load_page()

        self._init_default_materials()
        self._add_layer_row(0.0, -10.0, "Material-1")
        self._add_layer_row(-10.0, -20.0, "Material-2")
        self._update_area()

    def set_change_callback(self, callback: Optional[Callable[[], None]]):
        self._change_callback = callback

    def _notify_changed(self):
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

    def _spin(self, value: float, vmin: float, vmax: float, decimals: int = 3) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setDecimals(decimals)
        box.setRange(vmin, vmax)
        box.setValue(value)
        return box

    def _default_params_for_type(self, soil_type: str) -> Dict[str, float]:
        if soil_type == "API Sand":
            return {
                "gammaEff": 20.0,
                "phiDegree": 35.0,
                "K": 1.0,
                "Nq": 40.0,
                "max_unit_skin_friction": 1000000.0,
                "max_unit_end_bearing": 1000000.0,
            }
        if soil_type == "API Clay":
            return {
                "gammaEff": 17.0,
                "cu": 22.0,
                "cu_remolded": 15.0,
                "max_unit_skin_friction": 1000000.0,
                "max_unit_end_bearing": 1000000.0,
            }
        if soil_type == "Drilled Sand":
            return {
                "gammaEff": 18.0,
                "max_unit_skin_friction": 10000.0,
                "max_unit_end_bearing": 10000.0,
            }
        if soil_type == "Drilled Clay":
            return {
                "gammaEff": 17.0,
                "max_unit_skin_friction": 10000.0,
                "max_unit_end_bearing": 10000.0,
            }
        return {"ks": 100000.0, "kb": 100000.0}

    def _create_soil_material_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)

        manager_group = QGroupBox("Soil Material Management")
        manager_layout = QVBoxLayout(manager_group)

        top = QHBoxLayout()
        top.addWidget(QLabel(tr("Current Material:")))
        self.material_selector = QComboBox()
        top.addWidget(self.material_selector, 1)
        self.btn_new_material = QPushButton(tr("New"))
        self.btn_delete_material = QPushButton(tr("Delete"))
        self.btn_rename_material = QPushButton(tr("Rename"))
        top.addWidget(self.btn_new_material)
        top.addWidget(self.btn_delete_material)
        top.addWidget(self.btn_rename_material)
        manager_layout.addLayout(top)

        editor_group = QGroupBox("Material Parameters")
        self.editor_layout = QFormLayout(editor_group)
        self.material_type = QComboBox()
        self.material_type.addItems(SOIL_TYPES)
        self.editor_layout.addRow(
            tr("Soil model"),
            wrap_widget_with_help(editor_group, self.material_type, lambda: soil_model_help("axial", self.material_type.currentText())),
        )

        self.mat_gamma = self._spin(18.0, 0.0, 1000.0, 3)
        self.mat_phi = self._spin(30.0, 0.0, 80.0, 3)
        self.mat_cu = self._spin(80.0, 0.0, 50000.0, 3)
        self.mat_cu_remolded = self._spin(20.0, 0.0, 50000.0, 3)
        self.mat_K = self._spin(0.8, 0.0, 100.0, 3)
        self.mat_ks = self._spin(100000.0, 0.0, 1.0e9, 3)
        self.mat_kb = self._spin(100000.0, 0.0, 1.0e9, 3)
        self.mat_Nq = self._spin(20.0, 0.0, 500.0, 3)
        self.mat_max_skin = self._spin(1000000.0, 0.0, 1.0e9, 3)
        self.mat_max_end = self._spin(1000000.0, 0.0, 1.0e9, 3)

        self._param_rows: Dict[str, Dict] = {}

        def add_param_row(key: str, label: str, widget: QWidget, soil_types: List[str], help_key: str):
            row_index = self.editor_layout.rowCount()
            label_widget = QLabel(tr(label))
            row_widget = add_form_row_with_help(
                self.editor_layout,
                editor_group,
                tr(label),
                widget,
                lambda key=key: parameter_help("axial", self.material_type.currentText(), key),
            )
            self._param_rows[key] = {
                "row": row_widget,
                "types": set(soil_types),
                "widget": widget,
                "row_index": row_index,
                "label_widget": label_widget,
            }

        add_param_row("gammaEff", "Unit Weight (kN/m^3)", self.mat_gamma, ["API Sand", "API Clay", "Drilled Sand", "Drilled Clay"], "unit_weight")
        add_param_row("phiDegree", "Friction Angle (deg)", self.mat_phi, ["API Sand"], "phi")
        add_param_row("cu", "Undrained Shear Strength (kPa)", self.mat_cu, ["API Clay"], "cu")
        add_param_row("cu_remolded", "Remolded Shear Strength (kPa)", self.mat_cu_remolded, ["API Clay"], "cu_remolded")
        add_param_row("K", "Coefficient of Lateral Earth Pressure", self.mat_K, ["API Sand"], "K_api_sand")
        add_param_row("Nq", "Bearing Capacity Factor", self.mat_Nq, ["API Sand"], "Nq")
        add_param_row("max_unit_skin_friction", "Maximum Unit Skin Friction (kPa)", self.mat_max_skin, ["API Sand", "API Clay", "Drilled Sand", "Drilled Clay"], "max_skin")
        add_param_row("max_unit_end_bearing", "Maximum Unit End Bearing Resistance (kPa)", self.mat_max_end, ["API Sand", "API Clay", "Drilled Sand", "Drilled Clay"], "max_tip")
        add_param_row("ks", "ks (Elastic)", self.mat_ks, ["Elastic"], "k_modulus")
        add_param_row("kb", "kb (Elastic tip)", self.mat_kb, ["Elastic"], "max_tip")
        self.mat_bg_alpha = self._spin(0.28, 0.05, 0.95, 2)
        self.btn_pick_color = QPushButton(tr("Pick Layer Color"))
        self.color_preview = QLabel()
        self.color_preview.setMinimumHeight(24)
        self.color_preview.setMinimumWidth(120)
        self.color_preview.setMaximumWidth(150)
        color_widget = QWidget()
        color_layout = QHBoxLayout(color_widget)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.addWidget(self.btn_pick_color)
        color_layout.addWidget(self.color_preview)
        color_layout.addStretch()
        self.editor_layout.addRow("Layer color", color_widget)

        manager_layout.addWidget(editor_group)
        root.addWidget(manager_group)
        root.addStretch()

        self.material_selector.currentIndexChanged.connect(self._on_material_selected)
        self.material_type.currentTextChanged.connect(self._on_material_type_changed)
        self.btn_new_material.clicked.connect(self._new_material)
        self.btn_delete_material.clicked.connect(self._delete_material)
        self.btn_rename_material.clicked.connect(self._rename_material)

        for spin in [
            self.mat_gamma,
            self.mat_phi,
            self.mat_cu,
            self.mat_cu_remolded,
            self.mat_K,
            self.mat_ks,
            self.mat_kb,
            self.mat_Nq,
            self.mat_max_skin,
            self.mat_max_end,
            self.mat_bg_alpha,
        ]:
            spin.valueChanged.connect(self._on_material_param_changed)
        self.btn_pick_color.clicked.connect(self._pick_material_color)

        return page

    def _create_soil_layers_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)

        self.layer_table = QTableWidget(0, 3)
        self.layer_table.setHorizontalHeaderLabels(["Top z (-m)", "Bottom z (-m)", "Soil Material"])
        self.layer_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.layer_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.layer_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        configure_table_interaction(self.layer_table, select_rows=True)
        install_enter_navigation(self.layer_table, [0, 1], add_row_fn=lambda: self._add_layer_row())
        root.addWidget(self.layer_table)
        tool_row = QHBoxLayout()
        tool_row.addWidget(create_help_button(page, "soil_layers"))
        tool_row.addStretch()
        root.addLayout(tool_row)
        hint = QLabel(tr("Tip: Press Enter to jump between depth cells."))
        hint.setStyleSheet("color: #2980b9; font-size: 9pt; padding: 2px 0;")
        hint.setWordWrap(True)
        root.addWidget(hint)
        note = QLabel(tr("Soil layers are referenced to the ground line. The first layer top is fixed at 0 m; enter negative values downward."))
        note.setStyleSheet("color: #808080;")
        root.addWidget(note)

        btns = QHBoxLayout()
        self.btn_add_layer = QPushButton(tr("Add Layer"))
        self.btn_del_layer = QPushButton(tr("Delete Layer"))
        btns.addWidget(self.btn_add_layer)
        btns.addWidget(self.btn_del_layer)
        btns.addStretch()
        root.addLayout(btns)

        self.btn_add_layer.clicked.connect(lambda: self._add_layer_row())
        self.btn_del_layer.clicked.connect(self._delete_layer_row)
        self.layer_table.itemChanged.connect(lambda *_: self._notify_changed())
        soften_button_focus(page)
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
        self.pile_shape.addItems(["Circle", "Pipe"])
        self.pile_top_z = self._spin(0.0, -1000.0, 1000.0, 4)
        self.pile_bottom_z = self._spin(-17.0, -1000.0, 1000.0, 4)
        self.pile_len = self._spin(17.0, 0.1, 1000.0, 4)
        self.pile_d = self._spin(1.0, 0.01, 20.0, 4)
        self.pile_t = self._spin(0.05, 0.001, 5.0, 4)
        self.pile_concrete_material = QComboBox()
        self.pile_concrete_material.addItems(concrete_material_options())
        self.pile_E = self._spin(3.0e7, 1.0, 1.0e12, 3)
        self.ele_size = self._spin(0.0, 0.0, 10.0, 4)
        self.geometry_table = QTableWidget(1, 3)
        self.geometry_table.setHorizontalHeaderLabels(["Pile top z (m)", "Pile bottom z (m)", "Length (m)"])
        self.geometry_table.verticalHeader().setVisible(False)
        self.geometry_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        configure_table_interaction(self.geometry_table, select_rows=False)
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
                self.ele_size,
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
        geometry_layout = QVBoxLayout(geometry_box)
        geometry_layout.setContentsMargins(8, 8, 8, 8)
        geometry_layout.addWidget(self.geometry_table)
        root.addWidget(geometry_box, 0, Qt.AlignmentFlag.AlignTop)
        root.addStretch(1)
        self.pile_top_z.valueChanged.connect(self._sync_pile_bottom_from_top)
        self.pile_bottom_z.valueChanged.connect(self._sync_pile_top_from_bottom)
        self.pile_len.valueChanged.connect(self._sync_pile_bottom_from_length)
        self.pile_top_z.editingFinished.connect(self._sync_pile_bottom_from_top)
        self.pile_bottom_z.editingFinished.connect(self._sync_pile_top_from_bottom)
        self.pile_len.editingFinished.connect(self._sync_pile_bottom_from_length)
        self.pile_shape.currentTextChanged.connect(self._update_area)
        self.pile_d.valueChanged.connect(self._update_area)
        self.pile_t.valueChanged.connect(self._update_area)
        self.pile_len.valueChanged.connect(lambda *_: self.fiber_section_widget.refresh_external_constraints())
        self.fiber_section_widget.changed.connect(self._sync_section_model_visibility)
        self.pile_top_z.valueChanged.connect(lambda *_: self._notify_changed())
        self.pile_bottom_z.valueChanged.connect(lambda *_: self._notify_changed())
        self.pile_shape.currentTextChanged.connect(lambda *_: self._notify_changed())
        self.pile_len.valueChanged.connect(lambda *_: self._notify_changed())
        self.pile_d.valueChanged.connect(lambda *_: self._notify_changed())
        self.pile_t.valueChanged.connect(lambda *_: self._notify_changed())
        self.pile_concrete_material.currentTextChanged.connect(self._on_pile_concrete_material_changed)
        self.pile_E.valueChanged.connect(lambda *_: self._notify_changed())
        self._sync_pile_concrete_material_from_E(self.pile_E.value())
        self._sync_section_model_visibility()
        soften_button_focus(page)
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
        self.load_table = QTableWidget(1, 3)
        self.load_table.setHorizontalHeaderLabels(["Type", "Value", "Depth (-m)"])
        self.load_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.load_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.load_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.load_table.verticalHeader().setVisible(False)
        configure_table_interaction(self.load_table, select_rows=False)
        self.load_table.setItem(0, 0, QTableWidgetItem(tr("Axial Force N (kN)")))
        self.load_table.setItem(0, 1, QTableWidgetItem("-100.000"))
        self.load_table.setItem(0, 2, QTableWidgetItem("0.000"))
        type_item = self.load_table.item(0, 0)
        if type_item is not None:
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        layout.addWidget(self.load_table)
        tool_row = QHBoxLayout()
        tool_row.addWidget(create_help_button(page, "axial_load_table"))
        tool_row.addStretch()
        layout.addLayout(tool_row)
        note = QLabel(tr("Sign follows the global Z axis: downward compression is negative, upward tension is positive."))
        note.setWordWrap(True)
        note.setStyleSheet("color: #808080;")
        layout.addWidget(note)
        self.mesh_settings_widget = MeshSettingsWidget(page)
        self.mesh_settings_widget.set_total_length_provider(lambda: self.pile_len.value())
        self.mesh_settings_widget.set_change_callback(self._notify_changed)
        layout.addWidget(self.mesh_settings_widget)
        self.load_table.itemChanged.connect(lambda *_: self._notify_changed())
        soften_button_focus(page)
        return page

    def _init_default_materials(self):
        self.soil_materials = [
            {
                "name": "Material-1",
                "soil_type": "API Clay",
                "params": self._default_params_for_type("API Clay"),
                "bg_color": default_color_for_soil("API Clay"),
                "bg_alpha": 0.28,
            },
            {
                "name": "Material-2",
                "soil_type": "API Sand",
                "params": self._default_params_for_type("API Sand"),
                "bg_color": default_color_for_soil("API Sand"),
                "bg_alpha": 0.28,
            },
        ]
        self._refresh_material_combos()
        self.material_selector.setCurrentIndex(0)
        self._on_material_selected(0)

    def _material_names(self) -> List[str]:
        return [str(m.get("name", "")) for m in self.soil_materials]

    def _material_by_name(self, name: str) -> Optional[Dict]:
        for m in self.soil_materials:
            if str(m.get("name")) == name:
                return m
        return None

    def _refresh_material_combos(self):
        names = self._material_names()

        old_sel = self.material_selector.currentText()
        self.material_selector.blockSignals(True)
        self.material_selector.clear()
        self.material_selector.addItems(names)
        if old_sel in names:
            self.material_selector.setCurrentText(old_sel)
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

    def _load_material_to_editor(self, material: Dict):
        self._material_loading = True
        soil_type = str(material.get("soil_type", "API Sand"))
        idx = self.material_type.findText(soil_type)
        if idx >= 0:
            self.material_type.setCurrentIndex(idx)
        params = dict(material.get("params", {}))
        self.mat_gamma.setValue(float(params.get("gammaEff", 18.0)))
        self.mat_phi.setValue(float(params.get("phiDegree", 30.0)))
        self.mat_cu.setValue(float(params.get("cu", 80.0)))
        self.mat_cu_remolded.setValue(float(params.get("cu_remolded", 20.0)))
        self.mat_K.setValue(float(params.get("K", 0.8)))
        self.mat_ks.setValue(float(params.get("ks", 100000.0)))
        self.mat_kb.setValue(float(params.get("kb", 100000.0)))
        self.mat_Nq.setValue(float(params.get("Nq", 40.0)))
        self.mat_max_skin.setValue(float(params.get("max_unit_skin_friction", 1000000.0)))
        self.mat_max_end.setValue(float(params.get("max_unit_end_bearing", 1000000.0)))
        self.mat_bg_alpha.setValue(float(material.get("bg_alpha", 0.28)))
        self._set_color_preview(str(material.get("bg_color", "#f6e27a")))
        self._refresh_material_param_visibility(soil_type)
        self._material_loading = False

    def _material_params_from_editor(self, soil_type: str) -> Dict[str, float]:
        params: Dict[str, float] = {}
        if soil_type in ("API Sand", "API Clay", "Drilled Sand", "Drilled Clay"):
            params["gammaEff"] = self.mat_gamma.value()
        if soil_type in ("API Sand", "Drilled Sand"):
            if soil_type == "API Sand":
                params["phiDegree"] = self.mat_phi.value()
                params["Nq"] = self.mat_Nq.value()
            params["max_unit_skin_friction"] = self.mat_max_skin.value()
            params["max_unit_end_bearing"] = self.mat_max_end.value()
        if soil_type in ("API Clay", "Drilled Clay"):
            if soil_type == "API Clay":
                params["cu"] = self.mat_cu.value()
                params["cu_remolded"] = self.mat_cu_remolded.value()
            params["max_unit_skin_friction"] = self.mat_max_skin.value()
            params["max_unit_end_bearing"] = self.mat_max_end.value()
        if soil_type == "API Sand":
            params["K"] = self.mat_K.value()
        if soil_type == "Elastic":
            params["ks"] = self.mat_ks.value()
            params["kb"] = self.mat_kb.value()
        return params

    def _refresh_material_param_visibility(self, soil_type: str):
        for info in self._param_rows.values():
            visible = soil_type in info["types"]
            if hasattr(self.editor_layout, "setRowVisible"):
                self.editor_layout.setRowVisible(info["row_index"], visible)
            else:
                info["row"].setVisible(visible)
        skin_label = self._param_rows["max_unit_skin_friction"]["label_widget"]
        end_label = self._param_rows["max_unit_end_bearing"]["label_widget"]
        if soil_type in ("Drilled Sand", "Drilled Clay"):
            skin_label.setText(tr("Ultimate Shear Resistance (kPa)"))
            end_label.setText(tr("Ultimate End Bearing Resistance (kPa)"))
        else:
            skin_label.setText(tr("Maximum Unit Skin Friction (kPa)"))
            end_label.setText(tr("Maximum Unit End Bearing Resistance (kPa)"))

    def _set_color_preview(self, color_hex: str):
        self.color_preview.setStyleSheet(f"border: 1px solid #aaaaaa; background-color: {color_hex};")

    def _set_row_visible(self, form: QFormLayout, row_widget: QWidget, visible: bool):
        row_widget.setVisible(visible)
        label = form.labelForField(row_widget)
        if label is not None:
            label.setVisible(visible)

    @Slot()
    def _pick_material_color(self):
        idx = self.material_selector.currentIndex()
        if idx < 0 or idx >= len(self.soil_materials):
            return
        current = str(self.soil_materials[idx].get("bg_color", "#f6e27a"))
        color = QColorDialog.getColor()
        if color.isValid():
            color_hex = color.name()
            self.soil_materials[idx]["bg_color"] = color_hex
            self._set_color_preview(color_hex)
            self._notify_changed()

    @Slot(int)
    def _on_material_selected(self, index: int):
        if index < 0 or index >= len(self.soil_materials):
            return
        self._load_material_to_editor(self.soil_materials[index])

    @Slot(str)
    def _on_material_type_changed(self, soil_type: str):
        if self._material_loading:
            return
        idx = self.material_selector.currentIndex()
        if idx < 0 or idx >= len(self.soil_materials):
            return
        self.soil_materials[idx]["soil_type"] = soil_type
        self.soil_materials[idx]["params"] = self._default_params_for_type(soil_type)
        self.soil_materials[idx]["bg_color"] = default_color_for_soil(soil_type)
        self._load_material_to_editor(self.soil_materials[idx])
        self._notify_changed()

    @Slot()
    def _on_material_param_changed(self):
        if self._material_loading:
            return
        idx = self.material_selector.currentIndex()
        if idx < 0 or idx >= len(self.soil_materials):
            return
        soil_type = self.material_type.currentText()
        self.soil_materials[idx]["soil_type"] = soil_type
        self.soil_materials[idx]["params"] = self._material_params_from_editor(soil_type)
        self.soil_materials[idx]["bg_alpha"] = float(self.mat_bg_alpha.value())
        self._notify_changed()

    @Slot()
    def _new_material(self):
        base = "Material"
        names = set(self._material_names())
        i = 1
        while f"{base}-{i}" in names:
            i += 1
        default_name = f"{base}-{i}"
        name, ok = QInputDialog.getText(self.page_soil_material, tr("New Soil Material"), tr("Material name:"), text=default_name)
        name = name.strip()
        if not ok or not name:
            return
        if name in names:
            QMessageBox.warning(self.page_soil_material, tr("Name Exists"), tr("Material name already exists."))
            return
        self.soil_materials.append(
            {
                "name": name,
                "soil_type": "API Sand",
                "params": self._default_params_for_type("API Sand"),
                "bg_color": default_color_for_soil("API Sand"),
                "bg_alpha": 0.28,
            }
        )
        self._refresh_material_combos()
        self.material_selector.setCurrentText(name)
        self._on_material_selected(self.material_selector.currentIndex())
        self._notify_changed()

    @Slot()
    def _delete_material(self):
        if len(self.soil_materials) <= 1:
            QMessageBox.warning(self.page_soil_material, tr("Cannot Delete"), tr("At least one material must remain."))
            return
        idx = self.material_selector.currentIndex()
        if idx < 0 or idx >= len(self.soil_materials):
            return
        name = self.soil_materials[idx]["name"]
        del self.soil_materials[idx]
        self._refresh_material_combos()
        self.material_selector.setCurrentIndex(0)
        self._on_material_selected(0)
        for row in range(self.layer_table.rowCount()):
            combo = self.layer_table.cellWidget(row, 2)
            if isinstance(combo, QComboBox) and combo.currentText() == name:
                combo.setCurrentIndex(0)
        self._notify_changed()

    @Slot()
    def _rename_material(self):
        idx = self.material_selector.currentIndex()
        if idx < 0 or idx >= len(self.soil_materials):
            return
        old_name = str(self.soil_materials[idx]["name"])
        name, ok = QInputDialog.getText(self.page_soil_material, tr("Rename Soil Material"), tr("Material name:"), text=old_name)
        name = name.strip()
        if not ok or not name or name == old_name:
            return
        names = set(self._material_names())
        names.discard(old_name)
        if name in names:
            QMessageBox.warning(self.page_soil_material, tr("Name Exists"), tr("Material name already exists."))
            return
        self.soil_materials[idx]["name"] = name
        self._refresh_material_combos()
        self.material_selector.setCurrentText(name)
        self._notify_changed()

    def _add_layer_row(self, top: Optional[float] = None, bottom: Optional[float] = None, material_name: Optional[str] = None):
        row = self.layer_table.rowCount()
        self.layer_table.insertRow(row)
        self.layer_table.setItem(row, 0, QTableWidgetItem(f"{0.0 if top is None else top:.4f}"))
        self.layer_table.setItem(row, 1, QTableWidgetItem(f"{-1.0 if bottom is None else bottom:.4f}"))
        mat_combo = QComboBox()
        mat_combo.addItems(self._material_names())
        if material_name and material_name in self._material_names():
            mat_combo.setCurrentText(material_name)
        mat_combo.currentTextChanged.connect(lambda *_: self._notify_changed())
        self.layer_table.setCellWidget(row, 2, mat_combo)
        self._refresh_layer_constraints()
        self._notify_changed()

    @Slot()
    def _delete_layer_row(self):
        row = self.layer_table.currentRow()
        if row >= 0:
            self.layer_table.removeRow(row)
            self._refresh_layer_constraints()
            self._notify_changed()

    @Slot()
    def _update_area(self):
        if not hasattr(self, "pile_form") or not hasattr(self, "pile_t_row"):
            return
        if self.pile_shape.currentText() == "Circle":
            self.pile_t.setEnabled(False)
            self._set_row_visible(self.pile_form, self.pile_t_row, False)
        else:
            self.pile_t.setEnabled(True)
            self._set_row_visible(self.pile_form, self.pile_t_row, True)

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
        top = self.pile_top_z.value()
        self.pile_bottom_z.setValue(top - self.pile_len.value())
        self._pile_geometry_loading = False

    def _refresh_layer_constraints(self):
        if self.layer_table.rowCount() == 0:
            return
        first_item = self.layer_table.item(0, 0)
        if first_item is not None:
            first_item.setText("0.0000")
            first_item.setFlags(first_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        for row in range(1, self.layer_table.rowCount()):
            item = self.layer_table.item(row, 0)
            if item is not None:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)

    def _material_to_tz(self, material: Dict) -> Dict[str, float]:
        soil_type = str(material["soil_type"])
        src = dict(material.get("params", {}))
        if soil_type == "API Sand":
            out: Dict[str, float] = {
                "gammaEff": float(src.get("gammaEff", 18.0)),
                "phiDegree": float(src.get("phiDegree", 30.0)),
                "K": float(src.get("K", 1.0)),
                "max_unit_skin_friction": float(src.get("max_unit_skin_friction", 1000000.0)),
            }
            return out
        if soil_type == "API Clay":
            out = {
                "gammaEff": float(src.get("gammaEff", 18.0)),
                "cu": float(src.get("cu", 25.0)),
                "cu_remolded": float(src.get("cu_remolded", 20.0)),
                "max_unit_skin_friction": float(src.get("max_unit_skin_friction", 1000000.0)),
            }
            return out
        if soil_type == "Drilled Sand":
            out = {
                "gammaEff": float(src.get("gammaEff", 18.0)),
                "max_unit_skin_friction": float(src.get("max_unit_skin_friction", 10000.0)),
            }
            return out
        if soil_type == "Drilled Clay":
            out = {
                "gammaEff": float(src.get("gammaEff", 17.0)),
                "max_unit_skin_friction": float(src.get("max_unit_skin_friction", 10000.0)),
            }
            return out
        if soil_type == "Elastic":
            return {"ks": float(src.get("ks", 100000.0))}
        return {}

    def _material_to_qz(self, material: Dict) -> Dict[str, float]:
        soil_type = str(material["soil_type"])
        src = dict(material.get("params", {}))
        if soil_type in ("API Sand", "Drilled Sand"):
            out: Dict[str, float] = {
                "gammaEff": float(src.get("gammaEff", 18.0)),
                "max_unit_end_bearing": float(
                    src.get(
                        "max_unit_end_bearing",
                        10000.0 if soil_type == "Drilled Sand" else 1000000.0,
                    )
                ),
            }
            if soil_type == "API Sand":
                out["phiDegree"] = float(src.get("phiDegree", 30.0))
                out["Nq"] = float(src["Nq"])
            if float(src.get("A_base", 0.0)) > 0:
                out["A_base"] = float(src["A_base"])
            if float(src.get("A_tip", 0.0)) > 0:
                out["A_tip"] = float(src["A_tip"])
            return out
        if soil_type in ("API Clay", "Drilled Clay"):
            out = {
                "gammaEff": float(src.get("gammaEff", 18.0)),
                "max_unit_end_bearing": float(
                    src.get(
                        "max_unit_end_bearing",
                        10000.0 if soil_type == "Drilled Clay" else 1000000.0,
                    )
                ),
            }
            if soil_type == "API Clay":
                out["cu"] = float(src.get("cu", 25.0))
            if float(src.get("A_base", 0.0)) > 0:
                out["A_base"] = float(src["A_base"])
            if float(src.get("A_tip", 0.0)) > 0:
                out["A_tip"] = float(src["A_tip"])
            return out
        if soil_type == "Elastic":
            return {"kb": float(src.get("kb", 100000.0))}
        return {}

    def collect_payload(self) -> Dict:
        if not self.soil_materials:
            raise ValueError("At least one soil material is required.")
        if self.layer_table.rowCount() == 0:
            raise ValueError("At least one soil layer is required.")

        material_map = {str(m["name"]): m for m in self.soil_materials}

        layers: List[Dict] = []
        prev_bottom = None
        for row in range(self.layer_table.rowCount()):
            top_item = self.layer_table.item(row, 0)
            bottom_item = self.layer_table.item(row, 1)
            if top_item is None or bottom_item is None:
                raise ValueError(f"Layer row {row + 1} is incomplete.")
            try:
                z_top_abs = abs(float(top_item.text()))
                z_bottom_abs = abs(float(bottom_item.text()))
            except ValueError as exc:
                raise ValueError(f"Layer row {row + 1} has invalid depth value.") from exc
            if row == 0 and z_top_abs > 1.0e-8:
                raise ValueError("First layer top depth is fixed at 0.0 m.")
            z_top = z_top_abs
            z_bottom = z_bottom_abs
            if z_bottom <= z_top:
                raise ValueError(f"Layer row {row + 1}: bottom depth must be larger than top depth.")
            if prev_bottom is not None and z_top < prev_bottom - 1.0e-8:
                raise ValueError("Soil layers must be sorted and non-overlapping.")
            prev_bottom = z_bottom

            combo = self.layer_table.cellWidget(row, 2)
            material_name = combo.currentText() if isinstance(combo, QComboBox) else ""
            material = material_map.get(material_name)
            if material is None:
                raise ValueError(f"Layer row {row + 1}: invalid material selection.")

            layers.append(
                {
                    "z_top": z_top,
                    "z_bottom": z_bottom,
                    "material_name": material_name,
                    "soil_type": str(material["soil_type"]),
                    "params": self._material_to_tz(material),
                }
            )

        if self.pile_shape.currentText() == "Circle":
            area = math.pi * self.pile_d.value() ** 2 / 4.0
        else:
            t = self.pile_t.value()
            d = self.pile_d.value()
            if t <= 0 or 2.0 * t >= d:
                raise ValueError("Invalid pipe section geometry.")
            di = d - 2.0 * t
            area = math.pi * (d * d - di * di) / 4.0

        mesh_error = self.mesh_settings_widget.validate_custom_segments()
        if mesh_error:
            raise ValueError(mesh_error)
        mesh_settings = self.mesh_settings_widget.get_settings()
        rep_ele_size = representative_element_size(self.pile_len.value(), mesh_settings) or self.ele_size.value()

        return {
            "pile_top_z_m": self.pile_top_z.value(),
            "pile_bottom_z_m": self.pile_bottom_z.value(),
            "pile_length_m": self.pile_len.value(),
            "pile_diameter_m": self.pile_d.value(),
            "pile_concrete_material": self.pile_concrete_material.currentText(),
            "pile_E_kPa": self.pile_E.value(),
            "pile_A_m2": area,
            "ele_size_m": rep_ele_size,
            "mesh_settings": mesh_settings,
            "pile_shape": self.pile_shape.currentText(),
            "pile_thickness_m": self.pile_t.value(),
            "soil_materials": [
                {
                    "name": str(m["name"]),
                    "soil_type": str(m["soil_type"]),
                    "params": dict(m.get("params", {})),
                    "bg_color": str(m.get("bg_color", "#f6e27a")),
                    "bg_alpha": float(m.get("bg_alpha", 0.28)),
                }
                for m in self.soil_materials
            ],
            "layers": layers,
            "control_mode": "Load Control",
            "axial_load_kN": float(self.load_table.item(0, 1).text()),
            "load_z_m": abs(float(self.load_table.item(0, 2).text())),
            "axial_disp_m": 0.0,
            "steps": 20,
            **self.fiber_section_widget.get_payload(),
        }

    def _infer_materials_from_legacy_payload(self, payload: Dict) -> List[Dict]:
        materials: List[Dict] = []
        name_id = 1
        for layer in payload.get("layers", []):
            soil_type = str(layer.get("soil_type", "API Sand"))
            params = dict(layer.get("params", {}))
            if not any(m["soil_type"] == soil_type and m["params"] == params for m in materials):
                materials.append({"name": f"Material-{name_id}", "soil_type": soil_type, "params": params})
                name_id += 1

        if not materials:
            materials = [
                {
                    "name": "Sand-1",
                    "soil_type": "API Sand",
                    "params": self._default_params_for_type("API Sand"),
                    "bg_color": default_color_for_soil("API Sand"),
                    "bg_alpha": 0.28,
                }
            ]
        return materials

    def set_payload(self, payload: Dict):
        self._loading = True
        self._pile_geometry_loading = True
        if "pile_shape" in payload:
            idx = self.pile_shape.findText(str(payload["pile_shape"]))
            if idx >= 0:
                self.pile_shape.setCurrentIndex(idx)
        if "pile_length_m" in payload:
            self.pile_len.setValue(float(payload["pile_length_m"]))
        if "pile_top_z_m" in payload:
            self.pile_top_z.setValue(float(payload["pile_top_z_m"]))
        if "pile_bottom_z_m" in payload:
            self.pile_bottom_z.setValue(float(payload["pile_bottom_z_m"]))
        elif "pile_length_m" in payload:
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
        if "ele_size_m" in payload:
            self.ele_size.setValue(float(payload["ele_size_m"]))
        self._pile_geometry_loading = False
        self.fiber_section_widget.set_payload(payload)
        self.mesh_settings_widget.set_settings(payload.get("mesh_settings"))

        if "axial_load_kN" in payload:
            self.load_table.setItem(0, 1, QTableWidgetItem(f"{float(payload['axial_load_kN']):.3f}"))
        if "load_z_m" in payload:
            self.load_table.setItem(0, 2, QTableWidgetItem(f"{-float(payload['load_z_m']):.3f}"))

        loaded_materials = payload.get("soil_materials")
        if isinstance(loaded_materials, list) and loaded_materials:
            self.soil_materials = [
                {
                    "name": str(m.get("name", f"Material-{i + 1}")),
                    "soil_type": str(m.get("soil_type", "API Sand")),
                    "params": dict(m.get("params", {})),
                    "bg_color": str(m.get("bg_color", default_color_for_soil(str(m.get("soil_type", "API Sand"))))),
                    "bg_alpha": float(m.get("bg_alpha", 0.28)),
                }
                for i, m in enumerate(loaded_materials)
            ]
        else:
            self.soil_materials = self._infer_materials_from_legacy_payload(payload)

        self._refresh_material_combos()
        if self.soil_materials:
            self.material_selector.setCurrentIndex(0)
            self._on_material_selected(0)

        self.layer_table.setRowCount(0)
        for layer in payload.get("layers", []):
            mat_name = str(layer.get("material_name", ""))
            if not mat_name:
                soil_type = str(layer.get("soil_type", "API Sand"))
                found = next((m["name"] for m in self.soil_materials if m["soil_type"] == soil_type), self.soil_materials[0]["name"])
                mat_name = found
            display_top = -float(layer.get("z_top", 0.0))
            display_bottom = -float(layer.get("z_bottom", 1.0))
            self._add_layer_row(display_top, display_bottom, mat_name)

        tip_type = str(payload.get("tip_type", ""))
        tip_params = dict(payload.get("tip_params", {}))
        if tip_type and tip_params:
            tip_depth = self.pile_len.value()
            tip_mat_name = ""
            for layer in payload.get("layers", []):
                z_top = float(layer.get("z_top", 0.0))
                z_bottom = float(layer.get("z_bottom", 0.0))
                if z_top - 1.0e-8 <= tip_depth <= z_bottom + 1.0e-8:
                    tip_mat_name = str(layer.get("material_name", ""))
                    if not tip_mat_name:
                        st = str(layer.get("soil_type", ""))
                        tip_mat_name = next((m["name"] for m in self.soil_materials if m["soil_type"] == st), "")
                    break
            if tip_mat_name:
                m = self._material_by_name(tip_mat_name)
                if isinstance(m, dict):
                    merged = dict(m.get("params", {}))
                    merged.update(tip_params)
                    m["params"] = merged
                    sel_idx = self.material_selector.currentIndex()
                    if sel_idx >= 0:
                        self._on_material_selected(sel_idx)

        self._loading = False
        self._update_area()
        self._notify_changed()
