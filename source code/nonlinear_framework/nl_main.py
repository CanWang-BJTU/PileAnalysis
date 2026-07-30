# -*- coding: utf-8 -*-

import os
import sys
import json
import traceback
from typing import Optional, Callable, Any

from openpyxl import Workbook

from PySide6.QtCore import Qt, Slot, QTimer, Signal, QThread, QObject, QSignalBlocker, QEventLoop
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QAbstractSpinBox,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QProgressDialog,
    QVBoxLayout,
    QWidget,
    QAbstractItemView,
    QStatusBar,
    QLineEdit,
)

def _runtime_framework_dir() -> str:
    if getattr(sys, "frozen", False):
        exe_root = os.path.dirname(os.path.abspath(sys.executable))
        frozen_candidate = os.path.join(exe_root, "nonlinear_framework")
        if os.path.isdir(frozen_candidate):
            return frozen_candidate

        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            meipass_candidate = os.path.join(meipass, "nonlinear_framework")
            if os.path.isdir(meipass_candidate):
                return meipass_candidate

    return os.path.dirname(__file__)


ROOT_DIR = _runtime_framework_dir()
APP_ICON = os.path.join(ROOT_DIR, "gui_modules", "app_icon.ico")
LIVE_REFRESH_DEBOUNCE_MS = 80
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
PROJECT_ROOT = os.path.dirname(ROOT_DIR)
for extra_dir in (
    PROJECT_ROOT,
    os.path.join(PROJECT_ROOT, "language_settings"),
):
    if os.path.isdir(extra_dir) and extra_dir not in sys.path:
        sys.path.insert(0, extra_dir)

from core.parameter_collector import ParameterCollector
from core.case_io import blank_case_document, default_case_document, load_case, save_case
from core.spring_export import export_spring_parameters
from gui_modules.axial_executor import AxialExecutor
from gui_modules.axial_panel import AxialPanel
from gui_modules.combined_executor import CombinedExecutor
from gui_modules.combined_panel import CombinedPanel
from gui_modules.group_executor import GroupExecutor
from gui_modules.group_panel import GroupPanel
from gui_modules.help_system import show_help_manual
from gui_modules.lateral_executor import LateralExecutor
from gui_modules.lateral_panel import LateralPanel
from gui_modules.live_view import LiveView
from gui_modules.plot_manager import PlotManager
from gui_modules.result_formatter import ResultFormatter
from gui_shell import attach_navigation_menu
from language_manager import get_language
from ui_localization import translate_menu_bar, translate_text, translate_widget_tree


class _CalcWorker(QThread):
    """Run calculation in background thread to keep UI responsive."""
    finished = Signal(dict)      # result payload
    error = Signal(str)          # error message
    status = Signal(str)         # progress update
    progress = Signal(int, str)  # progress value and message

    def __init__(self, mode_index: int, payload: dict, case_doc: dict):
        super().__init__()
        self.mode_index = mode_index
        self.payload = payload
        self.case_doc = case_doc
        self._result = None
        self._input_obj = None

    def _emit_progress(self, value: int, message: str):
        value = max(0, min(int(value), 100))
        self.progress.emit(value, message)
        self.status.emit(message)

    def _collect_input(self, payload: dict):
        return ParameterCollector.collect(self.mode_index, payload)

    def _solve(self, input_obj):
        if self.mode_index == 0:
            return AxialExecutor.run(input_obj)
        if self.mode_index == 1:
            return LateralExecutor.run(input_obj)
        if self.mode_index == 2:
            return CombinedExecutor.run(input_obj)
        if self.mode_index == 3:
            return GroupExecutor.run(input_obj)
        raise ValueError(f"Unknown mode index: {self.mode_index}")

    def run(self):
        try:
            group_comparison = False
            if self.mode_index == 3:
                pile_types = self.payload.get("pile_types", []) or []
                group_comparison = any(
                    str(item.get("section_mode", "elastic")) == "comparison"
                    for item in pile_types
                    if isinstance(item, dict)
                )

            if (self.mode_index in (0, 1, 2) and str(self.payload.get("section_mode", "elastic")) == "comparison") or group_comparison:
                elastic_payload = dict(self.payload)
                fiber_payload = dict(self.payload)
                if self.mode_index == 3:
                    elastic_payload["pile_types"] = [
                        {**dict(item), "section_mode": "elastic"}
                        for item in (self.payload.get("pile_types", []) or [])
                        if isinstance(item, dict)
                    ]
                    fiber_payload["pile_types"] = [
                        {**dict(item), "section_mode": "fiber"}
                        for item in (self.payload.get("pile_types", []) or [])
                        if isinstance(item, dict)
                    ]
                else:
                    elastic_payload["section_mode"] = "elastic"
                    fiber_payload["section_mode"] = "fiber"

                self._emit_progress(10, "Collecting elastic parameters...")
                elastic_input = self._collect_input(elastic_payload)
                self._emit_progress(35, "Running elastic solver...")
                elastic_result = self._solve(elastic_input)

                self._emit_progress(55, "Collecting fiber parameters...")
                fiber_input = self._collect_input(fiber_payload)
                self._emit_progress(80, "Running fiber solver...")
                fiber_result = self._solve(fiber_input)

                self._input_obj = {"elastic": elastic_input, "fiber": fiber_input}
                result = {
                    "comparison_mode": True,
                    "elastic": elastic_result,
                    "fiber": fiber_result,
                }
            else:
                self._emit_progress(15, "Collecting parameters...")
                self._input_obj = self._collect_input(self.payload)
                self._emit_progress(65, "Running solver...")
                result = self._solve(self._input_obj)
            self._emit_progress(95, "Preparing results...")
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(f"{exc}\n\n{traceback.format_exc()}")


class _RenderController(QObject):
    """Serialize Live/Response rendering requests on the UI thread."""

    def __init__(
        self,
        parent: QObject,
        *,
        render_live: Callable[[Optional[dict], bool], None],
        render_live_title: Callable[[], None],
        reset_results: Callable[[], None],
        render_response: Callable[[str, dict, Any], None],
    ):
        super().__init__(parent)
        self._render_live = render_live
        self._render_live_title = render_live_title
        self._reset_results = reset_results
        self._render_response = render_response
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._flush)
        self._processing = False
        self._pending_live: tuple[Optional[dict], bool] | None = None
        self._pending_live_title = False
        self._pending_reset = False
        self._pending_response: tuple[str, dict, Any] | None = None

    def clear(self):
        self._timer.stop()
        self._pending_live = None
        self._pending_live_title = False
        self._pending_reset = False
        self._pending_response = None

    def request_live(self, payload: Optional[dict] = None, force: bool = False, immediate: bool = False):
        self._pending_live = (payload, force)
        if immediate:
            self._flush()
        else:
            self._timer.start(0)

    def request_live_title(self, immediate: bool = False):
        self._pending_live_title = True
        self._pending_live = None
        if immediate:
            self._flush()
        else:
            self._timer.start(0)

    def request_reset(self, immediate: bool = False):
        self._pending_reset = True
        self._pending_response = None
        if immediate:
            self._flush()
        else:
            self._timer.start(0)

    def request_response(self, kind: str, results: dict, layer_backgrounds, immediate: bool = False):
        self._pending_response = (kind, results, layer_backgrounds)
        if immediate:
            self._flush()
        else:
            self._timer.start(0)

    @Slot()
    def _flush(self):
        if self._processing:
            self._timer.start(0)
            return
        self._processing = True
        try:
            if self._pending_reset:
                self._pending_reset = False
                self._reset_results()
            if self._pending_response is not None:
                kind, results, layer_backgrounds = self._pending_response
                self._pending_response = None
                self._render_response(kind, results, layer_backgrounds)
            if self._pending_live_title:
                self._pending_live_title = False
                self._render_live_title()
            elif self._pending_live is not None:
                payload, force = self._pending_live
                self._pending_live = None
                self._render_live(payload, force)
        finally:
            self._processing = False


