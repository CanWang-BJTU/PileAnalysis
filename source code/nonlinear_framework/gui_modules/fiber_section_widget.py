# -*- coding: utf-8 -*-

from __future__ import annotations

import math
import os
from typing import Callable, Dict, List, Optional

import h5py
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from language_manager import get_language
from ui_localization import translate_text

HAS_MATPLOTLIB = True
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
    from matplotlib.figure import Figure
    from matplotlib.patches import Polygon as MplPolygon
    from matplotlib.tri import Triangulation
except Exception:
    HAS_MATPLOTLIB = False
    FigureCanvas = None
    NavigationToolbar = None
    Figure = None
    MplPolygon = None
    Triangulation = None


def _decode_value(value):
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, np.generic):
        return value.item()
    return value


def _dataset_rows(dataset) -> List[List[object]]:
    rows: List[List[object]] = []
    names = dataset.dtype.names or []
    for raw_row in dataset[:]:
        row = []
        for name in names:
            row.append(_decode_value(raw_row[name]))
        rows.append(row)
    return rows


def _first_scalar(group: h5py.Group, name: str):
    if name not in group:
        return None
    rows = _dataset_rows(group[name])
    if not rows or not rows[0]:
        return None
    return rows[0][0]


def _dataset_mapping(group: h5py.Group, name: str) -> Dict[str, object]:
    if name not in group:
        return {}
    dataset = group[name]
    names = dataset.dtype.names or []
    rows = dataset[:]
    if len(rows) == 0:
        return {}
    first = rows[0]
    mapping = {}
    for key in names:
        mapping[str(key)] = _decode_value(first[key])
    return mapping


def _match_first(group: h5py.Group, prefix: str):
    names = sorted([name for name in group.keys() if name.startswith(prefix)])
    return names[0] if names else None


