# -*- coding: utf-8 -*-

import os
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget
from language_manager import get_language
from ui_localization import translate_text

HAS_MATPLOTLIB = True
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
    from matplotlib.figure import Figure
except Exception:
    HAS_MATPLOTLIB = False
    FigureCanvas = None
    NavigationToolbar = None
    Figure = None


class PlotManager:
    """Render response curves into per-metric tabs, each with toolbar.

    For group mode, uses deferred (lazy) rendering to avoid creating
    dozens of matplotlib figures at once which causes lag and crashes.
    """

    def __init__(self, response_tabs: QTabWidget):
        self.response_tabs = response_tabs
        self.response_tabs.setUsesScrollButtons(True)
        self.response_tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        self.response_tabs.setDocumentMode(True)
        self._outer_tab_signal_connected = False
        self._orphaned_pages: List[QWidget] = []
        self.show_placeholder(self._tr("Run analysis to generate response plots."))
        # Deferred rendering bookkeeping for group mode
        self._deferred_pile_data: Optional[List[Dict]] = None
        self._deferred_layer_bgs = None
        self._deferred_chart_specs: Dict[int, List[Dict]] = {}
        self._rendered_outer_tabs: set = set()
        self._rendered_inner_tabs: Dict[int, set] = {}
        self._cleanup_timer = QTimer(self.response_tabs)
        self._cleanup_timer.setSingleShot(True)
        self._cleanup_timer.timeout.connect(self._release_orphaned_pages)

    def _detach_all_tabs(self):
        if self._outer_tab_signal_connected:
            try:
                self.response_tabs.currentChanged.disconnect(self._on_outer_tab_changed)
            except (RuntimeError, TypeError):
                pass
            self._outer_tab_signal_connected = False
        while self.response_tabs.count() > 0:
            page = self.response_tabs.widget(0)
            self.response_tabs.removeTab(0)
            if page is not None:
                page.hide()
                page.setParent(None)
                self._orphaned_pages.append(page)
        if self._orphaned_pages:
            self._cleanup_timer.start(150)

    def _release_orphaned_pages(self):
        while self._orphaned_pages:
            page = self._orphaned_pages.pop()
            try:
                page.deleteLater()
            except RuntimeError:
                pass

    def reset(self, message: Optional[str] = None):
        self._detach_all_tabs()
        self._deferred_pile_data = None
        self._deferred_layer_bgs = None
        self._deferred_chart_specs = {}
        self._rendered_outer_tabs = set()
        self._rendered_inner_tabs = {}
        self.show_placeholder(message or self._tr("Run analysis to generate response plots."))

    @staticmethod
    def _negated(values):
        if values is None:
            return []
        return [-float(value) for value in values]

    @staticmethod
    def _safe_sequence(value):
        if value is None:
            return []
        try:
            return list(value)
        except TypeError:
            return []

    def _tr(self, text: str) -> str:
        if get_language() != "zh":
            return text
        translations = {
            "Run analysis to generate response plots.": "运行分析后将在此生成响应曲线。",
            "Overview": "概览",
            "matplotlib is unavailable in this environment.": "当前环境缺少 matplotlib，无法绘图。",
            "No plot data is available for this response quantity.": "当前响应量没有可绘制的数据。",
            "Displacement Z": "Z 向位移",
            "Beam Axial Force": "杆单元轴力",
            "Displacement X": "X 向位移",
            "Displacement Y": "Y 向位移",
            "Rotation Y": "Y 向转角",
            "Beam Shear Force X'": "梁单元剪力 X'",
            "Beam Moment X'Z'": "梁单元弯矩 X'Z'",
            "Soil Reaction Force X'": "土反力 X'",
            "Soil Stiffness X'": "土刚度 X'",
            "Beam Shear X'": "梁单元剪力 X'",
            "Beam Shear Y'": "梁单元剪力 Y'",
            "Beam Moment Y'Z'": "梁单元弯矩 Y'Z'",
            "Axial Force": "轴力",
            "Shear X'": "剪力 X'",
            "Shear Y'": "剪力 Y'",
            "Moment X'": "弯矩 X'",
            "Moment Y'": "弯矩 Y'",
            "Depth From Pile Head (m)": "距桩顶深度 (m)",
            "Displacement X (mm)": "X 向位移 (mm)",
            "Displacement Y (mm)": "Y 向位移 (mm)",
            "Displacement Z (mm)": "Z 向位移 (mm)",
            "Rotation Y (rad)": "Y 向转角 (rad)",
            "Beam Axial Force (kN)": "杆单元轴力 (kN)",
            "Beam Shear X' (kN)": "梁单元剪力 X' (kN)",
            "Beam Shear Y' (kN)": "梁单元剪力 Y' (kN)",
            "Beam Moment Y'Z' (kN*m)": "梁单元弯矩 Y'Z' (kN*m)",
            "Beam Moment X'Z' (kN*m)": "梁单元弯矩 X'Z' (kN*m)",
            "Beam Shear Force X' (kN)": "梁单元剪力 X' (kN)",
            "Soil Reaction Force X' (kN/m)": "土反力 X' (kN/m)",
            "Soil Stiffness X' (kN/m^2)": "土刚度 X' (kN/m^2)",
            "Axial Force (kN)": "轴力 (kN)",
            "Shear X' (kN)": "剪力 X' (kN)",
            "Shear Y' (kN)": "剪力 Y' (kN)",
            "Moment X' (kN*m)": "弯矩 X' (kN*m)",
            "Moment Y' (kN*m)": "弯矩 Y' (kN*m)",
            "Run group analysis to generate response plots.": "运行群桩分析后将在此生成响应曲线。",
            "Loading chart…": "图表加载中…",
            "Click a tab to load the chart.": "点击标签加载图表。",
        }
        if text.startswith("Pile "):
            return text.replace("Pile ", "桩 ")
        return translations.get(text, text)

    def show_placeholder(self, message: str):
        self._detach_all_tabs()
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel(message)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 15px; color: #888888;")
        layout.addWidget(label)
        self.response_tabs.addTab(page, self._tr("Overview"))

    def _add_curve_tab(self, title: str, x_values, y_values, xlabel: str, ylabel: str, layer_backgrounds=None):
        self._add_curve_tab_to(self.response_tabs, title, x_values, y_values, xlabel, ylabel, layer_backgrounds)

    def _add_curve_tab_to(self, target_tabs: QTabWidget, title: str, x_values, y_values, xlabel: str, ylabel: str, layer_backgrounds=None):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        if not HAS_MATPLOTLIB:
            label = QLabel(self._tr("matplotlib is unavailable in this environment."))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
            target_tabs.addTab(page, self._tr(title))
            return

        x_series = list(x_values) if x_values is not None else []
        y_series = list(y_values) if y_values is not None else []
        point_count = min(len(x_series), len(y_series))
        if point_count == 0:
            label = QLabel(self._tr("No plot data is available for this response quantity."))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
            target_tabs.addTab(page, self._tr(title))
            return
        x_series = x_series[:point_count]
        y_series = y_series[:point_count]

        fig = Figure(figsize=(4.5, 4.0), tight_layout=True)
        canvas = FigureCanvas(fig)
        toolbar = NavigationToolbar(canvas, page)
        ax = fig.add_subplot(111)
        if layer_backgrounds:
            for bg in layer_backgrounds:
                z_top = float(bg.get("z_top", 0.0))
                z_bottom = float(bg.get("z_bottom", 0.0))
                color = str(bg.get("color", "#f0f0f0"))
                alpha = float(bg.get("alpha", 0.2))
                ax.axhspan(z_top, z_bottom, facecolor=color, alpha=alpha, edgecolor="none")
        ax.plot(x_series, y_series, linewidth=1.8, color="#c6844a")
        ax.set_xlabel(self._tr(xlabel))
        ax.set_ylabel(self._tr(ylabel))
        ax.grid(True, alpha=0.3)
        ax.invert_yaxis()

        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        target_tabs.addTab(page, self._tr(title))

    def export_all_charts(self, output_dir: str):
        if not HAS_MATPLOTLIB:
            return
        # Force-render all deferred tabs before export
        if self._deferred_pile_data is not None:
            for outer_idx in range(self.response_tabs.count()):
                self._ensure_outer_tab_rendered(outer_idx)
                page = self.response_tabs.widget(outer_idx)
                if page is None:
                    continue
                inner_tabs = page.findChild(QTabWidget)
                if inner_tabs is not None:
                    for inner_idx in range(inner_tabs.count()):
                        self._ensure_inner_tab_rendered(outer_idx, inner_tabs, inner_idx)
        os.makedirs(output_dir, exist_ok=True)
        for i in range(self.response_tabs.count()):
            page = self.response_tabs.widget(i)
            if page is None:
                continue
            # Direct canvases on the page
            canvas = page.findChild(FigureCanvas)
            if canvas is not None and canvas.figure is not None:
                title = self.response_tabs.tabText(i).strip() or f"chart_{i+1}"
                safe_name = "".join(ch if ch.isalnum() or ch in (" ", "_", "-") else "_" for ch in title).strip().replace(" ", "_")
                canvas.figure.savefig(os.path.join(output_dir, f"{safe_name}.png"), dpi=180, bbox_inches="tight")
            # Inner tabs (group mode)
            inner_tabs = page.findChild(QTabWidget)
            if inner_tabs is not None:
                outer_title = self.response_tabs.tabText(i).strip() or f"pile_{i+1}"
                for j in range(inner_tabs.count()):
                    inner_page = inner_tabs.widget(j)
                    if inner_page is None:
                        continue
                    inner_canvas = inner_page.findChild(FigureCanvas)
                    if inner_canvas is None or inner_canvas.figure is None:
                        continue
                    inner_title = inner_tabs.tabText(j).strip() or f"chart_{j+1}"
                    safe_name = "".join(
                        ch if ch.isalnum() or ch in (" ", "_", "-") else "_"
                        for ch in f"{outer_title}_{inner_title}"
                    ).strip().replace(" ", "_")
                    inner_canvas.figure.savefig(os.path.join(output_dir, f"{safe_name}.png"), dpi=180, bbox_inches="tight")

    def render_axial(self, results: Dict, layer_backgrounds=None):
        self._deferred_pile_data = None
        self._detach_all_tabs()
        depths = results.get("depths", [])
        disps_mm = self._negated(results.get("displacements", []))
        axial_force = results.get("axial_forces", [])

        self._add_curve_tab(
            "Disp Z",
            disps_mm,
            depths,
            "Displacement Z (mm, +up/-down)",
            "Depth From Pile Head (m)",
            layer_backgrounds=layer_backgrounds,
        )
        self._add_curve_tab(
            "Axial",
            axial_force,
            depths,
            "Axial Force (kN)",
            "Depth From Pile Head (m)",
            layer_backgrounds=layer_backgrounds,
        )

    def render_lateral(self, results: Dict, layer_backgrounds=None):
        self._deferred_pile_data = None
        self._detach_all_tabs()
        depths = results.get("depths", [])
        depths_ele = results.get("depths_ele", [])
        disps_mm = results.get("displacements", [])
        rotations = results.get("rotations", [])
        shears = results.get("shears", [])
        moments = results.get("moments", [])
        soil_rxn = results.get("soil_reactions", [])
        soil_rxn_per_m = results.get("soil_reactions_per_m", [])
        soil_stiffness = results.get("soil_stiffness", [])

        self._add_curve_tab("Disp X", disps_mm, depths, "Displacement X (mm)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab("Rot Y", rotations, depths, "Rotation Y (rad)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab("Shear X'", shears, depths_ele, "Beam Shear Force X' (kN)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab("Moment X'", moments, depths_ele, "Beam Moment X'Z' (kN*m)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab("Soil Rxn", soil_rxn_per_m, depths, "Soil Reaction Force X' (kN/m)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab("Soil K", soil_stiffness, depths, "Soil Stiffness X' (kN/m^2)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)

    def render_combined(self, results: Dict, layer_backgrounds=None):
        self._deferred_pile_data = None
        self._detach_all_tabs()
        depths = results.get("depths", [])
        depths_ele = results.get("depths_ele", [])
        disp_x = results.get("displacements_x", [])
        disp_y = results.get("displacements_y", [])
        disp_z = results.get("displacements_z", [])
        axial = results.get("axial_forces", [])
        shears = results.get("shears", [])
        shears_y = results.get("shears_y", [])
        moments = results.get("moments", [])
        moments_x = results.get("moments_x", [])

        self._add_curve_tab("Disp X", disp_x, depths, "Displacement X (mm)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab("Disp Y", disp_y, depths, "Displacement Y (mm)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab("Disp Z", disp_z, depths, "Displacement Z (mm, +up/-down)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab("Axial", axial, depths_ele, "Axial Force (kN)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab("Shear X'", shears, depths_ele, "Beam Shear X' (kN)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab("Shear Y'", shears_y, depths_ele, "Beam Shear Y' (kN)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab("Moment Y'", moments_x, depths_ele, "Beam Moment Y'Z' (kN*m)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab("Moment X'", moments, depths_ele, "Beam Moment X'Z' (kN*m)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)

    def render_comparison(self, mode: str, elastic_results: Dict, fiber_results: Dict, layer_backgrounds=None):
        self._deferred_pile_data = None
        self._detach_all_tabs()
        for key, label, results in (
            ("elastic", "Elastic", elastic_results),
            ("fiber", "Fiber", fiber_results),
        ):
            outer_page = QWidget()
            outer_layout = QVBoxLayout(outer_page)
            outer_layout.setContentsMargins(0, 0, 0, 0)
            outer_layout.setSpacing(0)
            inner_tabs = QTabWidget()
            inner_tabs.setDocumentMode(True)
            outer_layout.addWidget(inner_tabs)
            self.response_tabs.addTab(outer_page, self._tr(label))
            self._render_mode_to_tabs(mode, inner_tabs, results or {}, layer_backgrounds=layer_backgrounds)

    def _render_mode_to_tabs(self, mode: str, target_tabs: QTabWidget, results: Dict, layer_backgrounds=None):
        if mode == "axial":
            self._render_axial_to_tabs(target_tabs, results, layer_backgrounds)
        elif mode == "lateral":
            self._render_lateral_to_tabs(target_tabs, results, layer_backgrounds)
        elif mode == "combined":
            self._render_combined_to_tabs(target_tabs, results, layer_backgrounds)

    def _render_axial_to_tabs(self, target_tabs: QTabWidget, results: Dict, layer_backgrounds=None):
        depths = results.get("depths", [])
        disps_mm = self._negated(results.get("displacements", []))
        axial_force = results.get("axial_forces", [])
        self._add_curve_tab_to(
            target_tabs,
            "Disp Z",
            disps_mm,
            depths,
            "Displacement Z (mm, +up/-down)",
            "Depth From Pile Head (m)",
            layer_backgrounds=layer_backgrounds,
        )
        self._add_curve_tab_to(
            target_tabs,
            "Axial",
            axial_force,
            depths,
            "Axial Force (kN)",
            "Depth From Pile Head (m)",
            layer_backgrounds=layer_backgrounds,
        )

    def _render_lateral_to_tabs(self, target_tabs: QTabWidget, results: Dict, layer_backgrounds=None):
        depths = results.get("depths", [])
        depths_ele = results.get("depths_ele", [])
        self._add_curve_tab_to(target_tabs, "Disp X", results.get("displacements", []), depths, "Displacement X (mm)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab_to(target_tabs, "Rot Y", results.get("rotations", []), depths, "Rotation Y (rad)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab_to(target_tabs, "Shear X'", results.get("shears", []), depths_ele, "Beam Shear Force X' (kN)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab_to(target_tabs, "Moment X'", results.get("moments", []), depths_ele, "Beam Moment X'Z' (kN*m)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab_to(target_tabs, "Soil Rxn", results.get("soil_reactions_per_m", []), depths, "Soil Reaction Force X' (kN/m)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab_to(target_tabs, "Soil K", results.get("soil_stiffness", []), depths, "Soil Stiffness X' (kN/m^2)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)

    def _render_combined_to_tabs(self, target_tabs: QTabWidget, results: Dict, layer_backgrounds=None):
        depths = results.get("depths", [])
        depths_ele = results.get("depths_ele", [])
        self._add_curve_tab_to(target_tabs, "Disp X", results.get("displacements_x", []), depths, "Displacement X (mm)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab_to(target_tabs, "Disp Y", results.get("displacements_y", []), depths, "Displacement Y (mm)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab_to(target_tabs, "Disp Z", results.get("displacements_z", []), depths, "Displacement Z (mm, +up/-down)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab_to(target_tabs, "Axial", results.get("axial_forces", []), depths_ele, "Axial Force (kN)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab_to(target_tabs, "Shear X'", results.get("shears", []), depths_ele, "Beam Shear X' (kN)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab_to(target_tabs, "Shear Y'", results.get("shears_y", []), depths_ele, "Beam Shear Y' (kN)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab_to(target_tabs, "Moment Y'", results.get("moments_x", []), depths_ele, "Beam Moment Y'Z' (kN*m)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)
        self._add_curve_tab_to(target_tabs, "Moment X'", results.get("moments", []), depths_ele, "Beam Moment X'Z' (kN*m)", "Depth From Pile Head (m)", layer_backgrounds=layer_backgrounds)

    # ------------------------------------------------------------------
    # Group mode – deferred / lazy rendering
    # ------------------------------------------------------------------

    def render_group(self, results: Dict, layer_backgrounds=None):
        """Create lightweight tab stubs for each pile and defer chart creation."""
        self._detach_all_tabs()
        self._rendered_outer_tabs = set()
        self._rendered_inner_tabs = {}

        piles = self._safe_sequence(results.get("piles"))
        if len(piles) == 0:
            self.show_placeholder(self._tr("Run group analysis to generate response plots."))
            self._deferred_pile_data = None
            return

        self._deferred_pile_data = list(piles)
        self._deferred_layer_bgs = layer_backgrounds
        self._deferred_chart_specs = {}

        # Disconnect previous connections to avoid duplicates
        # Create lightweight placeholder tabs for each pile
        for pile in piles:
            page = QWidget()
            layout = QVBoxLayout(page)
            label = QLabel(self._tr("Loading chart…"))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("font-size: 14px; color: #999999;")
            label.setObjectName("_deferred_placeholder")
            layout.addWidget(label)
            tab_title = self._tr(f"Pile {int(pile.get('id', self.response_tabs.count() + 1))}")
            self.response_tabs.addTab(page, tab_title)

        # Connect tab switch signal for lazy rendering
        self.response_tabs.currentChanged.connect(self._on_outer_tab_changed)
        self._outer_tab_signal_connected = True
        # Immediately render first tab
        if self.response_tabs.count() > 0:
            self._ensure_outer_tab_rendered(0)

    @Slot(int)
    def _on_outer_tab_changed(self, index: int):
        """Triggered when user clicks on a different pile tab."""
        QTimer.singleShot(0, lambda idx=index: self._ensure_outer_tab_rendered(idx))

    def _ensure_outer_tab_rendered(self, index: int):
        """Lazily build the inner QTabWidget for pile at *index*."""
        if index in self._rendered_outer_tabs:
            return
        if self._deferred_pile_data is None or index >= len(self._deferred_pile_data):
            return
        self._rendered_outer_tabs.add(index)

        page = self.response_tabs.widget(index)
        if page is None:
            return

        # Remove placeholder label
        placeholder = page.findChild(QLabel, "_deferred_placeholder")
        if placeholder is not None:
            placeholder.deleteLater()

        pile = self._deferred_pile_data[index]
        layer_backgrounds = self._deferred_layer_bgs

        layout = page.layout()
        if layout is not None:
            layout.setContentsMargins(3, 3, 3, 3)
            layout.setSpacing(2)
        inner_tabs = QTabWidget()
        inner_tabs.setUsesScrollButtons(True)
        inner_tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        inner_tabs.setDocumentMode(True)
        layout.addWidget(inner_tabs)

        # Define chart specs – but don't create figures yet
        chart_specs = self._chart_specs_for_outer_index(index)
        self._rendered_inner_tabs[index] = set()

        # Create placeholder stubs for each chart type
        for spec in chart_specs:
            stub = QWidget()
            stub_layout = QVBoxLayout(stub)
            stub_label = QLabel(self._tr("Click a tab to load the chart."))
            stub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stub_label.setStyleSheet("font-size: 13px; color: #aaaaaa;")
            stub_label.setObjectName("_inner_placeholder")
            stub_layout.addWidget(stub_label)
            inner_tabs.addTab(stub, self._tr(spec.get("tab_title", spec["title"])))

        # Connect inner tab change for lazy inner rendering
        inner_tabs.currentChanged.connect(
            lambda inner_idx, outer_idx=index, tabs=inner_tabs: self._ensure_inner_tab_rendered(outer_idx, tabs, inner_idx)
        )
        # Render the first inner chart immediately
        if inner_tabs.count() > 0:
            self._ensure_inner_tab_rendered(index, inner_tabs, 0)

    def _ensure_inner_tab_rendered(self, outer_idx: int, inner_tabs: QTabWidget, inner_idx: int):
        """Lazily render a single chart inside an inner tab."""
        rendered = self._rendered_inner_tabs.get(outer_idx, set())
        if inner_idx in rendered:
            return
        rendered.add(inner_idx)
        self._rendered_inner_tabs[outer_idx] = rendered

        if self._deferred_pile_data is None or outer_idx >= len(self._deferred_pile_data):
            return

        specs = self._chart_specs_for_outer_index(outer_idx)
        if inner_idx >= len(specs):
            return

        spec = specs[inner_idx]
        page = inner_tabs.widget(inner_idx)
        if page is None:
            return

        # Remove placeholder
        placeholder = page.findChild(QLabel, "_inner_placeholder")
        if placeholder is not None:
            placeholder.deleteLater()

        layout = page.layout()

        if not HAS_MATPLOTLIB:
            label = QLabel(self._tr("matplotlib is unavailable in this environment."))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
            return

        x_series = list(spec["x"]) if spec["x"] is not None else []
        y_series = list(spec["y"]) if spec["y"] is not None else []
        point_count = min(len(x_series), len(y_series))
        if point_count == 0:
            label = QLabel(self._tr("No plot data is available for this response quantity."))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
            return
        x_series = x_series[:point_count]
        y_series = y_series[:point_count]

        fig = Figure(figsize=(4.5, 4.0), tight_layout=True)
        canvas = FigureCanvas(fig)
        toolbar = NavigationToolbar(canvas, page)
        ax = fig.add_subplot(111)

        layer_bgs = spec.get("layer_backgrounds")
        if layer_bgs:
            for bg in layer_bgs:
                z_top = float(bg.get("z_top", 0.0))
                z_bottom = float(bg.get("z_bottom", 0.0))
                color = str(bg.get("color", "#f0f0f0"))
                alpha = float(bg.get("alpha", 0.2))
                ax.axhspan(z_top, z_bottom, facecolor=color, alpha=alpha, edgecolor="none")

        ax.plot(x_series, y_series, linewidth=1.8, color="#c6844a")
        ax.set_xlabel(self._tr(spec["xlabel"]))
        ax.set_ylabel(self._tr(spec["ylabel"]))
        ax.grid(True, alpha=0.3)
        ax.invert_yaxis()

        layout.addWidget(toolbar)
        layout.addWidget(canvas)

    def _backgrounds_from_head(self, layer_backgrounds, pile_head_z: float, max_depth: float) -> List[Dict]:
        converted = []
        if not layer_backgrounds:
            return converted
        for bg in layer_backgrounds:
            z_top = float(bg.get("z_top", 0.0))
            z_bottom = float(bg.get("z_bottom", 0.0))
            depth_top = pile_head_z - z_top
            depth_bottom = pile_head_z - z_bottom
            start = min(depth_top, depth_bottom)
            end = max(depth_top, depth_bottom)
            if end < 0.0 or start > max_depth:
                continue
            converted.append(
                {
                    "z_top": max(start, 0.0),
                    "z_bottom": min(end, max_depth),
                    "color": bg.get("color", "#f0f0f0"),
                    "alpha": bg.get("alpha", 0.2),
                }
            )
        return converted

    def _pile_chart_specs(self, pile: Dict, layer_backgrounds) -> List[Dict]:
        """Return a list of chart specifications for one pile."""
        pile_head_z = float(pile.get("head_elevation", 0.0))
        max_node_depth = max((float(v) for v in pile.get("depths_from_head", [])), default=0.0)
        max_ele_depth = max((float(v) for v in pile.get("depths_ele_from_head", [])), default=max_node_depth)
        node_bgs = self._backgrounds_from_head(layer_backgrounds, pile_head_z, max_node_depth)
        ele_bgs = self._backgrounds_from_head(layer_backgrounds, pile_head_z, max_ele_depth)
        return [
            {
                "title": "Displacement X",
                "tab_title": "Disp X",
                "x": pile.get("disps_dx", []),
                "y": pile.get("depths_from_head", []),
                "xlabel": "Displacement X (mm)",
                "ylabel": "Depth From Pile Head (m)",
                "layer_backgrounds": node_bgs,
            },
            {
                "title": "Displacement Y",
                "tab_title": "Disp Y",
                "x": pile.get("disps_dy", []),
                "y": pile.get("depths_from_head", []),
                "xlabel": "Displacement Y (mm)",
                "ylabel": "Depth From Pile Head (m)",
                "layer_backgrounds": node_bgs,
            },
            {
                "title": "Displacement Z",
                "tab_title": "Disp Z",
                "x": pile.get("disps_dz", []),
                "y": pile.get("depths_from_head", []),
                "xlabel": "Displacement Z (mm, +up/-down)",
                "ylabel": "Depth From Pile Head (m)",
                "layer_backgrounds": node_bgs,
            },
            {
                "title": "Axial Force",
                "tab_title": "Axial",
                "x": pile.get("axial_forces", []),
                "y": pile.get("depths_ele_from_head", []),
                "xlabel": "Axial Force (kN)",
                "ylabel": "Depth From Pile Head (m)",
                "layer_backgrounds": ele_bgs,
            },
            {
                "title": "Shear X'",
                "tab_title": "Shear X'",
                "x": pile.get("rspile_shear_x", []),
                "y": pile.get("depths_ele_from_head", []),
                "xlabel": "Shear X' (kN)",
                "ylabel": "Depth From Pile Head (m)",
                "layer_backgrounds": ele_bgs,
            },
            {
                "title": "Shear Y'",
                "tab_title": "Shear Y'",
                "x": pile.get("rspile_shear_y", []),
                "y": pile.get("depths_ele_from_head", []),
                "xlabel": "Shear Y' (kN)",
                "ylabel": "Depth From Pile Head (m)",
                "layer_backgrounds": ele_bgs,
            },
            {
                "title": "Moment X'",
                "tab_title": "Moment X'",
                "x": pile.get("rspile_moment_x", []),
                "y": pile.get("depths_ele_from_head", []),
                "xlabel": "Moment X' (kN*m)",
                "ylabel": "Depth From Pile Head (m)",
                "layer_backgrounds": ele_bgs,
            },
            {
                "title": "Moment Y'",
                "tab_title": "Moment Y'",
                "x": pile.get("rspile_moment_y", []),
                "y": pile.get("depths_ele_from_head", []),
                "xlabel": "Moment Y' (kN*m)",
                "ylabel": "Depth From Pile Head (m)",
                "layer_backgrounds": ele_bgs,
            },
        ]

    def _chart_specs_for_outer_index(self, index: int) -> List[Dict]:
        cached = self._deferred_chart_specs.get(index)
        if cached is not None:
            return cached
        if self._deferred_pile_data is None or index >= len(self._deferred_pile_data):
            return []
        specs = self._pile_chart_specs(self._deferred_pile_data[index], self._deferred_layer_bgs)
        self._deferred_chart_specs[index] = specs
        return specs


_ORIGINAL_PLOT_MANAGER_INIT = PlotManager.__init__
_ORIGINAL_PLOT_MANAGER_SHOW_PLACEHOLDER = PlotManager.show_placeholder
_ORIGINAL_PLOT_MANAGER_RENDER_AXIAL = PlotManager.render_axial
_ORIGINAL_PLOT_MANAGER_RENDER_LATERAL = PlotManager.render_lateral
_ORIGINAL_PLOT_MANAGER_RENDER_COMBINED = PlotManager.render_combined
_ORIGINAL_PLOT_MANAGER_RENDER_GROUP = PlotManager.render_group
_ORIGINAL_PLOT_MANAGER_RENDER_COMPARISON = PlotManager.render_comparison


def _localized_plot_manager_tr(self, text: str) -> str:
    translated = translate_text(text, get_language())
    return str(translated if translated is not None else text)


def _configure_plot_fonts():
    try:
        import matplotlib
    except Exception:
        return
    if get_language() == "zh":
        matplotlib.rcParams["font.family"] = "sans-serif"
        matplotlib.rcParams["font.sans-serif"] = [
            "Microsoft YaHei",
            "SimHei",
            "Noto Sans CJK SC",
            "WenQuanYi Zen Hei",
            "Arial Unicode MS",
            "DejaVu Sans",
        ]
    else:
        matplotlib.rcParams["font.family"] = ["Times New Roman", "Times", "DejaVu Serif", "serif"]
    matplotlib.rcParams["axes.unicode_minus"] = False


def _localized_plot_manager_init(self, response_tabs: QTabWidget):
    _configure_plot_fonts()
    _ORIGINAL_PLOT_MANAGER_INIT(self, response_tabs)


def _plot_manager_show_placeholder(self, message: str):
    self.response_tabs.setTabPosition(QTabWidget.TabPosition.North)
    return _ORIGINAL_PLOT_MANAGER_SHOW_PLACEHOLDER(self, message)


def _plot_manager_render_axial(self, results: Dict, layer_backgrounds=None):
    self.response_tabs.setTabPosition(QTabWidget.TabPosition.North)
    return _ORIGINAL_PLOT_MANAGER_RENDER_AXIAL(self, results, layer_backgrounds)


def _plot_manager_render_lateral(self, results: Dict, layer_backgrounds=None):
    self.response_tabs.setTabPosition(QTabWidget.TabPosition.North)
    return _ORIGINAL_PLOT_MANAGER_RENDER_LATERAL(self, results, layer_backgrounds)


def _plot_manager_render_combined(self, results: Dict, layer_backgrounds=None):
    self.response_tabs.setTabPosition(QTabWidget.TabPosition.North)
    return _ORIGINAL_PLOT_MANAGER_RENDER_COMBINED(self, results, layer_backgrounds)


def _plot_manager_render_group(self, results: Dict, layer_backgrounds=None):
    self.response_tabs.setTabPosition(QTabWidget.TabPosition.North)
    return _ORIGINAL_PLOT_MANAGER_RENDER_GROUP(self, results, layer_backgrounds)


def _plot_manager_render_comparison(self, mode: str, elastic_results: Dict, fiber_results: Dict, layer_backgrounds=None):
    result = _ORIGINAL_PLOT_MANAGER_RENDER_COMPARISON(self, mode, elastic_results, fiber_results, layer_backgrounds)
    self.response_tabs.setTabPosition(QTabWidget.TabPosition.West)
    return result


PlotManager.__init__ = _localized_plot_manager_init
PlotManager._tr = _localized_plot_manager_tr
PlotManager.show_placeholder = _plot_manager_show_placeholder
PlotManager.render_axial = _plot_manager_render_axial
PlotManager.render_lateral = _plot_manager_render_lateral
PlotManager.render_combined = _plot_manager_render_combined
PlotManager.render_group = _plot_manager_render_group
PlotManager.render_comparison = _plot_manager_render_comparison