class MainWindow(QMainWindow):
    def _tr(self, text: str) -> str:
        return str(translate_text(text, get_language()))

    def __init__(self):
        super().__init__()

        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.availableGeometry()
            width = min(2048, int(screen_geo.width() * 0.95))
            height = min(1334, int(screen_geo.height() * 0.93))
        else:
            width, height = 2048, 1334

        self.setWindowTitle("PileAnalysis - Foundation Analysis")
        if os.path.exists(APP_ICON):
            self.setWindowIcon(QIcon(APP_ICON))
        self.setMinimumSize(1200, 800)
        self.resize(width, height)

        self.case_type: Optional[str] = None
        self.analysis_scope: Optional[str] = None
        self.case_imported = False
        self._import_details_expanded = False
        self._loaded_case_filename = ""
        self.current_mode_index = -1
        self.live_enabled = False
        self._import_in_progress = False
        self._suspend_live_refresh = False
        self._pending_live_force = False
        self._pending_live_payload = None
        self._live_needs_refresh = False
        self._live_refresh_running = False
        self._last_live_signature = None
        self._ui_transition_in_progress = False
        self._result_render_in_progress = False
        self.single_mode_names = ["Axial Analysis", "Lateral Analysis", "Combined Analysis"]
        self.case_doc = default_case_document()
        self._builtin_case_files = {
            "Axial Tutorial": os.path.join(ROOT_DIR, "case_samples", "axial_validation_case.dat"),
            "Lateral Tutorial": os.path.join(ROOT_DIR, "case_samples", "lateral_validation_case.dat"),
            "Combined Tutorial": os.path.join(ROOT_DIR, "case_samples", "combined_validation_case.dat"),
            "Group Tutorial": os.path.join(ROOT_DIR, "case_samples", "group_template_case.dat"),
        }
        self._live_refresh_timer = QTimer(self)
        self._live_refresh_timer.setSingleShot(True)
        self._live_refresh_timer.timeout.connect(self._flush_live_refresh)

        self.axial_panel = AxialPanel()
        self.lateral_panel = LateralPanel()
        self.combined_panel = CombinedPanel()
        self.group_panel = GroupPanel()
        self.axial_panel.set_payload(self.case_doc["payloads"]["axial"])
        self.lateral_panel.set_payload(self.case_doc["payloads"]["lateral"])
        self.combined_panel.set_payload(self.case_doc["payloads"]["combined"])
        self.group_panel.set_payload(self.case_doc["payloads"]["group"])
        self._build_ui()
        self._render_controller = _RenderController(
            self,
            render_live=self._refresh_live_view,
            render_live_title=self.live_view.render_title_only,
            reset_results=self._reset_result_views,
            render_response=self._render_response,
        )
        self._setup_menu_bar()
        self._setup_status_bar()
        self._restore_panel_callbacks()
        self._render_controller.request_live_title(immediate=True)

    def _build_ui(self):
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.main_splitter)
        self.main_splitter.addWidget(self._create_left_panel())
        self.main_splitter.addWidget(self._create_right_panel())
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setCollapsible(0, False)
        self.main_splitter.setCollapsible(1, False)
        self.main_splitter.setStretchFactor(0, 53)
        self.main_splitter.setStretchFactor(1, 47)
        self._apply_main_splitter_ratio()


    def _apply_main_splitter_ratio(self):
        if not hasattr(self, "main_splitter"):
            return
        total_width = max(self.main_splitter.width(), self.width(), 1)
        left_width = max(int(total_width * 0.53), 1)
        right_width = max(total_width - left_width, 1)
        self.main_splitter.setSizes([left_width, right_width])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_main_splitter_ratio()

    def _create_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(520)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        v_splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(v_splitter)

        self.visual_tabs = QTabWidget()
        self.plot_tabs = self.visual_tabs
        self.visual_tabs.currentChanged.connect(self._on_visual_tab_changed)

        live_widget = QWidget()
        live_layout = QVBoxLayout(live_widget)
        live_layout.setContentsMargins(5, 5, 5, 5)
        live_layout.setSpacing(0)
        self.live_view = LiveView(live_widget)
        self.live_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        live_layout.addWidget(self.live_view)
        self.visual_tabs.addTab(live_widget, "Live")

        response_widget = QWidget()
        response_layout = QVBoxLayout(response_widget)
        response_layout.setContentsMargins(5, 5, 5, 5)
        response_layout.setSpacing(0)
        self.response_plot_tabs = QTabWidget()
        response_layout.addWidget(self.response_plot_tabs)
        self.visual_tabs.addTab(response_widget, "Response")
        self.plot_manager = PlotManager(self.response_plot_tabs)

        v_splitter.addWidget(self.visual_tabs)

        results_group = QGroupBox("  Result Output")
        results_layout = QVBoxLayout(results_group)
        results_layout.setContentsMargins(6, 8, 6, 0)
        self.results_tabs = QTabWidget()

        self.summary_host = QWidget()
        self.summary_layout = QVBoxLayout(self.summary_host)
        self.summary_layout.setContentsMargins(0, 0, 0, 0)
        self.summary_layout.setSpacing(0)
        self.summary_stack = QStackedWidget()
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setPlaceholderText("Result summary will be displayed here...")
        self.summary_table = self._create_result_table_widget()
        self.summary_stack.addWidget(self.summary_text)
        self.summary_stack.addWidget(self.summary_table)
        self.summary_layout.addWidget(self.summary_stack)

        self.results_tabs.addTab(self.summary_host, "Summary")
        self.result_table_host = QWidget()
        self.result_table_layout = QVBoxLayout(self.result_table_host)
        self.result_table_layout.setContentsMargins(0, 0, 0, 0)
        self.result_table_layout.setSpacing(0)
        self.result_table = self._create_result_table_widget()
        self.result_table_layout.addWidget(self.result_table)
        self.group_result_tabs = None
        self.comparison_result_tabs = None
        self.comparison_result_tables = {}
        self.results_tabs.addTab(self.result_table_host, "Data Table")
        results_layout.addWidget(self.results_tabs)
        v_splitter.addWidget(results_group)

        total_height = self.height()
        v_splitter.setSizes([int(total_height * 0.65), int(total_height * 0.35)])
        return panel

    def _load_schematic_diagram(self, layout: QVBoxLayout):
        self.diagram_label = QLabel("Analysis diagram placeholder")
        self.diagram_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.diagram_label.setMinimumHeight(200)
        self.diagram_label.setStyleSheet(
            "font-size: 26px; color: #909090; background-color: white; border: 1px solid #d9d9d9;"
        )
        layout.addWidget(self.diagram_label)

    def _setup_plot_tabs(self):
        # legacy placeholder, kept for compatibility
        return

    def _create_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(420)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(8)

        guide_group = QGroupBox("Quick Start Guide")
        guide_layout = QVBoxLayout(guide_group)
        guide_label = QLabel()
        guide_label.setWordWrap(True)
        guide_label.setText(self._tr(
            "1. Select case type (existing/new)\n"
            "2. Select analysis scope (single/group)\n"
            "3. For single pile, select axial / lateral / combined mode\n"
            "4. Fill parameters and click [Run]"
        ))
        guide_layout.addWidget(guide_label)
        layout.addWidget(guide_group)

        self.selection_stack = QStackedWidget()
        self.selection_stack.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout.addWidget(self.selection_stack)
        self.case_selection_page = self._create_case_selection_page()
        self.selection_stack.addWidget(self.case_selection_page)
        self.scope_selection_page = self._create_scope_selection_page()
        self.selection_stack.addWidget(self.scope_selection_page)
        self.single_mode_selection_page = self._create_single_mode_selection_page()
        self.selection_stack.addWidget(self.single_mode_selection_page)

        self.wizard_stack = QStackedWidget()
        self.wizard_stack.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.wizard_stack, 1)

        placeholder = QWidget()
        placeholder_layout = QVBoxLayout(placeholder)
        placeholder_layout.addStretch()
        self.placeholder_label = QLabel("-> Please select a case type")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet("font-size: 17px; color: #909090;")
        placeholder_layout.addWidget(self.placeholder_label)
        placeholder_layout.addStretch()
        self.wizard_stack.addWidget(placeholder)

        wizard_page = QWidget()
        wizard_layout = QVBoxLayout(wizard_page)
        wizard_layout.setContentsMargins(0, 0, 0, 0)
        wizard_layout.setSpacing(6)
        self.parameter_tabs = QTabWidget()
        self.parameter_tabs.setTabPosition(QTabWidget.TabPosition.North)
        wizard_layout.addWidget(self.parameter_tabs, 1)

        nav_widget = QWidget()
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.addStretch()
        self.save_case_button = QPushButton("Save Case")
        self.save_case_button.setVisible(True)
        nav_layout.addWidget(self.save_case_button)
        self.export_case_button = QPushButton("Save and Export")
        self.export_case_button.setVisible(False)
        nav_layout.addWidget(self.export_case_button)
        self.calculate_button = QPushButton("Run")
        self.calculate_button.setEnabled(False)
        nav_layout.addWidget(self.calculate_button)
        wizard_layout.addWidget(nav_widget)
        self.wizard_stack.addWidget(wizard_page)

        self.case_button_group.idClicked.connect(self._on_case_type_selected)
        self.scope_button_group.idClicked.connect(self._on_scope_selected)
        self.mode_button_group.idClicked.connect(self._on_mode_selected)
        self.scope_mode_button_group.idClicked.connect(self._on_scope_mode_selected)
        self.back_case_btn.clicked.connect(self._back_to_case_selection)
        self.back_scope_btn.clicked.connect(self._back_to_scope_selection)
        self.import_button.clicked.connect(self._import_dat_file)
        self.scope_import_button.clicked.connect(self._import_dat_file)
        self.view_modify_button.clicked.connect(self._show_parameter_tabs)
        self.scope_view_modify_button.clicked.connect(self._show_parameter_tabs)
        self.direct_calc_button.clicked.connect(self.start_calculation)
        self.scope_direct_calc_button.clicked.connect(self.start_calculation)
        self.calculate_button.clicked.connect(self.start_calculation)
        self.save_case_button.clicked.connect(self._save_placeholder)
        self.export_case_button.clicked.connect(self._save_placeholder)
        return panel

    def _setup_menu_bar(self):
        menubar = self.menuBar()

        export_menu = menubar.addMenu("Export(&E)")
        action_export_summary = QAction("Export Summary", self)
        if os.path.exists(APP_ICON):
            action_export_summary.setIcon(QIcon(APP_ICON))
        action_export_summary.triggered.connect(self._export_summary_text)
        export_menu.addAction(action_export_summary)

        action_export_table = QAction("Export Data Table Excel", self)
        if os.path.exists(APP_ICON):
            action_export_table.setIcon(QIcon(APP_ICON))
        action_export_table.triggered.connect(self._export_data_table_excel)
        export_menu.addAction(action_export_table)

        action_export_plots = QAction("Export Response Charts", self)
        if os.path.exists(APP_ICON):
            action_export_plots.setIcon(QIcon(APP_ICON))
        action_export_plots.triggered.connect(self._export_response_charts)
        export_menu.addAction(action_export_plots)

        action_export_springs = QAction("Export Spring Parameters", self)
        if os.path.exists(APP_ICON):
            action_export_springs.setIcon(QIcon(APP_ICON))
        action_export_springs.triggered.connect(self._export_spring_parameters)
        export_menu.addAction(action_export_springs)

        help_menu = menubar.addMenu("Help(&H)")
        action_param_ref = QAction("Parameter Reference", self)
        action_param_ref.triggered.connect(self._show_parameter_reference)
        help_menu.addAction(action_param_ref)
        action_about = QAction("About", self)
        action_about.triggered.connect(self._show_about_clean)
        help_menu.addAction(action_about)

        tutorial_menu = menubar.addMenu("Examples(&T)")
        for label, path in self._builtin_case_files.items():
            action = QAction(label, self)
            action.triggered.connect(lambda _checked=False, p=path: self._load_builtin_case(p))
            tutorial_menu.addAction(action)
        attach_navigation_menu(self, current_target="nonlinear")

    def _setup_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        column_style = (
            "QLabel { color: #666666; padding: 0px 10px; border-right: 1px solid #cccccc; font-size: 9pt; }"
        )
        last_col_style = "QLabel { color: #666666; padding: 0px 10px; font-size: 9pt; }"

        current_language = get_language()
        author_text = "Authors: Wang Can, Guo Junjun" if current_language != "zh" else "作者：汪灿，郭军军"
        contact_text = "Contact: 24231238@bjtu.edu.cn / jjguo2@bjtu.edu.cn" if current_language != "zh" else "联系方式：24231238@bjtu.edu.cn / jjguo2@bjtu.edu.cn"
        version_text = "Version: 3.0.1" if current_language != "zh" else "版本：3.0.1"
        update_label = "Update" if current_language != "zh" else "更新"

        lbl_author = QLabel(author_text)
        lbl_author.setStyleSheet(column_style)
        self.status_bar.addWidget(lbl_author)

        lbl_email = QLabel(contact_text)
        lbl_email.setStyleSheet(column_style)
        self.status_bar.addWidget(lbl_email)

        lbl_version = QLabel(version_text)
        lbl_version.setStyleSheet(column_style)
        self.status_bar.addWidget(lbl_version)

        github_url = "https://github.com/CanWang-BJTU/PileAnalysis"
        lbl_doc = QLabel(
            f"<a href='{github_url}' style='color: #000000; text-decoration: none;'>{update_label}</a>"
        )
        lbl_doc.setOpenExternalLinks(True)
        lbl_doc.setToolTip(github_url)
        lbl_doc.setStyleSheet(last_col_style)
        self.status_bar.addWidget(lbl_doc)

        self.calc_status_label = QLabel("Ready")
        self.calc_status_label.setStyleSheet(
            "QLabel { color: #666666; padding: 2px 10px; border-left: 1px solid #cccccc; font-weight: bold; font-size: 9pt; }"
        )
        self.status_bar.addPermanentWidget(self.calc_status_label)
        lbl_author.setText(author_text)
        lbl_email.setText(contact_text)
        lbl_version.setText(version_text)
        lbl_doc.setText(
            f"<a href='{github_url}' style='color: #000000; text-decoration: none;'>{update_label}</a>"
        )
        self.calc_status_label.setText("Ready" if current_language != "zh" else "准备就绪")

    def _create_case_selection_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        case_group = QGroupBox("Case Selection")
        case_layout = QHBoxLayout(case_group)
        self.case_button_group = QButtonGroup(self)
        existing_case_rb = QRadioButton("Existing Case")
        self.case_button_group.addButton(existing_case_rb, 0)
        case_layout.addWidget(existing_case_rb)
        case_layout.addStretch()
        new_case_rb = QRadioButton("New Case")
        self.case_button_group.addButton(new_case_rb, 1)
        case_layout.addWidget(new_case_rb)
        layout.addWidget(case_group)
        layout.addStretch()
        return page

    def _create_scope_selection_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        scope_group = QGroupBox("Analysis Scope Selection")
        scope_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        scope_layout = QVBoxLayout(scope_group)
        scope_layout.setContentsMargins(10, 10, 10, 10)
        scope_layout.setSpacing(8)
        scope_row = QGridLayout()
        scope_row.setHorizontalSpacing(24)
        scope_row.setVerticalSpacing(4)
        self.scope_button_group = QButtonGroup(self)
        single_rb = QRadioButton("Single Pile Analysis")
        group_rb = QRadioButton("Group Pile Analysis")
        self.scope_button_group.addButton(single_rb, 0)
        self.scope_button_group.addButton(group_rb, 1)
        scope_row.addWidget(single_rb, 0, 0)
        scope_row.addWidget(group_rb, 0, 1)
        scope_layout.addLayout(scope_row)
        self.scope_mode_widget = QWidget()
        scope_mode_layout = QGridLayout(self.scope_mode_widget)
        scope_mode_layout.setContentsMargins(0, 0, 0, 0)
        scope_mode_layout.setHorizontalSpacing(18)
        scope_mode_layout.setVerticalSpacing(2)
        self.scope_mode_button_group = QButtonGroup(self)
        for i, name in enumerate(self.single_mode_names):
            rb = QRadioButton(name)
            self.scope_mode_button_group.addButton(rb, i)
            scope_mode_layout.addWidget(rb, 0, i)
        self.scope_mode_widget.setVisible(False)
        scope_layout.addWidget(self.scope_mode_widget)
        self.back_case_btn = QPushButton("Back to Case Selection")
        self.back_case_btn.setMaximumWidth(760)
        scope_layout.addWidget(self.back_case_btn)
        self.scope_import_widget = QWidget()
        scope_import_layout = QVBoxLayout(self.scope_import_widget)
        scope_import_layout.setContentsMargins(0, 0, 0, 0)
        scope_import_layout.setSpacing(6)
        self.scope_import_button = QPushButton("Import Existing Case (.dat)")
        self.scope_import_button.setMaximumWidth(760)
        scope_import_layout.addWidget(self.scope_import_button)
        self.scope_import_status_label = QLabel("")
        self.scope_import_status_label.setVisible(False)
        scope_import_layout.addWidget(self.scope_import_status_label)
        self.scope_view_modify_button = QPushButton("View and Edit")
        self.scope_view_modify_button.setMaximumWidth(760)
        self.scope_view_modify_button.setVisible(False)
        scope_import_layout.addWidget(self.scope_view_modify_button)
        self.scope_direct_calc_button = QPushButton("Run Directly")
        self.scope_direct_calc_button.setMaximumWidth(760)
        self.scope_direct_calc_button.setVisible(False)
        scope_import_layout.addWidget(self.scope_direct_calc_button)
        self.scope_import_widget.setVisible(False)
        scope_layout.addWidget(self.scope_import_widget)
        layout.addWidget(scope_group)
        layout.addStretch()
        return page

    def _create_single_mode_selection_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        mode_group = QGroupBox("Single Pile Mode Selection")
        mode_layout = QVBoxLayout(mode_group)
        mode_grid = QGridLayout()
        self.mode_button_group = QButtonGroup(self)
        for i, name in enumerate(self.single_mode_names):
            rb = QRadioButton(name)
            self.mode_button_group.addButton(rb, i)
            mode_grid.addWidget(rb, 0, i)
        mode_layout.addLayout(mode_grid)
        self.back_scope_btn = QPushButton("Back to Scope Selection")
        mode_layout.addWidget(self.back_scope_btn)

        self.import_widget = QWidget()
        import_layout = QVBoxLayout(self.import_widget)
        import_layout.setContentsMargins(0, 0, 0, 0)
        self.import_button = QPushButton("Import Existing Case (.dat)")
        import_layout.addWidget(self.import_button)
        self.import_status_label = QLabel("")
        self.import_status_label.setVisible(False)
        import_layout.addWidget(self.import_status_label)
        self.view_modify_button = QPushButton("View and Edit")
        self.view_modify_button.setVisible(False)
        import_layout.addWidget(self.view_modify_button)
        self.direct_calc_button = QPushButton("Run Directly")
        self.direct_calc_button.setVisible(False)
        import_layout.addWidget(self.direct_calc_button)
        mode_layout.addWidget(self.import_widget)
        self.import_widget.setVisible(False)

        layout.addWidget(mode_group)
        layout.addStretch()
        return page

    @Slot(int)
    def _on_case_type_selected(self, case_id: int):
        def _apply():
            self.case_type = "existing" if case_id == 0 else "new"
            self.analysis_scope = None
            self.case_imported = False
            self._import_details_expanded = False
            self.current_mode_index = -1
            if self.case_type == "new":
                self.case_doc = blank_case_document()
            self.selection_stack.setCurrentWidget(self.scope_selection_page)
            self._set_import_ui_visible(self.case_type == "existing")
            self._set_scope_mode_ui_visible(False)
            self._set_import_loaded("")
            if self.case_type == "existing":
                self.placeholder_label.setText("-> Please select single or group analysis, or import an existing case directly")
            else:
                self.placeholder_label.setText("-> Please select an analysis scope to start a blank case")
            self.wizard_stack.setCurrentIndex(0)
            self.parameter_tabs.clear()
            self._reset_result_views()
            self.live_enabled = False
            self._loaded_case_filename = ""
            self.live_view.render_title_only()
            self.calculate_button.setEnabled(False)
        self._run_ui_transition(_apply)

    @Slot()
    def _back_to_case_selection(self):
        def _apply():
            self.selection_stack.setCurrentWidget(self.case_selection_page)
            self.wizard_stack.setCurrentIndex(0)
            self.parameter_tabs.clear()
            self._reset_result_views()
            self.calculate_button.setEnabled(False)
            self.placeholder_label.setText("-> Please select a case type")
            self.case_type = None
            self.analysis_scope = None
            self.case_imported = False
            self._import_details_expanded = False
            self.current_mode_index = -1
            self.live_enabled = False
            self._loaded_case_filename = ""
            self._last_live_signature = None
            self._render_controller.request_live_title(immediate=True)
            self._set_import_ui_visible(False)
            self._set_scope_mode_ui_visible(False)
            self._set_import_loaded("")
        self._run_ui_transition(_apply)

    @Slot()
    def _back_to_scope_selection(self):
        def _apply():
            self.selection_stack.setCurrentWidget(self.scope_selection_page)
            self.wizard_stack.setCurrentIndex(0)
            self.parameter_tabs.clear()
            self._reset_result_views()
            self.calculate_button.setEnabled(False)
            self.current_mode_index = -1
            self._import_details_expanded = False
            self.live_enabled = False
            self._loaded_case_filename = ""
            self._last_live_signature = None
            self._render_controller.request_live_title(immediate=True)
            self._set_import_ui_visible(False)
            self._set_scope_mode_ui_visible(self.analysis_scope == "single" and self.case_imported)
            self._set_import_loaded("")
            if self.case_type == "existing":
                self.placeholder_label.setText("-> Please select single or group analysis, then import a case file")
            else:
                self.placeholder_label.setText("-> Please select an analysis scope")
        self._run_ui_transition(_apply)

    def _set_import_ui_visible(self, visible: bool):
        self.import_widget.setVisible(False)
        self.scope_import_widget.setVisible(visible)

    def _set_scope_mode_ui_visible(self, visible: bool):
        self.scope_mode_widget.setVisible(visible)

    def _sync_scope_mode_buttons(self):
        blockers = [QSignalBlocker(self.scope_mode_button_group), QSignalBlocker(self.mode_button_group)]
        try:
            for group in (self.scope_mode_button_group, self.mode_button_group):
                for button in group.buttons():
                    button.setChecked(group.id(button) == self.current_mode_index)
        finally:
            del blockers

    def _set_import_loaded(self, filename: str):
        self._loaded_case_filename = filename
        has_file = bool(filename)
        self.import_status_label.setVisible(has_file)
        self.view_modify_button.setVisible(False)
        self.direct_calc_button.setVisible(False)
        self.scope_import_status_label.setVisible(has_file)
        self.scope_view_modify_button.setVisible(has_file and not self._import_details_expanded)
        self.scope_direct_calc_button.setVisible(has_file and not self._import_details_expanded)
        self.scope_import_button.setText("Change File" if has_file else "Import Existing Case (.dat)")
        if has_file:
            mode_name = "Unknown"
            if self.current_mode_index == 0:
                mode_name = "Axial"
            elif self.current_mode_index == 1:
                mode_name = "Lateral"
            elif self.current_mode_index == 2:
                mode_name = "Combined"
            elif self.current_mode_index == 3:
                mode_name = "Group"
            text = f"Loaded: {filename} ({mode_name})"
            self.import_status_label.setText(text)
            self.scope_import_status_label.setText(text)
        else:
            self.import_status_label.setText("")
            self.scope_import_status_label.setText("")
            self.scope_import_button.setText("Import Existing Case (.dat)")

    def _apply_blank_panel_for_mode(self, mode_index: int):
        panel = self._make_panel_for_mode(mode_index)
        payload = self._payload_for_mode_from_doc(mode_index, self.case_doc)
        if self._payload_has_live_content(mode_index, payload):
            panel.set_payload(payload)
        self._replace_panel_for_mode(mode_index, panel)

    def _payload_for_mode_from_doc(self, mode_index: int, doc: dict) -> dict:
        payloads = doc.get("payloads", {}) if isinstance(doc, dict) else {}
        if mode_index == 0:
            return payloads.get("axial", {})
        if mode_index == 1:
            return payloads.get("lateral", {})
        if mode_index == 2:
            return payloads.get("combined", {})
        if mode_index == 3:
            return payloads.get("group", {})
        return {}

    def _payload_has_live_content(self, mode_index: int, payload: dict) -> bool:
        if not isinstance(payload, dict):
            return False
        layers = payload.get("layers")
        if isinstance(layers, list) and layers:
            return True
        if mode_index == 3:
            pile_layout = payload.get("pile_layout")
            pile_types = payload.get("pile_types")
            return bool(pile_layout or pile_types)
        pile_length = abs(float(payload.get("pile_length_m", 0.0) or 0.0))
        pile_top = float(payload.get("pile_top_z_m", 0.0) or 0.0)
        pile_bottom = float(payload.get("pile_bottom_z_m", 0.0) or 0.0)
        return pile_length > 1.0e-8 or abs(pile_top - pile_bottom) > 1.0e-8

    def _show_mode_tabs(self, refresh_live: bool = True):
        self.parameter_tabs.clear()
        if self.current_mode_index == 0:
            self.axial_panel.mount_to_tabs(self.parameter_tabs)
        elif self.current_mode_index == 1:
            self.lateral_panel.mount_to_tabs(self.parameter_tabs)
        elif self.current_mode_index == 2:
            self.combined_panel.mount_to_tabs(self.parameter_tabs)
        elif self.current_mode_index == 3:
            self.group_panel.mount_to_tabs(self.parameter_tabs)
        if refresh_live and not self._suspend_live_refresh and not self._import_in_progress:
            self._render_controller.request_live()

    def _iter_panels(self):
        return [
            self.axial_panel,
            self.lateral_panel,
            self.combined_panel,
            self.group_panel,
        ]

    def _panel_for_mode(self, mode_index: int):
        if mode_index == 0:
            return self.axial_panel
        if mode_index == 1:
            return self.lateral_panel
        if mode_index == 2:
            return self.combined_panel
        if mode_index == 3:
            return self.group_panel
        raise ValueError(f"Unknown mode index: {mode_index}")

    def _make_panel_for_mode(self, mode_index: int):
        if mode_index == 0:
            return AxialPanel()
        if mode_index == 1:
            return LateralPanel()
        if mode_index == 2:
            return CombinedPanel()
        if mode_index == 3:
            return GroupPanel()
        raise ValueError(f"Unknown mode index: {mode_index}")

    def _replace_panel_for_mode(self, mode_index: int, panel):
        if mode_index == 0:
            self.axial_panel = panel
        elif mode_index == 1:
            self.lateral_panel = panel
        elif mode_index == 2:
            self.combined_panel = panel
        elif mode_index == 3:
            self.group_panel = panel
        else:
            raise ValueError(f"Unknown mode index: {mode_index}")

    def _suspend_panel_callbacks(self):
        for panel in self._iter_panels():
            try:
                panel.set_change_callback(None)
            except Exception:
                pass

    def _restore_panel_callbacks(self):
        try:
            self.axial_panel.set_change_callback(self._on_axial_param_changed)
        except Exception:
            pass
        try:
            self.lateral_panel.set_change_callback(self._on_lateral_param_changed)
        except Exception:
            pass
        try:
            self.combined_panel.set_change_callback(self._on_combined_param_changed)
        except Exception:
            pass
        try:
            self.group_panel.set_change_callback(self._on_group_param_changed)
        except Exception:
            pass

    def _payload_for_current_mode_from_doc(self, doc: dict) -> dict:
        payloads = doc.get("payloads", {})
        if self.current_mode_index == 0:
            return payloads.get("axial", {}) if isinstance(payloads.get("axial", {}), dict) else {}
        if self.current_mode_index == 1:
            return payloads.get("lateral", {}) if isinstance(payloads.get("lateral", {}), dict) else {}
        if self.current_mode_index == 2:
            return payloads.get("combined", {}) if isinstance(payloads.get("combined", {}), dict) else {}
        if self.current_mode_index == 3:
            return payloads.get("group", {}) if isinstance(payloads.get("group", {}), dict) else {}
        return {}

    def _render_live_from_payload(self, payload: dict):
        if not hasattr(self, "live_view"):
            return
        self._last_live_signature = self._make_live_signature(payload)
        self._live_needs_refresh = False
        try:
            if self.current_mode_index == 3:
                self.live_view.render_group(payload if isinstance(payload, dict) else {})
            else:
                self.live_view.render_axial(payload if isinstance(payload, dict) else {})
        except Exception:
            self.live_view.render_title_only()

    def _reset_result_views(self):
        blockers = [
            QSignalBlocker(self.response_plot_tabs),
            QSignalBlocker(self.results_tabs),
            QSignalBlocker(self.visual_tabs),
        ]
        self.summary_text.clear()
        self.summary_text.setPlaceholderText("Result summary will be displayed here...")
        self.summary_table.clear()
        self.summary_table.setRowCount(0)
        self.summary_table.setColumnCount(0)
        self.summary_stack.setCurrentWidget(self.summary_text)
        self._show_single_result_table()
        self.result_table.clear()
        self.result_table.setRowCount(0)
        self.result_table.setColumnCount(0)
        self.plot_manager.reset()
        self._latest_results = None
        self._latest_result_payload = None
        self._latest_result_mode_key = None
        del blockers

    def _render_response(self, kind: str, results: dict, layer_backgrounds):
        if kind == "axial":
            self.plot_manager.render_axial(results, layer_backgrounds)
        elif kind == "lateral":
            self.plot_manager.render_lateral(results, layer_backgrounds)
        elif kind == "combined":
            self.plot_manager.render_combined(results, layer_backgrounds)
        elif kind == "group":
            self.plot_manager.render_group(results, layer_backgrounds)

    def _collect_live_payload(self) -> dict:
        if self.current_mode_index == 0:
            try:
                return self.axial_panel.collect_payload()
            except Exception:
                return self.case_doc.get("payloads", {}).get("axial", {})
        if self.current_mode_index == 1:
            try:
                return self.lateral_panel.collect_payload()
            except Exception:
                return self.case_doc.get("payloads", {}).get("lateral", {})
        if self.current_mode_index == 2:
            try:
                return self.combined_panel.collect_payload()
            except Exception:
                return self.case_doc.get("payloads", {}).get("combined", {})
        if self.current_mode_index == 3:
            try:
                return self.group_panel.collect_payload()
            except Exception:
                return self.case_doc.get("payloads", {}).get("group", {})
        return self.case_doc.get("payloads", {}).get("axial", {})

    def _make_live_signature(self, payload: Optional[dict]):
        try:
            normalized = payload if isinstance(payload, dict) else {}
            return (
                self.current_mode_index,
                json.dumps(normalized, sort_keys=True, ensure_ascii=False, default=str),
            )
        except Exception:
            return None

    def _run_ui_transition(self, action):
        if self._ui_transition_in_progress:
            return
        if self._result_render_in_progress:
            return
        if hasattr(self, "_calc_worker") and self._calc_worker is not None and self._calc_worker.isRunning():
            return
        self._ui_transition_in_progress = True
        self._live_refresh_timer.stop()
        if hasattr(self, "_render_controller"):
            self._render_controller.clear()
        self._pending_live_payload = None
        self._pending_live_force = False
        self._live_needs_refresh = False
        self._post_transition_live_request = None
        self._suspend_live_refresh = True
        blockers = [
            QSignalBlocker(self.parameter_tabs),
            QSignalBlocker(self.response_plot_tabs),
            QSignalBlocker(self.results_tabs),
            QSignalBlocker(self.visual_tabs),
        ]
        widgets = [self.parameter_tabs, self.response_plot_tabs, self.results_tabs, self.visual_tabs, self.live_view]
        try:
            self.visual_tabs.setCurrentIndex(0)
            self.results_tabs.setCurrentIndex(0)
            for widget in widgets:
                widget.setUpdatesEnabled(False)
            action()
        finally:
            for widget in reversed(widgets):
                widget.setUpdatesEnabled(True)
            del blockers
            self._suspend_live_refresh = False
            self._ui_transition_in_progress = False
            post_live = self._post_transition_live_request
            self._post_transition_live_request = None
            if post_live:
                payload, force = post_live
                QTimer.singleShot(
                    0,
                    lambda payload=payload, force=force: self._render_controller.request_live(
                        payload, force=force, immediate=True
                    ),
                )

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            focus = QApplication.focusWidget()
            if isinstance(focus, (QLineEdit, QTextEdit, QComboBox, QAbstractSpinBox, QTableWidget)):
                return super().keyPressEvent(event)
            current = self.selection_stack.currentWidget()
            if current is self.case_selection_page:
                for button in self.case_button_group.buttons():
                    if button.isChecked():
                        self._on_case_type_selected(self.case_button_group.id(button))
                        return
            elif current is self.scope_selection_page and self.case_type != "existing":
                for button in self.scope_button_group.buttons():
                    if button.isChecked():
                        self._on_scope_selected(self.scope_button_group.id(button))
                        return
            elif current is self.single_mode_selection_page:
                for button in self.mode_button_group.buttons():
                    if button.isChecked():
                        self._on_mode_selected(self.mode_button_group.id(button))
                        return
        super().keyPressEvent(event)

    def _create_result_table_widget(self) -> QTableWidget:
        table = QTableWidget(0, 0)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.verticalHeader().setVisible(False)
        table.setWordWrap(False)
        table.setAlternatingRowColors(True)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return table

    def _clear_layout_widgets(self, layout: QLayout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if child_layout is not None:
                self._clear_layout_widgets(child_layout)
            if widget is not None:
                widget.hide()
                widget.setParent(None)

    def _show_single_result_table(self):
        self._clear_layout_widgets(self.result_table_layout)
        self.group_result_tabs = None
        self.comparison_result_tabs = None
        self.comparison_result_tables = {}
        self.result_table = self._create_result_table_widget()
        self.result_table_layout.addWidget(self.result_table)

    def _create_comparison_result_tabs(self):
        self._clear_layout_widgets(self.result_table_layout)
        self.group_result_tabs = None
        self.comparison_result_tables = {}
        self.comparison_result_tabs = QTabWidget()
        self.comparison_result_tabs.setDocumentMode(True)
        for mode_name, label in (("elastic", "Elastic"), ("fiber", "Fiber")):
            table = self._create_result_table_widget()
            self.comparison_result_tabs.addTab(table, label)
            self.comparison_result_tables[mode_name] = table
        self.result_table = self.comparison_result_tables["elastic"]
        self.result_table_layout.addWidget(self.comparison_result_tabs)

    def _create_comparison_group_result_tabs(self, pile_count: int):
        self._clear_layout_widgets(self.result_table_layout)
        self.group_result_tabs = None
        self.comparison_result_tables = {}
        self.comparison_result_tabs = QTabWidget()
        self.comparison_result_tabs.setDocumentMode(True)
        for mode_name, label in (("elastic", "Elastic"), ("fiber", "Fiber")):
            inner_tabs = QTabWidget()
            inner_tabs.setDocumentMode(True)
            overview_table = self._create_result_table_widget()
            inner_tabs.addTab(overview_table, "Overview")
            pile_tables = []
            for pile_idx in range(pile_count):
                pile_table = self._create_result_table_widget()
                inner_tabs.addTab(pile_table, f"Pile {pile_idx + 1}")
                pile_tables.append(pile_table)
            self.comparison_result_tabs.addTab(inner_tabs, label)
            self.comparison_result_tables[mode_name] = {
                "tabs": inner_tabs,
                "overview": overview_table,
                "piles": pile_tables,
            }
        self.result_table = self.comparison_result_tables["elastic"]["overview"]
        self.result_table_layout.addWidget(self.comparison_result_tabs)

    def _create_group_result_tabs(self, pile_count: int):
        self._clear_layout_widgets(self.result_table_layout)
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        self.comparison_result_tabs = None
        self.comparison_result_tables = {}
        self.result_table = self._create_result_table_widget()
        tabs.addTab(self.result_table, "Overview")
        for pile_idx in range(pile_count):
            tabs.addTab(self._create_result_table_widget(), f"Pile {pile_idx + 1}")
        self.group_result_tabs = tabs
        self.result_table_layout.addWidget(tabs)

    def _current_result_table(self) -> QTableWidget:
        if self.group_result_tabs is not None:
            widget = self.group_result_tabs.currentWidget()
            if isinstance(widget, QTableWidget):
                return widget
        if self.comparison_result_tabs is not None:
            widget = self.comparison_result_tabs.currentWidget()
            if isinstance(widget, QTableWidget):
                return widget
            if isinstance(widget, QTabWidget):
                current = widget.currentWidget()
                if isinstance(current, QTableWidget):
                    return current
        return self.result_table

    def _show_summary_text(self, text: str):
        self.summary_text.setPlainText(text)
        self.summary_stack.setCurrentWidget(self.summary_text)

    def _show_summary_table(self, headers, rows):
        self._fill_table_widget(self.summary_table, headers, rows)
        self.summary_stack.setCurrentWidget(self.summary_table)

    def _fill_table_widget(self, table: QTableWidget, headers, rows):
        table.clear()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels([self._tr(str(header)) for header in headers])
        table.setRowCount(len(rows))
        for r_idx, row_vals in enumerate(rows):
            for c_idx, value in enumerate(row_vals):
                txt = f"{value:.8f}" if isinstance(value, float) else str(value)
                item = QTableWidgetItem(txt)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(r_idx, c_idx, item)
        self._finalize_result_table(table)

    @Slot(int)
    def _on_scope_selected(self, scope_id: int):
        def _apply():
            self.analysis_scope = "single" if scope_id == 0 else "group"
            self.current_mode_index = -1
            self._import_details_expanded = False
            self.parameter_tabs.clear()
            self._reset_result_views()
            self.wizard_stack.setCurrentIndex(0)
            self.calculate_button.setEnabled(False)
            self._set_import_loaded("")
            self.live_enabled = False
            self._last_live_signature = None
            self._render_controller.request_live_title(immediate=True)

            if self.analysis_scope == "single":
                self._set_scope_mode_ui_visible(True)
                if self.case_type == "existing":
                    self.selection_stack.setCurrentWidget(self.scope_selection_page)
                    self._set_import_ui_visible(True)
                    self.live_enabled = False
                    self._render_controller.request_live_title(immediate=True)
                    self.placeholder_label.setText("-> Import a single-pile case file; mode will be detected automatically")
                else:
                    self.selection_stack.setCurrentWidget(self.single_mode_selection_page)
                    self._set_import_ui_visible(False)
                    self.placeholder_label.setText("-> Please select a single pile mode")
                return

            self._set_import_ui_visible(self.case_type == "existing")
            self._set_scope_mode_ui_visible(False)
            self.current_mode_index = 3
            if self.case_type == "new":
                self._apply_blank_panel_for_mode(3)
                self._show_mode_tabs(refresh_live=False)
                self.selection_stack.setCurrentWidget(self.scope_selection_page)
                self.wizard_stack.setCurrentIndex(1)
                self.calculate_button.setEnabled(True)
                self.save_case_button.setEnabled(True)
                self.live_enabled = True
                self._render_controller.request_live(force=True, immediate=True)
                self.placeholder_label.setText("-> Start with pile types, pile layout, soil layers, and one load case")
            else:
                self.selection_stack.setCurrentWidget(self.scope_selection_page)
                self.live_enabled = False
                self.placeholder_label.setText("-> Import a group-pile case file; detailed tabs will stay collapsed")
                self.save_case_button.setEnabled(False)
        self._run_ui_transition(_apply)

    @Slot(int)
    def _on_mode_selected(self, index: int):
        def _apply():
            self.current_mode_index = index
            self._import_details_expanded = False
            self._reset_result_views()
            if self.analysis_scope == "single" and (self.case_type == "new" or self.case_imported):
                self._apply_blank_panel_for_mode(index)
            self.live_enabled = self.case_type == "new" or self.case_imported
            self._last_live_signature = None
            self._show_mode_tabs(refresh_live=False)
            self._sync_scope_mode_buttons()
            if self.live_enabled:
                try:
                    live_payload = self._panel_for_mode(index).collect_payload()
                except Exception:
                    live_payload = self._payload_for_mode_from_doc(index, self.case_doc)
                self._post_transition_live_request = (live_payload, True)
            else:
                self._render_controller.request_live_title(immediate=True)
            if self.case_type == "new":
                self.wizard_stack.setCurrentIndex(1)
                self.calculate_button.setEnabled(True)
                self.save_case_button.setEnabled(True)
                self.placeholder_label.setText("-> Start with pile geometry, at least one material/layer, and one load case")
            elif self.case_type == "existing" and self.case_imported:
                self.wizard_stack.setCurrentIndex(1)
                self.calculate_button.setEnabled(True)
                self.save_case_button.setEnabled(True)
            else:
                self.wizard_stack.setCurrentIndex(0)
                self.calculate_button.setEnabled(False)
                self.save_case_button.setEnabled(False)
        self._run_ui_transition(_apply)

    @Slot(int)
    def _on_scope_mode_selected(self, index: int):
        if self.analysis_scope != "single":
            return
        if self.case_type == "existing" and not self.case_imported:
            return
        self._on_mode_selected(index)

    @Slot()
    def _import_dat_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self._tr("Import Existing Case"),
            "",
            self._tr("DAT Files (*.dat);;All Files (*)"),
        )
        if not file_path:
            return
        try:
            doc = load_case(file_path)
        except Exception as exc:
            QMessageBox.critical(self, self._tr("Import Failed"), self._tr(str(exc)))
            return
        QTimer.singleShot(0, lambda: self._apply_imported_case_document(doc, file_path, open_editor=False, builtin=False))

    def _load_builtin_case(self, file_path: str):
        if not os.path.exists(file_path):
            QMessageBox.warning(self, self._tr("Notice"), self._tr(f"Sample case not found:\n{file_path}"))
            return
        try:
            doc = load_case(file_path)
        except Exception as exc:
            QMessageBox.critical(self, self._tr("Import Failed"), self._tr(str(exc)))
            return
        # Tutorials should follow the full existing-case import path, but land
        # directly in the expanded editable state.
        QTimer.singleShot(0, lambda: self._apply_imported_case_document(doc, file_path, open_editor=True, builtin=False))

    def _apply_imported_case_document(self, doc: dict, file_path: str, open_editor: bool = False, builtin: bool = False):
        if self._import_in_progress:
            return
        self._import_in_progress = True
        auto_open_editor = bool(open_editor)
        self._live_refresh_timer.stop()
        self._pending_live_payload = None
        self._pending_live_force = False
        live_was_visible = hasattr(self, "live_view") and self.live_view.isVisible()

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.setUpdatesEnabled(False)
        self._suspend_panel_callbacks()
        if hasattr(self, "live_view"):
            self.live_view.setUpdatesEnabled(False)
            self.live_view.hide()

        self._suspend_live_refresh = True
        try:
            self.case_doc = doc
            self.case_type = "existing"
            self._reset_result_views()
            mode_text = str(doc.get("mode", "axial")).lower()
            if mode_text == "axial":
                self.analysis_scope = "single"
                self.current_mode_index = 0
            elif mode_text == "lateral":
                self.analysis_scope = "single"
                self.current_mode_index = 1
            elif mode_text == "combined":
                self.analysis_scope = "single"
                self.current_mode_index = 2
            elif mode_text == "group":
                self.analysis_scope = "group"
                self.current_mode_index = 3
            else:
                QMessageBox.warning(self, self._tr("Invalid Mode"), self._tr(f"Unsupported case mode: {mode_text}"))
                return

            self._import_details_expanded = False
            if self.analysis_scope == "single":
                scope_button = self.scope_button_group.button(0)
                if scope_button is not None:
                    scope_button.setChecked(True)
                self._set_scope_mode_ui_visible(True)
                self._sync_scope_mode_buttons()
                # Existing-case imports stay on the scope page; expanding the
                # detailed editor should behave exactly like clicking
                # "View and Edit" from there.
                self.selection_stack.setCurrentWidget(self.scope_selection_page)
            else:
                self.selection_stack.setCurrentWidget(self.scope_selection_page)
                scope_button = self.scope_button_group.button(1)
                if scope_button is not None:
                    scope_button.setChecked(True)
                self._set_scope_mode_ui_visible(False)
            self._set_import_ui_visible(not builtin)
            payload = self._payload_for_current_mode_from_doc(doc)
            panel = self._make_panel_for_mode(self.current_mode_index)
            if isinstance(payload, dict) and payload:
                panel.set_payload(payload)
            self._replace_panel_for_mode(self.current_mode_index, panel)

            self.case_imported = True
            self.live_enabled = False
            self.parameter_tabs.clear()
            self.wizard_stack.setCurrentIndex(0)
            self.calculate_button.setEnabled(False)
            self.save_case_button.setEnabled(False)
            self.placeholder_label.setText("-> Case imported. Choose View and Edit or Run Directly")
            self._render_controller.request_live_title(immediate=True)
            self._set_import_loaded(os.path.basename(file_path))
        except Exception as exc:
            QMessageBox.critical(self, self._tr("Import Failed"), f"{exc}\n\n{traceback.format_exc()}")
        finally:
            self._suspend_live_refresh = False
            self._restore_panel_callbacks()
            self.setUpdatesEnabled(True)
            if hasattr(self, "live_view"):
                self.live_view.setUpdatesEnabled(True)
                if live_was_visible:
                    self.live_view.show()
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()
            self._import_in_progress = False
            if auto_open_editor:
                QTimer.singleShot(0, self._show_parameter_tabs)
            elif self.live_enabled:
                QTimer.singleShot(250, lambda: self._render_controller.request_live(force=True))

    @Slot()
    def _show_parameter_tabs(self):
        if self.current_mode_index < 0:
            QMessageBox.information(self, self._tr("Notice"), self._tr("Please select an analysis mode first."))
            return
        self._import_details_expanded = True
        self.live_enabled = True
        if hasattr(self, "live_view"):
            self.live_view.setUpdatesEnabled(True)
            self.live_view.show()
        self._show_mode_tabs(refresh_live=False)
        self._set_import_loaded(self._loaded_case_filename)
        self.wizard_stack.setCurrentIndex(1)
        self.calculate_button.setEnabled(True)
        self.save_case_button.setEnabled(True)
        try:
            live_payload = self._panel_for_mode(self.current_mode_index).collect_payload()
        except Exception:
            live_payload = self._payload_for_mode_from_doc(self.current_mode_index, self.case_doc)
        self._render_controller.request_live(live_payload, force=True, immediate=True)

    @Slot()
    def start_calculation(self):
        mode_names_map = {0: "axial", 1: "lateral", 2: "combined", 3: "group"}
        mode_label_map = {0: "Axial Analysis", 1: "Lateral Analysis", 2: "Combined Analysis", 3: "Group Analysis"}
        panels = {0: self.axial_panel, 1: self.lateral_panel, 2: self.combined_panel, 3: self.group_panel}

        if self.current_mode_index not in panels:
            return

        try:
            payload = panels[self.current_mode_index].collect_payload()
        except Exception as exc:
            self.calc_status_label.setText(self._tr("Parameter Error"))
            QMessageBox.critical(self, self._tr("Parameter Error"), self._tr(str(exc)))
            return

        mode_key = mode_names_map[self.current_mode_index]
        self.case_doc["mode"] = mode_key
        self.case_doc["payloads"][mode_key] = payload

        # Disable UI during calculation
        self.calculate_button.setEnabled(False)
        self.calculate_button.setText(self._tr("Computing..."))
        init_text = self._tr("Initializing...")
        self.calc_status_label.setText(init_text)
        self.calc_status_label.setStyleSheet(
            "QLabel { color: #e67e22; padding: 2px 10px; border-left: 1px solid #cccccc; font-weight: bold; font-size: 9pt; }"
        )
        self.calc_status_label.setToolTip(init_text)
        self.calc_status_label.repaint()
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

        # Store context for callback
        self._calc_mode_index = self.current_mode_index
        self._calc_payload = payload
        self._calc_mode_label = mode_label_map[self.current_mode_index]
        self._ignore_worker_status_updates = False
        self._show_progress_dialog(self._calc_mode_label)

        # Launch worker thread
        self._calc_worker = _CalcWorker(self.current_mode_index, payload, self.case_doc)
        self._calc_worker.progress.connect(self._on_calc_progress)
        self._calc_worker.status.connect(self._on_calc_status)
        self._calc_worker.finished.connect(self._on_calc_finished)
        self._calc_worker.error.connect(self._on_calc_error)
        self._calc_worker.start()

    def _show_progress_dialog(self, mode_label: str):
        dialog = getattr(self, "_progress_dialog", None)
        if dialog is None:
            dialog = QProgressDialog(self)
            dialog.setCancelButton(None)
            dialog.setMinimumDuration(0)
            dialog.setAutoClose(False)
            dialog.setAutoReset(False)
            dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
            self._progress_dialog = dialog
        dialog.setWindowTitle(mode_label)
        dialog.setLabelText(self._tr("Preparing calculation..."))
        dialog.setRange(0, 100)
        dialog.setValue(0)
        dialog.show()
        dialog.repaint()
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

    def _close_progress_dialog(self):
        dialog = getattr(self, "_progress_dialog", None)
        if dialog is None:
            return
        dialog.setValue(100)
        dialog.repaint()
        dialog.hide()

    @Slot(int, str)
    def _legacy_on_calc_progress_unused(self, value: int, msg: str):
        dialog = getattr(self, "_progress_dialog", None)
        if dialog is not None:
            dialog.setValue(max(0, min(int(value), 100)))
            dialog.setLabelText(msg)
            QApplication.processEvents()
        self.calc_status_label.setText(f"éˆ´?{msg}")

    @Slot(str)
    def _legacy_on_calc_status_unused(self, msg: str):
        self.calc_status_label.setText(f"⏳ {msg}")

    @Slot(dict)
    def _legacy_on_calc_finished_unused(self, results: dict):
        self._result_render_in_progress = True
        mode_idx = self._calc_mode_index
        payload = self._calc_payload
        input_obj = self._calc_worker._input_obj
        bgs = self._layer_backgrounds(payload)
        self._latest_results = results
        self._latest_result_payload = payload
        self._latest_result_mode_key = {0: "axial", 1: "lateral", 2: "combined", 3: "group"}.get(mode_idx)

        self.calc_status_label.setText("⏳ Rendering results...")
        try:
            if mode_idx == 0:
                self.summary_text.setPlainText(ResultFormatter.axial_summary(input_obj, results))
                self._populate_axial_table(results)
                self._render_controller.request_response("axial", results, bgs)
            elif mode_idx == 1:
                self.summary_text.setPlainText(ResultFormatter.lateral_summary(input_obj, results))
                self._populate_lateral_table(results)
                self._render_controller.request_response("lateral", results, bgs)
            elif mode_idx == 2:
                self.summary_text.setPlainText(ResultFormatter.combined_summary(input_obj, results))
                self._populate_combined_table(results)
                self._render_controller.request_response("combined", results, bgs)
            elif mode_idx == 3:
                self.summary_text.setPlainText(ResultFormatter.group_summary(input_obj, results))
                self._populate_group_table(results)
                self._render_controller.request_response("group", results, bgs)
        except Exception as exc:
            self._result_render_in_progress = False
            self._on_calc_error(f"Result rendering failed: {exc}")
            return

        self.live_enabled = True
        self._render_controller.request_live(payload, force=True)
        self.plot_tabs.setCurrentIndex(1)
        self._on_calculation_complete(self._calc_mode_label)

    @Slot(str)
    def _legacy_on_calc_error_unused(self, msg: str):
        self._result_render_in_progress = False
        self.calc_status_label.setText("❌ Run Failed")
        self.calc_status_label.setStyleSheet(
            "QLabel { color: #e74c3c; padding: 2px 10px; border-left: 1px solid #cccccc; font-weight: bold; font-size: 9pt; }"
        )
        self.calculate_button.setEnabled(True)
        self.calculate_button.setText("Run")
        if get_language() == "zh":
            self.calculate_button.setText("运行")
        QMessageBox.critical(self, "Run Failed", msg)

    def _legacy_on_calculation_complete_unused(self, mode_name: str):
        self.calc_status_label.setText("✅ Completed")
        self.calc_status_label.setStyleSheet(
            "QLabel { color: #27ae60; padding: 2px 10px; border-left: 1px solid #cccccc; font-weight: bold; font-size: 9pt; }"
        )
        self.calculate_button.setEnabled(True)
        self.calculate_button.setText("Run")
        if get_language() == "zh":
            self.calculate_button.setText("运行")
        self.visual_tabs.setCurrentIndex(1)
        self.results_tabs.setCurrentIndex(0)
        self._result_render_in_progress = False
        QMessageBox.information(self, "Completed", f"{mode_name} calculation completed.")

    @Slot(dict)
    def _on_calc_finished(self, results: dict):
        self._ignore_worker_status_updates = True
        self._result_render_in_progress = True
        mode_idx = self._calc_mode_index
        payload = self._calc_payload
        input_obj = self._calc_worker._input_obj
        bgs = self._layer_backgrounds(payload)
        self._latest_results = results
        self._latest_result_payload = payload
        self._latest_result_mode_key = {0: "axial", 1: "lateral", 2: "combined", 3: "group"}.get(mode_idx)

        self.calc_status_label.setText(self._tr("Rendering results..."))
        try:
            if isinstance(results, dict) and results.get("comparison_mode"):
                self._render_comparison_results(mode_idx, results, bgs)
            elif mode_idx == 0:
                self._show_summary_text(ResultFormatter.axial_summary(input_obj, results))
                self._populate_axial_table(results)
                self._render_controller.request_response("axial", results, bgs)
            elif mode_idx == 1:
                self._show_summary_text(ResultFormatter.lateral_summary(input_obj, results))
                self._populate_lateral_table(results)
                self._render_controller.request_response("lateral", results, bgs)
            elif mode_idx == 2:
                self._show_summary_text(ResultFormatter.combined_summary(input_obj, results))
                self._populate_combined_table(results)
                self._render_controller.request_response("combined", results, bgs)
            elif mode_idx == 3:
                self._show_summary_text(ResultFormatter.group_summary(input_obj, results))
                self._populate_group_table(results)
                self._render_controller.request_response("group", results, bgs)
        except Exception as exc:
            self._result_render_in_progress = False
            self._close_progress_dialog()
            self._on_calc_error(f"Result rendering failed: {exc}")
            return

        self.live_enabled = True
        self._render_controller.request_live(payload, force=True)
        self.plot_tabs.setCurrentIndex(1)
        self._on_calculation_complete(self._calc_mode_label)

    @Slot(str)
    def _on_calc_error(self, msg: str):
        self._ignore_worker_status_updates = True
        self._result_render_in_progress = False
        self._close_progress_dialog()
        self.calc_status_label.setText(self._tr("Run Failed"))
        self.calc_status_label.setStyleSheet(
            "QLabel { color: #e74c3c; padding: 2px 10px; border-left: 1px solid #cccccc; font-weight: bold; font-size: 9pt; }"
        )
        self.calculate_button.setEnabled(True)
        self.calculate_button.setText("Run")
        if get_language() == "zh":
            self.calculate_button.setText("æ©æ„¯î”‘")
        QMessageBox.critical(self, "Run Failed", msg)

    def _on_calculation_complete(self, mode_name: str):
        self._close_progress_dialog()
        self.calc_status_label.setText(self._tr("Completed"))
        self.calc_status_label.setStyleSheet(
            "QLabel { color: #27ae60; padding: 2px 10px; border-left: 1px solid #cccccc; font-weight: bold; font-size: 9pt; }"
        )
        self.calculate_button.setEnabled(True)
        self.calculate_button.setText("Run")
        if get_language() == "zh":
            self.calculate_button.setText("æ©æ„¯î”‘")
        self.visual_tabs.setCurrentIndex(1)
        self.results_tabs.setCurrentIndex(0)
        self._result_render_in_progress = False
        QMessageBox.information(self, "Completed", f"{mode_name} calculation completed.")

    def _render_comparison_results(self, mode_idx: int, results: dict, layer_backgrounds):
        elastic_results = dict(results.get("elastic") or {})
        fiber_results = dict(results.get("fiber") or {})
        self._show_summary_table(
            ["Metric", "Elastic", "Fiber"],
            self._build_comparison_summary_rows(mode_idx, elastic_results, fiber_results),
        )
        if mode_idx == 3:
            pile_count = max(len(elastic_results.get("piles", [])), len(fiber_results.get("piles", [])))
            self._create_comparison_group_result_tabs(pile_count)
            elastic_tables = self.comparison_result_tables.get("elastic", {})
            fiber_tables = self.comparison_result_tables.get("fiber", {})
            self._fill_group_result_tabs(elastic_results, elastic_tables)
            self._fill_group_result_tabs(fiber_results, fiber_tables)
            self.plot_manager.render_group(fiber_results, layer_backgrounds)
        else:
            self._create_comparison_result_tabs()
            elastic_table = self.comparison_result_tables.get("elastic")
            fiber_table = self.comparison_result_tables.get("fiber")
            elastic_headers, elastic_rows = self._comparison_table_data(mode_idx, elastic_results)
            fiber_headers, fiber_rows = self._comparison_table_data(mode_idx, fiber_results)
            if elastic_table is not None:
                self._fill_table_widget(elastic_table, elastic_headers, elastic_rows)
            if fiber_table is not None:
                self._fill_table_widget(fiber_table, fiber_headers, fiber_rows)
            mode_name = {0: "axial", 1: "lateral", 2: "combined"}.get(mode_idx)
            if mode_name:
                self.plot_manager.render_comparison(mode_name, elastic_results, fiber_results, layer_backgrounds)

    def _comparison_table_data(self, mode_idx: int, results: dict):
        if mode_idx == 0:
            return self._build_axial_table_data(results)
        if mode_idx == 1:
            return self._build_lateral_table_data(results)
        if mode_idx == 2:
            return self._build_combined_table_data(results)
        return [], []

    @staticmethod
    def _comparison_metric_row(label: str, elastic_value, fiber_value):
        return [label, elastic_value, fiber_value]

    def _build_comparison_summary_rows(self, mode_idx: int, elastic_results: dict, fiber_results: dict):
        if mode_idx == 0:
            return [
            self._comparison_metric_row("Top displacement Z (mm)", ResultFormatter.axial_z_mm_for_display(float(elastic_results.get("pile_top_disp", 0.0))), ResultFormatter.axial_z_mm_for_display(float(fiber_results.get("pile_top_disp", 0.0)))),
                self._comparison_metric_row("Total skin friction accumulated (kN)", float(elastic_results.get("total_skin_friction", 0.0)), float(fiber_results.get("total_skin_friction", 0.0))),
                self._comparison_metric_row("End bearing Z (kN)", float(elastic_results.get("end_bearing", 0.0)), float(fiber_results.get("end_bearing", 0.0))),
            ]
        if mode_idx == 1:
            return [
                self._comparison_metric_row("Top displacement (mm)", float(elastic_results.get("pile_top_disp", 0.0)), float(fiber_results.get("pile_top_disp", 0.0))),
                self._comparison_metric_row("Max moment (kN*m)", float(elastic_results.get("max_moment", 0.0)), float(fiber_results.get("max_moment", 0.0))),
                self._comparison_metric_row("Max moment depth (m)", float(elastic_results.get("max_moment_depth", 0.0)), float(fiber_results.get("max_moment_depth", 0.0))),
            ]
        if mode_idx == 2:
            return [
                self._comparison_metric_row("Head displacement X (mm)", float(elastic_results.get("head_disp_x_mm", 0.0)), float(fiber_results.get("head_disp_x_mm", 0.0))),
                self._comparison_metric_row("Max |axial force| (kN)", float(elastic_results.get("max_abs_axial", 0.0)), float(fiber_results.get("max_abs_axial", 0.0))),
                self._comparison_metric_row("Max |moment| (kN*m)", float(elastic_results.get("max_abs_moment", 0.0)), float(fiber_results.get("max_abs_moment", 0.0))),
            ]
        if mode_idx == 3:
            return [
                self._comparison_metric_row("Max |axial force| (kN)", float(elastic_results.get("max_abs_axial", 0.0)), float(fiber_results.get("max_abs_axial", 0.0))),
                self._comparison_metric_row("Max |shear| (kN)", float(elastic_results.get("max_abs_shear", 0.0)), float(fiber_results.get("max_abs_shear", 0.0))),
                self._comparison_metric_row("Max |moment| (kN*m)", float(elastic_results.get("max_abs_moment", 0.0)), float(fiber_results.get("max_abs_moment", 0.0))),
            ]
        return []

    def _build_axial_table_data(self, r: dict):
        headers = ["Index", "Depth (m)", "Disp Z (mm, +up/-down)", "Axial Force (kN)", "Skin Friction Z (kN)", "Ult Skin Z (kN)", "Soil Stiffness (kN/m)"]
        depths = r.get("depths", [])
        disps_mm = r.get("displacements", [])
        axial = r.get("axial_forces", [])
        skin = r.get("skin_frictions", [])
        ult_skin = r.get("ult_skin_frictions", [])
        n = min(len(depths), len(disps_mm), len(axial), len(skin), len(ult_skin))
        rows = []
        for i in range(n):
            disp_m = float(disps_mm[i]) / 1000.0
            stiffness = 0.0 if abs(disp_m) < 1.0e-12 else abs(float(skin[i]) / disp_m)
            rows.append([i, float(depths[i]), -float(disps_mm[i]), float(axial[i]), -float(skin[i]), -float(ult_skin[i]), stiffness])
        return headers, rows

    def _build_lateral_table_data(self, r: dict):
        headers = ["Index", "Depth (m)", "Disp (mm)", "Rotation (rad)", "Soil Reaction (kN)", "Soil Reaction per m (kN/m)", "Soil Stiffness (kN/m^2)", "Ele Depth (m)", "Moment (kN*m)", "Shear (kN)"]
        depths = r.get("depths", [])
        disps = r.get("displacements", [])
        rots = r.get("rotations", [])
        soil_rxn = r.get("soil_reactions", [])
        soil_rxn_per_m = r.get("soil_reactions_per_m", [])
        soil_stiffness = r.get("soil_stiffness", [])
        depths_ele = r.get("depths_ele", [])
        moments = r.get("moments", [])
        shears = r.get("shears", [])
        n = max(len(depths), len(depths_ele))
        rows = []
        for i in range(n):
            rows.append([i, float(depths[i]) if i < len(depths) else 0.0, float(disps[i]) if i < len(disps) else 0.0, float(rots[i]) if i < len(rots) else 0.0, float(soil_rxn[i]) if i < len(soil_rxn) else 0.0, float(soil_rxn_per_m[i]) if i < len(soil_rxn_per_m) else 0.0, float(soil_stiffness[i]) if i < len(soil_stiffness) else 0.0, float(depths_ele[i]) if i < len(depths_ele) else 0.0, float(moments[i]) if i < len(moments) else 0.0, float(shears[i]) if i < len(shears) else 0.0])
        return headers, rows

    def _build_combined_table_data(self, r: dict):
        headers = ["Index", "Depth (m)", "Disp X (mm)", "Disp Z (mm, +up/-down)", "Ele Depth (m)", "Axial Force Z (kN, +up/-down)", "Shear X' (kN)", "Moment X'Z' (kN*m)"]
        depths = r.get("depths", [])
        disp_x = r.get("displacements_x", [])
        disp_z = r.get("displacements_z", [])
        depths_ele = r.get("depths_ele", [])
        axial = r.get("axial_forces", [])
        shears = r.get("shears", [])
        moments = r.get("moments", [])
        n = max(len(depths), len(depths_ele))
        rows = []
        for i in range(n):
            rows.append([i, float(depths[i]) if i < len(depths) else 0.0, float(disp_x[i]) if i < len(disp_x) else 0.0, float(disp_z[i]) if i < len(disp_z) else 0.0, float(depths_ele[i]) if i < len(depths_ele) else 0.0, -float(axial[i]) if i < len(axial) else 0.0, float(shears[i]) if i < len(shears) else 0.0, float(moments[i]) if i < len(moments) else 0.0])
        return headers, rows

    def _group_table_data(self, r: dict):
        overview_headers = [
            "Pile",
            "Head Disp X (mm)",
            "Head Disp Y (mm)",
            "Head Disp Z (mm, +up/-down)",
            "Max |Axial| (kN)",
            "Max |Shear| (kN)",
            "Max |Moment| (kN*m)",
        ]
        pile_headers = [
            "Node",
            "Depth (m)",
            "Disp X (mm)",
            "Disp Y (mm)",
            "Disp Z (mm, +up/-down)",
            "Section Depth (m)",
            "Axial Force (kN)",
            "Shear X' (kN)",
            "Shear Y' (kN)",
            "Moment X' (kN*m)",
            "Moment Y' (kN*m)",
        ]
        overview_rows = []
        pile_rows_list = []
        piles = r.get("piles", [])
        for i, pile in enumerate(piles):
            disp = pile.get("head_disp_global", [0.0, 0.0, 0.0])
            overview_rows.append([
                int(pile.get("id", i + 1)),
                float(disp[0]) * 1000.0 if len(disp) > 0 else 0.0,
                float(disp[1]) * 1000.0 if len(disp) > 1 else 0.0,
                float(disp[2]) * 1000.0 if len(disp) > 2 else 0.0,
                max((abs(float(v)) for v in pile.get("axial_forces", [])), default=0.0),
                max((max((abs(float(v)) for v in pile.get("rspile_shear_x", [])), default=0.0), max((abs(float(v)) for v in pile.get("rspile_shear_y", [])), default=0.0))),
                max((max((abs(float(v)) for v in pile.get("rspile_moment_x", [])), default=0.0), max((abs(float(v)) for v in pile.get("rspile_moment_y", [])), default=0.0))),
            ])
            depths = pile.get("depths_from_head", [])
            disp_x = pile.get("disps_dx", [])
            disp_y = pile.get("disps_dy", [])
            disp_z = pile.get("disps_dz", [])
            section_depths = pile.get("depths_ele_from_head", [])
            axial = pile.get("axial_forces", [])
            shear_x = pile.get("rspile_shear_x", [])
            shear_y = pile.get("rspile_shear_y", [])
            moment_x = pile.get("rspile_moment_x", [])
            moment_y = pile.get("rspile_moment_y", [])
            row_count = max(len(depths), len(section_depths), len(axial), len(shear_x), len(shear_y), len(moment_x), len(moment_y))
            pile_rows = []
            for row_idx in range(row_count):
                pile_rows.append([
                    row_idx + 1,
                    float(depths[row_idx]) if row_idx < len(depths) else None,
                    float(disp_x[row_idx]) if row_idx < len(disp_x) else None,
                    float(disp_y[row_idx]) if row_idx < len(disp_y) else None,
                    float(disp_z[row_idx]) if row_idx < len(disp_z) else None,
                    float(section_depths[row_idx]) if row_idx < len(section_depths) else None,
                    float(axial[row_idx]) if row_idx < len(axial) else None,
                    float(shear_x[row_idx]) if row_idx < len(shear_x) else None,
                    float(shear_y[row_idx]) if row_idx < len(shear_y) else None,
                    float(moment_x[row_idx]) if row_idx < len(moment_x) else None,
                    float(moment_y[row_idx]) if row_idx < len(moment_y) else None,
                ])
            pile_rows_list.append(pile_rows)
        return overview_headers, overview_rows, pile_headers, pile_rows_list

    def _fill_group_result_tabs(self, r: dict, tab_bundle):
        if not isinstance(tab_bundle, dict):
            return
        overview_headers, overview_rows, pile_headers, pile_rows_list = self._group_table_data(r)
        overview_table = tab_bundle.get("overview")
        if isinstance(overview_table, QTableWidget):
            self._fill_table_widget(overview_table, overview_headers, overview_rows)
        for idx, pile_rows in enumerate(pile_rows_list):
            pile_tables = tab_bundle.get("piles", [])
            if idx < len(pile_tables) and isinstance(pile_tables[idx], QTableWidget):
                self._fill_table_widget(pile_tables[idx], pile_headers, pile_rows)
        tabs = tab_bundle.get("tabs")
        if isinstance(tabs, QTabWidget):
            tabs.setCurrentIndex(0)

    @Slot(int, str)
    def _on_calc_progress(self, value: int, msg: str):
        if getattr(self, "_ignore_worker_status_updates", False):
            return
        dialog = getattr(self, "_progress_dialog", None)
        translated_msg = self._tr(msg)
        if dialog is not None:
            dialog.setValue(max(0, min(int(value), 100)))
            dialog.setLabelText(translated_msg)
            dialog.repaint()
            QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        self.calc_status_label.setText(translated_msg)
        self.calc_status_label.setToolTip(translated_msg)
        self.calc_status_label.repaint()

    @Slot(str)
    def _on_calc_status(self, msg: str):
        if getattr(self, "_ignore_worker_status_updates", False):
            return
        translated_msg = self._tr(msg)
        self.calc_status_label.setText(translated_msg)
        self.calc_status_label.setToolTip(translated_msg)
        self.calc_status_label.repaint()

    def _on_axial_param_changed(self):
        self.live_enabled = True
        self._schedule_live_refresh()

    def _on_lateral_param_changed(self):
        self.live_enabled = True
        self._schedule_live_refresh()

    def _on_combined_param_changed(self):
        self.live_enabled = True
        self._schedule_live_refresh()

    def _on_group_param_changed(self):
        self.live_enabled = True
        self._schedule_live_refresh()

    def _schedule_live_refresh(self, payload_hint: Optional[dict] = None, force: bool = False):
        if self._suspend_live_refresh:
            self._pending_live_payload = payload_hint
            self._pending_live_force = self._pending_live_force or force
            self._live_needs_refresh = True
            return
        self._pending_live_payload = payload_hint
        self._pending_live_force = self._pending_live_force or force
        self._live_needs_refresh = True
        if hasattr(self, "visual_tabs") and self.visual_tabs.currentIndex() != 0 and not force:
            return
        self._live_refresh_timer.start(LIVE_REFRESH_DEBOUNCE_MS)

    @Slot()
    def _flush_live_refresh(self):
        if self._live_refresh_running:
            self._live_needs_refresh = True
            return
        payload = self._pending_live_payload
        force = self._pending_live_force
        self._pending_live_payload = None
        self._pending_live_force = False
        self._refresh_live_view(payload_hint=payload, force=force)

    def _refresh_live_view(self, payload_hint: Optional[dict] = None, force: bool = False):
        if not hasattr(self, "live_view"):
            return
        if self._suspend_live_refresh or self._import_in_progress:
            return
        if self._live_refresh_running:
            self._pending_live_payload = payload_hint
            self._pending_live_force = self._pending_live_force or force
            self._live_needs_refresh = True
            return
        if hasattr(self, "visual_tabs") and self.visual_tabs.currentIndex() != 0 and not force:
            self._pending_live_payload = payload_hint
            self._pending_live_force = self._pending_live_force or force
            self._live_needs_refresh = True
            return
        if not self.live_enabled and not force:
            self.live_view.render_title_only()
            self._live_needs_refresh = False
            return
        payload = payload_hint
        if payload is None:
            payload = self._collect_live_payload()
        signature = self._make_live_signature(payload)
        if not force and signature is not None and signature == self._last_live_signature:
            self._live_needs_refresh = False
            return
        self._live_refresh_running = True
        try:
            if self.current_mode_index == 3:
                self.live_view.render_group(payload if isinstance(payload, dict) else {})
            else:
                self.live_view.render_axial(payload if isinstance(payload, dict) else {})
            self._last_live_signature = signature
        except Exception:
            self.live_view.render_title_only()
        finally:
            self._live_refresh_running = False
        self._live_needs_refresh = False
        if (
            hasattr(self, "visual_tabs")
            and self.visual_tabs.currentIndex() == 0
            and (self._pending_live_payload is not None or self._pending_live_force)
            and not self._suspend_live_refresh
        ):
            self._live_refresh_timer.start(LIVE_REFRESH_DEBOUNCE_MS)

    @Slot(int)
    def _on_visual_tab_changed(self, index: int):
        if index != 0:
            return
        if self._live_needs_refresh or self._pending_live_payload is not None or self._pending_live_force:
            self._live_refresh_timer.stop()
            self._flush_live_refresh()

    def _layer_backgrounds(self, payload: dict):
        materials = payload.get("soil_materials")
        if not isinstance(materials, list):
            materials = payload.get("materials", [])
        mats = {str(m.get("name", "")): m for m in materials if isinstance(m, dict)}
        bgs = []
        for layer in payload.get("layers", []):
            if not isinstance(layer, dict):
                continue
            m = mats.get(str(layer.get("material_name", "")), {})
            bgs.append(
                {
                    "z_top": float(layer.get("z_top", 0.0)),
                    "z_bottom": float(layer.get("z_bottom", 0.0)),
                    "color": str(m.get("bg_color", "#f6e27a")),
                    "alpha": float(m.get("bg_alpha", 0.28)),
                }
            )
        return bgs

    def _populate_axial_table(self, r: dict):
        self._show_single_result_table()
        headers = [
            "Index",
            "Depth (m)",
            "Disp Z (mm, +up/-down)",
            "Axial Force (kN)",
            "Skin Friction Z (kN)",
            "Ult Skin Z (kN)",
            "Soil Stiffness (kN/m)",
        ]
        depths = r.get("depths", [])
        disps_mm = r.get("displacements", [])
        axial = r.get("axial_forces", [])
        skin = r.get("skin_frictions", [])
        ult_skin = r.get("ult_skin_frictions", [])
        n = min(len(depths), len(disps_mm), len(axial), len(skin), len(ult_skin))

        rows = []
        for i in range(n):
            disp_m = float(disps_mm[i]) / 1000.0
            k = 0.0 if abs(disp_m) < 1.0e-12 else abs(float(skin[i]) / disp_m)
            rows.append([
                i,
                float(depths[i]),
                -float(disps_mm[i]),
                float(axial[i]),
                -float(skin[i]),
                -float(ult_skin[i]),
                k,
            ])
        self._fill_table_widget(self.result_table, headers, rows)

    def _populate_lateral_table(self, r: dict):
        self._show_single_result_table()
        headers = [
            "Index",
            "Depth (m)",
            "Disp (mm)",
            "Rotation (rad)",
            "Soil Reaction (kN)",
            "Soil Reaction per m (kN/m)",
            "Soil Stiffness (kN/m^2)",
            "Ele Depth (m)",
            "Moment (kN*m)",
            "Shear (kN)",
        ]
        depths = r.get("depths", [])
        disps = r.get("displacements", [])
        rots = r.get("rotations", [])
        soil_rxn = r.get("soil_reactions", [])
        soil_rxn_per_m = r.get("soil_reactions_per_m", [])
        soil_stiffness = r.get("soil_stiffness", [])
        depths_ele = r.get("depths_ele", [])
        moments = r.get("moments", [])
        shears = r.get("shears", [])
        n = max(len(depths), len(depths_ele))

        rows = []
        for i in range(n):
            rows.append([
                i,
                float(depths[i]) if i < len(depths) else 0.0,
                float(disps[i]) if i < len(disps) else 0.0,
                float(rots[i]) if i < len(rots) else 0.0,
                float(soil_rxn[i]) if i < len(soil_rxn) else 0.0,
                float(soil_rxn_per_m[i]) if i < len(soil_rxn_per_m) else 0.0,
                float(soil_stiffness[i]) if i < len(soil_stiffness) else 0.0,
                float(depths_ele[i]) if i < len(depths_ele) else 0.0,
                float(moments[i]) if i < len(moments) else 0.0,
                float(shears[i]) if i < len(shears) else 0.0,
            ])
        self._fill_table_widget(self.result_table, headers, rows)

    def _populate_combined_table(self, r: dict):
        self._show_single_result_table()
        headers = [
            "Index",
            "Depth (m)",
            "Disp X (mm)",
            "Disp Z (mm, +up/-down)",
            "Ele Depth (m)",
            "Axial Force Z (kN, +up/-down)",
            "Shear X' (kN)",
            "Moment X'Z' (kN*m)",
        ]
        depths = r.get("depths", [])
        disp_x = r.get("displacements_x", [])
        disp_z = r.get("displacements_z", [])
        depths_ele = r.get("depths_ele", [])
        axial = r.get("axial_forces", [])
        shears = r.get("shears", [])
        moments = r.get("moments", [])
        n = max(len(depths), len(depths_ele))

        rows = []
        for i in range(n):
            rows.append([
                i,
                float(depths[i]) if i < len(depths) else 0.0,
                float(disp_x[i]) if i < len(disp_x) else 0.0,
                float(disp_z[i]) if i < len(disp_z) else 0.0,
                float(depths_ele[i]) if i < len(depths_ele) else 0.0,
                -float(axial[i]) if i < len(axial) else 0.0,
                float(shears[i]) if i < len(shears) else 0.0,
                float(moments[i]) if i < len(moments) else 0.0,
            ])
        self._fill_table_widget(self.result_table, headers, rows)

    def _populate_group_table(self, r: dict):
        overview_headers, overview_rows, pile_headers, pile_rows_list = self._group_table_data(r)
        self._create_group_result_tabs(len(pile_rows_list))
        self._fill_table_widget(self.result_table, overview_headers, overview_rows)
        for idx, pile_rows in enumerate(pile_rows_list):
            pile_table = self.group_result_tabs.widget(idx + 1)
            if isinstance(pile_table, QTableWidget):
                self._fill_table_widget(pile_table, pile_headers, pile_rows)
        self.group_result_tabs.setCurrentIndex(0)

    def _finalize_result_table(self, table: Optional[QTableWidget] = None):
        table = table or self.result_table
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(72)
        for col in range(table.columnCount()):
            if col == 0:
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
            else:
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        table.resizeColumnsToContents()
        if table.columnCount() > 0:
            header.setSectionResizeMode(table.columnCount() - 1, QHeaderView.ResizeMode.Stretch)

    @Slot()
    def _save_placeholder(self):
        if self.current_mode_index == 0:
            try:
                payload = self.axial_panel.collect_payload()
                self.case_doc["mode"] = "axial"
                self.case_doc["payloads"]["axial"] = payload
            except Exception as exc:
                QMessageBox.critical(self, self._tr("Save Failed"), self._tr(str(exc)))
                return
        elif self.current_mode_index == 1:
            try:
                payload = self.lateral_panel.collect_payload()
                self.case_doc["mode"] = "lateral"
                self.case_doc["payloads"]["lateral"] = payload
            except Exception as exc:
                QMessageBox.critical(self, self._tr("Save Failed"), self._tr(str(exc)))
                return
        elif self.current_mode_index == 2:
            try:
                payload = self.combined_panel.collect_payload()
                self.case_doc["mode"] = "combined"
                self.case_doc["payloads"]["combined"] = payload
            except Exception as exc:
                QMessageBox.critical(self, self._tr("Save Failed"), self._tr(str(exc)))
                return
        elif self.current_mode_index == 3:
            try:
                payload = self.group_panel.collect_payload()
                self.case_doc["mode"] = "group"
                self.case_doc["payloads"]["group"] = payload
            except Exception as exc:
                QMessageBox.critical(self, self._tr("Save Failed"), self._tr(str(exc)))
                return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self._tr("Save Case"),
            "pile_case.dat",
            self._tr("DAT Files (*.dat);;All Files (*)"),
        )
        if not file_path:
            return
        try:
            save_case(file_path, self.case_doc)
        except Exception as exc:
            QMessageBox.critical(self, self._tr("Save Failed"), self._tr(str(exc)))
            return
        QMessageBox.information(self, self._tr("Saved"), self._tr(f"Case saved:\n{file_path}"))

    def _export_summary_text(self):
        text = self.summary_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, self._tr("Export"), self._tr("No summary is available to export."))
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self._tr("Export Summary"),
            "pile_summary.txt",
            self._tr("Text Files (*.txt);;All Files (*)"),
        )
        if not file_path:
            return
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as exc:
            QMessageBox.critical(self, self._tr("Export Failed"), self._tr(str(exc)))
            return
        QMessageBox.information(self, self._tr("Exported"), self._tr(f"Summary exported:\n{file_path}"))

    def _table_has_exportable_data(self, table: QTableWidget) -> bool:
        return isinstance(table, QTableWidget) and table.columnCount() > 0 and table.rowCount() > 0

    def _safe_excel_sheet_name(self, name: str, used_names: set) -> str:
        invalid = set(r'[]:*?/\\')
        cleaned = "".join("_" if ch in invalid else ch for ch in str(name).strip()) or "Sheet"
        cleaned = cleaned[:31]
        candidate = cleaned
        suffix = 1
        while candidate in used_names:
            marker = f"_{suffix}"
            candidate = f"{cleaned[:31 - len(marker)]}{marker}"
            suffix += 1
        used_names.add(candidate)
        return candidate

    def _collect_table_sheets_from_tabs(self, tabs: QTabWidget, prefix: str = ""):
        sheets = []
        for idx in range(tabs.count()):
            title = tabs.tabText(idx).strip() or f"Sheet {idx + 1}"
            widget = tabs.widget(idx)
            sheet_title = f"{prefix} {title}".strip()
            if isinstance(widget, QTableWidget):
                if self._table_has_exportable_data(widget):
                    sheets.append((sheet_title, widget))
            elif isinstance(widget, QTabWidget):
                sheets.extend(self._collect_table_sheets_from_tabs(widget, sheet_title))
        return sheets

    def _collect_result_table_sheets(self):
        if isinstance(self.comparison_result_tabs, QTabWidget) and self.comparison_result_tabs.count() > 0:
            sheets = self._collect_table_sheets_from_tabs(self.comparison_result_tabs)
            if sheets:
                return sheets
        if isinstance(self.group_result_tabs, QTabWidget) and self.group_result_tabs.count() > 0:
            sheets = self._collect_table_sheets_from_tabs(self.group_result_tabs)
            if sheets:
                return sheets
        table = self._current_result_table()
        return [("Data Table", table)] if self._table_has_exportable_data(table) else []

    def _excel_cell_value(self, text: str):
        text = str(text).strip()
        if not text:
            return ""
        try:
            as_int = int(text)
            if str(as_int) == text:
                return as_int
        except ValueError:
            pass
        try:
            return float(text)
        except ValueError:
            return text

    def _write_data_table_excel(self, file_path: str, sheets):
        wb = Workbook()
        default_sheet = wb.active
        wb.remove(default_sheet)
        used_names = set()
        for raw_name, table in sheets:
            ws = wb.create_sheet(self._safe_excel_sheet_name(raw_name, used_names))
            headers = [
                table.horizontalHeaderItem(i).text() if table.horizontalHeaderItem(i) else ""
                for i in range(table.columnCount())
            ]
            ws.append(headers)
            for row_idx in range(table.rowCount()):
                ws.append([
                    self._excel_cell_value(table.item(row_idx, col_idx).text()) if table.item(row_idx, col_idx) else ""
                    for col_idx in range(table.columnCount())
                ])
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for col_cells in ws.columns:
                max_len = max((len(str(cell.value)) if cell.value is not None else 0 for cell in col_cells), default=0)
                ws.column_dimensions[col_cells[0].column_letter].width = min(max(max_len + 2, 10), 28)
        wb.save(file_path)

    def _export_data_table_excel(self):
        sheets = self._collect_result_table_sheets()
        if not sheets:
            QMessageBox.warning(self, self._tr("Export"), self._tr("No data table is available to export."))
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self._tr("Export Data Table Excel"),
            "pile_results.xlsx",
            self._tr("Excel Files (*.xlsx);;All Files (*)"),
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".xlsx"):
            file_path += ".xlsx"
        try:
            self._write_data_table_excel(file_path, sheets)
        except Exception as exc:
            QMessageBox.critical(self, self._tr("Export Failed"), self._tr(str(exc)))
            return
        QMessageBox.information(self, self._tr("Exported"), self._tr(f"Data table exported:\n{file_path}"))

    def _export_response_charts(self):
        if self.response_plot_tabs.count() == 0:
            QMessageBox.warning(self, self._tr("Export"), self._tr("No response charts are available to export."))
            return
        folder = QFileDialog.getExistingDirectory(self, self._tr("Export Response Charts"))
        if not folder:
            return
        try:
            self.plot_manager.export_all_charts(folder)
        except Exception as exc:
            QMessageBox.critical(self, self._tr("Export Failed"), self._tr(str(exc)))
            return
        QMessageBox.information(self, self._tr("Exported"), self._tr(f"Charts exported to:\n{folder}"))

    def _export_spring_parameters(self):
        mode_key = getattr(self, "_latest_result_mode_key", None)
        payload = getattr(self, "_latest_result_payload", None)
        results = getattr(self, "_latest_results", None)
        if not mode_key or not isinstance(payload, dict) or not isinstance(results, dict):
            QMessageBox.warning(self, self._tr("Export"), self._tr("No completed analysis is available to export spring parameters."))
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self._tr("Export Spring Parameters"),
            f"{mode_key}_spring_parameters.xlsx",
            self._tr("Excel Files (*.xlsx);;All Files (*)"),
        )
        if not file_path:
            return
        try:
            export_spring_parameters(mode_key, payload, results, file_path)
        except Exception as exc:
            QMessageBox.critical(self, self._tr("Export Failed"), self._tr(str(exc)))
            return
        QMessageBox.information(self, self._tr("Exported"), self._tr(f"Spring parameters exported:\n{file_path}"))

    def _show_about_clean(self):
        QMessageBox.about(
            self,
            "About PileAnalysis",
            (
                "<h3>PileAnalysis</h3>"
                "<p>Nonlinear pile foundation analysis environment.</p>"
                "<p>Supports axial, lateral, combined, and group pile analysis.</p>"
                "<p><b>Authors:</b> Wang Can, Guo Junjun</p>"
                "<p><b>Version:</b> 3.0</p>"
            ),
        )

    def _show_about_dialog(self):
        self._show_about_clean()

    def _show_about(self):
        self._show_about_clean()

    def _show_parameter_reference(self):
        show_help_manual(self)