class SectionMCPyReader:
    @staticmethod
    def list_cases(path: str) -> List[str]:
        with h5py.File(path, "r") as f:
            return sorted([name for name in f.keys() if name.startswith("mc_analysis_")])

    @staticmethod
    def load(path: str, case_name: Optional[str] = None) -> Dict:
        with h5py.File(path, "r") as f:
            if "fiberMesh" not in f:
                raise ValueError("Selected H5 does not contain a fiberMesh group.")
            case_names = sorted([name for name in f.keys() if name.startswith("mc_analysis_")])
            if case_name is None:
                if not case_names:
                    raise ValueError("Selected H5 does not contain any mc_analysis_* group.")
                case_name = case_names[0]
            if case_name not in f:
                raise ValueError(f"Analysis case '{case_name}' was not found in the H5 file.")

            fiber_group = f["fiberMesh"]
            case_group = f[case_name]

            core_fibers = SectionMCPyReader._fiber_rows(fiber_group.get("coreFiberInfo"), "core")
            inner_cover_fibers = SectionMCPyReader._fiber_rows(fiber_group.get("innerCoverFiberInfo"), "inner_cover")
            outer_cover_fibers = SectionMCPyReader._fiber_rows(fiber_group.get("outCoverFiberInfo"), "outer_cover")

            rebar_group_names = [row[0] for row in _dataset_rows(fiber_group["barFiberName"])] if "barFiberName" in fiber_group else []
            rebar_groups = []
            rebar_fibers: List[Dict] = []
            for group_name in rebar_group_names:
                fibers = SectionMCPyReader._fiber_rows(fiber_group.get(str(group_name)), "rebar")
                rebar_groups.append(
                    {
                        "name": str(group_name),
                        "fiber_count": len(fibers),
                        "total_area_m2": float(sum(f["area_m2"] for f in fibers)),
                        "fibers": fibers,
                    }
                )
                rebar_fibers.extend(fibers)

            out_points = SectionMCPyReader._point_rows(fiber_group.get("outPoints"))
            core_points = SectionMCPyReader._point_rows(fiber_group.get("corePoints"))
            inner_points = []
            if "innerPointsName" in fiber_group:
                for row in _dataset_rows(fiber_group["innerPointsName"]):
                    dataset_name = str(row[0])
                    inner_points.append(SectionMCPyReader._point_rows(fiber_group.get(dataset_name)))
            core_triangles = SectionMCPyReader._triangle_rows(fiber_group.get("coreTriangles"))
            out_triangles = []
            if "outTrianglesName" in fiber_group:
                for row in _dataset_rows(fiber_group["outTrianglesName"]):
                    dataset_name = str(row[0])
                    out_triangles.append(SectionMCPyReader._triangle_rows(fiber_group.get(dataset_name)))
            inner_triangles = []
            if "innerTrianglesName" in fiber_group:
                for row in _dataset_rows(fiber_group["innerTrianglesName"]):
                    dataset_name = str(row[0])
                    inner_triangles.append(SectionMCPyReader._triangle_rows(fiber_group.get(dataset_name)))

            all_fibers = core_fibers + inner_cover_fibers + outer_cover_fibers + rebar_fibers
            props = SectionMCPyReader._section_properties(all_fibers)

            core_material_dataset = _match_first(case_group, "coreMaterial")
            rebar_material_datasets = sorted([name for name in case_group.keys() if name.startswith("rebarMaterial")])
            rebar_materials = []
            for dataset_name in rebar_material_datasets:
                value = _first_scalar(case_group, dataset_name)
                if value is not None:
                    rebar_materials.append(str(value))

            material_info = {
                "case_name": str(_first_scalar(case_group, "caseName") or case_name.replace("mc_analysis_", "")),
                "section_type": str(_first_scalar(case_group, "sectionType") or "Unknown"),
                "concrete_material": str(_first_scalar(case_group, core_material_dataset) or ""),
                "rebar_material": ", ".join(rebar_materials),
                "stirrup_type": _first_scalar(case_group, "stirrupType"),
                "stirrup_diameter_m": _first_scalar(case_group, "stirrupDiameter"),
                "stirrup_space_m": _first_scalar(case_group, "stirrupSpace"),
                "stirrup_yield_strength_mpa": _first_scalar(case_group, "stirrupYieldStrength"),
                "rebar_space_m": _first_scalar(case_group, "rebarSpace"),
                "stirrup_ratio_y": _first_scalar(case_group, "stirrupRatioY"),
                "stirrup_ratio_z": _first_scalar(case_group, "stirrupRatioZ"),
            }
            material_params = {
                "core_concrete": _dataset_mapping(case_group, "coreConcreteMatParas"),
                "cover_concrete": _dataset_mapping(case_group, "coverConcreteMatParas"),
                "rebar": _dataset_mapping(case_group, "barMatParas"),
            }

            total_rebar_area = float(sum(group["total_area_m2"] for group in rebar_groups))
            reinforcement_ratio = 0.0 if props["area_m2"] <= 1.0e-12 else total_rebar_area / props["area_m2"]

            return {
                "name": material_info["case_name"] or os.path.splitext(os.path.basename(path))[0],
                "source_h5_path": path,
                "source_case": case_name,
                "material_info": material_info,
                "material_params": material_params,
                "fibers": {
                    "core": core_fibers,
                    "inner_cover": inner_cover_fibers,
                    "outer_cover": outer_cover_fibers,
                    "rebar_groups": rebar_groups,
                },
                "geometry": {
                    "out_points": out_points,
                    "core_points": core_points,
                    "inner_points": inner_points,
                    "core_triangles": core_triangles,
                    "out_triangles": out_triangles,
                    "inner_triangles": inner_triangles,
                    "section_width_height_ratio": _first_scalar(fiber_group, "sectionWidthHeightRatio"),
                },
                "summary": {
                    "fiber_count": len(all_fibers),
                    "core_fiber_count": len(core_fibers),
                    "inner_cover_fiber_count": len(inner_cover_fibers),
                    "outer_cover_fiber_count": len(outer_cover_fibers),
                    "rebar_fiber_count": len(rebar_fibers),
                    "rebar_group_count": len(rebar_groups),
                    "total_rebar_area_m2": total_rebar_area,
                    "reinforcement_ratio": reinforcement_ratio,
                    **props,
                },
            }

    @staticmethod
    def _fiber_rows(dataset, role: str) -> List[Dict]:
        if dataset is None:
            return []
        rows = _dataset_rows(dataset)
        fibers = []
        for row in rows:
            if len(row) < 4:
                continue
            fibers.append(
                {
                    "tag": int(row[0]),
                    "y_m": float(row[1]),
                    "z_m": float(row[2]),
                    "area_m2": float(row[3]),
                    "role": role,
                }
            )
        return fibers

    @staticmethod
    def _point_rows(dataset) -> List[List[float]]:
        if dataset is None:
            return []
        points = []
        for row in _dataset_rows(dataset):
            if len(row) >= 2:
                points.append([float(row[0]), float(row[1])])
        return points

    @staticmethod
    def _triangle_rows(dataset) -> List[List[int]]:
        if dataset is None:
            return []
        triangles = []
        for row in _dataset_rows(dataset):
            if len(row) >= 3:
                triangles.append([int(row[0]), int(row[1]), int(row[2])])
        return triangles

    @staticmethod
    def _section_properties(fibers: List[Dict]) -> Dict:
        if not fibers:
            return {
                "area_m2": 0.0,
                "centroid_y_m": 0.0,
                "centroid_z_m": 0.0,
                "iy_m4": 0.0,
                "iz_m4": 0.0,
                "j_approx_m4": 0.0,
            }
        areas = np.array([float(f["area_m2"]) for f in fibers], dtype=float)
        ys = np.array([float(f["y_m"]) for f in fibers], dtype=float)
        zs = np.array([float(f["z_m"]) for f in fibers], dtype=float)
        area = float(np.sum(areas))
        cy = float(np.sum(areas * ys) / max(area, 1.0e-12))
        cz = float(np.sum(areas * zs) / max(area, 1.0e-12))
        iy = float(np.sum(areas * (zs - cz) ** 2))
        iz = float(np.sum(areas * (ys - cy) ** 2))
        return {
            "area_m2": area,
            "centroid_y_m": cy,
            "centroid_z_m": cz,
            "iy_m4": iy,
            "iz_m4": iz,
            "j_approx_m4": iy + iz,
        }


