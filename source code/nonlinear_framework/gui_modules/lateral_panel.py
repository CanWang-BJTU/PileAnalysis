# -*- coding: utf-8 -*-

import math
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QBrush, QColor, QFont
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
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)
from core.mesh_spec import representative_element_size
from gui_modules.fiber_section_widget import FiberSectionWidget
from gui_modules.concrete_material_utils import (
    USER_DEFINED_CONCRETE,
    concrete_elastic_modulus_kpa,
    concrete_material_options,
    infer_concrete_material_from_E,
)
from gui_modules.help_system import create_help_button, parameter_help, soil_model_help, wrap_widget_with_help
from gui_modules.i18n_utils import tr
from gui_modules.interaction_utils import configure_table_interaction, install_enter_navigation, soften_button_focus
from gui_modules.mesh_settings_widget import MeshSettingsWidget


LATERAL_SOIL_TYPES = [
    "API Method for Sand",
    "Sand",
    "Soft Clay Soil",
    "Submerged Stiff Clay",
    "Dry Stiff Clay",
    "Modified Stiff Clay without Free Water",
    "Weak Rock",
    "Elastic",
]


def default_color_for_lateral_soil(soil_type: str) -> str:
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


class LateralPanel:
    """Lateral mode parameter UI with material-library workflow."""

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
        self._add_layer_row(0.0, -10.0, "SoftClay-1")
        self._add_layer_row(-10.0, -19.0, "Sand-1")
        self._update_section()

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

    def _spin(self, value: float, vmin: float, vmax: float, decimals: int = 4) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setDecimals(decimals)
        box.setRange(vmin, vmax)
        box.setValue(value)
        return box

    def _default_params_for_type(self, soil_type: str) -> Dict:
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
        editor_layout = QFormLayout(editor_group)
        self.material_type = QComboBox()
        self.material_type.addItems(LATERAL_SOIL_TYPES)
        editor_layout.addRow(
            tr("Soil model"),
            wrap_widget_with_help(editor_group, self.material_type, lambda: soil_model_help("lateral", self.material_type.currentText())),
        )

        self.mat_gamma = self._spin(18.0, 0.0, 1000.0, 3)
        self.mat_phi = self._spin(35.0, 0.0, 80.0, 3)
        self.mat_kpy = self._spin(16300.0, 0.0, 1.0e8, 3)
        self.mat_k_modulus = self._spin(0.0, 0.0, 1.0e8, 3)
        self.mat_cu = self._spin(32.0, 0.0, 50000.0, 3)
        self.mat_eps50 = self._spin(0.02, 0.0, 1.0, 5)
        self.mat_J = self._spin(0.5, 0.0, 10.0, 4)
        self.mat_ca = self._spin(100.0, 0.0, 50000.0, 3)
        self.mat_qu = self._spin(1000.0, 0.0, 1.0e8, 3)
        self.mat_Eir = self._spin(7240000.0, 0.0, 1.0e10, 3)
        self.mat_RQD = self._spin(0.0, 0.0, 100.0, 3)
        self.mat_krm = self._spin(0.0005, 0.0, 100.0, 6)
        self.mat_kh = self._spin(10000.0, 0.0, 1.0e9, 3)

        self._param_rows: Dict[str, Dict] = {}
        self.editor_layout = editor_layout

        def add_param_row(key: str, label: str, widget: QWidget, soil_types: List[str], help_key: str):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(widget)
            row_layout.addWidget(
                create_help_button(
                    editor_group,
                    lambda key=key: parameter_help("lateral", self.material_type.currentText(), key),
                )
            )
            editor_layout.addRow(tr(label), row_widget)
            self._param_rows[key] = {
                "row": row_widget,
                "types": set(soil_types),
                "widget": widget,
                "label": editor_layout.labelForField(row_widget),
                "default_label": label,
            }

        all_non_elastic = [
            "API Method for Sand",
            "Sand",
            "Soft Clay Soil",
            "Submerged Stiff Clay",
            "Dry Stiff Clay",
            "Modified Stiff Clay without Free Water",
            "Weak Rock",
        ]
        add_param_row("gammaEff", "Unit Weight (kN/m^3)", self.mat_gamma, all_non_elastic, "unit_weight")
        add_param_row("phiDegree", "Friction Angle (deg)", self.mat_phi, ["API Method for Sand", "Sand"], "phi")
        add_param_row("kpy", "Kpy (kN/m^3)", self.mat_kpy, ["Sand"], "kpy")
        add_param_row("k_modulus", "Initial Modulus of Subgrade Reaction (kN/m^3)", self.mat_k_modulus, ["API Method for Sand", "Submerged Stiff Clay", "Modified Stiff Clay without Free Water"], "k_modulus")
        add_param_row("cu", "Undrained Shear Strength (kPa)", self.mat_cu, ["Soft Clay Soil", "Submerged Stiff Clay", "Dry Stiff Clay", "Modified Stiff Clay without Free Water"], "cu")
        add_param_row("eps50", "Strain Factor", self.mat_eps50, ["Soft Clay Soil", "Submerged Stiff Clay", "Dry Stiff Clay", "Modified Stiff Clay without Free Water"], "eps50")
        add_param_row("J", "J", self.mat_J, [], "eps50")
        add_param_row("ca", "ca (kPa)", self.mat_ca, [], "cu")
        add_param_row("qu", "Uniaxial Compressive Strength (kPa)", self.mat_qu, ["Weak Rock"], "qu")
        add_param_row("Eir", "Reaction Modulus of Rock (kPa)", self.mat_Eir, ["Weak Rock"], "Eir")
        add_param_row("RQD", "Rock Quality Designation (RQD) (%)", self.mat_RQD, ["Weak Rock"], "RQD")
        add_param_row("krm", "krm", self.mat_krm, ["Weak Rock"], "krm")
        add_param_row("kh", "kh (Elastic)", self.mat_kh, ["Elastic"], "k_modulus")
        self.btn_pick_color = QPushButton(tr("Pick Layer Color"))
        self.color_preview = QLabel()
        self.color_preview.setMinimumHeight(24)
        color_widget = QWidget()
        color_layout = QHBoxLayout(color_widget)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.addWidget(self.btn_pick_color)
        color_layout.addWidget(self.color_preview, 1)
        editor_layout.addRow("Layer color", color_widget)

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
            self.mat_kpy,
            self.mat_k_modulus,
            self.mat_cu,
            self.mat_eps50,
            self.mat_J,
            self.mat_ca,
            self.mat_qu,
            self.mat_Eir,
            self.mat_RQD,
            self.mat_krm,
            self.mat_kh,
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
        note = QLabel(tr("Depth is from the pile head. Enter negative values downward."))
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
        self.pile_bottom_z = self._spin(-19.0, -1000.0, 1000.0, 4)
        self.pile_len = self._spin(19.0, 0.1, 1000.0, 4)
        self.pile_d = self._spin(0.5, 0.01, 20.0, 4)
        self.pile_t = self._spin(0.02, 0.001, 5.0, 4)
        self.pile_concrete_material = QComboBox()
        self.pile_concrete_material.addItems(concrete_material_options())
        self.pile_E = self._spin(2.0e8, 1.0, 1.0e12, 3)
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
        self.load_table = QTableWidget(0, 4)
        self.load_table.horizontalHeader().setVisible(False)
        for col in range(4):
            self.load_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        self.load_table.verticalHeader().setVisible(False)
        configure_table_interaction(self.load_table, select_rows=False)
        self.load_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.load_table)
        tool_row = QHBoxLayout()
        tool_row.addWidget(create_help_button(page, "lateral_load_table"))
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
        soften_button_focus(page)
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
        self.load_table.setSpan(base, 2, 1, 2)

        case_item = self._make_readonly_item(f"{tr('Case')} {(base // 4) + 1}")
        self.load_table.setItem(base + 1, 0, case_item)
        self.load_table.setSpan(base + 1, 0, 1, 2)
        self.load_table.setItem(base + 1, 2, self._make_value_item(f"{float(depth_ui):.3f}"))
        self.load_table.setSpan(base + 1, 2, 1, 2)

        for col, text in enumerate(["Fx (kN)", "Fy (kN)", "Mx (kN*m)", "My (kN*m)"]):
            self.load_table.setItem(base + 2, col, self._make_readonly_item(tr(text)))
        for col, value in enumerate([fx, fy, mx, my]):
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
            self.load_table.setSpan(base_row + 1, 2, 1, 2)
        if self.load_table.rowCount() == 0:
            self._add_load_case_row()
        self._update_load_table_height()
        self._notify_changed()

    def _update_load_table_height(self):
        rows = max(self.load_table.rowCount(), 4)
        header_h = 0
        total_h = header_h + sum(self.load_table.rowHeight(row) or 28 for row in range(rows if self.load_table.rowCount() else 0))
        if self.load_table.rowCount() == 0:
            total_h = 120
        total_h += 6
        self.load_table.setFixedHeight(min(max(total_h, 120), 250))

    def _init_default_materials(self):
        self.soil_materials = [
            {
                "name": "SoftClay-1",
                "soil_type": "Soft Clay Soil",
                "params": self._default_params_for_type("Soft Clay Soil"),
                "bg_color": default_color_for_lateral_soil("Soft Clay Soil"),
                "bg_alpha": 0.28,
            },
            {
                "name": "Sand-1",
                "soil_type": "Sand",
                "params": self._default_params_for_type("Sand"),
                "bg_color": default_color_for_lateral_soil("Sand"),
                "bg_alpha": 0.28,
            },
        ]
        self._refresh_material_combos()
        self.material_selector.setCurrentIndex(0)
        self._on_material_selected(0)

    def _material_names(self) -> List[str]:
        return [str(m.get("name", "")) for m in self.soil_materials]

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

    def _refresh_param_visibility(self, soil_type: str):
        label_overrides = {
            ("k_modulus", "API Method for Sand"): "Initial Modulus of Subgrade Reaction (kN/m^3)",
            ("k_modulus", "Submerged Stiff Clay"): "Ks (kN/m^3)",
            ("k_modulus", "Modified Stiff Clay without Free Water"): "Initial Stiffness (kN/m^3)",
            ("krm", "Weak Rock"): "Constant Krm",
        }
        for info in self._param_rows.values():
            visible = soil_type in info["types"]
            if hasattr(self.editor_layout, "setRowVisible"):
                row_index = self.editor_layout.getWidgetPosition(info["row"])[0]
                self.editor_layout.setRowVisible(row_index, visible)
            else:
                info["row"].setVisible(visible)
            label_widget = info.get("label")
            if label_widget is not None:
                key = next((k for k, v in self._param_rows.items() if v is info), None)
                label_widget.setText(tr(label_overrides.get((key, soil_type), info["default_label"])))

    def _load_material_to_editor(self, material: Dict):
        self._material_loading = True
        soil_type = str(material.get("soil_type", "Sand"))
        idx = self.material_type.findText(soil_type)
        if idx >= 0:
            self.material_type.setCurrentIndex(idx)
        params = dict(material.get("params", {}))
        self.mat_gamma.setValue(float(params.get("gammaEff", 18.0)))
        self.mat_phi.setValue(float(params.get("phiDegree", 35.0)))
        self.mat_kpy.setValue(float(params.get("kpy", 16300.0)))
        self.mat_k_modulus.setValue(float(params.get("k_modulus", 0.0)))
        self.mat_cu.setValue(float(params.get("cu", 32.0)))
        self.mat_eps50.setValue(float(params.get("eps50", 0.02)))
        self.mat_J.setValue(float(params.get("J", 0.5)))
        self.mat_ca.setValue(float(params.get("ca", 100.0)))
        self.mat_qu.setValue(float(params.get("qu", 1000.0)))
        self.mat_Eir.setValue(float(params.get("Eir", 7240000.0)))
        self.mat_RQD.setValue(float(params.get("RQD", 0.0)))
        self.mat_krm.setValue(float(params.get("krm", 0.0005)))
        self.mat_kh.setValue(float(params.get("kh", 10000.0)))
        self._set_color_preview(str(material.get("bg_color", default_color_for_lateral_soil(soil_type))))
        self._refresh_param_visibility(soil_type)
        self._material_loading = False

    def _params_from_editor(self, soil_type: str) -> Dict:
        p: Dict = {}
        if soil_type in ("API Method for Sand", "Sand", "Soft Clay Soil", "Submerged Stiff Clay", "Dry Stiff Clay", "Modified Stiff Clay without Free Water", "Weak Rock"):
            p["gammaEff"] = self.mat_gamma.value()
        if soil_type in ("API Method for Sand", "Sand"):
            p["phiDegree"] = self.mat_phi.value()
        if soil_type == "Sand":
            p["kpy"] = self.mat_kpy.value()
        if soil_type == "API Method for Sand":
            p["k_modulus"] = self.mat_k_modulus.value()
        if soil_type in ("Soft Clay Soil", "Submerged Stiff Clay", "Dry Stiff Clay", "Modified Stiff Clay without Free Water"):
            p["cu"] = self.mat_cu.value()
            p["eps50"] = self.mat_eps50.value()
        if soil_type == "Submerged Stiff Clay":
            p["k_modulus"] = self.mat_k_modulus.value()
        if soil_type == "Modified Stiff Clay without Free Water":
            p["k_modulus"] = self.mat_k_modulus.value()
        if soil_type == "Weak Rock":
            p["qu"] = self.mat_qu.value()
            p["Eir"] = self.mat_Eir.value()
            p["RQD"] = self.mat_RQD.value()
            p["krm"] = self.mat_krm.value()
        if soil_type == "Elastic":
            p["kh"] = self.mat_kh.value()
        return p

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
        self.soil_materials[idx]["bg_color"] = default_color_for_lateral_soil(soil_type)
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
        self.soil_materials[idx]["params"] = self._params_from_editor(soil_type)
        self._notify_changed()

    @Slot()
    def _new_material(self):
        names = set(self._material_names())
        i = 1
        while f"Material-{i}" in names:
            i += 1
        default_name = f"Material-{i}"
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
                "soil_type": "Sand",
                "params": self._default_params_for_type("Sand"),
                "bg_color": default_color_for_lateral_soil("Sand"),
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
        removed_name = self.soil_materials[idx]["name"]
        del self.soil_materials[idx]
        self._refresh_material_combos()
        self.material_selector.setCurrentIndex(0)
        self._on_material_selected(0)
        for row in range(self.layer_table.rowCount()):
            combo = self.layer_table.cellWidget(row, 2)
            if isinstance(combo, QComboBox) and combo.currentText() == removed_name:
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
        self._notify_changed()

    @Slot()
    def _delete_layer_row(self):
        row = self.layer_table.currentRow()
        if row >= 0:
            self.layer_table.removeRow(row)
            self._notify_changed()

    @Slot()
    def _update_section(self):
        if not hasattr(self, "pile_form") or not hasattr(self, "pile_t_row"):
            return
        d = self.pile_d.value()
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
        self.pile_bottom_z.setValue(self.pile_top_z.value() - self.pile_len.value())
        self._pile_geometry_loading = False

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
                z_top = abs(float(top_item.text()))
                z_bottom = abs(float(bottom_item.text()))
            except ValueError as exc:
                raise ValueError(f"Layer row {row + 1} has invalid depth value.") from exc
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
                    "params": dict(material.get("params", {})),
                }
            )

        if layers[0]["z_top"] > 1.0e-8:
            raise ValueError("First layer top depth must start at 0.0 m.")

        d = self.pile_d.value()
        if self.pile_shape.currentText() == "Circle":
            area = math.pi * d * d / 4.0
            inertia = math.pi * d**4 / 64.0
        else:
            t = self.pile_t.value()
            if t <= 0 or 2.0 * t >= d:
                raise ValueError("Invalid pipe section geometry.")
            di = d - 2.0 * t
            area = math.pi * (d * d - di * di) / 4.0
            inertia = math.pi * (d**4 - di**4) / 64.0

        mesh_error = self.mesh_settings_widget.validate_custom_segments()
        if mesh_error:
            raise ValueError(mesh_error)
        mesh_settings = self.mesh_settings_widget.get_settings()
        rep_ele_size = representative_element_size(self.pile_len.value(), mesh_settings) or self.ele_size.value()

        load_cases = []
        for base in range(0, self.load_table.rowCount(), 4):
            depth_item = self.load_table.item(base + 1, 2)
            value_items = [self.load_table.item(base + 3, col) for col in range(4)]
            if depth_item is None or any(item is None for item in value_items):
                continue
            depth_ui = float(depth_item.text() or 0.0)
            fx = float(value_items[0].text() or 0.0)
            fy = float(value_items[1].text() or 0.0)
            mx = float(value_items[2].text() or 0.0)
            my = float(value_items[3].text() or 0.0)
            load_cases.append(
                {
                    "case_no": (base // 4) + 1,
                    "depth_ui": depth_ui,
                    "depth_m": abs(depth_ui),
                    "Fx": fx,
                    "Fy": fy,
                    "Mx": mx,
                    "My": my,
                }
            )

        loads = []
        for row in load_cases:
            for load_type in ("Fx", "Fy", "Mx", "My"):
                loads.append(
                    {
                        "type": load_type,
                        "value": float(row.get(load_type, 0.0)),
                        "depth_ui": float(row.get("depth_ui", 0.0)),
                        "depth_m": float(row.get("depth_m", 0.0)),
                    }
                )

        first_case = load_cases[0] if load_cases else {"Fx": 0.0, "My": 0.0, "depth_m": 0.0}
        return {
            "pile_top_z_m": self.pile_top_z.value(),
            "pile_bottom_z_m": self.pile_bottom_z.value(),
            "pile_length_m": self.pile_len.value(),
            "pile_diameter_m": d,
            "pile_concrete_material": self.pile_concrete_material.currentText(),
            "pile_E_kPa": self.pile_E.value(),
            "pile_A_m2": area,
            "pile_I_m4": inertia,
            "pile_shape": self.pile_shape.currentText(),
            "pile_thickness_m": self.pile_t.value(),
            "free_length_m": max(self.pile_top_z.value(), 0.0),
            "ele_size_m": rep_ele_size,
            "mesh_settings": mesh_settings,
            "soil_materials": [
                {
                    "name": str(m["name"]),
                    "soil_type": str(m["soil_type"]),
                    "params": dict(m.get("params", {})),
                    "bg_color": str(m.get("bg_color", default_color_for_lateral_soil(str(m.get("soil_type", "Sand"))))),
                    "bg_alpha": float(m.get("bg_alpha", 0.28)),
                }
                for m in self.soil_materials
            ],
            "layers": layers,
            "control_mode": "Load Control",
            "load_cases": load_cases,
            "loads": loads,
            "lateral_load_kN": float(first_case.get("Fx", 0.0)),
            "lateral_disp_m": 0.0,
            "moment_load_kN_m": float(first_case.get("My", 0.0)),
            "shear_depth_m": float(first_case.get("depth_m", 0.0)),
            "moment_depth_m": float(first_case.get("depth_m", 0.0)),
            "steps": 50,
            **self.fiber_section_widget.get_payload(),
        }

    def _infer_materials_from_legacy_payload(self, payload: Dict) -> List[Dict]:
        materials: List[Dict] = []
        name_id = 1
        for layer in payload.get("layers", []):
            soil_type = str(layer.get("soil_type", "Sand"))
            params = dict(layer.get("params", {}))
            if not any(m["soil_type"] == soil_type and m["params"] == params for m in materials):
                materials.append({"name": f"Material-{name_id}", "soil_type": soil_type, "params": params})
                name_id += 1
        if not materials:
            materials = [
                {
                    "name": "Sand-1",
                    "soil_type": "Sand",
                    "params": self._default_params_for_type("Sand"),
                    "bg_color": default_color_for_lateral_soil("Sand"),
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
        if "ele_size_m" in payload:
            self.ele_size.setValue(float(payload["ele_size_m"]))
        self._pile_geometry_loading = False
        self.fiber_section_widget.set_payload(payload)
        self.mesh_settings_widget.set_settings(payload.get("mesh_settings"))
        self.load_table.setRowCount(0)
        load_cases = payload.get("load_cases", [])
        if isinstance(load_cases, list) and load_cases:
            for row in load_cases:
                if not isinstance(row, dict):
                    continue
                self._add_load_case_row(
                    depth_ui=float(row.get("depth_ui", -float(row.get("depth_m", 0.0)))),
                    fx=float(row.get("Fx", 0.0)),
                    fy=float(row.get("Fy", 0.0)),
                    mx=float(row.get("Mx", 0.0)),
                    my=float(row.get("My", 0.0)),
                )
        else:
            load_lookup = {}
            if isinstance(payload.get("loads"), list):
                for row in payload.get("loads", []):
                    if isinstance(row, dict):
                        load_lookup[str(row.get("type", ""))] = dict(row)
            else:
                load_lookup = {
                    "Fx": {"value": float(payload.get("lateral_load_kN", payload.get("load", {}).get("lateral_kN", 0.0))), "depth_m": float(payload.get("shear_depth_m", 0.0))},
                    "My": {"value": float(payload.get("moment_load_kN_m", payload.get("load", {}).get("moment_kN_m", 0.0))), "depth_m": float(payload.get("moment_depth_m", 0.0))},
                }
            depth_ui = 0.0
            for load_type in ("Fx", "Fy", "Mx", "My"):
                entry = load_lookup.get(load_type, {})
                if "depth_ui" in entry:
                    depth_ui = float(entry.get("depth_ui", depth_ui))
                    break
                if "depth_m" in entry:
                    depth_ui = -float(entry.get("depth_m", 0.0))
                    break
            self._add_load_case_row(
                depth_ui=float(depth_ui),
                fx=float(load_lookup.get("Fx", {}).get("value", 0.0)),
                fy=float(load_lookup.get("Fy", {}).get("value", 0.0)),
                mx=float(load_lookup.get("Mx", {}).get("value", 0.0)),
                my=float(load_lookup.get("My", {}).get("value", 0.0)),
            )

        loaded_materials = payload.get("soil_materials")
        if isinstance(loaded_materials, list) and loaded_materials:
            self.soil_materials = [
                {
                    "name": str(m.get("name", f"Material-{i + 1}")),
                    "soil_type": str(m.get("soil_type", "Sand")),
                    "params": dict(m.get("params", {})),
                    "bg_color": str(m.get("bg_color", default_color_for_lateral_soil(str(m.get("soil_type", "Sand"))))),
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
                soil_type = str(layer.get("soil_type", "Sand"))
                mat_name = next((m["name"] for m in self.soil_materials if m["soil_type"] == soil_type), self.soil_materials[0]["name"])
            self._add_layer_row(-float(layer.get("z_top", 0.0)), -float(layer.get("z_bottom", 1.0)), mat_name)

        self._loading = False
        self._update_section()
        self._notify_changed()