_ZH_TRANSLATIONS = {
    "PileAnalysis - Foundation Analysis": "PileAnalysis - 非线性分析",
    "Live": "实时视图",
    "Response": "响应曲线",
    "Result Output": "结果输出",
    "Result summary will be displayed here...": "结果摘要将显示在此处...",
    "Summary": "结果摘要",
    "Data Table": "数据表",
    "Quick Start Guide": "快速开始",
    "1. Select case type (existing/new)\n2. Select analysis scope (single/group)\n3. For single pile, select axial / lateral / combined mode\n4. Fill parameters and click [Run]": "1. 选择工况类型（已有/新建）\n2. 选择分析范围（单桩/群桩）\n3. 单桩时选择轴向 / 横向 / 组合分析\n4. 填写参数并点击【运行】",
    "Save Case": "保存工况",
    "Save and Export": "保存并导出",
    "Run": "运行",
    "About": "关于",
    "Export(&E)": "导出(&E)",
    "Export Summary": "导出摘要",
    "Export Data Table Excel": "导出数据表 Excel",
    "Export Response Charts": "导出响应曲线",
    "Export Spring Parameters": "导出弹簧参数",
    "Help": "帮助",
    "Authors: Can Wang, Junjun Guo": "作者: Can Wang, Junjun Guo",
    "Contact: 24231238@bjtu.edu.cn / jjguo2@bjtu.edu.cn": "联系方式: 24231238@bjtu.edu.cn / jjguo2@bjtu.edu.cn",
    "Version: 3.0.1": "版本: 3.0.1",
    "Project Repository": "项目仓库",
    "Ready": "就绪",
    "Case Selection": "工况选择",
    "Existing Case": "已有工况",
    "New Case": "新建工况",
    "Analysis Scope Selection": "分析范围选择",
    "Single Pile Analysis": "单桩分析",
    "Group Pile Analysis": "群桩分析",
    "Back to Case Selection": "返回工况选择",
    "Import Existing Case (.dat)": "导入已有工况 (.dat)",
    "View and Edit": "查看并编辑",
    "Run Directly": "直接运行",
    "Single Pile Mode Selection": "单桩模式选择",
    "Back to Scope Selection": "返回范围选择",
    "Axial Analysis": "轴向分析",
    "Lateral Analysis": "横向分析",
    "Combined Analysis": "组合分析",
    "-> Please select an analysis scope": "-> 请选择分析范围",
    "-> Please select a case type": "-> 请选择工况类型",
    "-> Please select a single pile mode": "-> 请选择单桩分析模式",
    "-> Please import a case file first": "-> 请先导入工况文件",
    "Running...": "计算中...",
    "Run Failed": "计算失败",
    "Completed": "计算完成",
    "Saved": "已保存",
    "Export": "导出",
    "Export Failed": "导出失败",
    "Exported": "导出完成",
    "Notice": "提示",
    "Import Failed": "导入失败",
    "Invalid Mode": "模式无效",
    "No summary is available to export.": "当前没有可导出的结果摘要。",
    "No data table is available to export.": "当前没有可导出的数据表。",
    "No response charts are available to export.": "当前没有可导出的响应曲线。",
    "Please select an analysis mode first.": "请先选择分析模式。",
}