class FiberSectionWidget(QWidget):
    changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None, allow_comparison: bool = True):
        super().__init__(parent)
        self._change_callback: Optional[Callable[[], None]] = None
        self._total_length_provider: Optional[Callable[[], float]] = None
        self._section_library: List[Dict] = []
        self._loading = False
        self._allow_comparison = bool(allow_comparison)
        self._external_elastic_widget: Optional[QWidget] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)
        self._root_layout = root

        mode_box = QGroupBox("Section Model")
        mode_layout = QHBoxLayout(mode_box)
        self.elastic_radio = QRadioButton("Elastic")
        self.fiber_radio = QRadioButton("Nonlinear Fiber")
        self.comparison_radio = QRadioButton("Comparison")
        self.elastic_radio.setChecked(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.elastic_radio)
        self.mode_group.addButton(self.fiber_radio)
        self.mode_group.addButton(self.comparison_radio)
        mode_layout.addWidget(self.elastic_radio)
        mode_layout.addWidget(self.fiber_radio)
        mode_layout.addWidget(self.comparison_radio)
        mode_layout.addStretch()
        root.addWidget(mode_box)
        self.comparison_radio.setVisible(self._allow_comparison)

        self.elastic_host = QWidget()
        self.elastic_host_layout = QVBoxLayout(self.elastic_host)
        self.elastic_host_layout.setContentsMargins(0, 0, 0, 0)
        self.elastic_host_layout.setSpacing(0)
        self.elastic_host_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        root.addWidget(self.elastic_host)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        self.comparison_tabs = QTabWidget()
        self.comparison_tabs.setDocumentMode(True)
        self.comparison_elastic_page = QWidget()
        self.comparison_elastic_layout = QVBoxLayout(self.comparison_elastic_page)
        self.comparison_elastic_layout.setContentsMargins(0, 0, 0, 0)
        self.comparison_elastic_layout.setSpacing(0)
        self.comparison_elastic_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.comparison_fiber_page = QWidget()
        self.comparison_fiber_layout = QVBoxLayout(self.comparison_fiber_page)
        self.comparison_fiber_layout.setContentsMargins(0, 0, 0, 0)
        self.comparison_fiber_layout.setSpacing(0)
        self.comparison_fiber_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.comparison_tabs.addTab(self.comparison_elastic_page, "Elastic")
        self.comparison_tabs.addTab(self.comparison_fiber_page, "Fiber")
        root.addWidget(self.comparison_tabs)

        self.definition_tab = QWidget()
        self.segment_tab = QWidget()
        self.tabs.addTab(self.definition_tab, "Fiber Section Definition")
        self.tabs.addTab(self.segment_tab, "Pile Section Layout")

        self._build_definition_tab()
        self._build_segment_tab()
        self._refresh_mode_ui()

        self.elastic_radio.toggled.connect(self._on_mode_changed)
        self.fiber_radio.toggled.connect(self._on_mode_changed)
        self.comparison_radio.toggled.connect(self._on_mode_changed)
        self.tabs.currentChanged.connect(lambda _=None: self._update_tab_heights())
        self.comparison_tabs.currentChanged.connect(lambda _=None: self._update_tab_heights())

    def set_change_callback(self, callback: Optional[Callable[[], None]]):
        self._change_callback = callback

    def set_external_elastic_widget(self, widget: Optional[QWidget]):
        self._external_elastic_widget = widget
        self._refresh_mode_ui()

    def set_total_length_provider(self, provider: Optional[Callable[[], float]]):
        self._total_length_provider = provider
        self._refresh_segment_hint()

    def refresh_external_constraints(self):
        self._refresh_segment_hint()

    def is_fiber_mode(self) -> bool:
        return self.fiber_radio.isChecked()

    def is_comparison_mode(self) -> bool:
        return self._allow_comparison and self.comparison_radio.isChecked()

    def current_mode(self) -> str:
        if self.is_comparison_mode():
            return "comparison"
        if self.is_fiber_mode():
            return "fiber"
        return "elastic"

    def get_payload(self) -> Dict:
        return {
            "section_mode": self.current_mode(),
            "fiber_section_library": self._section_library,
            "fiber_section_segments": self._read_segments(),
        }

    def set_payload(self, payload: Optional[Dict]):
        payload = dict(payload or {})
        self._loading = True
        mode = str(payload.get("section_mode", "elastic"))
        normalized_mode = mode
        if normalized_mode == "comparison" and not self._allow_comparison:
            normalized_mode = "fiber"
        self.elastic_radio.setChecked(normalized_mode == "elastic")
        self.fiber_radio.setChecked(normalized_mode == "fiber")
        self.comparison_radio.setChecked(normalized_mode == "comparison")
        self._section_library = list(payload.get("fiber_section_library", []) or [])
        self._refresh_section_selector()
        self._write_segments(payload.get("fiber_section_segments", []))
        self._loading = False
        self._refresh_mode_ui()
        self._load_current_section()
        self._refresh_segment_hint()

    def _build_definition_tab(self):
        layout = QVBoxLayout(self.definition_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Section:"))
        self.section_selector = QComboBox()
        self.section_selector.setMinimumWidth(220)
        toolbar.addWidget(self.section_selector)
        self.new_btn = QPushButton("New")
        self.delete_btn = QPushButton("Delete")
        self.rename_btn = QPushButton("Rename")
        self.import_btn = QPushButton("Import H5")
        for button in (self.new_btn, self.delete_btn, self.rename_btn, self.import_btn):
            toolbar.addWidget(button)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        info_frame = QFrame()
        info_layout = QFormLayout(info_frame)
        info_layout.setHorizontalSpacing(10)
        info_layout.setVerticalSpacing(6)
        self.info_fields: Dict[str, QLineEdit] = {}
        self._info_field_rows: Dict[str, tuple] = {}
        for label, key in [
            ("Case Name", "case_name"),
            ("Concrete Material", "concrete_material"),
            ("Rebar Material", "rebar_material"),
            ("Stirrup Type", "stirrup_type"),
            ("Stirrup Diameter (m)", "stirrup_diameter_m"),
            ("Stirrup Space (m)", "stirrup_space_m"),
            ("Stirrup Yield Strength (MPa)", "stirrup_yield_strength_mpa"),
            ("Rebar Space (m)", "rebar_space_m"),
            ("Stirrup Ratio Y", "stirrup_ratio_y"),
            ("Stirrup Ratio Z", "stirrup_ratio_z"),
            ("Fiber Count", "fiber_count"),
            ("Rebar Groups", "rebar_group_count"),
            ("Area (m^2)", "area_m2"),
            ("Rebar Area (m^2)", "total_rebar_area_m2"),
            ("Rebar Ratio", "reinforcement_ratio"),
        ]:
            label_widget = QLabel(label)
            edit = QLineEdit()
            edit.setReadOnly(True)
            self.info_fields[key] = edit
            self._info_field_rows[key] = (info_layout.rowCount(), label_widget, edit)
            info_layout.addRow(label_widget, edit)
        self.info_form_layout = info_layout
        layout.addWidget(info_frame)

        self.rebar_table = QTableWidget(0, 3)
        self.rebar_table.setHorizontalHeaderLabels(["Group", "Fiber Count", "Total Area (m^2)"])
        self.rebar_table.verticalHeader().setVisible(False)
        self.rebar_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.rebar_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.rebar_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.rebar_table.setFixedHeight(130)
        layout.addWidget(self.rebar_table)

        preview_box = QGroupBox("Section Preview")
        preview_box.setMinimumHeight(360)
        preview_layout = QVBoxLayout(preview_box)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        if HAS_MATPLOTLIB:
            self.preview_tabs = QTabWidget(preview_box)

            self.mesh_tab = QWidget()
            self.mesh_figure = Figure(figsize=(5.8, 4.2))
            self.mesh_canvas = FigureCanvas(self.mesh_figure)
            self.mesh_canvas.setMinimumHeight(300)
            self.mesh_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.mesh_toolbar = NavigationToolbar(self.mesh_canvas, self.mesh_tab)
            mesh_layout = QVBoxLayout(self.mesh_tab)
            mesh_layout.setContentsMargins(0, 0, 0, 0)
            mesh_layout.setSpacing(4)
            mesh_layout.addWidget(self.mesh_toolbar)
            mesh_layout.addWidget(self.mesh_canvas, 1)

            self.points_tab = QWidget()
            self.points_figure = Figure(figsize=(5.8, 4.2))
            self.points_canvas = FigureCanvas(self.points_figure)
            self.points_canvas.setMinimumHeight(300)
            self.points_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.points_toolbar = NavigationToolbar(self.points_canvas, self.points_tab)
            points_layout = QVBoxLayout(self.points_tab)
            points_layout.setContentsMargins(0, 0, 0, 0)
            points_layout.setSpacing(4)
            points_layout.addWidget(self.points_toolbar)
            points_layout.addWidget(self.points_canvas, 1)

            self.preview_tabs.addTab(self.mesh_tab, "Mesh")
            self.preview_tabs.addTab(self.points_tab, "Fiber Points")
            preview_layout.addWidget(self.preview_tabs)
        else:
            self.preview_tabs = None
            self.mesh_figure = None
            self.mesh_canvas = None
            self.points_figure = None
            self.points_canvas = None
            preview_layout.addWidget(QLabel("matplotlib is unavailable in this environment."))
        layout.addWidget(preview_box, 1)

        self.section_selector.currentIndexChanged.connect(self._load_current_section)
        self.new_btn.clicked.connect(self._new_section)
        self.delete_btn.clicked.connect(self._delete_section)
        self.rename_btn.clicked.connect(self._rename_section)
        self.import_btn.clicked.connect(self._import_section)

    def _build_segment_tab(self):
        layout = QVBoxLayout(self.segment_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        hint_row = QHBoxLayout()
        self.segment_hint = QLabel(str(translate_text("Define pile sections by top/bottom depth and imported fiber section.", get_language())))
        self.segment_hint.setStyleSheet("color: #666666;")
        hint_row.addWidget(self.segment_hint)
        hint_row.addStretch()
        layout.addLayout(hint_row)

        self.segment_table = QTableWidget(0, 3)
        self.segment_table.setHorizontalHeaderLabels(["Top (m)", "Bottom (m)", "Section"])
        self.segment_table.verticalHeader().setVisible(False)
        self.segment_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.segment_table)

        btn_row = QHBoxLayout()
        self.add_segment_btn = QPushButton("Add Segment")
        self.delete_segment_btn = QPushButton("Delete Segment")
        btn_row.addWidget(self.add_segment_btn)
        btn_row.addWidget(self.delete_segment_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.add_segment_btn.clicked.connect(self._add_segment_row)
        self.delete_segment_btn.clicked.connect(self._delete_segment_row)
        self.segment_table.itemChanged.connect(lambda *_: self._emit_changed())

    def _on_mode_changed(self):
        if self._loading:
            return
        self._refresh_mode_ui()
        self._emit_changed()

    def _refresh_mode_ui(self):
        mode = self.current_mode()
        self._dock_widget(self.tabs, self._root_layout, 2)
        self.elastic_host.setVisible(False)
        self.tabs.setVisible(False)
        self.comparison_tabs.setVisible(False)
        self.definition_tab.setEnabled(mode != "elastic")
        self.segment_tab.setEnabled(mode != "elastic")
        if mode == "elastic":
            if self._external_elastic_widget is not None:
                self._dock_widget(self._external_elastic_widget, self.elastic_host_layout)
                self._external_elastic_widget.setVisible(True)
                self.elastic_host.setVisible(True)
        elif mode == "fiber":
            self.tabs.setVisible(True)
        elif mode == "comparison":
            self._dock_widget(self.tabs, self.comparison_fiber_layout)
            self.tabs.setVisible(True)
            if self._external_elastic_widget is not None:
                self._dock_widget(self._external_elastic_widget, self.comparison_elastic_layout)
                self._external_elastic_widget.setVisible(True)
            self.comparison_tabs.setVisible(True)
        self._update_tab_heights()

    def _update_tab_heights(self):
        self._fit_tab_widget_to_current_page(self.tabs)
        self._fit_tab_widget_to_current_page(self.comparison_tabs)

    @staticmethod
    def _fit_tab_widget_to_current_page(tab_widget: QTabWidget):
        current = tab_widget.currentWidget()
        if current is None:
            return
        tab_bar = tab_widget.tabBar()
        target = current.sizeHint().height() + tab_bar.sizeHint().height() + 12
        target = max(target, tab_bar.sizeHint().height() + 12)
        tab_widget.setMinimumHeight(target)
        tab_widget.setMaximumHeight(target)

    @staticmethod
    def _dock_widget(widget: Optional[QWidget], layout: QVBoxLayout, index: Optional[int] = None):
        if widget is None:
            return
        if widget.parentWidget() is layout.parentWidget() and layout.indexOf(widget) >= 0:
            return
        widget.setParent(None)
        if index is None or index < 0 or index > layout.count():
            layout.addWidget(widget)
        else:
            layout.insertWidget(index, widget)

    def _refresh_section_selector(self):
        current = self.section_selector.currentText()
        self.section_selector.blockSignals(True)
        self.section_selector.clear()
        for section in self._section_library:
            self.section_selector.addItem(str(section.get("name", "Unnamed")))
        if current:
            idx = self.section_selector.findText(current)
            if idx >= 0:
                self.section_selector.setCurrentIndex(idx)
        if self.section_selector.count() == 0:
            self.section_selector.blockSignals(False)
            self._clear_section_display()
            self._refresh_segment_section_choices()
            return
        if self.section_selector.currentIndex() < 0:
            self.section_selector.setCurrentIndex(0)
        self.section_selector.blockSignals(False)
        self._refresh_segment_section_choices()

    def _current_section(self) -> Optional[Dict]:
        idx = self.section_selector.currentIndex()
        if idx < 0 or idx >= len(self._section_library):
            return None
        return self._section_library[idx]

    def _load_current_section(self):
        section = self._current_section()
        if section is None:
            self._clear_section_display()
            return
        material = dict(section.get("material_info", {}))
        summary = dict(section.get("summary", {}))
        values = {
            "case_name": material.get("case_name", section.get("name", "")),
            "concrete_material": material.get("concrete_material", ""),
            "rebar_material": material.get("rebar_material", ""),
            "stirrup_type": material.get("stirrup_type", ""),
            "stirrup_diameter_m": material.get("stirrup_diameter_m", ""),
            "stirrup_space_m": material.get("stirrup_space_m", ""),
            "stirrup_yield_strength_mpa": material.get("stirrup_yield_strength_mpa", ""),
            "rebar_space_m": material.get("rebar_space_m", ""),
            "stirrup_ratio_y": material.get("stirrup_ratio_y", ""),
            "stirrup_ratio_z": material.get("stirrup_ratio_z", ""),
            "fiber_count": summary.get("fiber_count", 0),
            "rebar_group_count": summary.get("rebar_group_count", 0),
            "area_m2": summary.get("area_m2", 0.0),
            "total_rebar_area_m2": summary.get("total_rebar_area_m2", 0.0),
            "reinforcement_ratio": summary.get("reinforcement_ratio", 0.0),
        }
        for key, widget in self.info_fields.items():
            value = values.get(key, "")
            visible = not self._is_empty_info_value(value)
            self._set_info_row_visible(key, visible)
            if isinstance(value, float):
                widget.setText(f"{value:.6g}")
            else:
                widget.setText("" if not visible else str(value))
        self._fill_rebar_table(section)
        self._render_preview(section)

    def _clear_section_display(self):
        for key, widget in self.info_fields.items():
            widget.clear()
            self._set_info_row_visible(key, True)
        self.rebar_table.setRowCount(0)
        self._render_preview(None)

    @staticmethod
    def _is_empty_info_value(value) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            stripped = value.strip()
            return stripped == "" or stripped.lower() == "none"
        return False

    def _set_info_row_visible(self, key: str, visible: bool):
        row_info = self._info_field_rows.get(key)
        if row_info is None:
            return
        row_index, label_widget, field_widget = row_info
        try:
            self.info_form_layout.setRowVisible(row_index, visible)
        except Exception:
            label_widget.setVisible(visible)
            field_widget.setVisible(visible)

    def _fill_rebar_table(self, section: Dict):
        groups = list(section.get("fibers", {}).get("rebar_groups", []) or [])
        self.rebar_table.setRowCount(len(groups))
        for row, group in enumerate(groups):
            for col, value in enumerate([
                str(group.get("name", "")),
                int(group.get("fiber_count", 0)),
                f"{float(group.get('total_area_m2', 0.0)):.6g}",
            ]):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.rebar_table.setItem(row, col, item)

    def _render_preview(self, section: Optional[Dict]):
        if not HAS_MATPLOTLIB or self.mesh_figure is None or self.mesh_canvas is None or self.points_figure is None or self.points_canvas is None:
            return
        if section is None:
            self.mesh_figure.clear()
            self.points_figure.clear()
            mesh_ax = self.mesh_figure.add_subplot(111)
            points_ax = self.points_figure.add_subplot(111)
            empty_title = str(translate_text("No section loaded", get_language()))
            mesh_ax.set_title(empty_title)
            points_ax.set_title(empty_title)
            self.mesh_canvas.draw_idle()
            self.points_canvas.draw_idle()
            return
        self._render_mesh_preview(section)
        self._render_fiber_points_preview(section)

    @staticmethod
    def _fit_centered_limits(
        ax,
        width: float,
        height: float,
        canvas_width: float,
        canvas_height: float,
        center_x: float,
        center_y: float,
        fill_ratio: float = 0.80,
        extra_pad: float = 0.03,
    ):
        width = max(float(width), 1.0e-6)
        height = max(float(height), 1.0e-6)
        canvas_width = max(float(canvas_width), 1.0)
        canvas_height = max(float(canvas_height), 1.0)
        fill_ratio = min(max(float(fill_ratio), 0.1), 1.0)
        viewport_ratio = canvas_width / canvas_height
        data_ratio = width / height
        if data_ratio >= viewport_ratio:
            half_w = 0.5 * width / fill_ratio
            half_h = half_w / viewport_ratio
        else:
            half_h = 0.5 * height / fill_ratio
            half_w = half_h * viewport_ratio
        pad_scale = 1.0 + max(float(extra_pad), 0.0)
        half_w *= pad_scale
        half_h *= pad_scale
        ax.set_xlim(center_x - half_w, center_x + half_w)
        ax.set_ylim(center_y - half_h, center_y + half_h)

    def _render_mesh_preview(self, section: Dict):
        self.mesh_figure.clear()
        ax = self.mesh_figure.add_axes([0.10, 0.10, 0.80, 0.80])
        geom = dict(section.get("geometry", {}))
        out_points = geom.get("out_points", []) or []
        core_points = geom.get("core_points", []) or []
        inner_points = geom.get("inner_points", []) or []
        core_triangles = geom.get("core_triangles", []) or []
        out_triangles = geom.get("out_triangles", []) or []
        inner_triangles = geom.get("inner_triangles", []) or []
        bounds_x = []
        bounds_y = []

        def _append_bounds(points):
            if points is None:
                return
            try:
                for point in points:
                    if len(point) >= 2:
                        bounds_x.append(float(point[0]))
                        bounds_y.append(float(point[1]))
            except Exception:
                pass

        _append_bounds(core_points)
        _append_bounds(out_points)
        for hole in inner_points:
            _append_bounds(hole)
        rebar_groups = (section.get("fibers", {}) or {}).get("rebar_groups", []) or []
        for group in rebar_groups:
            for each_bar in group.get("fibers", []) or []:
                bounds_x.append(float(each_bar.get("y_m", 0.0)))
                bounds_y.append(float(each_bar.get("z_m", 0.0)))
        ax.clear()
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_frame_on(False)
        ax.axis("off")
        ax.set_anchor("C")
        if bounds_x and bounds_y:
            x_min, x_max = min(bounds_x), max(bounds_x)
            y_min, y_max = min(bounds_y), max(bounds_y)
            cx = 0.5 * (x_min + x_max)
            cy = 0.5 * (y_min + y_max)
            self._fit_centered_limits(
                ax,
                x_max - x_min,
                y_max - y_min,
                self.mesh_canvas.width(),
                self.mesh_canvas.height(),
                cx,
                cy,
                fill_ratio=0.80,
                extra_pad=0.02,
            )

        if Triangulation is not None and len(core_points) > 0 and len(core_triangles) > 0:
            tri = Triangulation(
                np.asarray([float(p[0]) for p in core_points], dtype=float),
                np.asarray([float(p[1]) for p in core_points], dtype=float),
                np.asarray(core_triangles, dtype=int),
            )
            ax.triplot(tri, color="b", linewidth=1.0)

        if Triangulation is not None:
            for idx, points in enumerate(inner_points):
                triangles = inner_triangles[idx] if idx < len(inner_triangles) else []
                if len(points) > 0 and len(triangles) > 0:
                    tri = Triangulation(
                        np.asarray([float(p[0]) for p in points], dtype=float),
                        np.asarray([float(p[1]) for p in points], dtype=float),
                        np.asarray(triangles, dtype=int),
                    )
                    ax.triplot(tri, color="r", linewidth=1.0)

            if len(out_points) > 0 and isinstance(out_points[0][0], (int, float)):
                out_region_points = [out_points]
            else:
                out_region_points = list(out_points)
            for idx, points in enumerate(out_region_points):
                triangles = out_triangles[idx] if idx < len(out_triangles) else []
                if len(points) > 0 and len(triangles) > 0:
                    tri = Triangulation(
                        np.asarray([float(p[0]) for p in points], dtype=float),
                        np.asarray([float(p[1]) for p in points], dtype=float),
                        np.asarray(triangles, dtype=int),
                    )
                    ax.triplot(tri, color="r", linewidth=1.0)

        self.mesh_canvas.draw()
        pt0 = ax.transData.transform((0.0, 0.0))
        pt1 = ax.transData.transform((1.0, 0.0))
        dx_pixels = max(pt1[0] - pt0[0], 1.0e-9)
        inches_per_data = dx_pixels / self.mesh_figure.dpi
        points_per_data = inches_per_data * 72.0

        for group in rebar_groups:
            for each_bar in group.get("fibers", []) or []:
                radius = (max(float(each_bar.get("area_m2", 0.0)), 1.0e-12) / 3.14159267) ** 0.5
                area = (1.15 * radius * points_per_data) ** 2
                ax.scatter(float(each_bar.get("y_m", 0.0)), float(each_bar.get("z_m", 0.0)), marker="o", s=area, color="k")

        self.mesh_canvas.draw()
        self.mesh_canvas.draw_idle()

    def _render_fiber_points_preview(self, section: Dict):
        self.points_figure.clear()
        ax = self.points_figure.add_axes([0.10, 0.10, 0.80, 0.80])

        fibers = dict(section.get("fibers", {}) or {})
        core_fibers = list(fibers.get("core", []) or [])
        inner_cover_fibers = list(fibers.get("inner_cover", []) or [])
        out_cover_fibers = list(fibers.get("outer_cover", []) or [])
        bars_fiber_list = [list(group.get("fibers", []) or []) for group in (fibers.get("rebar_groups", []) or [])]

        x_plot = []
        y_plot = []
        for each in core_fibers:
            x_plot.append(float(each.get("y_m", 0.0)))
            y_plot.append(float(each.get("z_m", 0.0)))
        for each in inner_cover_fibers:
            x_plot.append(float(each.get("y_m", 0.0)))
            y_plot.append(float(each.get("z_m", 0.0)))
        for each in out_cover_fibers:
            x_plot.append(float(each.get("y_m", 0.0)))
            y_plot.append(float(each.get("z_m", 0.0)))
        for each_type in bars_fiber_list:
            for each in each_type:
                x_plot.append(float(each.get("y_m", 0.0)))
                y_plot.append(float(each.get("z_m", 0.0)))

        bar_color_list = ["k", "brown", "lightblue", "gold"]
        colors_list = []
        for _ in core_fibers:
            colors_list.append("b")
        for _ in inner_cover_fibers:
            colors_list.append("g")
        for _ in out_cover_fibers:
            colors_list.append("g")
        for i1, each_type in enumerate(bars_fiber_list):
            color = bar_color_list[i1 % 4]
            for _ in each_type:
                colors_list.append(color)

        x_span = max(max(x_plot) - min(x_plot), 1.0e-6) if x_plot else 1.0
        y_span = max(max(y_plot) - min(y_plot), 1.0e-6) if y_plot else 1.0
        span = max(x_span, y_span, 1.0e-6)
        fig_size = min(self.points_figure.get_size_inches())
        marker_size = max(1.2, min(8.0, 55.0 * fig_size / span))
        sizes = np.full(len(x_plot), marker_size)
        ax.scatter(x_plot, y_plot, c=np.array(colors_list), s=sizes)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_frame_on(False)
        ax.axis("off")
        ax.set_anchor("C")

        if x_plot and y_plot:
            x_min, x_max = min(x_plot), max(x_plot)
            y_min, y_max = min(y_plot), max(y_plot)
            cx = 0.5 * (x_min + x_max)
            cy = 0.5 * (y_min + y_max)
            self._fit_centered_limits(
                ax,
                x_max - x_min,
                y_max - y_min,
                self.points_canvas.width(),
                self.points_canvas.height(),
                cx,
                cy,
                fill_ratio=0.80,
                extra_pad=0.02,
            )

        self.points_canvas.draw()
        self.points_canvas.draw_idle()

    def _new_section(self):
        name, ok = QInputDialog.getText(self, "New Fiber Section", "Section name:", text=f"Section-{len(self._section_library) + 1}")
        name = name.strip()
        if not ok or not name:
            return
        if any(str(sec.get("name", "")) == name for sec in self._section_library):
            QMessageBox.warning(self, "Name Exists", "Section name already exists.")
            return
        self._section_library.append(
            {
                "name": name,
                "source_h5_path": "",
                "source_case": "",
                "material_info": {},
                "material_params": {},
                "fibers": {"core": [], "inner_cover": [], "outer_cover": [], "rebar_groups": []},
                "geometry": {"out_points": [], "core_points": [], "inner_points": []},
                "summary": {},
            }
        )
        self._refresh_section_selector()
        self.section_selector.setCurrentText(name)
        self._load_current_section()
        self._emit_changed()

    def _delete_section(self):
        idx = self.section_selector.currentIndex()
        if idx < 0 or idx >= len(self._section_library):
            return
        name = str(self._section_library[idx].get("name", ""))
        del self._section_library[idx]
        self._refresh_section_selector()
        for row in range(self.segment_table.rowCount()):
            combo = self.segment_table.cellWidget(row, 2)
            if isinstance(combo, QComboBox) and combo.currentText() == name:
                if combo.count() > 0:
                    combo.setCurrentIndex(0)
        self._emit_changed()

    def _rename_section(self):
        section = self._current_section()
        if section is None:
            return
        old_name = str(section.get("name", ""))
        name, ok = QInputDialog.getText(self, "Rename Fiber Section", "Section name:", text=old_name)
        name = name.strip()
        if not ok or not name or name == old_name:
            return
        if any(str(sec.get("name", "")) == name for sec in self._section_library if sec is not section):
            QMessageBox.warning(self, "Name Exists", "Section name already exists.")
            return
        section["name"] = name
        self._refresh_section_selector()
        self.section_selector.setCurrentText(name)
        self._refresh_segment_section_choices()
        self._emit_changed()

    def _import_section(self):
        section = self._current_section()
        if section is None:
            self._new_section()
            section = self._current_section()
            if section is None:
                return
        file_path, _ = QFileDialog.getOpenFileName(self, "Import SectionMCPy H5", "", "H5 Files (*.h5)")
        if not file_path:
            return
        try:
            case_names = SectionMCPyReader.list_cases(file_path)
            selected_case = None
            if len(case_names) > 1:
                selected_case, ok = QInputDialog.getItem(self, "Select Analysis Case", "mc_analysis case:", [name.replace("mc_analysis_", "") for name in case_names], 0, False)
                if not ok:
                    return
                selected_case = f"mc_analysis_{selected_case}"
            loaded = SectionMCPyReader.load(file_path, selected_case)
        except Exception as exc:
            QMessageBox.critical(self, "Import Failed", str(exc))
            return
        preserved_name = str(section.get("name", "") or loaded.get("name", "Section"))
        section.clear()
        section.update(loaded)
        section["name"] = preserved_name
        self._refresh_section_selector()
        self.section_selector.setCurrentText(preserved_name)
        self._load_current_section()
        if self.segment_table.rowCount() == 0:
            self._add_segment_row(0.0, self._current_total_length(), preserved_name)
        self._emit_changed()

    def _refresh_segment_section_choices(self):
        names = [str(section.get("name", "")) for section in self._section_library]
        for row in range(self.segment_table.rowCount()):
            combo = self.segment_table.cellWidget(row, 2)
            if not isinstance(combo, QComboBox):
                continue
            current = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(names)
            if current in names:
                combo.setCurrentText(current)
            elif names:
                combo.setCurrentIndex(0)
            combo.blockSignals(False)

    def _add_segment_row(self, top: Optional[float] = None, bottom: Optional[float] = None, section_name: Optional[str] = None):
        row = self.segment_table.rowCount()
        self.segment_table.insertRow(row)
        if top is None:
            top = 0.0 if row == 0 else self._safe_float(self.segment_table.item(row - 1, 1))
        if bottom is None:
            total_length = self._current_total_length()
            bottom = total_length if total_length > float(top) else float(top) + 1.0
        self.segment_table.setItem(row, 0, QTableWidgetItem(f"{float(top):.4f}"))
        self.segment_table.setItem(row, 1, QTableWidgetItem(f"{float(bottom):.4f}"))
        combo = QComboBox()
        combo.addItems([str(section.get("name", "")) for section in self._section_library])
        if section_name and combo.findText(section_name) >= 0:
            combo.setCurrentText(section_name)
        combo.currentTextChanged.connect(lambda *_: self._emit_changed())
        self.segment_table.setCellWidget(row, 2, combo)
        self._emit_changed()

    def _delete_segment_row(self):
        row = self.segment_table.currentRow()
        if row < 0:
            row = self.segment_table.rowCount() - 1
        if row >= 0:
            self.segment_table.removeRow(row)
            self._emit_changed()

    def _read_segments(self) -> List[Dict]:
        segments = []
        for row in range(self.segment_table.rowCount()):
            top = self._safe_float(self.segment_table.item(row, 0))
            bottom = self._safe_float(self.segment_table.item(row, 1))
            combo = self.segment_table.cellWidget(row, 2)
            section_name = combo.currentText() if isinstance(combo, QComboBox) else ""
            segments.append({"top_m": float(top), "bottom_m": float(bottom), "section_name": section_name})
        return segments

    def _write_segments(self, segments: List[Dict]):
        self.segment_table.setRowCount(0)
        for segment in segments or []:
            self._add_segment_row(
                float(segment.get("top_m", 0.0)),
                float(segment.get("bottom_m", 0.0)),
                str(segment.get("section_name", "")),
            )

    def _current_total_length(self) -> float:
        if callable(self._total_length_provider):
            try:
                return max(float(self._total_length_provider()), 0.0)
            except Exception:
                return 0.0
        return 0.0

    def _refresh_segment_hint(self):
        total_length = self._current_total_length()
        if total_length > 0.0:
            self.segment_hint.setText(
                str(translate_text(f"Define fiber-section segments from 0.0 m to {total_length:.4f} m.", get_language()))
            )
        else:
            self.segment_hint.setText(
                str(translate_text("Define pile sections by top/bottom depth and imported fiber section.", get_language()))
            )

    @staticmethod
    def _safe_float(item: Optional[QTableWidgetItem]) -> float:
        if item is None:
            return 0.0
        try:
            return float(item.text())
        except Exception:
            return 0.0

    def _emit_changed(self):
        if self._loading:
            return
        self.changed.emit()
        if callable(self._change_callback):
            try:
                self._change_callback()
            except Exception:
                pass
