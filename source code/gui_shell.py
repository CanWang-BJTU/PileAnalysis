"""Shared launcher and navigation helpers for the integrated PileAnalysis desktop."""

from __future__ import annotations

import importlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

def _runtime_root_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent


def _runtime_working_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return _runtime_root_dir()


ROOT_DIR = _runtime_root_dir()
LANGUAGE_DIR = ROOT_DIR / "language_settings"
for bootstrap_path in (ROOT_DIR, LANGUAGE_DIR):
    bootstrap_str = str(bootstrap_path)
    if bootstrap_path.exists() and bootstrap_str not in sys.path:
        sys.path.insert(0, bootstrap_str)

from language_manager import get_language, set_language


NONLINEAR_DIR = ROOT_DIR / "nonlinear_framework"
M_METHOD_DIR = ROOT_DIR / "mmethod_framework"
NL_MAIN_PATH = NONLINEAR_DIR / "nl_main.py"
M_MAIN_PATH = M_METHOD_DIR / "gui_modules" / "m_main.py"

LAUNCHER_ICON = NONLINEAR_DIR / "gui_modules" / "app_icon.ico"
WINDOW_CACHE: list[QMainWindow] = []


def _ensure_import_path(target_file: Path) -> None:
    for path in (
        ROOT_DIR,
        NONLINEAR_DIR,
        LANGUAGE_DIR,
        M_METHOD_DIR,
        M_METHOD_DIR / "core",
        M_METHOD_DIR / "gui_modules",
        target_file.parent,
    ):
        path_str = str(path)
        if path.exists() and path_str not in sys.path:
            sys.path.insert(0, path_str)