_ZH_TRANSLATIONS.update(
    {
        "Help": "帮助",
        "Help(&H)": "帮助(&H)",
        "Examples(&T)": "教程(&T)",
        "Parameter Reference": "参数参考",
        "Authors: Wang Can, Guo Junjun": "作者：汪灿，郭军军",
        "Authors: Can Wang, Junjun Guo": "作者：汪灿，郭军军",
        "Contact: 24231238@bjtu.edu.cn / jjguo2@bjtu.edu.cn": "联系方式：24231238@bjtu.edu.cn / jjguo2@bjtu.edu.cn",
        "Version: 3.0.1": "版本：3.0.1",
        "Project Repository": "更新",
        "Update": "更新",
        "Axial Tutorial": "轴向算例",
        "Lateral Tutorial": "横向算例",
        "Combined Tutorial": "组合算例",
        "Group Tutorial": "群桩算例",
        "Ready": "准备就绪",
    }
)


_ZH_TRANSLATIONS.update(
    {
        "Help": "帮助",
        "Help(&H)": "帮助(&H)",
        "Examples(&T)": "教程(&T)",
        "Parameter Reference": "参数说明",
        "Authors: Wang Can, Guo Junjun": "作者：汪灿，郭军军",
        "Authors: Can Wang, Junjun Guo": "作者：汪灿，郭军军",
        "Contact: 24231238@bjtu.edu.cn / jjguo2@bjtu.edu.cn": "联系方式：24231238@bjtu.edu.cn / jjguo2@bjtu.edu.cn",
        "Version: 3.0.1": "版本：3.0.1",
        "Project Repository": "更新",
        "Update": "更新",
        "Axial Tutorial": "轴向算例",
        "Lateral Tutorial": "横向算例",
        "Combined Tutorial": "组合算例",
        "Group Tutorial": "群桩算例",
        "Quick Start Guide": "快速开始指南",
        "1. Select case type (existing/new)\n2. Select analysis scope (single/group)\n3. For single pile, select axial / lateral / combined mode\n4. Fill parameters and click [Run]": "1. 选择工况类型（已有/新建）\n2. 选择分析范围（单桩/群桩）\n3. 单桩分析请选择轴向 / 横向 / 组合模式\n4. 填写参数后点击【开始计算】",
        "Ready": "准备就绪",
    }
)


