# -*- coding: utf-8 -*-

from typing import Callable, Dict, List, Optional

from PySide6.QtCore import QSignalBlocker, Qt, Slot
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
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
    QRadioButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from core.mesh_spec import build_mesh_positions, representative_element_size
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
from gui_modules.interaction_utils import configure_table_interaction, install_enter_navigation, soften_button_focus
from gui_modules.mesh_settings_widget import MeshSettingsWidget

from gui_modules.axial_panel import SOIL_TYPES
from gui_modules.lateral_panel import LATERAL_SOIL_TYPES


CONNECTIVITY_TYPES = ["Fixed", "Pinned", "Restrained"]


class GroupPanel:
    def __init__(self):
        self._loading = False
        self._pile_type_loading = False
        self._pile_geometry_loading = False
        self._change_callback: Optional[Callable[[], None]] = None
        self.materials: List[Dict] = []
        self.pile_types: List[Dict] = []

        self.page_soil_material = self._create_soil_material_page()
        self.page_soil_layers = self._create_soil_layers_page()
        self.page_pile_definition = self._create_pile_definition_page()
        self.page_cap_definition = self._create_cap_definition_page()
        self.page_pile_layout = self._create_pile_layout_page()
        self.page_load = self._create_load_page()

        self._init_default_materials()
        self._init_default_pile_types()
        self._add_layer_row(0.0, -10.0, "Material-1")
        self._add_layer_row(-10.0, -27.0, "Material-2")
        self._add_layout_row(-1.5, -1.5, 0.0, -27.0, "PileType-1", "Fixed")
        self._add_layout_row(1.5, -1.5, 0.0, -27.0, "PileType-1", "Fixed")
        self._add_layout_row(-1.5, 1.5, 0.0, -27.0, "PileType-1", "Fixed")
        self._add_layout_row(1.5, 1.5, 0.0, -27.0, "PileType-1", "Fixed")
        self._sync_cap_from_piles()

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
        tabs.addTab(self._wrap_scroll_page(self.page_pile_definition), "Pile Definition")
        tabs.addTab(self._wrap_scroll_page(self.page_cap_definition), "Cap Definition")
        tabs.addTab(self._wrap_scroll_page(self.page_pile_layout), "Pile Layout")
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

    def _default_axial_params(self, soil_type: str) -> Dict[str, float]:
        if soil_type == "API Sand":
            return {"gammaEff": 18.0, "phiDegree": 30.0, "K": 1.0, "Nq": 40.0, "max_unit_skin_friction": 1.0e6, "max_unit_end_bearing": 1.0e6}
        if soil_type == "API Clay":
            return {"gammaEff": 18.0, "cu": 25.0, "cu_remolded": 20.0, "max_unit_skin_friction": 1.0e6, "max_unit_end_bearing": 1.0e6}
        if soil_type in ("Drilled Sand", "Drilled Clay"):
            return {"gammaEff": 18.0, "max_unit_skin_friction": 10000.0, "max_unit_end_bearing": 10000.0}
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

    def _default_pile_type(self, name: str) -> Dict:
        return {
            "name": name,
            "pile_shape": "Circle",
            "pile_top_z_m": 0.0,
            "pile_bottom_z_m": -27.0,
            "pile_length_m": 27.0,
            "pile_diameter_m": 1.0,
            "pile_thickness_m": 0.04,
            "pile_concrete_material": USER_DEFINED_CONCRETE,
            "pile_E_kPa": 3.0e7,
            "free_length_m": 0.0,
            "ele_size_m": 0.0,
            "section_mode": "elastic",
            "fiber_section_library": [],
            "fiber_section_segments": [],
        }

    def _material_names(self) -> List[str]:
        return [str(m.get("name", "")) for m in self.materials]

    def _pile_type_names(self) -> List[str]:
        return [str(m.get("name", "")) for m in self.pile_types]

    def _init_default_materials(self):
        self.materials = [
            {
                "name": "Material-1",
                "bg_color": "#e8c7cf",
                "bg_alpha": 0.28,
                "axial_type": "API Clay",
                "axial_params": self._default_axial_params("API Clay"),
                "lateral_type": "Soft Clay Soil",
                "lateral_params": self._default_lateral_params("Soft Clay Soil"),
            },
            {
                "name": "Material-2",
                "bg_color": "#fde2b8",
                "bg_alpha": 0.28,
                "axial_type": "API Sand",
                "axial_params": self._default_axial_params("API Sand"),
                "lateral_type": "Sand",
                "lateral_params": self._default_lateral_params("Sand"),
            },
        ]
        self._refresh_material_selector()
        self.material_selector.setCurrentIndex(0)
        self._load_material(0)

    def _init_default_pile_types(self):
        self.pile_types = [self._default_pile_type("PileType-1")]
        self._refresh_pile_type_selector()
        self.pile_type_selector.setCurrentIndex(0)
        self._load_pile_type(0)

    def _create_soil_material_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)
        group = QGroupBox("Soil Material Management")
        outer = QVBoxLayout(group)

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
        self.btn_new_material = QPushButton(tr("New"))
        self.btn_delete_material = QPushButton(tr("Delete"))
        self.btn_rename_material = QPushButton(tr("Rename"))
        top.addWidget(self.btn_new_material)
        top.addWidget(self.btn_delete_material)
        top.addWidget(self.btn_rename_material)
        outer.addLayout(top)

        self.material_tabs = QTabWidget()
        self.material_tabs.addTab(self._create_axial_material_tab(), "Axial")
        self.material_tabs.addTab(self._create_lateral_material_tab(), "Lateral")
        outer.addWidget(self.material_tabs)

        root.addWidget(group)

        self.material_selector.currentIndexChanged.connect(self._load_material)
        self.btn_pick_color.clicked.connect(self._pick_color)
        self.btn_new_material.clicked.connect(self._new_material)
        self.btn_delete_material.clicked.connect(self._delete_material)
        self.btn_rename_material.clicked.connect(self._rename_material)
        self.axial_type.currentTextChanged.connect(self._on_axial_type_changed)
        self.lateral_type.currentTextChanged.connect(self._on_lateral_type_changed)

        for widget in [
            self.ax_gamma, self.ax_phi, self.ax_cu, self.ax_cu_remolded, self.ax_K, self.ax_Nq,
            self.ax_max_skin, self.ax_max_tip, self.ax_ks, self.ax_kb,
            self.lt_gamma, self.lt_phi, self.lt_kpy, self.lt_kmod, self.lt_cu, self.lt_eps50, self.lt_J, self.lt_ca,
            self.lt_qu, self.lt_Eir, self.lt_RQD, self.lt_krm, self.lt_kh,
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
        self.ax_cu = self._spin(25.0, 0.0, 50000.0, 3)
        self.ax_cu_remolded = self._spin(20.0, 0.0, 50000.0, 3)
        self.ax_K = self._spin(1.0, 0.0, 100.0, 3)
        self.ax_Nq = self._spin(40.0, 0.0, 500.0, 3)
        self.ax_max_skin = self._spin(1.0e6, 0.0, 1.0e9, 3)
        self.ax_max_tip = self._spin(1.0e6, 0.0, 1.0e9, 3)
        self.ax_ks = self._spin(100000.0, 0.0, 1.0e9, 3)
        self.ax_kb = self._spin(100000.0, 0.0, 1.0e9, 3)
        self._ax_rows = {}

        def add_row(key: str, label: str, widget: QWidget, types: List[str]):
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(widget)
            help_map = {
                "gammaEff": "unit_weight",
                "phiDegree": "phi",
                "cu": "cu",
                "cu_remolded": "cu_remolded",
                "K": "K_api_sand",
                "Nq": "Nq",
                "max_unit_skin_friction": "max_skin",
                "max_unit_end_bearing": "max_tip",
                "drilled_skin": "max_skin",
                "drilled_tip": "max_tip",
                "ks": "k_modulus",
                "kb": "max_tip",
            }
            layout.addWidget(
                create_help_button(
                    page,
                    lambda key=key: parameter_help("axial", self.axial_type.currentText(), key),
                )
            )
            row_index = self.axial_form.rowCount()
            self.axial_form.addRow(tr(label), row)
            self._ax_rows[key] = {"row_index": row_index, "row": row, "types": set(types), "label": label}

        add_row("gammaEff", "Unit Weight (kN/m^3)", self.ax_gamma, ["API Sand", "API Clay", "Drilled Sand", "Drilled Clay"])
        add_row("phiDegree", "Friction Angle (deg)", self.ax_phi, ["API Sand"])
        add_row("cu", "Undrained Shear Strength (kPa)", self.ax_cu, ["API Clay"])
        add_row("cu_remolded", "Remolded Shear Strength (kPa)", self.ax_cu_remolded, ["API Clay"])
        add_row("K", "Coefficient of Lateral Earth Pressure", self.ax_K, ["API Sand"])
        add_row("Nq", "Bearing Capacity Factor", self.ax_Nq, ["API Sand"])
        add_row("max_unit_skin_friction", "Maximum Unit Skin Friction (kPa)", self.ax_max_skin, ["API Sand", "API Clay", "Drilled Sand", "Drilled Clay"])
        add_row("max_unit_end_bearing", "Maximum Unit End Bearing Resistance (kPa)", self.ax_max_tip, ["API Sand", "API Clay", "Drilled Sand", "Drilled Clay"])
        add_row("ks", "ks (Elastic)", self.ax_ks, ["Elastic"])
        add_row("kb", "kb (Elastic)", self.ax_kb, ["Elastic"])
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
        self.lt_gamma = self._spin(20.0, 0.0, 1000.0, 3)
        self.lt_phi = self._spin(38.0, 0.0, 80.0, 3)
        self.lt_kpy = self._spin(61000.0, 0.0, 1.0e8, 3)
        self.lt_kmod = self._spin(5400.0, 0.0, 1.0e8, 3)
        self.lt_cu = self._spin(25.0, 0.0, 50000.0, 3)
        self.lt_eps50 = self._spin(0.02, 0.0, 1.0, 5)
        self.lt_J = self._spin(0.5, 0.0, 10.0, 4)
        self.lt_ca = self._spin(100.0, 0.0, 50000.0, 3)
        self.lt_qu = self._spin(3450.0, 0.0, 1.0e8, 3)
        self.lt_Eir = self._spin(7240000.0, 0.0, 1.0e10, 3)
        self.lt_RQD = self._spin(0.0, 0.0, 100.0, 3)
        self.lt_krm = self._spin(0.0005, 0.0, 100.0, 6)
        self.lt_kh = self._spin(10000.0, 0.0, 1.0e9, 3)
        self._lt_rows = {}

        def add_row(key: str, label: str, widget: QWidget, types: List[str]):
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(widget)
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
            layout.addWidget(
                create_help_button(
                    page,
                    lambda key=key: parameter_help("lateral", self.lateral_type.currentText(), key),
                )
            )
            row_index = self.lateral_form.rowCount()
            self.lateral_form.addRow(tr(label), row)
            self._lt_rows[key] = {"row_index": row_index, "row": row, "types": set(types), "label": label}

        add_row("gammaEff", "Unit Weight (kN/m^3)", self.lt_gamma, ["API Method for Sand", "Sand", "Soft Clay Soil", "Submerged Stiff Clay", "Dry Stiff Clay", "Modified Stiff Clay without Free Water", "Weak Rock"])
        add_row("phiDegree", "Friction Angle (deg)", self.lt_phi, ["API Method for Sand", "Sand"])
        add_row("kpy", "Kpy (kN/m^3)", self.lt_kpy, ["Sand"])
        add_row("k_modulus", "Initial Modulus of Subgrade Reaction (kN/m^3)", self.lt_kmod, ["API Method for Sand", "Submerged Stiff Clay", "Modified Stiff Clay without Free Water"])
        add_row("cu", "Undrained Shear Strength (kPa)", self.lt_cu, ["Soft Clay Soil", "Submerged Stiff Clay", "Dry Stiff Clay", "Modified Stiff Clay without Free Water"])
        add_row("eps50", "Strain Factor", self.lt_eps50, ["Soft Clay Soil", "Submerged Stiff Clay", "Dry Stiff Clay", "Modified Stiff Clay without Free Water"])
        add_row("J", "J", self.lt_J, [])
        add_row("ca", "ca (kPa)", self.lt_ca, [])
        add_row("qu", "Uniaxial Compressive Strength (kPa)", self.lt_qu, ["Weak Rock"])
        add_row("Eir", "Reaction Modulus of Rock (kPa)", self.lt_Eir, ["Weak Rock"])
        add_row("RQD", "Rock Quality Designation (RQD) (%)", self.lt_RQD, ["Weak Rock"])
        add_row("krm", "Constant Krm", self.lt_krm, ["Weak Rock"])
        add_row("kh", "kh (Elastic)", self.lt_kh, ["Elastic"])
        return page

    def _create_soil_layers_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)
        self.layer_table = QTableWidget(0, 3)
        self.layer_table.setHorizontalHeaderLabels(["Top z (-m)", "Bottom z (-m)", "Soil Material"])
        for col in range(3):
            self.layer_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        # Enter-key navigation: Top z -> Bottom z -> next row Top z
        self._layer_delegate = install_enter_navigation(
            self.layer_table, [0, 1],
            add_row_fn=lambda: self._add_layer_row(),
        )
        root.addWidget(self.layer_table)
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

    def _create_pile_definition_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)
        group = QGroupBox("Pile Type Management")
        outer = QVBoxLayout(group)
        top = QHBoxLayout()
        top.addWidget(QLabel(tr("Current Type:")))
        self.pile_type_selector = QComboBox()
        top.addWidget(self.pile_type_selector, 1)
        self.btn_new_pile_type = QPushButton(tr("New"))
        self.btn_delete_pile_type = QPushButton(tr("Delete"))
        self.btn_rename_pile_type = QPushButton(tr("Rename"))
        top.addWidget(self.btn_new_pile_type)
        top.addWidget(self.btn_delete_pile_type)
        top.addWidget(self.btn_rename_pile_type)
        outer.addLayout(top)

        self.fiber_section_widget = FiberSectionWidget(group, allow_comparison=True)
        self.fiber_section_widget.set_total_length_provider(lambda: self.pile_len.value())
        self.fiber_section_widget.set_change_callback(self._on_pile_type_param_changed)
        outer.addWidget(self.fiber_section_widget, 0, Qt.AlignmentFlag.AlignTop)

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
        self.pile_bottom_z = self._spin(-27.0, -1000.0, 1000.0, 4)
        self.pile_len = self._spin(27.0, 0.1, 1000.0, 4)
        self.pile_d = self._spin(1.0, 0.01, 20.0, 4)
        self.pile_t = self._spin(0.04, 0.001, 5.0, 4)
        self.pile_concrete_material = QComboBox()
        self.pile_concrete_material.addItems(concrete_material_options())
        self.pile_E = self._spin(3.0e7, 1.0, 1.0e12, 3)
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
                self.pile_top_z,
                self.pile_bottom_z,
                self.pile_len,
            ]
        )
        self.pile_shape_row = wrap_widget_with_help(page, self.pile_shape, "pile_shape")
        self.pile_d_row = wrap_widget_with_help(page, self.pile_d, "pile_diameter")
        self.pile_t_row = wrap_widget_with_help(page, self.pile_t, "pile_thickness")
        self.pile_shape_row_index = form.rowCount()
        form.addRow("Pile shape", self.pile_shape_row)
        self.pile_d_row_index = form.rowCount()
        form.addRow("Diameter (m)", self.pile_d_row)
        self.pile_t_row_index = form.rowCount()
        form.addRow("Thickness (m, pipe)", self.pile_t_row)
        self.pile_material_row = wrap_widget_with_help(page, self.pile_concrete_material, None)
        self.pile_material_row_index = form.rowCount()
        form.addRow("Concrete material", self.pile_material_row)
        self.pile_E_row = wrap_widget_with_help(page, self.pile_E, "pile_E")
        self.pile_E_row_index = form.rowCount()
        form.addRow("Elastic modulus E (kPa)", self.pile_E_row)
        self.fiber_section_widget.set_external_elastic_widget(form_host)

        geometry_box = QGroupBox("Pile Geometry")
        geometry_layout = QFormLayout(geometry_box)
        geometry_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        geometry_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        geometry_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        geometry_layout.setHorizontalSpacing(10)
        geometry_layout.setVerticalSpacing(8)
        geometry_layout.addRow("Pile geometry", self.geometry_table)

        outer.addWidget(geometry_box, 0, Qt.AlignmentFlag.AlignTop)
        root.addWidget(group, 0, Qt.AlignmentFlag.AlignTop)
        root.addStretch(1)

        self.pile_type_selector.currentIndexChanged.connect(self._load_pile_type)
        self.btn_new_pile_type.clicked.connect(self._new_pile_type)
        self.btn_delete_pile_type.clicked.connect(self._delete_pile_type)
        self.btn_rename_pile_type.clicked.connect(self._rename_pile_type)
        self.pile_shape.currentTextChanged.connect(self._on_pile_shape_changed)
        self.pile_top_z.valueChanged.connect(self._sync_pile_bottom_from_top)
        self.pile_bottom_z.valueChanged.connect(self._sync_pile_top_from_bottom)
        self.pile_len.valueChanged.connect(self._sync_pile_bottom_from_length)
        self.pile_top_z.editingFinished.connect(self._sync_pile_bottom_from_top)
        self.pile_bottom_z.editingFinished.connect(self._sync_pile_top_from_bottom)
        self.pile_len.editingFinished.connect(self._sync_pile_bottom_from_length)
        self.pile_concrete_material.currentTextChanged.connect(self._on_pile_concrete_material_changed)
        for widget in [self.pile_d, self.pile_t, self.pile_E, self.pile_top_z, self.pile_bottom_z, self.pile_len]:
            widget.valueChanged.connect(self._on_pile_type_param_changed)
        self.pile_shape.currentTextChanged.connect(self._on_pile_type_param_changed)
        self.pile_len.valueChanged.connect(lambda *_: self.fiber_section_widget.refresh_external_constraints())
        self.fiber_section_widget.changed.connect(self._sync_section_model_visibility)
        self._sync_pile_concrete_material_from_E(self.pile_E.value())
        self._sync_section_model_visibility()
        soften_button_focus(page)
        return page

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

    def _sync_section_model_visibility(self):
        if hasattr(self, "elastic_section_box"):
            self.elastic_section_box.setVisible(True)

    @Slot(str)
    def _on_pile_concrete_material_changed(self, material_name: str):
        if self._pile_type_loading:
            self._apply_pile_concrete_material(material_name)
            return
        self._apply_pile_concrete_material(material_name)
        self._on_pile_type_param_changed()

    def _set_pile_editor_widths(self, widgets: List[QWidget]):
        for widget in widgets:
            widget.setMinimumWidth(180)
            widget.setMaximumWidth(340)
        self.geometry_table.setMinimumWidth(420)
        self.geometry_table.setMaximumWidth(620)
        self.geometry_table.setFixedHeight(44)

    def _create_cap_definition_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)
        group = QGroupBox("Cap Definition")
        form = QFormLayout(group)
        self.cap_length_x = self._spin(6.0, 0.1, 1000.0, 4)
        self.cap_length_y = self._spin(6.0, 0.1, 1000.0, 4)
        self.cap_height = self._spin(1.0, 0.1, 100.0, 4)
        self.cap_center_z = QLabel("-")
        self.cap_top_z = QLabel("-")
        self.cap_bottom_z = QLabel("-")
        form.addRow("Cap length X (m)", wrap_widget_with_help(group, self.cap_length_x, "cap_length_x"))
        form.addRow("Cap length Y (m)", wrap_widget_with_help(group, self.cap_length_y, "cap_length_y"))
        form.addRow("Cap height (m)", wrap_widget_with_help(group, self.cap_height, "cap_height"))
        form.addRow("Cap center z (m)", self.cap_center_z)
        form.addRow("Cap top z (m)", self.cap_top_z)
        form.addRow("Cap bottom z (m)", self.cap_bottom_z)
        note = QLabel(tr("The global coordinate origin is fixed at the cap center. Cap bottom follows the highest pile top elevation."))
        note.setWordWrap(True)
        note.setStyleSheet("color: #808080;")
        form.addRow("", note)
        root.addWidget(group)
        self.cap_length_x.valueChanged.connect(self._on_cap_changed)
        self.cap_length_y.valueChanged.connect(self._on_cap_changed)
        self.cap_height.valueChanged.connect(self._on_cap_changed)
        return page

    def _create_pile_layout_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)
        self.layout_table = QTableWidget(0, 7)
        self.layout_table.setHorizontalHeaderLabels(["X (m)", "Y (m)", "Top z (m)", "Bottom z (m)", "Pile Type", "Connectivity", "p Mult."])
        for col in range(7):
            self.layout_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        # Enter-key navigation: X -> Y -> Top z -> Bottom z -> next row X
        self._layout_delegate = install_enter_navigation(
            self.layout_table, [0, 1, 2, 3],
            add_row_fn=lambda: self._add_layout_row(),
        )
        root.addWidget(self.layout_table)
        tool_row = QHBoxLayout()
        tool_row.addWidget(create_help_button(page, "pile_layout"))
        tool_row.addSpacing(10)
        tool_row.addWidget(QLabel(tr("p Multiplier:")))
        self.p_multiplier_auto_radio = QRadioButton(tr("Automatic"))
        self.p_multiplier_manual_radio = QRadioButton(tr("Manual"))
        self.p_multiplier_auto_radio.setChecked(True)
        self.p_multiplier_auto_note = QLabel(tr("Calculated automatically by the program."))
        self.p_multiplier_auto_note.setStyleSheet("color: #808080;")
        tool_row.addWidget(self.p_multiplier_auto_radio)
        tool_row.addWidget(self.p_multiplier_manual_radio)
        tool_row.addWidget(self.p_multiplier_auto_note)
        tool_row.addStretch()
        root.addLayout(tool_row)
        hint = QLabel(tr("Tip: Press Enter to jump between coordinate cells."))
        hint.setStyleSheet("color: #2980b9; font-size: 9pt; padding: 2px 0;")
        hint.setWordWrap(True)
        root.addWidget(hint)
        note = QLabel(tr("Coordinates are in the cap plane with the cap center as the origin."))
        note.setStyleSheet("color: #808080;")
        root.addWidget(note)
        btns = QHBoxLayout()
        self.btn_add_layout = QPushButton(tr("Add Pile"))
        self.btn_delete_layout = QPushButton(tr("Delete Pile"))
        btns.addWidget(self.btn_add_layout)
        btns.addWidget(self.btn_delete_layout)
        btns.addStretch()
        root.addLayout(btns)
        self.btn_add_layout.clicked.connect(lambda: self._add_layout_row())
        self.btn_delete_layout.clicked.connect(self._delete_layout_row)
        self.layout_table.itemChanged.connect(self._on_layout_item_changed)
        self.p_multiplier_auto_radio.toggled.connect(self._on_p_multiplier_mode_changed)
        self.p_multiplier_manual_radio.toggled.connect(self._on_p_multiplier_mode_changed)
        self._on_p_multiplier_mode_changed()
        return page

    def _create_load_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.load_table = QTableWidget(0, 6)
        self.load_table.horizontalHeader().setVisible(False)
        for col in range(6):
            self.load_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        self.load_table.verticalHeader().setVisible(False)
        layout.addWidget(self.load_table)
        tool_row = QHBoxLayout()
        tool_row.addWidget(create_help_button(page, "group_load_table"))
        tool_row.addStretch()
        layout.addLayout(tool_row)
        load_btns = QHBoxLayout()
        self.btn_add_load_case = QPushButton(tr("Add Load Case"))
        self.btn_delete_load_case = QPushButton(tr("Delete Load Case"))
        load_btns.addWidget(self.btn_add_load_case)
        load_btns.addWidget(self.btn_delete_load_case)
        load_btns.addStretch()
        layout.addLayout(load_btns)
        mesh_row = QHBoxLayout()
        self.mesh_pile_label = QLabel(tr("Pile"))
        self.mesh_pile_selector = QComboBox()
        self.mesh_pile_selector.setMinimumWidth(160)
        mesh_row.addWidget(self.mesh_pile_label)
        mesh_row.addWidget(self.mesh_pile_selector)
        mesh_row.addStretch()
        layout.addLayout(mesh_row)
        # Hide pile selector by default; only show when advanced mesh is enabled
        self.mesh_pile_label.setVisible(False)
        self.mesh_pile_selector.setVisible(False)
        self.mesh_settings_widget = MeshSettingsWidget(page)
        self._mesh_settings_by_pile: Dict[str, Dict] = {}
        self._mesh_selector_loading = False
        self._current_mesh_pile_key: Optional[str] = None
        self.mesh_settings_widget.set_total_length_provider(self._selected_pile_length)
        self.mesh_settings_widget.set_change_callback(self._notify_changed)
        layout.addWidget(self.mesh_settings_widget)
        self.btn_add_load_case.clicked.connect(lambda: self._add_load_case_row())
        self.btn_delete_load_case.clicked.connect(self._delete_load_case_row)
        self.mesh_pile_selector.currentTextChanged.connect(self._on_mesh_pile_changed)
        # Toggle pile selector visibility with advanced mesh checkbox
        self.mesh_settings_widget.advanced_enabled.toggled.connect(self._on_mesh_advanced_toggled)
        self.load_table.itemChanged.connect(lambda *_: self._notify_changed())
        self._add_load_case_row()
        self._refresh_mesh_pile_selector()
        return page

    def _add_load_case_row(
        self,
        x: float = 0.0,
        y: float = 0.0,
        fx: float = 0.0,
        fy: float = 0.0,
        fz: float = 0.0,
        mx: float = 0.0,
        my: float = 0.0,
        mz: float = 0.0,
    ):
        base = self.load_table.rowCount()
        for _ in range(4):
            self.load_table.insertRow(self.load_table.rowCount())
        self.load_table.setRowHeight(base, 24)
        self.load_table.setRowHeight(base + 1, 30)
        self.load_table.setRowHeight(base + 2, 24)
        self.load_table.setRowHeight(base + 3, 30)

        headers_geo = [tr("Load Case"), tr("X Coordinate (m)"), tr("Y Coordinate (m)")]
        for i, text in enumerate(headers_geo):
            col = i * 2
            item = QTableWidgetItem(text)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setBackground(QBrush(QColor("#f5f5f5")))
            font = QFont()
            font.setBold(True)
            item.setFont(font)
            self.load_table.setItem(base, col, item)
            self.load_table.setSpan(base, col, 1, 2)

        no_item = QTableWidgetItem(f"{tr('Load')} {(base // 4) + 1}")
        no_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        no_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.load_table.setItem(base + 1, 0, no_item)
        self.load_table.setSpan(base + 1, 0, 1, 2)

        x_item = QTableWidgetItem(f"{float(x):.3f}")
        x_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.load_table.setItem(base + 1, 2, x_item)
        self.load_table.setSpan(base + 1, 2, 1, 2)

        y_item = QTableWidgetItem(f"{float(y):.3f}")
        y_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.load_table.setItem(base + 1, 4, y_item)
        self.load_table.setSpan(base + 1, 4, 1, 2)

        for col, text in enumerate(["Nx (kN)", "Ny (kN)", "Nz (kN)", "Mx (kN*m)", "My (kN*m)", "Mz (kN*m)"]):
            item = QTableWidgetItem(tr(text))
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setBackground(QBrush(QColor("#f5f5f5")))
            font = QFont()
            font.setBold(True)
            item.setFont(font)
            self.load_table.setItem(base + 2, col, item)

        for col, value in enumerate([fx, fy, fz, mx, my, mz]):
            item = QTableWidgetItem(f"{float(value):.3f}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.load_table.setItem(base + 3, col, item)
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
                item = QTableWidgetItem()
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.load_table.setItem(base_row + 1, 0, item)
            item.setText(f"{tr('Load')} {(base_row // 4) + 1}")
        if self.load_table.rowCount() == 0:
            self._add_load_case_row()
        self._update_load_table_height()
        self._notify_changed()

    def _update_load_table_height(self):
        if self.load_table.rowCount() == 0:
            self.load_table.setFixedHeight(150)
            return
        total_h = sum(self.load_table.rowHeight(row) or 28 for row in range(self.load_table.rowCount())) + 8
        self.load_table.setFixedHeight(min(max(total_h, 150), 320))

    def _mesh_key_for_layout_row(self, row_index: int) -> str:
        return f"Pile {row_index + 1}"

    def _save_current_mesh_settings(self):
        key = self._current_mesh_pile_key
        if key:
            self._mesh_settings_by_pile[key] = self.mesh_settings_widget.get_settings()

    def _selected_pile_length(self) -> float:
        text = self.mesh_pile_selector.currentText().strip()
        if text.startswith("Pile "):
            try:
                row = max(int(text.split()[-1]) - 1, 0)
            except Exception:
                row = 0
        else:
            row = 0
        if 0 <= row < self.layout_table.rowCount():
            top_item = self.layout_table.item(row, 2)
            bottom_item = self.layout_table.item(row, 3)
            if top_item is not None and bottom_item is not None:
                try:
                    return abs(float(top_item.text()) - float(bottom_item.text()))
                except Exception:
                    return self.pile_len.value()
        return self.pile_len.value()

    def _refresh_mesh_pile_selector(self):
        previous = self.mesh_pile_selector.currentText()
        if previous:
            self._save_current_mesh_settings()
        self._mesh_selector_loading = True
        self.mesh_pile_selector.blockSignals(True)
        self.mesh_pile_selector.clear()
        count = max(self.layout_table.rowCount(), 1)
        for idx in range(count):
            self.mesh_pile_selector.addItem(self._mesh_key_for_layout_row(idx))
        if previous and self.mesh_pile_selector.findText(previous) >= 0:
            self.mesh_pile_selector.setCurrentText(previous)
        else:
            self.mesh_pile_selector.setCurrentIndex(0)
        self.mesh_pile_selector.blockSignals(False)
        self._mesh_selector_loading = False
        self._on_mesh_pile_changed(self.mesh_pile_selector.currentText())

    @Slot(str)
    def _on_mesh_pile_changed(self, key: str):
        if self._mesh_selector_loading:
            return
        previous = self._current_mesh_pile_key
        if previous and previous != key:
            self._mesh_settings_by_pile[previous] = self.mesh_settings_widget.get_settings()
        self._current_mesh_pile_key = key
        self.mesh_settings_widget.set_settings(self._mesh_settings_by_pile.get(key))
        self._notify_changed()

    def _on_mesh_advanced_toggled(self, checked: bool):
        """Show/hide the per-pile mesh selector based on advanced checkbox."""
        self.mesh_pile_label.setVisible(checked)
        self.mesh_pile_selector.setVisible(checked)

    def _set_color_preview(self, color_hex: str):
        self.color_preview.setStyleSheet(f"border: 1px solid #aaaaaa; background-color: {color_hex};")

    def _set_row_visible(self, form: QFormLayout, row_index: int, row_widget: QWidget, visible: bool):
        if row_index is not None and hasattr(form, "setRowVisible"):
            form.setRowVisible(row_index, visible)
        else:
            row_widget.setVisible(visible)
            label = form.labelForField(row_widget)
            if label is not None:
                label.setVisible(visible)

    def _refresh_axial_visibility(self, soil_type: str):
        for key, info in self._ax_rows.items():
            visible = soil_type in info["types"]
            self._set_row_visible(self.axial_form, info.get("row_index"), info["row"], visible)
            label = self.axial_form.labelForField(info["row"])
            if label is not None:
                if key == "max_unit_skin_friction" and soil_type in {"Drilled Sand", "Drilled Clay"}:
                    label.setText(tr("Ultimate Shear Resistance (kPa)"))
                elif key == "max_unit_end_bearing" and soil_type in {"Drilled Sand", "Drilled Clay"}:
                    label.setText(tr("Ultimate End Bearing Resistance (kPa)"))
                else:
                    label.setText(tr(info["label"]))

    def _refresh_lateral_visibility(self, soil_type: str):
        label_overrides = {
            ("k_modulus", "API Method for Sand"): "Initial Modulus of Subgrade Reaction (kN/m^3)",
            ("k_modulus", "Submerged Stiff Clay"): "Ks (kN/m^3)",
            ("k_modulus", "Modified Stiff Clay without Free Water"): "Initial Stiffness (kN/m^3)",
            ("krm", "Weak Rock"): "Constant Krm",
        }
        for key, info in self._lt_rows.items():
            visible = soil_type in info["types"]
            self._set_row_visible(self.lateral_form, info.get("row_index"), info["row"], visible)
            label = self.lateral_form.labelForField(info["row"])
            if label is not None:
                label.setText(tr(label_overrides.get((key, soil_type), info["label"])))

    @Slot(int)
    def _load_material(self, index: int):
        if index < 0 or index >= len(self.materials):
            return
        mat = self.materials[index]
        self._loading = True
        self._set_color_preview(str(mat.get("bg_color", "#e8c7cf")))

        axial_type = str(mat.get("axial_type", "API Clay"))
        ax = dict(mat.get("axial_params", {}))
        self.axial_type.setCurrentText(axial_type)
        self.ax_gamma.setValue(float(ax.get("gammaEff", 18.0)))
        self.ax_phi.setValue(float(ax.get("phiDegree", 30.0)))
        self.ax_cu.setValue(float(ax.get("cu", 25.0)))
        self.ax_cu_remolded.setValue(float(ax.get("cu_remolded", 20.0)))
        self.ax_K.setValue(float(ax.get("K", 1.0)))
        self.ax_Nq.setValue(float(ax.get("Nq", 40.0)))
        self.ax_max_skin.setValue(float(ax.get("max_unit_skin_friction", 1.0e6)))
        self.ax_max_tip.setValue(float(ax.get("max_unit_end_bearing", 1.0e6)))
        self.ax_ks.setValue(float(ax.get("ks", 100000.0)))
        self.ax_kb.setValue(float(ax.get("kb", 100000.0)))
        self._refresh_axial_visibility(axial_type)

        lateral_type = str(mat.get("lateral_type", "Soft Clay Soil"))
        lt = dict(mat.get("lateral_params", {}))
        self.lateral_type.setCurrentText(lateral_type)
        self.lt_gamma.setValue(float(lt.get("gammaEff", 20.0)))
        self.lt_phi.setValue(float(lt.get("phiDegree", 38.0)))
        self.lt_kpy.setValue(float(lt.get("kpy", 61000.0)))
        self.lt_kmod.setValue(float(lt.get("k_modulus", 5400.0)))
        self.lt_cu.setValue(float(lt.get("cu", 25.0)))
        self.lt_eps50.setValue(float(lt.get("eps50", 0.02)))
        self.lt_J.setValue(float(lt.get("J", 0.5)))
        self.lt_ca.setValue(float(lt.get("ca", 100.0)))
        self.lt_qu.setValue(float(lt.get("qu", 3450.0)))
        self.lt_Eir.setValue(float(lt.get("Eir", 7240000.0)))
        self.lt_RQD.setValue(float(lt.get("RQD", 0.0)))
        self.lt_krm.setValue(float(lt.get("krm", 0.0005)))
        self.lt_kh.setValue(float(lt.get("kh", 10000.0)))
        self._refresh_lateral_visibility(lateral_type)
        self._loading = False

    def _axial_params_from_editor(self, soil_type: str) -> Dict[str, float]:
        params: Dict[str, float] = {}
        if soil_type in ("API Sand", "API Clay", "Drilled Sand", "Drilled Clay"):
            params["gammaEff"] = self.ax_gamma.value()
        if soil_type == "API Sand":
            params["phiDegree"] = self.ax_phi.value()
            params["K"] = self.ax_K.value()
            params["Nq"] = self.ax_Nq.value()
            params["max_unit_skin_friction"] = self.ax_max_skin.value()
            params["max_unit_end_bearing"] = self.ax_max_tip.value()
        elif soil_type == "API Clay":
            params["cu"] = self.ax_cu.value()
            params["cu_remolded"] = self.ax_cu_remolded.value()
            params["max_unit_skin_friction"] = self.ax_max_skin.value()
            params["max_unit_end_bearing"] = self.ax_max_tip.value()
        elif soil_type in ("Drilled Sand", "Drilled Clay"):
            params["max_unit_skin_friction"] = self.ax_max_skin.value()
            params["max_unit_end_bearing"] = self.ax_max_tip.value()
        elif soil_type == "Elastic":
            params["ks"] = self.ax_ks.value()
            params["kb"] = self.ax_kb.value()
        return params

    def _lateral_params_from_editor(self, soil_type: str) -> Dict[str, float]:
        params: Dict[str, float] = {}
        if soil_type in ("API Method for Sand", "Sand", "Soft Clay Soil", "Submerged Stiff Clay", "Dry Stiff Clay", "Modified Stiff Clay without Free Water", "Weak Rock"):
            params["gammaEff"] = self.lt_gamma.value()
        if soil_type in ("API Method for Sand", "Sand"):
            params["phiDegree"] = self.lt_phi.value()
        if soil_type == "Sand":
            params["kpy"] = self.lt_kpy.value()
        if soil_type in ("API Method for Sand", "Submerged Stiff Clay", "Modified Stiff Clay without Free Water"):
            params["k_modulus"] = self.lt_kmod.value()
        if soil_type in ("Soft Clay Soil", "Submerged Stiff Clay", "Dry Stiff Clay", "Modified Stiff Clay without Free Water"):
            params["cu"] = self.lt_cu.value()
            params["eps50"] = self.lt_eps50.value()
        if soil_type == "Modified Stiff Clay without Free Water":
            params["k_modulus"] = self.lt_kmod.value()
        if soil_type == "Weak Rock":
            params["qu"] = self.lt_qu.value()
            params["Eir"] = self.lt_Eir.value()
            params["RQD"] = self.lt_RQD.value()
            params["krm"] = self.lt_krm.value()
        if soil_type == "Elastic":
            params["kh"] = self.lt_kh.value()
        return params

    @Slot(str)
    def _on_axial_type_changed(self, soil_type: str):
        if self._loading:
            return
        idx = self.material_selector.currentIndex()
        if idx < 0:
            return
        self.materials[idx]["axial_type"] = soil_type
        self.materials[idx]["axial_params"] = self._default_axial_params(soil_type)
        self._load_material(idx)
        self._notify_changed()

    @Slot(str)
    def _on_lateral_type_changed(self, soil_type: str):
        if self._loading:
            return
        idx = self.material_selector.currentIndex()
        if idx < 0:
            return
        self.materials[idx]["lateral_type"] = soil_type
        self.materials[idx]["lateral_params"] = self._default_lateral_params(soil_type)
        self._load_material(idx)
        self._notify_changed()

    @Slot()
    def _on_param_changed(self):
        if self._loading:
            return
        idx = self.material_selector.currentIndex()
        if idx < 0:
            return
        self.materials[idx]["axial_type"] = self.axial_type.currentText()
        self.materials[idx]["axial_params"] = self._axial_params_from_editor(self.axial_type.currentText())
        self.materials[idx]["lateral_type"] = self.lateral_type.currentText()
        self.materials[idx]["lateral_params"] = self._lateral_params_from_editor(self.lateral_type.currentText())
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
                "bg_color": "#e8c7cf",
                "bg_alpha": 0.28,
                "axial_type": "API Clay",
                "axial_params": self._default_axial_params("API Clay"),
                "lateral_type": "Soft Clay Soil",
                "lateral_params": self._default_lateral_params("Soft Clay Soil"),
            }
        )
        self._refresh_material_selector()
        self.material_selector.setCurrentText(name)
        self._notify_changed()

    @Slot()
    def _delete_material(self):
        if len(self.materials) <= 1:
            QMessageBox.warning(self.page_soil_material, tr("Cannot Delete"), tr("At least one soil material must remain."))
            return
        idx = self.material_selector.currentIndex()
        if idx < 0:
            return
        removed = str(self.materials[idx].get("name", ""))
        del self.materials[idx]
        self._refresh_material_selector()
        self.material_selector.setCurrentIndex(0)
        self._load_material(0)
        for row in range(self.layer_table.rowCount()):
            combo = self.layer_table.cellWidget(row, 2)
            if isinstance(combo, QComboBox) and combo.currentText() == removed:
                combo.setCurrentIndex(0)
        self._notify_changed()

    @Slot()
    def _rename_material(self):
        idx = self.material_selector.currentIndex()
        if idx < 0:
            return
        old_name = str(self.materials[idx].get("name", ""))
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

    def _refresh_material_selector(self):
        names = self._material_names()
        current = self.material_selector.currentText() if hasattr(self, "material_selector") else ""
        self.material_selector.blockSignals(True)
        self.material_selector.clear()
        self.material_selector.addItems(names)
        if current in names:
            self.material_selector.setCurrentText(current)
        self.material_selector.blockSignals(False)
        if hasattr(self, "layer_table"):
            for row in range(self.layer_table.rowCount()):
                combo = self.layer_table.cellWidget(row, 2)
                if isinstance(combo, QComboBox):
                    chosen = combo.currentText()
                    combo.blockSignals(True)
                    combo.clear()
                    combo.addItems(names)
                    if chosen in names:
                        combo.setCurrentText(chosen)
                    elif names:
                        combo.setCurrentIndex(0)
                    combo.blockSignals(False)

    def _add_layer_row(self, top: float, bottom: float, material_name: str):
        row = self.layer_table.rowCount()
        self.layer_table.insertRow(row)
        top_item = QTableWidgetItem(f"{top:.4f}")
        if row == 0:
            top_item.setFlags(top_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.layer_table.setItem(row, 0, top_item)
        self.layer_table.setItem(row, 1, QTableWidgetItem(f"{bottom:.4f}"))
        combo = QComboBox()
        combo.addItems(self._material_names())
        if material_name in self._material_names():
            combo.setCurrentText(material_name)
        combo.currentTextChanged.connect(lambda *_: self._notify_changed())
        self.layer_table.setCellWidget(row, 2, combo)

    @Slot()
    def _delete_layer_row(self):
        row = self.layer_table.currentRow()
        if row < 0:
            row = self.layer_table.rowCount() - 1
        if row < 0:
            return
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
        self._notify_changed()

    def _refresh_pile_type_selector(self):
        names = self._pile_type_names()
        current = self.pile_type_selector.currentText() if hasattr(self, "pile_type_selector") else ""
        self.pile_type_selector.blockSignals(True)
        self.pile_type_selector.clear()
        self.pile_type_selector.addItems(names)
        if current in names:
            self.pile_type_selector.setCurrentText(current)
        self.pile_type_selector.blockSignals(False)
        if hasattr(self, "layout_table"):
            for row in range(self.layout_table.rowCount()):
                combo = self.layout_table.cellWidget(row, 4)
                if isinstance(combo, QComboBox):
                    chosen = combo.currentText()
                    combo.blockSignals(True)
                    combo.clear()
                    combo.addItems(names)
                    if chosen in names:
                        combo.setCurrentText(chosen)
                    elif names:
                        combo.setCurrentIndex(0)
                    combo.blockSignals(False)

    @Slot(int)
    def _load_pile_type(self, index: int):
        if index < 0 or index >= len(self.pile_types):
            return
        pile = self.pile_types[index]
        self._pile_type_loading = True
        self.pile_shape.setCurrentText(str(pile.get("pile_shape", "Circle")))
        self.pile_top_z.setValue(float(pile.get("pile_top_z_m", 0.0)))
        self.pile_bottom_z.setValue(float(pile.get("pile_bottom_z_m", -27.0)))
        self.pile_len.setValue(float(pile.get("pile_length_m", 27.0)))
        self.pile_d.setValue(float(pile.get("pile_diameter_m", 1.0)))
        self.pile_t.setValue(float(pile.get("pile_thickness_m", 0.04)))
        pile_material = str(pile.get("pile_concrete_material", "") or "")
        if pile_material not in concrete_material_options():
            pile_material = infer_concrete_material_from_E(float(pile.get("pile_E_kPa", 3.0e7)))
        self.pile_concrete_material.setCurrentText(pile_material)
        if pile_material == USER_DEFINED_CONCRETE:
            self.pile_E.setValue(float(pile.get("pile_E_kPa", 3.0e7)))
        else:
            self._apply_pile_concrete_material(pile_material)
        self.fiber_section_widget.set_payload(pile)
        self._sync_derived_group_pile_fields()
        self._pile_type_loading = False
        self._update_section()

    def _current_pile_type_payload(self, name: str) -> Dict:
        self._sync_derived_group_pile_fields()
        return {
            "name": name,
            "pile_shape": self.pile_shape.currentText(),
            "pile_top_z_m": self.pile_top_z.value(),
            "pile_bottom_z_m": self.pile_bottom_z.value(),
            "pile_length_m": self.pile_len.value(),
            "pile_diameter_m": self.pile_d.value(),
            "pile_thickness_m": self.pile_t.value(),
            "pile_concrete_material": self.pile_concrete_material.currentText(),
            "pile_E_kPa": self.pile_E.value(),
            "free_length_m": max(self.pile_top_z.value(), 0.0),
            "ele_size_m": 0.0,
            **self.fiber_section_widget.get_payload(),
        }

    def _active_group_fiber_section(self) -> Optional[Dict]:
        payload = self.fiber_section_widget.get_payload()
        mode = str(payload.get("section_mode", "elastic"))
        if mode not in {"fiber", "comparison"}:
            return None
        library = [
            dict(item)
            for item in (payload.get("fiber_section_library", []) or [])
            if isinstance(item, dict)
        ]
        if not library:
            return None
        sections = {str(item.get("name", "")): item for item in library}
        for segment in payload.get("fiber_section_segments", []) or []:
            if not isinstance(segment, dict):
                continue
            section_name = str(segment.get("section_name", "")).strip()
            section = sections.get(section_name)
            if section is not None:
                return section
        return library[0]

    def _derive_pile_properties_from_h5(self) -> Optional[Dict]:
        section = self._active_group_fiber_section()
        if not section:
            return None
        summary = dict(section.get("summary", {}) or {})
        geometry = dict(section.get("geometry", {}) or {})
        mats = dict(section.get("material_params", {}) or {})

        out_points = geometry.get("out_points", []) or []
        xs = []
        ys = []
        for point in out_points:
            try:
                if len(point) >= 2:
                    xs.append(float(point[0]))
                    ys.append(float(point[1]))
            except Exception:
                continue
        diameter = 0.0
        if xs and ys:
            diameter = max(max(xs) - min(xs), max(ys) - min(ys))
        area = float(summary.get("area_m2", 0.0) or 0.0)
        iy = float(summary.get("iy_m4", 0.0) or 0.0)
        iz = float(summary.get("iz_m4", 0.0) or 0.0)
        inertia = max(0.5 * (iy + iz), 0.0)

        core_Ec = float(dict(mats.get("core_concrete", {}) or {}).get("Ec", 0.0) or 0.0)
        cover_Ec = float(dict(mats.get("cover_concrete", {}) or {}).get("Ec", 0.0) or 0.0)
        rebar_Es = float(dict(mats.get("rebar", {}) or {}).get("Es", 0.0) or 0.0)
        fiber_groups = dict(section.get("fibers", {}) or {})
        ea = 0.0
        eiy = 0.0
        eiz = 0.0
        for fiber in (fiber_groups.get("core", []) or []):
            a = float(fiber.get("area_m2", 0.0) or 0.0)
            y = float(fiber.get("y_m", 0.0) or 0.0)
            z = float(fiber.get("z_m", 0.0) or 0.0)
            ea += core_Ec * a
            eiy += core_Ec * a * z * z
            eiz += core_Ec * a * y * y
        for key in ("inner_cover", "outer_cover"):
            for fiber in (fiber_groups.get(key, []) or []):
                a = float(fiber.get("area_m2", 0.0) or 0.0)
                y = float(fiber.get("y_m", 0.0) or 0.0)
                z = float(fiber.get("z_m", 0.0) or 0.0)
                ea += cover_Ec * a
                eiy += cover_Ec * a * z * z
                eiz += cover_Ec * a * y * y
        for group in (fiber_groups.get("rebar_groups", []) or []):
            for fiber in (group.get("fibers", []) or []):
                a = float(fiber.get("area_m2", 0.0) or 0.0)
                y = float(fiber.get("y_m", 0.0) or 0.0)
                z = float(fiber.get("z_m", 0.0) or 0.0)
                ea += rebar_Es * a
                eiy += rebar_Es * a * z * z
                eiz += rebar_Es * a * y * y

        e_eq = 0.0
        if area > 1.0e-12 and ea > 0.0:
            e_eq = ea / area
        if inertia > 1.0e-12:
            e_from_i = []
            if iy > 1.0e-12 and eiy > 0.0:
                e_from_i.append(eiy / iy)
            if iz > 1.0e-12 and eiz > 0.0:
                e_from_i.append(eiz / iz)
            if e_from_i:
                e_eq = sum(e_from_i) / len(e_from_i)
        material_info = dict(section.get("material_info", {}) or {})
        concrete_name = str(material_info.get("concrete_material", "") or USER_DEFINED_CONCRETE)
        if concrete_name not in concrete_material_options():
            concrete_name = USER_DEFINED_CONCRETE
        return {
            "pile_shape": "Circle",
            "pile_diameter_m": max(diameter, 1.0e-6),
            "pile_thickness_m": 0.0,
            "pile_concrete_material": concrete_name,
            "pile_E_kPa": max(e_eq, 1.0),
        }

    def _sync_derived_group_pile_fields(self):
        derived = self._derive_pile_properties_from_h5()
        if not derived:
            return
        blockers = [
            QSignalBlocker(self.pile_shape),
            QSignalBlocker(self.pile_d),
            QSignalBlocker(self.pile_t),
            QSignalBlocker(self.pile_concrete_material),
            QSignalBlocker(self.pile_E),
        ]
        self.pile_shape.setCurrentText(str(derived["pile_shape"]))
        self.pile_d.setValue(float(derived["pile_diameter_m"]))
        self.pile_t.setValue(float(derived["pile_thickness_m"]))
        self.pile_concrete_material.setCurrentText(str(derived["pile_concrete_material"]))
        self.pile_E.setValue(float(derived["pile_E_kPa"]))
        del blockers

    @Slot()
    def _on_pile_shape_changed(self, _text: str):
        if self._pile_type_loading:
            return
        self._update_section()

    @Slot()
    def _on_pile_type_param_changed(self):
        if self._pile_type_loading:
            return
        idx = self.pile_type_selector.currentIndex()
        if idx < 0:
            return
        self.pile_types[idx] = self._current_pile_type_payload(str(self.pile_types[idx].get("name", f"PileType-{idx + 1}")))
        self._update_section()
        self._sync_cap_from_piles()
        self._notify_changed()

    def _update_section(self):
        if not hasattr(self, "pile_form") or not hasattr(self, "pile_t_row"):
            return
        mode = self.fiber_section_widget.current_mode() if hasattr(self, "fiber_section_widget") else "elastic"
        derived_mode = mode == "fiber"
        if derived_mode:
            self._sync_derived_group_pile_fields()
        show_manual_rows = not derived_mode
        self._set_row_visible(self.pile_form, self.pile_shape_row_index, self.pile_shape_row, show_manual_rows)
        self._set_row_visible(self.pile_form, self.pile_d_row_index, self.pile_d_row, show_manual_rows)
        self._set_row_visible(self.pile_form, self.pile_material_row_index, self.pile_material_row, show_manual_rows)
        self._set_row_visible(self.pile_form, self.pile_E_row_index, self.pile_E_row, show_manual_rows)
        if hasattr(self, "geometry_table"):
            self.geometry_table.setColumnHidden(0, False)
            self.geometry_table.setColumnHidden(1, False)
        if show_manual_rows and self.pile_shape.currentText() == "Pipe":
            self.pile_t.setEnabled(True)
            self._set_row_visible(self.pile_form, self.pile_t_row_index, self.pile_t_row, True)
        else:
            self.pile_t.setEnabled(False)
            self._set_row_visible(self.pile_form, self.pile_t_row_index, self.pile_t_row, False)

    @Slot()
    def _new_pile_type(self):
        names = set(self._pile_type_names())
        i = 1
        while f"PileType-{i}" in names:
            i += 1
        name, ok = QInputDialog.getText(self.page_pile_definition, tr("New Pile Type"), tr("Pile type name:"), text=f"PileType-{i}")
        name = name.strip()
        if not ok or not name:
            return
        if name in names:
            QMessageBox.warning(self.page_pile_definition, tr("Name Exists"), tr("Pile type name already exists."))
            return
        self.pile_types.append(self._default_pile_type(name))
        self._refresh_pile_type_selector()
        self.pile_type_selector.setCurrentText(name)
        self._notify_changed()

    @Slot()
    def _delete_pile_type(self):
        if len(self.pile_types) <= 1:
            QMessageBox.warning(self.page_pile_definition, tr("Cannot Delete"), tr("At least one pile type must remain."))
            return
        idx = self.pile_type_selector.currentIndex()
        if idx < 0:
            return
        removed = str(self.pile_types[idx].get("name", ""))
        del self.pile_types[idx]
        self._refresh_pile_type_selector()
        self.pile_type_selector.setCurrentIndex(0)
        self._load_pile_type(0)
        for row in range(self.layout_table.rowCount()):
            combo = self.layout_table.cellWidget(row, 4)
            if isinstance(combo, QComboBox) and combo.currentText() == removed:
                combo.setCurrentIndex(0)
        self._sync_cap_from_piles()
        self._notify_changed()

    @Slot()
    def _rename_pile_type(self):
        idx = self.pile_type_selector.currentIndex()
        if idx < 0:
            return
        old_name = str(self.pile_types[idx].get("name", ""))
        name, ok = QInputDialog.getText(self.page_pile_definition, tr("Rename Pile Type"), tr("Pile type name:"), text=old_name)
        name = name.strip()
        if not ok or not name or name == old_name:
            return
        names = set(self._pile_type_names())
        names.discard(old_name)
        if name in names:
            QMessageBox.warning(self.page_pile_definition, tr("Name Exists"), tr("Pile type name already exists."))
            return
        self.pile_types[idx]["name"] = name
        self._refresh_pile_type_selector()
        self.pile_type_selector.setCurrentText(name)
        self._notify_changed()

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

    def _sync_cap_from_piles(self):
        pile_tops = [float(p.get("pile_top_z_m", 0.0)) for p in self.pile_types if isinstance(p, dict)]
        cap_bottom = max(pile_tops) if pile_tops else 0.0
        cap_height = self.cap_height.value()
        cap_top = cap_bottom + cap_height
        cap_center = 0.5 * (cap_top + cap_bottom)
        self.cap_bottom_z.setText(f"{cap_bottom:.4f}")
        self.cap_top_z.setText(f"{cap_top:.4f}")
        self.cap_center_z.setText(f"{cap_center:.4f}")

    @Slot()
    def _on_cap_changed(self):
        self._sync_cap_from_piles()
        self._notify_changed()

    def _add_layout_row(
        self,
        x: float = 0.0,
        y: float = 0.0,
        top_z: float = 0.0,
        bottom_z: float = -27.0,
        pile_type_name: Optional[str] = None,
        connectivity: str = "Fixed",
        p_multiplier: Optional[float] = None,
    ):
        row = self.layout_table.rowCount()
        self.layout_table.insertRow(row)
        self.layout_table.setItem(row, 0, QTableWidgetItem(f"{x:.4f}"))
        self.layout_table.setItem(row, 1, QTableWidgetItem(f"{y:.4f}"))
        self.layout_table.setItem(row, 2, QTableWidgetItem(f"{top_z:.4f}"))
        self.layout_table.setItem(row, 3, QTableWidgetItem(f"{bottom_z:.4f}"))
        pile_combo = QComboBox()
        pile_combo.addItems(self._pile_type_names())
        if pile_type_name is None and self._pile_type_names():
            pile_type_name = self._pile_type_names()[0]
        if pile_type_name in self._pile_type_names():
            pile_combo.setCurrentText(pile_type_name)
        pile_combo.currentTextChanged.connect(lambda *_: self._notify_changed())
        self.layout_table.setCellWidget(row, 4, pile_combo)
        conn_combo = QComboBox()
        conn_combo.addItems(CONNECTIVITY_TYPES)
        conn_combo.setCurrentText(connectivity)
        conn_combo.currentTextChanged.connect(lambda *_: self._notify_changed())
        self.layout_table.setCellWidget(row, 5, conn_combo)
        if p_multiplier is None:
            p_multiplier = 1.0
        self.layout_table.setItem(row, 6, QTableWidgetItem(f"{float(p_multiplier):.4f}"))
        self._refresh_mesh_pile_selector()

    @Slot()
    def _on_p_multiplier_mode_changed(self):
        manual = self.p_multiplier_manual_radio.isChecked()
        self.p_multiplier_auto_note.setVisible(not manual)
        self.layout_table.setColumnHidden(6, not manual)
        self._notify_changed()

    @Slot()
    def _delete_layout_row(self):
        row = self.layout_table.currentRow()
        if row < 0:
            row = self.layout_table.rowCount() - 1
        if row < 0:
            return
        self.layout_table.removeRow(row)
        self._refresh_mesh_pile_selector()
        self._notify_changed()

    @Slot()
    def _on_layout_item_changed(self):
        if self._loading:
            return
        self._refresh_mesh_pile_selector()
        self._notify_changed()

    def collect_payload(self) -> Dict:
        self._save_current_mesh_settings()
        layers: List[Dict] = []
        prev_bottom = None
        for row in range(self.layer_table.rowCount()):
            top_item = self.layer_table.item(row, 0)
            bottom_item = self.layer_table.item(row, 1)
            if top_item is None or bottom_item is None:
                continue
            combo = self.layer_table.cellWidget(row, 2)
            z_top = float(top_item.text())
            z_bottom = float(bottom_item.text())
            if row == 0 and abs(z_top) > 1.0e-8:
                raise ValueError("First layer top depth is fixed at 0.0 m.")
            if z_bottom >= z_top:
                raise ValueError(f"Layer row {row + 1}: bottom depth must be smaller than top depth.")
            if prev_bottom is not None and z_top > prev_bottom + 1.0e-8:
                raise ValueError("Soil layers must be sorted and non-overlapping.")
            prev_bottom = z_bottom
            layers.append({"z_top": z_top, "z_bottom": z_bottom, "material_name": combo.currentText() if isinstance(combo, QComboBox) else ""})

        pile_layout: List[Dict] = []
        for row in range(self.layout_table.rowCount()):
            x_item = self.layout_table.item(row, 0)
            y_item = self.layout_table.item(row, 1)
            top_item = self.layout_table.item(row, 2)
            bottom_item = self.layout_table.item(row, 3)
            p_item = self.layout_table.item(row, 6)
            if None in (x_item, y_item, top_item, bottom_item):
                continue
            pile_combo = self.layout_table.cellWidget(row, 4)
            conn_combo = self.layout_table.cellWidget(row, 5)
            p_multiplier = 1.0
            if p_item is not None and p_item.text().strip():
                p_multiplier = float(p_item.text())
            pile_layout.append({
                "x_m": float(x_item.text()),
                "y_m": float(y_item.text()),
                "top_z_m": float(top_item.text()),
                "bottom_z_m": float(bottom_item.text()),
                "pile_type_name": pile_combo.currentText() if isinstance(pile_combo, QComboBox) else "",
                "connectivity": (conn_combo.currentText() if isinstance(conn_combo, QComboBox) else "Fixed").lower(),
                "p_multiplier_manual": p_multiplier,
            })

        load_cases: List[Dict] = []
        for base in range(0, self.load_table.rowCount(), 4):
            x_item = self.load_table.item(base + 1, 2)
            y_item = self.load_table.item(base + 1, 4)
            values = [self.load_table.item(base + 3, col) for col in range(6)]
            if x_item is None or y_item is None or any(item is None for item in values):
                continue
            fx_item, fy_item, fz_item, mx_item, my_item, mz_item = values
            load_cases.append(
                {
                    "load_no": (base // 4) + 1,
                    "x_m": float(x_item.text()),
                    "y_m": float(y_item.text()),
                    "Fx": float(fx_item.text()),
                    "Fy": float(fy_item.text()),
                    "Fz": float(fz_item.text()),
                    "Mx": float(mx_item.text()),
                    "My": float(my_item.text()),
                    "Mz": float(mz_item.text()),
                }
            )

        mesh_settings = self.mesh_settings_widget.get_settings()
        mesh_error = self.mesh_settings_widget.validate_custom_segments()
        if mesh_error:
            raise ValueError(mesh_error)
        mesh_settings_by_pile = {
            key: dict(value)
            for key, value in self._mesh_settings_by_pile.items()
            if isinstance(value, dict)
        }
        for idx, pile in enumerate(pile_layout, start=1):
            total_length = abs(float(pile.get("top_z_m", 0.0)) - float(pile.get("bottom_z_m", 0.0)))
            pile_mesh_settings = mesh_settings_by_pile.get(self._mesh_key_for_layout_row(idx - 1), mesh_settings)
            try:
                build_mesh_positions(total_length, pile_mesh_settings)
            except Exception as exc:
                raise ValueError(f"Pile row {idx} mesh setting is invalid for pile length {total_length:.4f} m: {exc}") from exc
        reference_length = abs(float(pile_layout[0].get("top_z_m", 0.0)) - float(pile_layout[0].get("bottom_z_m", 0.0))) if pile_layout else self.pile_len.value()
        reference_mesh = mesh_settings_by_pile.get(self._mesh_key_for_layout_row(0), mesh_settings)
        rep_ele_size = representative_element_size(reference_length, reference_mesh) or 0.0

        return {
            "materials": [dict(m) for m in self.materials],
            "layers": layers,
            "pile_types": [dict(p) for p in self.pile_types],
            "mesh_settings": mesh_settings,
            "mesh_settings_by_pile": mesh_settings_by_pile,
            "ele_size_m": rep_ele_size,
            "cap": {
                "shape": "Rectangular",
                "length_x_m": self.cap_length_x.value(),
                "length_y_m": self.cap_length_y.value(),
                "height_m": self.cap_height.value(),
                "center_z_m": float(self.cap_center_z.text() or "0.0"),
                "bottom_z_m": float(self.cap_bottom_z.text() or "0.0"),
            },
            "pile_layout": pile_layout,
            "load_cases": load_cases,
            "loads": load_cases,
            "p_multiplier_mode": "manual" if self.p_multiplier_manual_radio.isChecked() else "automatic",
            "p_multiplier_manual": float(pile_layout[0].get("p_multiplier_manual", 1.0)) if pile_layout else 1.0,
            "coordinate_origin": "cap_center",
            "analysis_type": "static_group_3d",
            "active_models": ["py", "tz", "qz"],
            "steps": 40,
        }

    def set_payload(self, payload: Dict):
        self._loading = True
        blockers = [
            QSignalBlocker(self.material_selector),
            QSignalBlocker(self.axial_type),
            QSignalBlocker(self.lateral_type),
            QSignalBlocker(self.layer_table),
            QSignalBlocker(self.pile_type_selector),
            QSignalBlocker(self.layout_table),
            QSignalBlocker(self.load_table),
            QSignalBlocker(self.cap_length_x),
            QSignalBlocker(self.cap_length_y),
            QSignalBlocker(self.cap_height),
            QSignalBlocker(self.mesh_pile_selector),
            QSignalBlocker(self.p_multiplier_auto_radio),
            QSignalBlocker(self.p_multiplier_manual_radio),
        ]
        update_widgets = [
            getattr(self, "page_soil_material", None),
            getattr(self, "page_soil_layers", None),
            getattr(self, "page_pile_definition", None),
            getattr(self, "page_cap_definition", None),
            getattr(self, "page_pile_layout", None),
            getattr(self, "page_load", None),
        ]
        for widget in update_widgets:
            if widget is not None:
                widget.setUpdatesEnabled(False)
        try:
            self._mesh_settings_by_pile = {
                str(key): dict(value)
                for key, value in (payload.get("mesh_settings_by_pile") or {}).items()
                if isinstance(value, dict)
            }
            self.mesh_settings_widget.set_settings(payload.get("mesh_settings"))
            materials = payload.get("materials", [])
            if isinstance(materials, list) and materials:
                normalized = []
                for idx, mat in enumerate(materials, start=1):
                    if not isinstance(mat, dict):
                        continue
                    if "axial_type" in mat or "lateral_type" in mat:
                        normalized.append({
                            "name": str(mat.get("name", f"Material-{idx}")),
                            "bg_color": str(mat.get("bg_color", "#e8c7cf")),
                            "bg_alpha": float(mat.get("bg_alpha", 0.28)),
                            "axial_type": str(mat.get("axial_type", "API Clay")),
                            "axial_params": dict(mat.get("axial_params", {})),
                            "lateral_type": str(mat.get("lateral_type", "Soft Clay Soil")),
                            "lateral_params": dict(mat.get("lateral_params", {})),
                        })
                    else:
                        lateral_type = str(mat.get("soil_type", "Sand"))
                        axial_type = "API Sand" if lateral_type in ("Sand", "API Method for Sand") else "API Clay"
                        normalized.append({
                            "name": str(mat.get("name", f"Material-{idx}")),
                            "bg_color": str(mat.get("bg_color", "#e8c7cf")),
                            "bg_alpha": float(mat.get("bg_alpha", 0.28)),
                            "axial_type": axial_type,
                            "axial_params": self._default_axial_params(axial_type),
                            "lateral_type": lateral_type,
                            "lateral_params": dict(mat.get("params", {})) or self._default_lateral_params(lateral_type),
                        })
                if normalized:
                    self.materials = normalized
            self._refresh_material_selector()
            if self.materials:
                self.material_selector.setCurrentIndex(0)
                self._load_material(0)

            self.layer_table.setRowCount(0)
            for layer in payload.get("layers", []):
                if isinstance(layer, dict):
                    z_top = -abs(float(layer.get("z_top", 0.0)))
                    z_bottom = -abs(float(layer.get("z_bottom", -1.0)))
                    self._add_layer_row(z_top, z_bottom, str(layer.get("material_name", self._material_names()[0] if self._material_names() else "")))

            pile_types = payload.get("pile_types", [])
            if isinstance(pile_types, list) and pile_types:
                self.pile_types = [dict(p) for p in pile_types if isinstance(p, dict)]
            self._refresh_pile_type_selector()
            if self.pile_types:
                self.pile_type_selector.setCurrentIndex(0)
                self._load_pile_type(0)

            cap = payload.get("cap", {})
            if isinstance(cap, dict):
                self.cap_length_x.setValue(float(cap.get("length_x_m", 6.0)))
                self.cap_length_y.setValue(float(cap.get("length_y_m", 6.0)))
                self.cap_height.setValue(float(cap.get("height_m", 1.0)))

            self.layout_table.setRowCount(0)
            for row in payload.get("pile_layout", []):
                if isinstance(row, dict):
                    self._add_layout_row(
                        float(row.get("x_m", 0.0)),
                        float(row.get("y_m", 0.0)),
                        float(row.get("top_z_m", 0.0)),
                        float(row.get("bottom_z_m", -27.0)),
                        str(row.get("pile_type_name", self._pile_type_names()[0] if self._pile_type_names() else "")),
                        str(row.get("connectivity", "Fixed")).capitalize(),
                        float(row.get("p_multiplier_manual", payload.get("p_multiplier_manual", 1.0))),
                    )

            self.load_table.setRowCount(0)
            load_cases = payload.get("load_cases", [])
            if isinstance(load_cases, list) and load_cases:
                for row in load_cases:
                    if not isinstance(row, dict):
                        continue
                    self._add_load_case_row(
                        x=float(row.get("x_m", 0.0)),
                        y=float(row.get("y_m", 0.0)),
                        fx=float(row.get("Fx", 0.0)),
                        fy=float(row.get("Fy", 0.0)),
                        fz=float(row.get("Fz", 0.0)),
                        mx=float(row.get("Mx", 0.0)),
                        my=float(row.get("My", 0.0)),
                        mz=float(row.get("Mz", 0.0)),
                    )
            else:
                loads = payload.get("loads", [])
                if isinstance(loads, list) and loads and any(isinstance(row, dict) and "type" in row for row in loads):
                    merged = {"x_m": 0.0, "y_m": 0.0, "Fx": 0.0, "Fy": 0.0, "Fz": 0.0, "Mx": 0.0, "My": 0.0, "Mz": 0.0}
                    for row in loads:
                        if not isinstance(row, dict):
                            continue
                        load_type = str(row.get("type", "")).split()[0]
                        if load_type in merged:
                            merged[load_type] = float(row.get("value", 0.0))
                            merged["x_m"] = float(row.get("x_m", merged["x_m"]))
                            merged["y_m"] = float(row.get("y_m", merged["y_m"]))
                    self._add_load_case_row(
                        x=merged["x_m"], y=merged["y_m"], fx=merged["Fx"], fy=merged["Fy"],
                        fz=merged["Fz"], mx=merged["Mx"], my=merged["My"], mz=merged["Mz"],
                    )
                else:
                    self._add_load_case_row()

            p_mode = str(payload.get("p_multiplier_mode", "automatic")).lower()
            self.p_multiplier_manual_radio.setChecked(p_mode == "manual")
            self.p_multiplier_auto_radio.setChecked(p_mode != "manual")
            self._on_p_multiplier_mode_changed()
            self._refresh_mesh_pile_selector()
            self._sync_cap_from_piles()
            self._update_section()
        finally:
            for widget in update_widgets:
                if widget is not None:
                    widget.setUpdatesEnabled(True)
            self._loading = False
            del blockers
        self._notify_changed()