def _load_window_class(module_name: str, target_file: Path, import_name: str | None = None):
    if getattr(sys, "frozen", False) and import_name:
        module = importlib.import_module(import_name)
        return module.MainWindow

    if not target_file.exists():
        raise FileNotFoundError(f"Entry file not found: {target_file}")

    _ensure_import_path(target_file)
    spec = importlib.util.spec_from_file_location(module_name, target_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module spec for {target_file}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.MainWindow


def center_window(window: QMainWindow) -> None:
    screen = QApplication.primaryScreen()
    if not screen:
        return

    geometry = screen.availableGeometry()
    frame = window.frameGeometry()
    frame.moveCenter(geometry.center())
    window.move(frame.topLeft())


def open_program(
    target: str,
    current_window: QMainWindow | None = None,
    language: str | None = None,
) -> QMainWindow:
    if language is not None:
        set_language(language)

    target_map = {
        "nonlinear": ("integrated_nl_main", NL_MAIN_PATH, "nonlinear_framework.nl_main"),
        "m-method": (
            "integrated_m_main",
            M_MAIN_PATH,
            "mmethod_framework.gui_modules.m_main",
        ),
    }
    if target not in target_map:
        raise ValueError(f"Unknown target: {target}")

    _module_name, target_file, _import_name = target_map[target]
    env = os.environ.copy()
    if getattr(sys, "frozen", False):
        # In frozen mode, forcing parent _MEIPASS paths into PYTHONPATH can
        # break binary extension imports (for example NumPy C-extensions) in
        # spawned child processes.
        env.pop("PYTHONPATH", None)
        # Force a fresh onefile runtime context in the child process. This
        # avoids sharing parent extraction state that can lead to missing
        # binary modules in heavy packages like NumPy.
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        env.pop("_MEIPASS2", None)
        subprocess.Popen([sys.executable, "--target", target], cwd=str(_runtime_working_dir()), env=env)
    else:
        path_entries = [
            str(ROOT_DIR),
            str(NONLINEAR_DIR),
            str(LANGUAGE_DIR),
            str(M_METHOD_DIR),
            str(M_METHOD_DIR / "core"),
            str(M_METHOD_DIR / "gui_modules"),
            str(target_file.parent),
        ]
        existing_pythonpath = env.get("PYTHONPATH", "")
        if existing_pythonpath:
            path_entries.append(existing_pythonpath)
        env["PYTHONPATH"] = os.pathsep.join(path_entries)
        subprocess.Popen([sys.executable, str(target_file)], cwd=str(target_file.parent), env=env)

    if current_window is not None:
        current_window.close()

    return current_window if current_window is not None else open_launcher()


def attach_navigation_menu(
    window: QMainWindow,
    current_target: str,
    launcher_callback: Callable[[], None] | None = None,
) -> None:
    current_language = get_language()
    menubar = window.menuBar()
    navigate_menu = menubar.addMenu("启动台" if current_language == "zh" else "Navigate")

    open_launcher_action = QAction("打开启动台" if current_language == "zh" else "Open Launcher", window)
    open_launcher_action.triggered.connect(
        launcher_callback if launcher_callback is not None else lambda: open_launcher()
    )
    navigate_menu.addAction(open_launcher_action)

    if current_language == "zh":
        switch_label = "打开 M 法程序" if current_target == "nonlinear" else "打开非线性法程序"
    else:
        switch_label = "Open M-Method Program" if current_target == "nonlinear" else "Open Nonlinear Program"
    switch_target = "m-method" if current_target == "nonlinear" else "nonlinear"
    switch_action = QAction(switch_label, window)
    switch_action.triggered.connect(lambda: open_program(switch_target, current_window=window))
    navigate_menu.addAction(switch_action)

    language_menu = menubar.addMenu("语言" if current_language == "zh" else "Language")
    english_action = QAction("English", window)
    english_action.triggered.connect(lambda: open_program(current_target, current_window=window, language="en"))
    language_menu.addAction(english_action)

    chinese_action = QAction("中文", window)
    chinese_action.triggered.connect(lambda: open_program(current_target, current_window=window, language="zh"))
    language_menu.addAction(chinese_action)


class LauncherWindow(QMainWindow):
    """Entry window that requires language selection before opening either GUI."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PileAnalysis Launcher")
        self.setMinimumSize(620, 500)
        self.resize(760, 560)
        self.selected_language: str | None = None

        if LAUNCHER_ICON.exists():
            self.setWindowIcon(QIcon(str(LAUNCHER_ICON)))

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(56, 42, 56, 42)
        layout.setSpacing(18)
        layout.addStretch()

        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(24, 24, 24, 24)
        header_layout.setSpacing(10)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if LAUNCHER_ICON.exists():
            icon_label.setPixmap(QIcon(str(LAUNCHER_ICON)).pixmap(160, 160))
        else:
            icon_label.setText("PileAnalysis")
        header_layout.addWidget(icon_label)

        title_label = QLabel("PileAnalysis")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 22px; font-weight: 700; color: #1f2937;")
        header_layout.addWidget(title_label)

        subtitle_label = QLabel("Step 1: Select language. Step 2: Choose the analysis method.")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("font-size: 13px; color: #6b7280;")
        self.subtitle_label = subtitle_label
        header_layout.addWidget(subtitle_label)
        layout.addWidget(header_widget)

        lang_row = QHBoxLayout()
        lang_row.setSpacing(16)

        self.en_button = QPushButton("English")
        self.en_button.setMinimumHeight(48)
        self.en_button.clicked.connect(lambda: self._select_language("en"))
        lang_row.addWidget(self.en_button)

        self.zh_button = QPushButton("中文")
        self.zh_button.setMinimumHeight(48)
        self.zh_button.clicked.connect(lambda: self._select_language("zh"))
        lang_row.addWidget(self.zh_button)
        layout.addLayout(lang_row)

        self.language_status_label = QLabel("No language selected")
        self.language_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.language_status_label.setStyleSheet("font-size: 13px; color: #6b7280;")
        layout.addWidget(self.language_status_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(16)

        self.m_button = QPushButton("Open M-Method")
        self.m_button.setMinimumHeight(54)
        self.m_button.setEnabled(False)
        self.m_button.clicked.connect(lambda: open_program("m-method", current_window=self, language=self.selected_language))
        button_row.addWidget(self.m_button)

        self.nl_button = QPushButton("Open Nonlinear")
        self.nl_button.setMinimumHeight(54)
        self.nl_button.setEnabled(False)
        self.nl_button.clicked.connect(lambda: open_program("nonlinear", current_window=self, language=self.selected_language))
        button_row.addWidget(self.nl_button)
        layout.addLayout(button_row)

        layout.addStretch()
        self.setCentralWidget(container)
        self.setStyleSheet(
            """
            QMainWindow {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #f8fafc, stop: 1 #e2e8f0
                );
            }
            QPushButton {
                background-color: #111827;
                color: white;
                border: none;
                border-radius: 14px;
                font-size: 14px;
                font-weight: 600;
                padding: 12px 18px;
            }
            QPushButton:hover {
                background-color: #1f2937;
            }
            QPushButton:pressed {
                background-color: #0f172a;
            }
            QPushButton:disabled {
                background-color: #9ca3af;
                color: #f3f4f6;
            }
            """
        )

    def _select_language(self, language: str) -> None:
        self.selected_language = set_language(language)
        self.m_button.setEnabled(True)
        self.nl_button.setEnabled(True)

        if self.selected_language == "zh":
            self.subtitle_label.setText("第 1 步：选择语言。第 2 步：选择分析方法。")
            self.language_status_label.setText("已选择语言：中文")
            self.m_button.setText("打开 M 法")
            self.nl_button.setText("打开非线性法")
            self.zh_button.setStyleSheet("background-color: #0f766e; color: white;")
            self.en_button.setStyleSheet("")
        else:
            self.subtitle_label.setText("Step 1: Select language. Step 2: Choose the analysis method.")
            self.language_status_label.setText("Selected language: English")
            self.m_button.setText("Open M-Method")
            self.nl_button.setText("Open Nonlinear")
            self.en_button.setStyleSheet("background-color: #0f766e; color: white;")
            self.zh_button.setStyleSheet("")


def open_launcher() -> QMainWindow:
    launcher = LauncherWindow()
    center_window(launcher)
    launcher.show()
    launcher.raise_()
    launcher.activateWindow()
    WINDOW_CACHE.append(launcher)
    return launcher


def run_launcher() -> int:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        app.setApplicationName("PileAnalysis Launcher")
        if LAUNCHER_ICON.exists():
            app.setWindowIcon(QIcon(str(LAUNCHER_ICON)))

    if not get_language():
        set_language("en")
    open_launcher()

    if owns_app:
        return app.exec()
    return 0


def run_target(target: str) -> int:
    target_map = {
        "nonlinear": ("integrated_nl_main", NL_MAIN_PATH, "nonlinear_framework.nl_main", "PileAnalysis"),
        "m-method": (
            "integrated_m_main",
            M_MAIN_PATH,
            "mmethod_framework.gui_modules.m_main",
            "PileAnalysis",
        ),
    }
    if target not in target_map:
        raise ValueError(f"Unknown target: {target}")

    module_name, target_file, import_name, app_name = target_map[target]
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
    app.setApplicationName(app_name)
    if LAUNCHER_ICON.exists():
        app.setWindowIcon(QIcon(str(LAUNCHER_ICON)))

    window_class = _load_window_class(module_name, target_file, import_name=import_name)
    window = window_class()
    if isinstance(window, QMainWindow):
        center_window(window)
    window.show()
    window.raise_()
    window.activateWindow()
    WINDOW_CACHE.append(window)

    if owns_app:
        return app.exec()
    return 0


def show_launch_error(parent: QWidget | None, exc: Exception) -> None:
    QMessageBox.critical(parent, "Launch Error", f"Unable to open the requested application.\n\n{exc}")