def _zh(text: str) -> str:
    return _ZH_TRANSLATIONS.get(text, text)


def _apply_zh_overlay(widget):
    translate_widget_tree(widget, "zh")
    translate_menu_bar(widget, "zh")


_ORIGINAL_NL_INIT = MainWindow.__init__
_ORIGINAL_SHOW_PARAMETER_TABS = MainWindow._show_parameter_tabs
_ORIGINAL_CASE_SELECTED = MainWindow._on_case_type_selected
_ORIGINAL_SCOPE_SELECTED = MainWindow._on_scope_selected
_ORIGINAL_MODE_SELECTED = MainWindow._on_mode_selected


def _bilingual_nl_init(self):
    _ORIGINAL_NL_INIT(self)
    if get_language() == "zh":
        _apply_zh_overlay(self)
        self.setWindowTitle("PileAnalysis - 非线性分析")


def _bilingual_show_parameter_tabs(self):
    _ORIGINAL_SHOW_PARAMETER_TABS(self)
    if get_language() == "zh":
        _apply_zh_overlay(self)


def _bilingual_case_selected(self, case_id: int):
    _ORIGINAL_CASE_SELECTED(self, case_id)
    if get_language() == "zh":
        _apply_zh_overlay(self)


def _bilingual_scope_selected(self, scope_id: int):
    _ORIGINAL_SCOPE_SELECTED(self, scope_id)
    if get_language() == "zh":
        _apply_zh_overlay(self)


def _bilingual_mode_selected(self, index: int):
    _ORIGINAL_MODE_SELECTED(self, index)
    if get_language() == "zh":
        _apply_zh_overlay(self)


_ORIGINAL_SET_IMPORT_LOADED = MainWindow._set_import_loaded
_ORIGINAL_POPULATE_GROUP_TABLE = MainWindow._populate_group_table
_ORIGINAL_NL_SHOW_PROGRESS_DIALOG = MainWindow._show_progress_dialog
_ORIGINAL_NL_CALC_ERROR = MainWindow._on_calc_error
_ORIGINAL_NL_CALC_COMPLETE = MainWindow._on_calculation_complete
_ORIGINAL_NL_SET_IMPORT_LOADED = MainWindow._set_import_loaded
_ORIGINAL_NL_SHOW_ABOUT = MainWindow._show_about_clean


def _bilingual_set_import_loaded(self, filename: str):
    _ORIGINAL_SET_IMPORT_LOADED(self, filename)
    if get_language() == "zh":
        _apply_zh_overlay(self)


def _bilingual_populate_group_table(self, r: dict):
    _ORIGINAL_POPULATE_GROUP_TABLE(self, r)
    if get_language() == "zh":
        _apply_zh_overlay(self)


def _localized_show_progress_dialog(self, mode_label: str):
    _ORIGINAL_NL_SHOW_PROGRESS_DIALOG(self, mode_label)
    dialog = getattr(self, "_progress_dialog", None)
    if dialog is not None:
        dialog.setWindowTitle(self._tr(mode_label))
        dialog.setLabelText(self._tr("Preparing calculation..."))


def _localized_calc_error(self, msg: str):
    self._result_render_in_progress = False
    self._close_progress_dialog()
    self.calc_status_label.setText(self._tr("Run Failed"))
    self.calc_status_label.setStyleSheet(
        "QLabel { color: #e74c3c; padding: 2px 10px; border-left: 1px solid #cccccc; font-weight: bold; font-size: 9pt; }"
    )
    self.calculate_button.setEnabled(True)
    self.calculate_button.setText(self._tr("Run"))
    QMessageBox.critical(self, self._tr("Run Failed"), self._tr(msg))


def _localized_calc_complete(self, mode_name: str):
    self._close_progress_dialog()
    self.calc_status_label.setText(self._tr("Completed"))
    self.calc_status_label.setStyleSheet(
        "QLabel { color: #27ae60; padding: 2px 10px; border-left: 1px solid #cccccc; font-weight: bold; font-size: 9pt; }"
    )
    self.calculate_button.setEnabled(True)
    self.calculate_button.setText(self._tr("Run"))
    self.visual_tabs.setCurrentIndex(1)
    self.results_tabs.setCurrentIndex(0)
    self._result_render_in_progress = False
    QMessageBox.information(self, self._tr("Completed"), self._tr(f"{mode_name} calculation completed."))


def _localized_set_import_loaded(self, filename: str):
    _ORIGINAL_NL_SET_IMPORT_LOADED(self, filename)
    if filename:
        mode_name = "Unknown"
        if self.current_mode_index == 0:
            mode_name = "Axial"
        elif self.current_mode_index == 1:
            mode_name = "Lateral"
        elif self.current_mode_index == 2:
            mode_name = "Combined"
        elif self.current_mode_index == 3:
            mode_name = "Group"
        text = self._tr(f"Loaded: {filename} ({mode_name})")
        self.import_status_label.setText(text)
        self.scope_import_status_label.setText(text)
        self.scope_import_button.setText(self._tr("Change File"))
    else:
        self.scope_import_button.setText(self._tr("Import Existing Case (.dat)"))


def _localized_show_about(self):
    language = get_language()
    if language == "zh":
        QMessageBox.about(
            self,
            self._tr("About PileAnalysis"),
            (
                "<h3>PileAnalysis</h3>"
                "<p>非线性桩基础分析环境。</p>"
                "<p>支持轴向、横向、组合以及群桩分析。</p>"
                "<p><b>作者：</b>汪灿，郭军军</p>"
                "<p><b>版本：</b>3.0</p>"
            ),
        )
        return
    _ORIGINAL_NL_SHOW_ABOUT(self)


MainWindow.__init__ = _bilingual_nl_init
MainWindow._show_parameter_tabs = _bilingual_show_parameter_tabs
MainWindow._on_case_type_selected = _bilingual_case_selected
MainWindow._on_scope_selected = _bilingual_scope_selected
MainWindow._on_mode_selected = _bilingual_mode_selected
MainWindow._set_import_loaded = _bilingual_set_import_loaded
MainWindow._populate_group_table = _bilingual_populate_group_table
MainWindow._show_progress_dialog = _localized_show_progress_dialog
MainWindow._on_calc_error = _localized_calc_error
MainWindow._on_calculation_complete = _localized_calc_complete
MainWindow._set_import_loaded = _localized_set_import_loaded
MainWindow._show_about_clean = _localized_show_about


_ORIGINAL_CREATE_COMPARISON_RESULT_TABS = MainWindow._create_comparison_result_tabs
_ORIGINAL_CREATE_COMPARISON_GROUP_RESULT_TABS = MainWindow._create_comparison_group_result_tabs
_ORIGINAL_CREATE_GROUP_RESULT_TABS = MainWindow._create_group_result_tabs


def _localized_create_comparison_result_tabs(self):
    _ORIGINAL_CREATE_COMPARISON_RESULT_TABS(self)
    if self.comparison_result_tabs is not None:
        self.comparison_result_tabs.setTabPosition(QTabWidget.TabPosition.West)
        for i in range(self.comparison_result_tabs.count()):
            self.comparison_result_tabs.setTabText(i, self._tr(self.comparison_result_tabs.tabText(i)))


def _localized_create_comparison_group_result_tabs(self, pile_count: int):
    _ORIGINAL_CREATE_COMPARISON_GROUP_RESULT_TABS(self, pile_count)
    if self.comparison_result_tabs is not None:
        self.comparison_result_tabs.setTabPosition(QTabWidget.TabPosition.West)
        for i in range(self.comparison_result_tabs.count()):
            self.comparison_result_tabs.setTabText(i, self._tr(self.comparison_result_tabs.tabText(i)))
            inner_tabs = self.comparison_result_tabs.widget(i)
            if isinstance(inner_tabs, QTabWidget):
                for j in range(inner_tabs.count()):
                    inner_tabs.setTabText(j, self._tr(inner_tabs.tabText(j)))


def _localized_create_group_result_tabs(self, pile_count: int):
    _ORIGINAL_CREATE_GROUP_RESULT_TABS(self, pile_count)
    if self.group_result_tabs is not None:
        for i in range(self.group_result_tabs.count()):
            self.group_result_tabs.setTabText(i, self._tr(self.group_result_tabs.tabText(i)))


def _localized_comparison_metric_row(self, label: str, elastic_value, fiber_value):
    return [self._tr(label), elastic_value, fiber_value]


MainWindow._create_comparison_result_tabs = _localized_create_comparison_result_tabs
MainWindow._create_comparison_group_result_tabs = _localized_create_comparison_group_result_tabs
MainWindow._create_group_result_tabs = _localized_create_group_result_tabs
MainWindow._comparison_metric_row = _localized_comparison_metric_row


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("PileAnalysis")
    font = app.font()
    font.setFamily("Times New Roman")
    app.setFont(font)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
