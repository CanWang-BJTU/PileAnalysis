                                                                         
                                                      
                            
                                     
                                                                         

import sys
import os
import math
import copy
import logging
from pathlib import Path
import tempfile
from typing import Dict, List, Optional, Any
import numpy as np
import traceback

CURRENT_FILE = Path(__file__).resolve() if '__file__' in globals() else Path.cwd() / "m-main.py"
GUI_MODULES_DIR = CURRENT_FILE.parent
FRAMEWORK_DIR = GUI_MODULES_DIR.parent
PROJECT_ROOT_DIR = FRAMEWORK_DIR.parent
CORE_DIR = FRAMEWORK_DIR / "core"
CASE_SAMPLES_DIR = FRAMEWORK_DIR / "case_samples"

RESOURCE_ALIASES = {
    "模式一算例.dat": "mode_1_example.dat",
    "模式二算例.dat": "mode_2_example.dat",
    "模式三算例.dat": "mode_3_example.dat",
    "pile说明书算例1_12桩双工况.dat": "pile_manual_example_01_12_pile_dual_case.dat",
    "pile说明书算例2_4桩带模拟桩.dat": "pile_manual_example_02_4_piles_with_simulated_pile.dat",
    "pile说明书算例3_16桩斜桩差异化.dat": "pile_manual_example_03_16_inclined_piles.dat",
    "pile说明书算例4_3桩非中心模拟桩.dat": "pile_manual_example_04_3_pile_eccentric_simulated.dat",
    "pile说明书算例一.png": "pile_manual_example_01.png",
    "pile说明书算例二.png": "pile_manual_example_02.png",
    "pile说明书算例三.png": "pile_manual_example_03.png",
    "pile说明书算例四.png": "pile_manual_example_04.png",
}

for search_dir in (str(PROJECT_ROOT_DIR), str(GUI_MODULES_DIR), str(CORE_DIR)):
    if search_dir not in sys.path:
        sys.path.insert(0, search_dir)

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QFormLayout, QLineEdit, QDoubleSpinBox, QCheckBox, QComboBox,
    QMessageBox, QFileDialog, QGroupBox, QSplitter, QScrollArea, QFrame,
    QSizePolicy, QGridLayout, QToolBar, QMenu, QSpinBox, QRadioButton,
    QButtonGroup, QProgressBar, QDialog, QToolButton, QStyledItemDelegate,
    QTextEdit, QProgressDialog, QStackedWidget, QStatusBar, QInputDialog,
    QDialogButtonBox, QTextBrowser
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread, QSize, QEvent, QDateTime
from PySide6.QtGui import (
    QPixmap, QAction, QIcon, QFont, QColor, QPalette, QBrush, 
    QPainter, QPen, QImage, QKeySequence
)
from gui_shell import attach_navigation_menu
from language_manager import get_language
from ui_localization import translate_menu_bar, translate_widget_tree

               
try:
    import matplotlib
    matplotlib.use('Qt5Agg')
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB_QT = True
except ImportError:
    HAS_MATPLOTLIB_QT = False
    FigureCanvas = None
    NavigationToolbar = None
    Figure = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _candidate_base_dirs(extra_dirs: Optional[List[Path]] = None) -> List[Path]:
    dirs: List[Path] = []
    if extra_dirs:
        dirs.extend(extra_dirs)

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        dirs.append(Path(meipass))

    dirs.extend([
        Path.cwd(),
        GUI_MODULES_DIR,
        CORE_DIR,
        CASE_SAMPLES_DIR,
        FRAMEWORK_DIR,
        PROJECT_ROOT_DIR,
    ])

    unique_dirs: List[Path] = []
    seen = set()
    for directory in dirs:
        try:
            resolved = directory.resolve()
        except OSError:
            resolved = directory
        key = str(resolved)
        if key not in seen:
            seen.add(key)
            unique_dirs.append(directory)
    return unique_dirs


def _find_existing_resource(filename: str, extra_dirs: Optional[List[Path]] = None) -> Optional[Path]:
    candidates: List[Path] = []
    name_candidates = [filename]
    alias = RESOURCE_ALIASES.get(filename)
    if alias and alias not in name_candidates:
        name_candidates.append(alias)

    for candidate_name in name_candidates:
        target = Path(candidate_name)
        if target.is_absolute():
            candidates.append(target)
        else:
            for base_dir in _candidate_base_dirs(extra_dirs):
                candidates.append(base_dir / candidate_name)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _find_bcad_pile_executable() -> Optional[Path]:
    return _find_existing_resource("BCAD-PILE.exe", extra_dirs=[CORE_DIR])


def _iter_schematic_candidates(language: str) -> List[tuple]:
    names: List[str] = []
    if language == "en":
        names.extend([
            "pile_foundation_schematic_en.ai",
            "pile_foundation_schematic_en.png",
            "pile_foundation_schematic_en.pdf",
        ])
    names.extend([
        "pile_foundation_schematic.ai",
        "pile_foundation_schematic.png",
        "pile_foundation_schematic.pdf",
        "schematic.png",
    ])

    candidates = []
    for name in names:
        path = _find_existing_resource(name, extra_dirs=[GUI_MODULES_DIR])
        if path:
            candidates.append((path, path.suffix.lower().lstrip(".")))
    return candidates


def _get_plot_title_kwargs(language: str) -> dict:
    if language == "en":
        return {"fontfamily": "Times New Roman"}

    try:
        from matplotlib.font_manager import FontProperties

        return {
            "fontproperties": FontProperties(
                family=[
                    "Microsoft YaHei",
                    "SimHei",
                    "SimSun",
                    "Noto Sans CJK SC",
                    "Arial Unicode MS",
                ]
            )
        }
    except Exception:
        return {
            "fontfamily": "Microsoft YaHei"
        }

try:
    from dat_generator import (
        DATGenerator, CalculationMode, PileTypeParams,
        PilePosition, LoadCase, FreeSegment, EmbeddedSegment,
        PileShape, PileSupportType
    )
    HAS_DAT_GENERATOR = True
except ImportError as e:
    logger.error(f"无法导入 dat_generator: {e}")
    HAS_DAT_GENERATOR = False
    DATGenerator = None
    CalculationMode = None

try:
    from pile_engine import (
        PileEngine, AsyncPileEngine, CalculationResult, EngineStatus
    )
    HAS_ENGINE = True
except ImportError as e:
    logger.error(f"无法导入 pile_engine: {e}")
    HAS_ENGINE = False
    PileEngine = None
    AsyncPileEngine = None
    CalculationResult = None

try:
    from result_parser import ResultParser, OutputMode
    HAS_PARSER = True
except ImportError as e:
    logger.error(f"无法导入 result_parser: {e}")
    HAS_PARSER = False
    ResultParser = None

try:
    from plot_module import PilePlotter, bytesio_to_qpixmap
    HAS_PLOTTER = True
except ImportError as e:
    logger.error(f"无法导入 plot_module: {e}")
    HAS_PLOTTER = False
    PilePlotter = None
    bytesio_to_qpixmap = None


                                                                         
         
                                                                         
class ScalableImageLabel(QLabel):

    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._original_pixmap = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(100, 100)        
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #f5f5f5;")
    
    def setOriginalPixmap(self, pixmap: QPixmap):

        self._original_pixmap = pixmap
        self._updateScaledPixmap()
    
    def originalPixmap(self) -> QPixmap:

        return self._original_pixmap
    
    def _updateScaledPixmap(self):

        if self._original_pixmap is None or self._original_pixmap.isNull():
            return
        
                            
        available_width = self.width() - 10            
        available_height = self.height() - 10            
        
        if available_width <= 0 or available_height <= 0:
            return
        
                      
        pixmap_width = self._original_pixmap.width()
        pixmap_height = self._original_pixmap.height()
        
        if pixmap_width <= 0 or pixmap_height <= 0:
            return
        
                           
        scale_w = available_width / pixmap_width
        scale_h = available_height / pixmap_height
        scale = min(scale_w, scale_h)              
        
                  
        scaled_width = int(pixmap_width * scale)
        scaled_height = int(pixmap_height * scale)
        
                    
        scaled_width = max(1, scaled_width)
        scaled_height = max(1, scaled_height)
        
                   
        scaled_pixmap = self._original_pixmap.scaled(
            scaled_width,
            scaled_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        super().setPixmap(scaled_pixmap)
    
    def resizeEvent(self, event):

        super().resizeEvent(event)
        self._updateScaledPixmap()
    
    def showEvent(self, event):

        super().showEvent(event)
                     
        QTimer.singleShot(10, self._updateScaledPixmap)


                                                                         
        
                                                                         
class PileCoordinateDelegate(QStyledItemDelegate):

    

    enterPressed = Signal(int, int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._table = parent
    
    def createEditor(self, parent, option, index):


        if index.column() in (1, 2):
            editor = QLineEdit(parent)
            editor.setStyleSheet("""
                QLineEdit {
                    border: 1px solid #555555;
                    border-radius: 2px;
                    padding: 2px 5px;
                    background-color: white;
                    color: #000000;
                    selection-background-color: #e0e0e0;
                    selection-color: #000000;
                }
            """)
            editor.setAlignment(Qt.AlignmentFlag.AlignCenter)

            editor.setProperty("col", index.column())
            editor.installEventFilter(self)
            return editor
        return super().createEditor(parent, option, index)
    
    def eventFilter(self, obj, event):

        if isinstance(obj, QLineEdit) and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                row = obj.property("row")
                col = obj.property("col")

                self.commitData.emit(obj)
                self.closeEditor.emit(obj, QStyledItemDelegate.EndEditHint.NoHint)

                if self._table:
                    self._navigate_next(row, col)
                return True
        return super().eventFilter(obj, event)
    
    def _navigate_next(self, row, col):

        if not self._table:
            return
        

        if col == 1:
            QTimer.singleShot(0, lambda: self._edit_cell(row, 2))

        elif col == 2:
            next_row = row + 1
            if next_row < self._table.rowCount():
                QTimer.singleShot(0, lambda: self._edit_cell(next_row, 1))
            else:

                main_window = self._table.window()
                if hasattr(main_window, '_add_pile_row'):
                    main_window._add_pile_row()
                    QTimer.singleShot(0, lambda: self._edit_cell(next_row, 1))
    
    def _edit_cell(self, row, col):

        if self._table and row < self._table.rowCount():
            self._table.setCurrentCell(row, col)
            item = self._table.item(row, col)
            if item:
                self._table.editItem(item)
    
    def setEditorData(self, editor, index):

        if isinstance(editor, QLineEdit):
            value = index.model().data(index, Qt.ItemDataRole.EditRole)
            editor.setText(str(value) if value else "")
            editor.selectAll()
        else:
            super().setEditorData(editor, index)
    
    def setModelData(self, editor, model, index):

        if isinstance(editor, QLineEdit):
            model.setData(index, editor.text(), Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)

class SimuPileDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setStyleSheet("""
            QLineEdit {
                border: 1px solid #555555;
                border-radius: 2px;
                padding: 2px 5px;
                background-color: white;
                color: #000000;
                selection-background-color: #e0e0e0;
                selection-color: #000000;
            }
        """)
        editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
                                    
        editor.setProperty("row", index.row())
        editor.setProperty("col", index.column())
        editor.installEventFilter(self)
        return editor

    def eventFilter(self, obj, event):

        if isinstance(obj, QLineEdit) and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):

                self.commitData.emit(obj)
                self.closeEditor.emit(obj, QStyledItemDelegate.EndEditHint.NoHint)
                

                row = obj.property("row")
                col = obj.property("col")
                if self.parent():
                   self._navigate_next(self.parent(), row, col)
                return True
        return super().eventFilter(obj, event)

    def _navigate_next(self, table, row, col):
        row_count = table.rowCount()
        if row_count == 0:
            return
            
                                     
                           
        is_matrix_mode = False
        if row_count >= 3:
            item = table.item(2, 0)
            if item and "全量刚度矩阵" in item.text():
                is_matrix_mode = True
        
        if is_matrix_mode:
            self._navigate_matrix_mode(table, row, col)
        else:
            self._navigate_diagonal_mode(table, row, col)
    
    def _navigate_diagonal_mode(self, table, row, col):
        rows_per_group = 4
        group_idx = row // rows_per_group
        row_in_group = row % rows_per_group
        
        next_row = row
        next_col = col
        
        if row_in_group == 1:        
            if col == 2:          
                next_col = 4
            elif col == 4:              
                next_row = group_idx * rows_per_group + 3
                next_col = 0
                
        elif row_in_group == 3:        
            if col < 5:
                next_col = col + 1
            else:                  
                next_row = (group_idx + 1) * rows_per_group + 1
                next_col = 2
                if next_row >= table.rowCount():
                    return        
        
              
        if next_row < table.rowCount():
            QTimer.singleShot(0, lambda: self._edit_cell(table, next_row, next_col))
    
    def _navigate_matrix_mode(self, table, row, col):
        rows_per_group = 9
        group_idx = row // rows_per_group
        row_in_group = row % rows_per_group
        base_row = group_idx * rows_per_group
        
        next_row = row
        next_col = col
        
        if row_in_group == 1:        
            if col == 2:          
                next_col = 4
            elif col == 4:                 
                next_row = base_row + 3
                next_col = 0
                
        elif 3 <= row_in_group <= 8:              
            matrix_row_idx = row_in_group - 3       
            
            if col < 5:
                       
                next_col = col + 1
            else:
                               
                if matrix_row_idx < 5:         
                    next_row = row + 1
                    next_col = 0
                else:                        
                    next_row = (group_idx + 1) * rows_per_group + 1
                    next_col = 2
                    if next_row >= table.rowCount():
                        return        
        
              
        if next_row < table.rowCount():
            QTimer.singleShot(0, lambda: self._edit_cell(table, next_row, next_col))

    def _edit_cell(self, table, row, col):
        if row < table.rowCount():
            table.setCurrentCell(row, col)
            item = table.item(row, col)
            if item and (item.flags() & Qt.ItemFlag.ItemIsEditable):
                table.editItem(item)

    def setEditorData(self, editor, index):
        if isinstance(editor, QLineEdit):
            value = index.model().data(index, Qt.ItemDataRole.EditRole)
            editor.setText(str(value) if value else "")
            editor.selectAll()
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        if isinstance(editor, QLineEdit):
            model.setData(index, editor.text(), Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)


class MultiCaseTableDelegate(QStyledItemDelegate):
    
    def __init__(self, parent=None, add_case_callback=None):
        super().__init__(parent)
        self._add_case_callback = add_case_callback              
    
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setStyleSheet("""
            QLineEdit {
                border: 1px solid #555555;
                border-radius: 2px;
                padding: 2px 5px;
                background-color: white;
                color: #000000;
                selection-background-color: #e0e0e0;
                selection-color: #000000;
            }
        """)
        editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        editor.setProperty("row", index.row())
        editor.setProperty("col", index.column())
        editor.installEventFilter(self)
        return editor

    def eventFilter(self, obj, event):

        if isinstance(obj, QLineEdit) and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.commitData.emit(obj)
                self.closeEditor.emit(obj, QStyledItemDelegate.EndEditHint.NoHint)
                
                row = obj.property("row")
                col = obj.property("col")
                if self.parent():
                   self._navigate_next(self.parent(), row, col)
                return True
        return super().eventFilter(obj, event)

    def _navigate_next(self, table, row, col):
        next_row = row
        next_col = col
        
                                                  
        if (row % 4) == 1:
            if col == 2:          
                next_col = 4
            elif col == 4:           
                next_row = row + 2
                next_col = 0
                
                                                       
        elif (row % 4) == 3:
            if col < 5:
                next_col = col + 1
            else:
                              
                next_row = row + 2
                next_col = 2
                                
                if next_row >= table.rowCount():
                    if self._add_case_callback:
                        self._add_case_callback()
                    else:
                        return

        if next_row < table.rowCount():
            QTimer.singleShot(0, lambda: self._edit_cell(table, next_row, next_col))

    def _edit_cell(self, table, row, col):
        if row < table.rowCount():
            table.setCurrentCell(row, col)
            item = table.item(row, col)
            if item:
                table.editItem(item)

    def setEditorData(self, editor, index):
        if isinstance(editor, QLineEdit):
            value = index.model().data(index, Qt.ItemDataRole.EditRole)
            editor.setText(str(value) if value else "")
            editor.selectAll()
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        if isinstance(editor, QLineEdit):
            model.setData(index, editor.text(), Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)


                                                                         
        
                                                                         
class SegmentTableDelegate(QStyledItemDelegate):

    
    def __init__(self, parent=None, col_count=3, add_row_callback=None):
        super().__init__(parent)
        self._table = parent
        self._col_count = col_count        
        self._add_row_callback = add_row_callback             
    
    def createEditor(self, parent, option, index):

        editor = QLineEdit(parent)
        editor.setStyleSheet("""
            QLineEdit {
                border: 1px solid #555555;
                border-radius: 2px;
                padding: 2px 5px;
                background-color: white;
                color: #000000;
                selection-background-color: #e0e0e0;
                selection-color: #000000;
            }
        """)
        editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        editor.setProperty("row", index.row())
        editor.setProperty("col", index.column())
        editor.installEventFilter(self)
        return editor
    
    def eventFilter(self, obj, event):

        if isinstance(obj, QLineEdit) and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                row = obj.property("row")
                col = obj.property("col")
                         
                self.commitData.emit(obj)
                self.closeEditor.emit(obj, QStyledItemDelegate.EndEditHint.NoHint)
                           
                if self._table:
                    self._navigate_next(row, col)
                return True
        return super().eventFilter(obj, event)
    
    def _navigate_next(self, row, col):

        if not self._table:
            return
        
        next_col = col + 1
        next_row = row
        
                              
        if next_col >= self._col_count:
            next_col = 0
            next_row = row + 1
        
                      
        if next_row >= self._table.rowCount():
            if self._add_row_callback:
                self._add_row_callback()
        
                    
        QTimer.singleShot(0, lambda: self._edit_cell(next_row, next_col))
    
    def _edit_cell(self, row, col):

        if self._table and row < self._table.rowCount():
            self._table.setCurrentCell(row, col)
            item = self._table.item(row, col)
            if item:
                self._table.editItem(item)
    
    def setEditorData(self, editor, index):

        if isinstance(editor, QLineEdit):
            value = index.model().data(index, Qt.ItemDataRole.EditRole)
            editor.setText(str(value) if value else "")
            editor.selectAll()
        else:
            super().setEditorData(editor, index)
    
    def setModelData(self, editor, model, index):

        if isinstance(editor, QLineEdit):
            model.setData(index, editor.text(), Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)


                                                                         
        
                                                                         
class PileTypeEditor(QWidget):


    dataChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
                           
        self._original_differential = False
        self._differential_params = None
        self._build_ui()

    def _setup_spinbox_enter_navigation(self, spinbox):
        spinbox.installEventFilter(self)
                                
        spinbox.setStyleSheet("""
            QDoubleSpinBox {
                padding: 5px;
                border: 1px solid #cccccc;
                border-radius: 3px;
                color: #000000;
            }
            QDoubleSpinBox:focus {
                border: 1px solid #555555;
                background-color: white;
            }
        """)
    
    def eventFilter(self, obj, event):
        if event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                               
                self.focusNextChild()
                return True
        return super().eventFilter(obj, event)

    def _create_help_button(self, help_text):
        help_btn = QToolButton()
        help_btn.setText("?")
        help_btn.setFixedSize(16, 16)
        help_btn.setStyleSheet("""
            QToolButton {
                background-color: #2196F3;
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 9px;
                padding: 0px;
            }
            QToolButton:hover {
                background-color: #1976D2;
            }
        """)
        help_btn.setToolTip("点击查看参数说明")
        help_btn.clicked.connect(lambda: QMessageBox.information(self, "参数说明", help_text))
        return help_btn

    def _add_row_with_help(self, form_layout, label_text, widget, help_text):
        row_layout = QHBoxLayout()
        row_layout.addWidget(widget)
        row_layout.addWidget(self._create_help_button(help_text))
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_widget = QWidget()
        row_widget.setLayout(row_layout)
        form_layout.addRow(label_text, row_widget)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)

        basic_group = QGroupBox("基本参数")
        basic_form = QFormLayout(basic_group)

        self.ksh_combo = QComboBox()
        self.ksh_combo.addItems(["圆形截面 (0)", "方形截面 (1)"])
        self.ksh_combo.setToolTip(
            "【KSH】桩截面形状\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "0 = 圆形/管桩 (Circular/Pipe Pile)\n"
            "1 = 方形/矩形桩 (Square/Rectangular)\n\n"
        )
        basic_form.addRow("截面形状 (KSH):", self.ksh_combo)

        self.ksu_combo = QComboBox()
        self.ksu_combo.addItems([
            "1 - 钻孔灌注摩擦桩",
            "2 - 打入或振动下沉摩擦桩",
            "3 - 柱承桩(桩底非嵌固)",
            "4 - 柱承桩(桩底嵌固)"
        ])
        self.ksu_combo.setToolTip(
            "【KSU】桩基类型代码\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "1 = 钻孔灌注摩擦桩\n"
            "   依靠侧摩阻力为主，钻孔施工\n"
            "   → 输入 m₀ (桩底土比例系数)\n\n"
            "2 = 打入或振动下沉摩擦桩\n"
            "   依靠侧摩阻力为主，打入施工\n"
            "   → 输入 m₀ (桩底土比例系数)\n\n"
            "3 = 柱承桩(桩底非嵌固)\n"
            "   端承桩，桩底视为铰接/简支\n"
            "   → 输入 c₀ (岩石地基系数)\n\n"
            "4 = 柱承桩(桩底嵌固)\n"
            "   端承桩，桩底视为固定/固结\n"
            "   → 输入 c₀ (岩石地基系数)\n\n"
        )
        basic_form.addRow("桩端约束 (KSU):", self.ksu_combo)

        angle_widget = QWidget()
        angle_layout = QHBoxLayout(angle_widget)
        angle_layout.setContentsMargins(0, 0, 0, 0)

        self.angle_alpha = QDoubleSpinBox()
        self.angle_alpha.setRange(-1.0, 1.0)
        self.angle_alpha.setDecimals(6)
        self.angle_alpha.setSingleStep(0.1)
        self.angle_alpha.setValue(0.0)

        self.angle_beta = QDoubleSpinBox()
        self.angle_beta.setRange(-1.0, 1.0)
        self.angle_beta.setDecimals(6)
        self.angle_beta.setSingleStep(0.1)
        self.angle_beta.setValue(0.0)

        self.angle_gamma = QDoubleSpinBox()
        self.angle_gamma.setRange(-1.0, 1.0)
        self.angle_gamma.setDecimals(6)
        self.angle_gamma.setSingleStep(0.1)
        self.angle_gamma.setValue(1.0)

        angle_layout.addWidget(QLabel("αx:"))
        angle_layout.addWidget(self.angle_alpha)
        angle_layout.addWidget(QLabel("αy:"))
        angle_layout.addWidget(self.angle_beta)
        angle_layout.addWidget(QLabel("αz:"))
        angle_layout.addWidget(self.angle_gamma)

        btn_normalize = QPushButton("归一化")
        btn_normalize.setMaximumWidth(60)
        btn_normalize.clicked.connect(self._normalize_direction)
        btn_normalize.setToolTip("使方向余弦满足 α²+β²+γ²=1")
        angle_layout.addWidget(btn_normalize)
        angle_widget.setToolTip(
            "【AGL】方向余弦 (Direction Cosines)\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "定义桩轴线Z'在整体坐标系的方向\n\n"
            "αx, αy, αz = cos(∠X), cos(∠Y), cos(∠Z)\n"
            "必须满足: α²ₓ + α²ᵧ + α²ᵤ = 1\n\n"
            "常用配置:\n"
            "• 垂直桩: (0, 0, 1)\n"
            "• 斜桩15°(向X): (0.259, 0, 0.966)\n"
            "• 斜桩30°(向X): (0.5, 0, 0.866)"
        )

        basic_form.addRow("方向余弦 (AGL):", angle_widget)
        content_layout.addWidget(basic_group)

        material_group = QGroupBox("桩身材料参数")
        material_form = QFormLayout(material_group)

        self.peh_input = QDoubleSpinBox()
        self.peh_input.setRange(0, 1e12)
        self.peh_input.setDecimals(0)
        self.peh_input.setSingleStep(1e6)
        self.peh_input.setValue(0.0)
        self._setup_spinbox_enter_navigation(self.peh_input)
                           
        peh_help_text = (
            "【PEH】混凝土弹性模量\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "标准值参考 (GB 50010):\n"
            "• C20: 2.55 × 10⁷ kN/m²\n"
            "• C25: 2.80 × 10⁷ kN/m²\n"
            "• C30: 3.00 × 10⁷ kN/m²\n"
            "• C35: 3.15 × 10⁷ kN/m²\n"
            "• C40: 3.25 × 10⁷ kN/m²"
        )
        self.peh_input.setToolTip(peh_help_text)
        self._add_row_with_help(material_form, "弹性模量 E (KN/m²):", self.peh_input, peh_help_text)

        self.pke_input = QDoubleSpinBox()
        self.pke_input.setRange(0.0, 2.0)
        self.pke_input.setDecimals(4)
        self.pke_input.setSingleStep(0.05)
        self.pke_input.setValue(1.0)
        self._setup_spinbox_enter_navigation(self.pke_input)
        pke_help_text = (
            "【PKE】刚度折减系数\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "用于修正桩身惯性矩 I:\n"
            "I_effective = I_gross × PKE\n\n"
            "推荐取值:\n"
            "• 圆形桩: 1.0 (不折减)\n"
            "• 方形桩: 1.0-1.2\n"
            "• 开裂/损伤: 0.5-0.8\n"
            "• 考虑裂缝: 0.7-0.9"
        )
        self.pke_input.setToolTip(pke_help_text)
        self._add_row_with_help(material_form, "惯性矩修正系数:", self.pke_input, pke_help_text)

        content_layout.addWidget(material_group)

        above_group = QGroupBox("地上部分（自由段） - 可选    方向从上往下")
        above_layout = QVBoxLayout(above_group)

        self.above_table = QTableWidget(0, 3)
        self.above_table.setHorizontalHeaderLabels([
            "段长 H (m)", "直径/边长 D (m)", "分段数 N"
        ])
                   
        above_header = self.above_table.horizontalHeader()
        above_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        above_header_item1 = QTableWidgetItem()
        above_header_item1.setToolTip("【HFR】自由段高度\n冲刷线以上部分\n典型值: 1.0-10.0 m")
        above_header_item2 = QTableWidgetItem()
        above_header_item2.setToolTip("【DOF】桩身直径或边长\n圆桩为直径，方桩为边长\n典型值: 0.5-2.0 m")
        above_header_item3 = QTableWidgetItem()
        above_header_item3.setToolTip("【NSF】当前段输出点数\n用于内力位移输出\n通常取: 2")
        
                              
        self.above_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #cccccc;
                background-color: white;
                alternate-background-color: #f9f9f9;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #e8e8e8;
                color: #000000;
            }
            QTableWidget::item:focus {
                background-color: #e0e0e0;
                color: #000000;
                border: 1px solid #555555;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 5px;
                border: 1px solid #cccccc;
                font-weight: bold;
            }
        """)
        self.above_table.setAlternatingRowColors(True)
        
                       
        self.above_table_delegate = SegmentTableDelegate(
            self.above_table, 
            col_count=3,
            add_row_callback=lambda: self._add_table_row(self.above_table, ["", "", "1"])
        )
        for col in range(3):
            self.above_table.setItemDelegateForColumn(col, self.above_table_delegate)
        
        self.above_table.setMinimumHeight(100)
        self.above_table.setMaximumHeight(150)
        above_layout.addWidget(self.above_table)

        above_btn_layout = QHBoxLayout()
                  
        btn_above_help = QPushButton("参数说明")
        btn_above_help.setMaximumWidth(100)
        btn_above_help.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #333333;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
                border: 1px solid #999999;
            }
        """)
        btn_above_help.clicked.connect(self._show_above_segment_help)
        above_btn_layout.addWidget(btn_above_help)
        above_btn_layout.addStretch()
        btn_add_above = QPushButton("+ 添加段")
        btn_add_above.clicked.connect(
            lambda: self._add_table_row(self.above_table, ["", "", "1"])
        )
        btn_del_above = QPushButton("- 删除")
        btn_del_above.clicked.connect(
            lambda: self._del_table_row(self.above_table)
        )
        above_btn_layout.addWidget(btn_add_above)
        above_btn_layout.addWidget(btn_del_above)
        above_layout.addLayout(above_btn_layout)

        content_layout.addWidget(above_group)

        below_group = QGroupBox("地下部分（土层参数） - 必填    方向从上往下")
        below_layout = QVBoxLayout(below_group)

        self.below_table = QTableWidget(0, 5)
        self.below_table.setHorizontalHeaderLabels([
            "层厚 H (m)", "直径 D (m)", "m 值 (KN/m⁴)",
            "内摩擦角 φ (°)", "分段数 N"
        ])
                   
        below_header = self.below_table.horizontalHeader()
        below_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.below_table.setToolTip(
            "【地下土层参数】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "至少定义1层，建议按地质分层\n\n"
            "• HBL: 土层厚度 (m)\n"
            "• DOB: 该层桩径 (m)\n"
            "• PMT: 土的m值 (kN/m⁴)\n"
            "  软塑粘土: 5000-10000\n"
            "  可塑粘土: 10000-20000\n"
            "  中密砂土: 15000-30000\n"
            "  密实砂土: 30000-50000\n\n"
            "• PFI: 内摩擦角 (°)\n"
            "  粘土: 10-25°\n"
            "  粉土: 15-30°\n"
            "  砂土: 25-40°\n\n"
            "• NSG: 输出点数 (通常2-5)"
        )
        
                              
        self.below_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #cccccc;
                background-color: white;
                alternate-background-color: #f9f9f9;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #e8e8e8;
                color: #000000;
            }
            QTableWidget::item:focus {
                background-color: #e0e0e0;
                color: #000000;
                border: 1px solid #555555;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 5px;
                border: 1px solid #cccccc;
                font-weight: bold;
            }
        """)
        self.below_table.setAlternatingRowColors(True)
        
                       
        self.below_table_delegate = SegmentTableDelegate(
            self.below_table, 
            col_count=5,
            add_row_callback=lambda: self._add_table_row(self.below_table, ["", "", "", "", "1"])
        )
        for col in range(5):
            self.below_table.setItemDelegateForColumn(col, self.below_table_delegate)
        
        self.below_table.setMinimumHeight(150)
        below_layout.addWidget(self.below_table)

        below_btn_layout = QHBoxLayout()
                  
        btn_below_help = QPushButton("参数说明")
        btn_below_help.setMaximumWidth(100)
        btn_below_help.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #333333;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
                border: 1px solid #999999;
            }
        """)
        btn_below_help.clicked.connect(self._show_below_segment_help)
        below_btn_layout.addWidget(btn_below_help)
        below_btn_layout.addStretch()
        btn_add_below = QPushButton("+ 添加层")
        btn_add_below.clicked.connect(
            lambda: self._add_table_row(
                self.below_table, ["", "", "", "", "1"]
            )
        )
        btn_del_below = QPushButton("- 删除")
        btn_del_below.clicked.connect(
            lambda: self._del_table_row(self.below_table)
        )
        below_btn_layout.addWidget(btn_add_below)
        below_btn_layout.addWidget(btn_del_below)
        below_layout.addLayout(below_btn_layout)

        content_layout.addWidget(below_group)

        bottom_group = QGroupBox("桩底参数")
        bottom_form = QFormLayout(bottom_group)

        self.pmb_input = QDoubleSpinBox()
        self.pmb_input.setRange(0, 1e9)
        self.pmb_input.setDecimals(2)
        self.pmb_input.setSingleStep(1000)
        self.pmb_input.setValue(0.0)
        self._setup_spinbox_enter_navigation(self.pmb_input)
        
                           
        self.pmb_label = QLabel("桩底地基系数 m₀ (KN/m⁴):")
        
                           
        pmb_help_text = (
            "【PMB】桩底地基系数\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "根据KSU类型选择参数意义:\n\n"
            "KSU=1,2 (摩擦桩):\n"
            "  输入 m₀ (桩底土比例系数) kN/m⁴\n"
            "  软塑土: 5,000-15,000\n"
            "  可塑土: 15,000-30,000\n"
            "  密实土: 30,000-50,000\n\n"
            "KSU=3,4 (端承桩):\n"
            "  输入 c₀ (岩石地基系数) kN/m³\n"
            "  强风化: 50,000-200,000\n"
            "  中风化: 200,000-500,000\n"
            "  微风化: 500,000-1,000,000"
        )
        self.pmb_input.setToolTip(pmb_help_text)
        
                      
        row_layout = QHBoxLayout()
        row_layout.addWidget(self.pmb_input)
        row_layout.addWidget(self._create_help_button(pmb_help_text))
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_widget = QWidget()
        row_widget.setLayout(row_layout)
        bottom_form.addRow(self.pmb_label, row_widget)
        
                             
        self.ksu_combo.currentIndexChanged.connect(self._on_ksu_changed)

        content_layout.addWidget(bottom_group)
        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _on_ksu_changed(self, index):
                                                           
        if index <= 1:                 
            self.pmb_label.setText("桩底地基系数 m₀ (KN/m⁴):")
        else:                 
            self.pmb_label.setText("桩底地基系数 c₀ (KN/m³):")

    def _normalize_direction(self):
        ax = self.angle_alpha.value()
        ay = self.angle_beta.value()
        az = self.angle_gamma.value()

        norm = math.sqrt(ax**2 + ay**2 + az**2)
        if norm > 1e-10:
            self.angle_alpha.setValue(ax / norm)
            self.angle_beta.setValue(ay / norm)
            self.angle_gamma.setValue(az / norm)
        else:
            self.angle_alpha.setValue(0.0)
            self.angle_beta.setValue(0.0)
            self.angle_gamma.setValue(1.0)
            QMessageBox.warning(self, "警告", "方向向量为零，已重置为垂直方向 (0, 0, 1)")

    def _add_table_row(self, table, default_values):
        row = table.rowCount()
        table.insertRow(row)
        for col, val in enumerate(default_values):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, col, item)
        self.dataChanged.emit()

    def _del_table_row(self, table):
        row = table.currentRow()
        if row >= 0:
            table.removeRow(row)
            self.dataChanged.emit()
    
    def _show_above_segment_help(self):
        help_dialog = QMessageBox(self)
        help_dialog.setWindowTitle("地上部分（自由段）参数说明")
        help_dialog.setTextFormat(Qt.TextFormat.RichText)
        help_dialog.setText(
            "<h3>地上部分（自由段）- 可选参数</h3>"
            "<p><b>定义：</b>冲刷线或地面以上的桩身部分</p>"
            "<hr>"
            "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse;'>"
            "<tr style='background-color: #1976D2; color: white;'>"
            "<th>参数名</th><th>变量</th><th>单位</th><th>说明</th>"
            "</tr>"
            "<tr>"
            "<td><b>段长 H</b></td>"
            "<td>HFR</td>"
            "<td>m</td>"
            "<td>自由段的高度<br>典型值: 1.0-10.0 m</td>"
            "</tr>"
            "<tr style='background-color: #E3F2FD;'>"
            "<td><b>直径/边长 D</b></td>"
            "<td>DOF</td>"
            "<td>m</td>"
            "<td>桩身截面尺寸<br>• 圆桩：填直径<br>• 方桩：填边长<br>典型值: 0.5-2.0 m</td>"
            "</tr>"
            "<tr>"
            "<td><b>分段数 N</b></td>"
            "<td>NSF</td>"
            "<td>-</td>"
            "<td>输出点数量<br>用于内力位移输出<br>建议值: 2-5</td>"
            "</tr>"
            "</table>"
            "<br>"
            "<p><b>使用场景：</b></p>"
            "<ul>"
            "<li>桥墩桩：地面至承台底的部分</li>"
            "<li>码头桩：海床至承台底的部分</li>"
            "<li>考虑冲刷：冲刷线以上部分</li>"
            "</ul>"
            "<p style='color: #666;'><i>提示：如果桩顶直接埋于地面，可不填此部分</i></p>"
        )
        help_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        help_dialog.exec()
    
    def _show_below_segment_help(self):
        help_dialog = QMessageBox(self)
        help_dialog.setWindowTitle("地下部分（土层）参数说明")
        help_dialog.setTextFormat(Qt.TextFormat.RichText)
        help_dialog.setText(
            "<h3>地下部分（埋置段）- 必填参数</h3>"
            "<p><b>定义：</b>冲刷线或地面以下，嵌入土层中的桩身部分</p>"
            "<hr>"
            "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse; width: 100%;'>"
            "<tr style='background-color: #1976D2; color: white;'>"
            "<th>参数名</th><th>变量</th><th>单位</th><th>说明</th>"
            "</tr>"
            "<tr>"
            "<td><b>层厚 H</b></td>"
            "<td>HBL</td>"
            "<td>m</td>"
            "<td>该土层的厚度（桩在该层的长度）<br>按地质勘察报告分层</td>"
            "</tr>"
            "<tr style='background-color: #E3F2FD;'>"
            "<td><b>直径 D</b></td>"
            "<td>DOB</td>"
            "<td>m</td>"
            "<td>该层桩身直径/边长<br>支持变截面桩</td>"
            "</tr>"
            "<tr>"
            "<td><b>m 值</b></td>"
            "<td>PMT</td>"
            "<td>kN/m⁴</td>"
            "<td><b style='color: red;'>关键参数！</b>土的水平抗力比例系数<br>"
            "• 软塑粘土: 5,000-10,000<br>"
            "• 可塑粘土: 10,000-20,000<br>"
            "• 硬塑粘土: 20,000-30,000<br>"
            "• 中密砂土: 15,000-30,000<br>"
            "• 密实砂土: 30,000-80,000<br>"
            "<a href='#' style='color: #1976D2;'>点击菜单【帮助-参数参考值】查看详表</a>"
            "</td>"
            "</tr>"
            "<tr style='background-color: #E3F2FD;'>"
            "<td><b>内摩擦角 φ</b></td>"
            "<td>PFI</td>"
            "<td>度 (°)</td>"
            "<td>土的内摩擦角，用于极限抗力计算<br>"
            "• 粘土: 10-25°<br>"
            "• 粉土: 15-30°<br>"
            "• 砂土: 25-40°<br>"
            "<a href='#' style='color: #1976D2;'>详见【帮助-参数参考值】</a>"
            "</td>"
            "</tr>"
            "<tr>"
            "<td><b>分段数 N</b></td>"
            "<td>NSG</td>"
            "<td>-</td>"
            "<td>输出点数量<br>建议值: 2-5</td>"
            "</tr>"
            "</table>"
            "<br>"
            "<p><b style='color: red;'>重要提示：</b></p>"
            "<ul>"
            "<li>至少定义 <b>1层</b>土层参数</li>"
            "<li>建议按地质勘察报告的<b>土层分层</b>逐层定义</li>"
            "<li><b>m 值</b>对计算结果影响最大，需根据土工试验确定</li>"
            "<li>所有层厚之和应等于桩的<b>有效埋深</b></li>"
            "</ul>"
            "<p style='color: #666;'><i>提示：按 F1 键可快速查看参数参考值表</i></p>"
        )
        help_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        help_dialog.exec()

    def get_data(self):
        data = {
            'ksh': self.ksh_combo.currentIndex(),
            'ksu': self.ksu_combo.currentIndex() + 1,
            'angle': [
                self.angle_alpha.value(),
                self.angle_beta.value(),
                self.angle_gamma.value()
            ],
            'peh': self.peh_input.value(),
            'pke': self.pke_input.value(),
            'pmb': self.pmb_input.value(),
            'above_ground': [],
            'below_ground': [],
        }

                    
        if self._original_differential:
            data['_original_differential'] = True
            if self._differential_params:
                data['_differential_params'] = self._differential_params

        for row in range(self.above_table.rowCount()):
            item0 = self.above_table.item(row, 0)
            item1 = self.above_table.item(row, 1)
            item2 = self.above_table.item(row, 2)
            if item0 and item1 and item2:
                try:
                    length = float(item0.text())
                    diameter = float(item1.text())
                    segments = int(item2.text())
                    data['above_ground'].append([length, diameter, segments])
                except ValueError:
                    continue

        for row in range(self.below_table.rowCount()):
            items = [self.below_table.item(row, col) for col in range(5)]
            if all(items):
                try:
                    thickness = float(items[0].text())
                    diameter = float(items[1].text())
                    m_value = float(items[2].text())
                    friction_angle = float(items[3].text())
                    segments = int(items[4].text())
                    data['below_ground'].append([
                        thickness, diameter, m_value, friction_angle, segments
                    ])
                except ValueError:
                    continue

        return data

    def set_data(self, data):
                    
        self._original_differential = data.get('_original_differential', False)
        self._differential_params = data.get('_differential_params', None)
        
        self.ksh_combo.setCurrentIndex(data.get('ksh', 0))
        self.ksu_combo.setCurrentIndex(max(0, data.get('ksu', 1) - 1))

        angle = data.get('angle', [0.0, 0.0, 1.0])
        self.angle_alpha.setValue(angle[0] if len(angle) > 0 else 0.0)
        self.angle_beta.setValue(angle[1] if len(angle) > 1 else 0.0)
        self.angle_gamma.setValue(angle[2] if len(angle) > 2 else 1.0)

        self.peh_input.setValue(data.get('peh', 3.0e7))
        self.pke_input.setValue(data.get('pke', 1.0))
        self.pmb_input.setValue(data.get('pmb', 15000.0))

        self.above_table.setRowCount(0)
        for item in data.get('above_ground', []):
            self._add_table_row(self.above_table, [str(x) for x in item])

        self.below_table.setRowCount(0)
        for item in data.get('below_ground', []):
            self._add_table_row(self.below_table, [str(x) for x in item])

class PileManualDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PILE说明书算例解析")
        self.resize(1400, 800)
        
        layout = QVBoxLayout(self)
        
              
        header = QLabel("PILE说明书算例解析")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #1976D2; padding: 10px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
             
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #C2C7CB; }
            QTabBar::tab {
                background-color: #E1E1E1;
                color: #333;
                padding: 8px 15px;
                border: 1px solid #C4C4C3;
                border-bottom: none;
                min-width: 120px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-top: 3px solid #1976D2;
            }
        """)
        
              
        self._setup_cases()
        
        layout.addWidget(self.tabs)
        
              
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.accept)
        layout.addWidget(btn_box)

    def _setup_cases(self):
        cases = [
            ("算例一: 12桩双工况", "pile说明书算例1_12桩双工况.dat", "pile说明书算例一.png",
             """
             <h4>算例一：12桩基础双工况分析</h4>
             <p><b>特点：</b>此算例展示了一个包含12根桩的大型群桩基础，在两种不同荷载工况下的受力分析。</p>
             <ul>
             <li><b>工况1：</b>常规竖向荷载与水平力组合。</li>
             <li><b>工况2：</b>极端偏心荷载作用。</li>
             </ul>
             <p>通过此算例可以学习如何定义多工况以及分析大型群桩的荷载分配。</p>
             """),
             
            ("算例二: 4桩带模拟桩", "pile说明书算例2_4桩带模拟桩.dat", "pile说明书算例二.png",
             """
             <h4>算例二：4桩基础带模拟桩</h4>
             <p><b>特点：</b>演示了如何在群桩分析中引入“模拟桩”来考虑既有桩基或特殊边界条件。</p>
             <p><b>模拟桩：</b>不直接承受新建结构的荷载，但通过土体相互作用影响其他桩的计算结果。</p>
             """),
             
            ("算例三: 16桩斜桩差异化", "pile说明书算例3_16桩斜桩差异化.dat", "pile说明书算例三.png",
             """
             <h4>算例三：16桩斜桩差异化设计</h4>
             <p><b>特点：</b>包含不同倾斜角度的斜桩（差异化参数），适用于复杂地形获受力要求。</p>
             <p><b>关注点：</b>
             1. 斜桩的方向余弦定义。<br>
             2. 不同位置桩采用不同的几何参数。
             </p>
             """),
             
            ("算例四: 3桩非中心模拟桩", "pile说明书算例4_3桩非中心模拟桩.dat", "pile说明书算例四.png",
             """
             <h4>算例四：3桩非中心模拟桩</h4>
             <p><b>特点：</b>非对称布局的3桩基础，并包含非中心位置的模拟桩。</p>
             <p>展示了不规则桩位布置下的群桩效应分析。</p>
             """)
        ]
        
        for title, dat, img, desc in cases:
            self._add_3column_tab(title, dat, img, desc)

    def _add_3column_tab(self, title, dat_filename, img_filename, desc_html):
        tab_widget = QWidget()
                    
        layout = QHBoxLayout(tab_widget)
        
                              
        col1 = QGroupBox("示意图")
        col1_layout = QVBoxLayout(col1)
        col1_layout.setContentsMargins(0, 10, 0, 0)
        
        img_path = self._find_resource_path(img_filename)
        if HAS_MATPLOTLIB_QT and img_path:
            try:
                import matplotlib.pyplot as plt
                from matplotlib.figure import Figure
                
                fig = Figure(figsize=(5, 4), facecolor='white')
                ax = fig.add_subplot(111)
                
                image_data = plt.imread(str(img_path))
                ax.imshow(image_data)
                ax.axis('off')
                fig.tight_layout(pad=0.2)
                
                canvas = FigureCanvas(fig)
                canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                
                toolbar = NavigationToolbar(canvas, col1)
                toolbar.setStyleSheet("background-color: #f0f0f0; border-bottom: 1px solid #ccc;")
                
                col1_layout.addWidget(toolbar)
                col1_layout.addWidget(canvas)
            except Exception as e:
                logger.error(f"Matplotlib error: {e}")
                self._fallback_image(col1_layout, img_path, img_filename)
        else:
            self._fallback_image(col1_layout, img_path, img_filename)
            
        layout.addWidget(col1, 4)      
        
                                
        col2 = QGroupBox("算例分析")
        col2_layout = QVBoxLayout(col2)
        
        desc_browser = QTextBrowser()
        desc_browser.setHtml(desc_html)
        col2_layout.addWidget(desc_browser)
        
        layout.addWidget(col2, 2)      
        
                                 
        col3 = QGroupBox("DAT输入文件")
        col3_layout = QVBoxLayout(col3)
        
        dat_preview = QTextEdit()
        dat_preview.setReadOnly(True)
        dat_preview.setFont(QFont("Consolas", 9))
        dat_preview.setText(self._read_file_content(dat_filename))
              
        self._highlight_dat_syntax(dat_preview)
        
        col3_layout.addWidget(dat_preview)
        
        layout.addWidget(col3, 3)      
        
        self.tabs.addTab(tab_widget, title)

    def _fallback_image(self, layout, img_path, img_filename):
        label = ScalableImageLabel()
        if img_path:
            label.setOriginalPixmap(QPixmap(str(img_path)))
        else:
            label.setText(f"图片未找到: {img_filename}")
        layout.addWidget(label)

    def _find_resource_path(self, filename):
        possible_paths = [
            Path.cwd() / filename,
            Path.cwd() / "源代码以及图表等原始文件" / filename,
            Path(__file__).parent / filename,
            Path(__file__).parent / "源代码以及图表等原始文件" / filename,
        ]
        if hasattr(sys, '_MEIPASS'):
             possible_paths.insert(0, Path(sys._MEIPASS) / filename)
        for p in possible_paths:
            if p.exists():
                return p
        return None

    def _read_file_content(self, filename):
        path = self._find_resource_path(filename)
        if path:
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    return f.read()
            except Exception:
                return "读取失败"
        return "文件未找到"

    def _highlight_dat_syntax(self, text_edit):

        pass

class TutorialDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PileAnalysis - 算例详解与说明")
        self.resize(1000, 700)
        
        layout = QVBoxLayout(self)
        
              
                                           
                                  
                                      



        
               
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #C2C7CB; }
            QTabWidget::tab-bar { left: 5px; }
            QTabBar::tab {
                background-color: #f2f2f2;
                border: 1px solid #C4C4C3;
                border-bottom-color: #C2C7CB;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                min-width: 8ex;
                padding: 4px 8px;
                color: #333333;
            }
            QTabBar::tab:selected, QTabBar::tab:hover {
                background-color: white;
            }
            QTabBar::tab:selected {
                border-color: #9B9B9B;
                border-bottom-color: white;
            }
        """)
        
       
        style_header = "background-color: #1976D2; color: white; padding: 5px;"
        style_row = "background-color: #E3F2FD; padding: 5px;"
        
               
        top_hint = QLabel(
            "<div style='border: 1px solid #FFEEBA; padding: 10px; color: red;'>"
            "<b>提示：</b>右侧为该模式算例教程的原始DAT文件内容。<br>"
            "点击主程序菜单栏【教程】中对应的算例选项，即可<b>自动导入</b>并<b>跳转至参数界面</b>进行查看与修改并保存。"
            "</div>"
        )
        top_hint.setTextFormat(Qt.TextFormat.RichText)
        layout.insertWidget(0, top_hint)         

                                
                                
        self.add_tutorial_tab("模式一：群桩刚度", "模式一算例.dat", 
            f"""
            <h4 style='color: black;'>模式一：群桩刚度求解</h4>
            <p>计算整个桩群基础在承台中心的6x6刚度矩阵。</p>
            <p><b>适用场景：</b>上部结构分析时，将桩基简化为等效弹簧。</p>
            <hr>
            <p><b>说明：</b></p>
            <ul>
            <li><b>不需要荷载或位移输入</b></li>
            <li><b>输出</b>: 6自由度刚度矩阵 (Kx, Ky, Kz, KRx, KRy, KRz 及耦合项)</li>
            </ul>
            <br>
            <div style='padding: 10px; border-left: 5px solid #1976D2;'>
            <p><b>【本算例情景】</b></p>
            <p>一个由 <b>2根大直径桩</b> 组成的排架基础。</p>
            <p><b>桩身参数：</b>桩径 2.0m，嵌岩或坚硬土层（m值高达 75000~2250000 kN/m⁴）。</p>
            </div>
            """
        )
        
        self.add_tutorial_tab("模式二：单桩刚度", "模式二算例.dat", 
            f"""
            <h4 style='color: black;'>模式二：单桩刚度分析</h4>
            <p>针对指定的某一根桩，计算其桩头的刚度矩阵。</p>
            <p><b>适用场景：</b>分析单桩特性，或手动合成群桩刚度。</p>
            <hr>
            <p><b>输入特点：</b></p>
            <ul>
            <li><b>[CALC_PILE]</b>: 指定要计算的那根桩的编号 (No.)</li>
            <li>其余输入与模式一类似</li>
            </ul>
            <br>
            <div style='padding: 10px; border-left: 5px solid #1976D2;'>
            <p><b>【本算例情景】</b></p>
            <p>模型与模式一相同。</p>
            <p><b>特定目标：</b>只计算 <b>2号桩</b> (No. 2) 的单桩刚度。</p>
            </div>
            """
        )
        
        self.add_tutorial_tab("模式三：桩基反算", "模式三算例.dat", 
            f"""
            <h4 style='color: black;'>模式三：桩基反算</h4>
            <p>已知承台受到的外荷载，计算桩基的内力（轴力、弯矩、剪力）和变形（位移、转角）。</p>
            <p><b>适用场景：</b>常规桩基设计验算。</p>
            <hr>
            <p><b>关键参数说明：</b></p>
            <ul>
            <li><b>[LOADS]</b>: 承台中心荷载 (Fx, Fy, Fz, Mx, My, Mz)</li>
            <li><b>[P_TYPE]</b>: 桩类型定义，包含地面以上/以下分段参数</li>
            <li><b>[ARRANGE]</b>: 桩位坐标及类型引用</li>
            </ul>
            <br>
            <div style='padding: 10px; border-left: 5px solid #1976D2;'>
            <p><b>【本算例情景】</b></p>
            <p>一个由 <b>4根桩</b> 组成的矩形桩基（桩间距 5m/6m）。</p>
            <p><b>荷载状况：</b>承台受到竖向荷载 <b>-8000 kN</b>，同时伴有水平力 (Fx=500, Fy=300) 和弯矩作用。</p>
            <p><b>桩身参数：</b>桩径 1.5m，桩长 30m，穿越3层土（m值分别为 8000, 15000, 25000 kN/m⁴），并包含1根模拟桩。</p>
            </div>
            """
        )
        
        layout.addWidget(self.tabs)


        
        
              
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.accept)
        layout.addWidget(btn_box)

    def add_tutorial_tab(self, title, filename, desc_html):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
                 
        desc_browser = QTextBrowser()
        desc_browser.setHtml(desc_html)
        desc_browser.setOpenExternalLinks(True)
        desc_browser.setMaximumWidth(350)
        layout.addWidget(desc_browser)
        
                      
        file_preview = QTextEdit()
        file_preview.setReadOnly(True)
        file_preview.setFont(QFont("Consolas", 9))
        
                  
        content = self._read_file_content(filename)
            
        file_preview.setText(content)
        
              
        self._highlight_dat_syntax(file_preview)
        
        layout.addWidget(file_preview)
        self.tabs.addTab(widget, title)

    def _create_pile_manual_section(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 10, 0, 0)
        
            
        header = QLabel("PILE说明书算例详解表")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #1976D2; border-bottom: 2px solid #1976D2; padding-bottom: 5px;")
        layout.addWidget(header)
        
                     
        self.pile_manual_tabs = QTabWidget()
        self.pile_manual_tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #C2C7CB; }
            QTabBar::tab {
                background-color: #E1E1E1;
                color: #333;
                padding: 5px 10px;
                border: 1px solid #C4C4C3;
                border-bottom: none;
                min-width: 100px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-top: 2px solid #1976D2;
            }
        """)
        
                   
        self._add_pile_manual_tab("算例一: 12桩双工况", 
            "pile说明书算例1_12桩双工况.dat", 
            "pile说明书算例一.png",
            """
            <h4>算例一：12桩基础双工况分析</h4>
            <p><b>特点：</b>此算例展示了一个包含12根桩的大型群桩基础，在两种不同荷载工况下的受力分析。</p>
            <ul>
            <li><b>工况1：</b>常规竖向荷载与水平力组合。</li>
            <li><b>工况2：</b>极端偏心荷载作用。</li>
            </ul>
            <p>通过此算例可以学习如何定义多工况以及分析大型群桩的荷载分配。</p>
            """
        )
        
        self._add_pile_manual_tab("算例二: 4桩带模拟桩", 
            "pile说明书算例2_4桩带模拟桩.dat", 
            "pile说明书算例二.png",
            """
            <h4>算例二：4桩基础带模拟桩</h4>
            <p><b>特点：</b>演示了如何在群桩分析中引入“模拟桩”来考虑既有桩基或特殊边界条件。</p>
            <p><b>模拟桩：</b>不直接承受新建结构的荷载，但通过土体相互作用影响其他桩的计算结果。</p>
            """
        )
        
        self._add_pile_manual_tab("算例三: 16桩斜桩差异化", 
            "pile说明书算例3_16桩斜桩差异化.dat", 
            "pile说明书算例三.png",
            """
            <h4>算例三：16桩斜桩差异化设计</h4>
            <p><b>特点：</b>包含不同倾斜角度的斜桩（差异化参数），适用于复杂地形获受力要求。</p>
            <p><b>关注点：</b>
            1. 斜桩的方向余弦定义。<br>
            2. 不同位置桩采用不同的几何参数。
            </p>
            """
        )
        
        self._add_pile_manual_tab("算例四: 3桩非中心模拟桩", 
            "pile说明书算例4_3桩非中心模拟桩.dat", 
            "pile说明书算例四.png",
            """
            <h4>算例四：3桩非中心模拟桩</h4>
            <p><b>特点：</b>非对称布局的3桩基础，并包含非中心位置的模拟桩。</p>
            <p>展示了不规则桩位布置下的群桩效应分析。</p>
            """
        )
        
        layout.addWidget(self.pile_manual_tabs)
        return container

    def _add_pile_manual_tab(self, title, dat_filename, img_filename, desc_html):
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
                                
        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.setHandleWidth(8)
        
                                      
        img_container = QGroupBox("PILE说明书")
        img_layout = QVBoxLayout(img_container)
        img_layout.setContentsMargins(5, 15, 5, 5)              
        
                  
        img_path = self._find_resource_path(img_filename)
        
        if HAS_MATPLOTLIB_QT and img_path:
            try:
                                         
                import matplotlib.pyplot as plt
                from matplotlib.figure import Figure
                
                           
                fig = Figure(figsize=(8, 6), facecolor='white')
                ax = fig.add_subplot(111)
                
                      
                image_data = plt.imread(str(img_path))
                ax.imshow(image_data)
                ax.axis('off')         
                fig.tight_layout(pad=0.5)
                
                           
                canvas = FigureCanvas(fig)
                canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                
                            
                toolbar = NavigationToolbar(canvas, img_container)
                toolbar.setStyleSheet("background-color: #f0f0f0; border-bottom: 1px solid #ccc;")
                
                img_layout.addWidget(toolbar)
                img_layout.addWidget(canvas)
                
            except Exception as e:
                logger.error(f"Matplotlib 加载图片失败: {e}")
                             
                self._fallback_image_label(img_layout, img_path, img_filename)
        else:
                                              
            self._fallback_image_label(img_layout, img_path, img_filename)
            
        v_splitter.addWidget(img_container)
        
                                
        info_container = QGroupBox("DAT文件分析与说明")
        info_layout = QHBoxLayout(info_container)
        info_layout.setContentsMargins(5, 15, 5, 5)
        
                 
        desc_browser = QTextBrowser()
        desc_browser.setHtml(desc_html)
        desc_browser.setMaximumWidth(400)         
        info_layout.addWidget(desc_browser)
        
                    
        dat_preview = QTextEdit()
        dat_preview.setReadOnly(True)
        dat_preview.setFont(QFont("Consolas", 9))
        dat_preview.setText(self._read_file_content(dat_filename))
        self._highlight_dat_syntax(dat_preview)
        
        info_layout.addWidget(dat_preview)
        
        v_splitter.addWidget(info_container)
        
                                
        v_splitter.setStretchFactor(0, 6)
        v_splitter.setStretchFactor(1, 4)
        
        layout.addWidget(v_splitter)
        self.pile_manual_tabs.addTab(tab_widget, title)

    def _fallback_image_label(self, layout, img_path, img_filename):
        img_label = ScalableImageLabel()
        if img_path:
            img_label.setOriginalPixmap(QPixmap(str(img_path)))
        else:
            img_label.setText(f"未找到图片: {img_filename}")
        layout.addWidget(img_label)

    def _find_resource_path(self, filename):
        possible_paths = [
            Path.cwd() / filename,
            Path.cwd() / "源代码以及图表等原始文件" / filename,
            Path(__file__).parent / filename,
            Path(__file__).parent / "源代码以及图表等原始文件" / filename,
        ]
        
                        
        if hasattr(sys, '_MEIPASS'):
             possible_paths.insert(0, Path(sys._MEIPASS) / filename)
             
        for p in possible_paths:
            if p.exists():
                return p
        return None

    def _read_file_content(self, filename):
        path = self._find_resource_path(filename)
        if path:
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    return f.read()
            except Exception as e:
                return f"读取出错: {e}"
        return "文件未找到"

    def _highlight_dat_syntax(self, text_edit):

                                           
        pass


                                                                         
     
                                                                         
class MainWindow(QMainWindow):

    
           
    calculation_finished = Signal(object)
    calculation_progress = Signal(str)
    reverse_finished = Signal(object, object, object)
    verification_finished = Signal(object, object)
    stiffness_calc_finished = Signal(object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PileAnalysis - 桩基分析程序 ")

        self._setup_window_size()

        self.pile_type_names = []
        self.pile_type_editors = {}
        self.current_mode_index = -1
        self.case_type = None                   
        self.case_imported = False
        self.mode_names = [
            "模式1: 荷载→内力变形",
            "模式2: 位移→荷载反算",
            "模式3: 承台整体刚度",
            "模式4: 单桩刚度计算"
        ]

        self._init_calculation_modules()

        self.work_dir = Path(tempfile.mkdtemp(prefix='pile_calc_'))
        logger.info(f"工作目录: {self.work_dir}")

        self.progress_dialog = None
        self._reverse_displacement = None
        self._reverse_gui_data = None
        
        self.calculation_finished.connect(self._on_calc_finished)
        self.calculation_progress.connect(self._on_calc_progress)
        self.reverse_finished.connect(self._on_reverse_finished)
        self.verification_finished.connect(self._on_verification_finished)
        self.stiffness_calc_finished.connect(self._on_stiffness_calc_finished)

        self._build_ui()

                                                      
               
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
                 
                           
                                  
                                  
        column_style = """
            QLabel { 
                color: #666666; 
                padding: 0px 10px;
                border-right: 1px solid #cccccc;
                font-size: 9pt; 
            }
        """
        
                             
        last_col_style = """
            QLabel { 
                color: #666666; 
                padding: 0px 10px; 
                font-size: 9pt;
            }
        """

                        
        lbl_author = QLabel("作者：汪灿，郭军军")
        lbl_author.setStyleSheet(column_style)
        self.status_bar.addWidget(lbl_author)
        self.author_label = lbl_author

                        
        lbl_email = QLabel("邮箱：24231238@bjtu.edu.cn / jjguo2@bjtu.edu.cn")
        lbl_email.setToolTip("24231238@bjtu.edu.cn / jjguo2@bjtu.edu.cn")         
        lbl_email.setStyleSheet(column_style)
        self.status_bar.addWidget(lbl_email)
        self.email_label = lbl_email

                         
        lbl_version = QLabel("版本：3.0")
        lbl_version.setStyleSheet(column_style)
        self.status_bar.addWidget(lbl_version)
        self.version_label = lbl_version

                                   
        github_url = "https://github.com/CanWang-BJTU/PileAnalysis"
        
                                                                     
        lbl_doc = QLabel(f"<a href='{github_url}' style='color: #000000; text-decoration: none;'>更新下载</a>")
        lbl_doc.setStyleSheet(last_col_style)                 
        lbl_doc.setOpenExternalLinks(True)                
        lbl_doc.setToolTip(f"点击访问源码仓库:\n{github_url}")
        self.status_bar.addWidget(lbl_doc)
        self.download_label = lbl_doc

                                    
        self.calc_status_label = QLabel("准备就绪")
        self.calc_status_label.setStyleSheet("""
            QLabel {
                color: #666666;
                padding: 2px 10px;
                border-left: 1px solid #cccccc;
                font-weight: bold;
                font-size: 9pt;
            }
        """)
        self.status_bar.addPermanentWidget(self.calc_status_label)
                                                         
                                                                             
            
                                                                             

    def _setup_window_size(self):
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            self._screen_width = screen_geometry.width()
            self._screen_height = screen_geometry.height()
            
                          
            if self._screen_width >= 2560:         
                width = int(self._screen_width * 0.70)
                height = int(self._screen_height * 0.80)
            elif self._screen_width >= 1920:         
                width = int(self._screen_width * 0.75)
                height = int(self._screen_height * 0.85)
            elif self._screen_width >= 1366:            
                width = int(self._screen_width * 0.90)
                height = int(self._screen_height * 0.90)
            else:        
                width = int(self._screen_width * 0.95)
                height = int(self._screen_height * 0.95)
        else:
            self._screen_width = 1920
            self._screen_height = 1080
            width = 1400
            height = 900

                  
        self.setMinimumSize(1000, 700)
        self.resize(width, height)
        
        if screen:
            center = screen_geometry.center()
            frame_geometry = self.frameGeometry()
            frame_geometry.moveCenter(center)
            self.move(frame_geometry.topLeft())
    
    def _get_adaptive_figsize(self, base_width=9, base_height=3.5):
        try:
                              
            if hasattr(self, 'plot_tabs') and self.plot_tabs.isVisible():
                available_width = self.plot_tabs.width()
                available_height = self.plot_tabs.height()
            else:
                available_width = self.width() * 0.5
                available_height = self.height() * 0.4
            
                          
                                                   
            base_available_width = 800
            base_available_height = 400
            
            scale_w = available_width / base_available_width
            scale_h = available_height / base_available_height
            scale = min(scale_w, scale_h, 1.5)          
            scale = max(scale, 0.6)          
            
            fig_width = base_width * scale
            fig_height = base_height * scale
            
                  
            fig_width = max(6, min(fig_width, 14))
            fig_height = max(2.5, min(fig_height, 6))
            
            return (fig_width, fig_height)
        except Exception:
            return (base_width, base_height)
    
    def _get_adaptive_dpi(self):
        try:
            screen = QApplication.primaryScreen()
            if screen:
                logical_dpi = screen.logicalDotsPerInch()
                                    
                if logical_dpi > 144:          
                    return 150
                elif logical_dpi > 120:
                    return 130
                else:
                    return 120
        except Exception:
            pass
        return 120
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
                                
                               

    def _setup_spinbox_enter_navigation(self, spinbox):
        spinbox.installEventFilter(self)
                                
        spinbox.setStyleSheet("""
            QDoubleSpinBox {
                padding: 5px;
                border: 1px solid #cccccc;
                border-radius: 3px;
                color: #000000;
            }
            QDoubleSpinBox:focus {
                border: 1px solid #555555;
                background-color: white;
            }
        """)
    
    def _setup_lineedit_enter_navigation(self, lineedit):
        lineedit.installEventFilter(self)
                        
        lineedit.setStyleSheet("""
            QLineEdit {
                padding: 5px;
                border: 1px solid #cccccc;
                border-radius: 3px;
            }
            QLineEdit:focus {
                border: 1px solid #555555;
                background-color: white;
            }
            QLineEdit::placeholder {
                color: #999999;
            }
        """)
    
    def eventFilter(self, obj, event):
        if event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                           
                if hasattr(self, 'pile_table') and obj == self.pile_table:
                    return self._handle_pile_table_enter()
                               
                self.focusNextChild()
                return True
        return super().eventFilter(obj, event)
    
    def _handle_pile_table_enter(self):
        current_row = self.pile_table.currentRow()
        current_col = self.pile_table.currentColumn()
        
        if current_row < 0:
            return False
        
                            
        if current_col == 1:
            self.pile_table.setCurrentCell(current_row, 2)
            self.pile_table.editItem(self.pile_table.item(current_row, 2))
            return True
                               
        elif current_col == 2:
            next_row = current_row + 1
            if next_row < self.pile_table.rowCount():
                self.pile_table.setCurrentCell(next_row, 1)
                self.pile_table.editItem(self.pile_table.item(next_row, 1))
            else:
                                   
                self._add_pile_row()
                self.pile_table.setCurrentCell(next_row, 1)
                self.pile_table.editItem(self.pile_table.item(next_row, 1))
            return True
        
        return False

        self.setMinimumSize(1200, 800)
        self.resize(width, height)

    def _init_calculation_modules(self):
        self.async_engine = None
        self.exe_path = ""

        if HAS_ENGINE and AsyncPileEngine is not None:
            try:
                current_dir = Path(__file__).parent if '__file__' in globals() else Path.cwd()
                bcad_pile_exe = current_dir / "BCAD-PILE.exe"
                
                self.async_engine = AsyncPileEngine()
                
                if bcad_pile_exe.exists():
                    success = self.async_engine.engine.set_executable_path(str(bcad_pile_exe))
                    if success:
                        self.exe_path = str(bcad_pile_exe)
                        logger.info(f"已自动加载计算引擎: {self.exe_path}")
                        QTimer.singleShot(100, lambda: self.update_status(f"计算引擎就绪: {Path(self.exe_path).name}"))
                    else:
                        logger.warning(f"无法设置计算引擎: {bcad_pile_exe}")
                        QTimer.singleShot(100, lambda: self.update_status("计算引擎未就绪"))
                elif self.async_engine.engine.exe_path:
                    self.exe_path = self.async_engine.engine.exe_path
                    logger.info(f"已找到计算引擎: {self.exe_path}")
                    QTimer.singleShot(100, lambda: self.update_status(f"✓ 计算引擎就绪: {Path(self.exe_path).name}"))
                else:
                    logger.warning("未找到 BCAD-PILE.exe，请确保它在程序同目录下")
                    QTimer.singleShot(100, lambda: self.update_status("⚠ 未找到计算引擎，请确保计算内核在程序同目录"))
            except Exception as e:
                logger.error(f"初始化计算引擎失败: {e}")
                self.async_engine = None
                QTimer.singleShot(100, lambda: self.update_status(f"计算引擎初始化失败: {e}"))

        self.parser = None
        if HAS_PARSER and ResultParser is not None:
            self.parser = ResultParser()

        self.plotter = None
        if HAS_PLOTTER and PilePlotter is not None:
            try:
                self.plotter = PilePlotter()
            except Exception as e:
                logger.error(f"初始化绘图器失败: {e}")
                self.plotter = None

    def _build_ui(self):
                 
        menubar = self.menuBar()
        
              
        export_menu = menubar.addMenu("导出(&E)")
        
        export_all_action = export_menu.addAction("导出全部结果")
        export_all_action.setShortcut("Ctrl+E")
        export_all_action.triggered.connect(self._export_all_results)
        
        export_menu.addSeparator()
        
        export_plots_action = export_menu.addAction("仅导出图片")
        export_plots_action.triggered.connect(lambda: self._export_all_results(plots_only=True))
        
        export_text_action = export_menu.addAction("仅导出文本结果")
        export_text_action.triggered.connect(lambda: self._export_all_results(text_only=True))
        
        export_menu.addSeparator()
        
        export_stiffness_action = export_menu.addAction("导出刚度矩阵CSV")
        export_stiffness_action.setShortcut("Ctrl+Shift+S")
        export_stiffness_action.triggered.connect(self._export_stiffness_csv)
        
        export_summary_csv_action = export_menu.addAction("导出结果摘要CSV")
        export_summary_csv_action.setShortcut("Ctrl+Shift+C")
        export_summary_csv_action.triggered.connect(self._export_summary_csv)
        
              
        help_menu = menubar.addMenu("帮助(&H)")
        
        param_ref_action = help_menu.addAction("参数参考值")
        param_ref_action.setShortcut("F1")
        param_ref_action.triggered.connect(MainWindow.show_parameter_reference)
        
        
        about_action = help_menu.addAction("关于")
        about_action.triggered.connect(self._show_about)

                  
        tutorial_menu = menubar.addMenu("教程(&T)")
        
                
        t1 = tutorial_menu.addAction("模式一算例：群桩刚度")
        t1.triggered.connect(lambda: self._load_tutorial_case(1))
        
        t2 = tutorial_menu.addAction("模式二算例：单桩刚度")
        t2.triggered.connect(lambda: self._load_tutorial_case(2))
        
        t3 = tutorial_menu.addAction("模式三算例：桩基反算")
        t3.triggered.connect(lambda: self._load_tutorial_case(3))
        
        tutorial_menu.addSeparator()

                          
        pile_manual_menu = tutorial_menu.addMenu("PILE说明书算例 (导入)")
        
        pm1 = pile_manual_menu.addAction("算例1: 12桩双工况")
        pm1.triggered.connect(lambda: self._load_pile_manual_case(1))

        pm2 = pile_manual_menu.addAction("算例2: 4桩带模拟桩")
        pm2.triggered.connect(lambda: self._load_pile_manual_case(2))

        pm3 = pile_manual_menu.addAction("算例3: 16桩斜桩差异化")
        pm3.triggered.connect(lambda: self._load_pile_manual_case(3))

        pm4 = pile_manual_menu.addAction("算例4: 3桩非中心模拟桩")
        pm4.triggered.connect(lambda: self._load_pile_manual_case(4))

        tutorial_menu.addSeparator()
        
            
        t_detail = tutorial_menu.addAction("算例详解与说明表")
        t_detail.setShortcut("F2")
        t_detail.triggered.connect(self._show_tutorial_dialog)

        attach_navigation_menu(self, "m-method")

                             
        pile_manual_analysis = tutorial_menu.addAction("PILE说明书算例解析")
        pile_manual_analysis.setShortcut("F3")
        pile_manual_analysis.triggered.connect(self._show_pile_manual_dialog)




        
                 
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(main_splitter)

        main_splitter.addWidget(self._create_left_panel())
        main_splitter.addWidget(self._create_right_panel())

        width = self.width()
        main_splitter.setSizes([int(width * 0.55), int(width * 0.45)])

    def _show_pile_manual_dialog(self):
        try:
            dialog = PileManualDialog(self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开PILE说明书解析对话框:\n{str(e)}\n\n{traceback.format_exc()}")
            logger.error(f"打开PILE说明书解析对话框失败: {e}", exc_info=True)

    def _create_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        v_splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(v_splitter)

                           
        self.visual_tabs = QTabWidget()
        
                                        
        diagram_widget = QWidget()
        diagram_layout = QVBoxLayout(diagram_widget)
        diagram_layout.setContentsMargins(2, 2, 2, 2)
        diagram_layout.setSpacing(2)
        
        self._load_schematic_diagram(diagram_layout)
        
        self.visual_tabs.addTab(diagram_widget, "计算原理示意图")
        
                    
        plot_widget = QWidget()
        plot_layout = QVBoxLayout(plot_widget)
        plot_layout.setContentsMargins(5, 5, 5, 5)
        
                                
        self.plot_tabs = QTabWidget()
        self._setup_plot_tabs()
        
        plot_layout.addWidget(self.plot_tabs)
        self.visual_tabs.addTab(plot_widget, "图形绘制区")
        
        v_splitter.addWidget(self.visual_tabs)

                   
        results_group = QGroupBox("计算结果输出区")
        results_layout = QVBoxLayout(results_group)
        self.results_tabs = QTabWidget()

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setPlaceholderText("计算结果摘要将显示在此...")

        self.raw_output_text = QTextEdit()
        self.raw_output_text.setReadOnly(True)
        self.raw_output_text.setPlaceholderText("原始刚度矩阵和计算输出将显示在此...")
        self.raw_output_text.setFont(QFont("Consolas", 9))

        self.results_tabs.addTab(self.summary_text, "结果摘要")
        self.results_tabs.addTab(self.raw_output_text, "原始输出")
        results_layout.addWidget(self.results_tabs)
        v_splitter.addWidget(results_group)

        total_height = self.height()
        v_splitter.setSizes([
            int(total_height * 0.65),                
            int(total_height * 0.35)                 
        ])

        return panel

    def _load_schematic_diagram(self, layout: QVBoxLayout):
        
     
        possible_paths = []
        
                            
        if hasattr(sys, '_MEIPASS'):
            base_path = Path(sys._MEIPASS)
            possible_paths.extend([
                (base_path / "桩基空间示意图.ai", 'ai'),
                (base_path / "pile_foundation_schematic.ai", 'ai'),
                (base_path / "pile_foundation_schematic_en.ai", 'ai'),
                (base_path / "示意图.ai", 'ai'),
                (base_path / "示意图.pdf", 'pdf'),
                (base_path / "app_icon.ico", 'png'),            
            ])

        if get_language() == "en":
            possible_paths.extend([
                (Path.cwd() / "桩基空间示意图-EN.ai", 'ai'),
                (Path(__file__).parent / "桩基空间示意图-EN.ai", 'ai'),
            ])
        possible_paths.extend([
            (Path(__file__).parent / "桩基空间示意图.ai", 'ai'),
            (Path(__file__).parent / "pile_foundation_schematic.ai", 'ai'),
            (Path(__file__).parent / "pile_foundation_schematic_en.ai", 'ai'),
            (Path(__file__).parent / "示意图.ai", 'ai'),
            (Path(__file__).parent / "示意图.pdf", 'pdf'),
            (Path(__file__).parent / "示意图.png", 'png'),
            (Path(__file__).parent / "schematic.png", 'png'),
            (Path(__file__).parent / "assets" / "示意图.png", 'png'),
            (Path.cwd() / "桩基空间示意图.ai", 'ai'),
            (Path.cwd() / "示意图.png", 'png'),
        ])
        
                 
        diagram_path = None
        file_type = None
        for path, ftype in possible_paths:
            if path.exists():
                diagram_path = path
                file_type = ftype
                break
        
        image_data = None
        
        if diagram_path:
                                        
            if file_type in ('ai', 'pdf'):
                try:
                    import fitz           
                    doc = fitz.open(str(diagram_path))
                    if doc.page_count > 0:
                        page = doc[0]
                                        
                        zoom = 6.0              
                        mat = fitz.Matrix(zoom, zoom)
                        pix = page.get_pixmap(matrix=mat, alpha=False)
                        
                                                   
                        import numpy as np
                        img_data = pix.samples
                        image_data = np.frombuffer(img_data, dtype=np.uint8).reshape(
                            pix.height, pix.width, pix.n
                        )
                        logger.info(f"已使用 PyMuPDF 加载示意图: {diagram_path}")
                    doc.close()
                except ImportError:
                    logger.warning("PyMuPDF 未安装，无法加载 AI/PDF 文件")
                except Exception as e:
                    logger.error(f"PyMuPDF 加载失败: {e}")
            
                                                      
            if image_data is None:
                try:
                    import matplotlib.pyplot as plt
                    image_data = plt.imread(str(diagram_path))
                    logger.info(f"已加载图像: {diagram_path}")
                except Exception as e:
                    logger.error(f"加载图像失败: {e}")
        
                                                           
        if HAS_MATPLOTLIB_QT and image_data is not None:
            try:
                import matplotlib.pyplot as plt
                from matplotlib.figure import Figure
                
                           
                fig = Figure(figsize=(10, 8), facecolor='white')
                ax = fig.add_subplot(111)
                ax.imshow(image_data)
                ax.axis('off')
                title_text = "Pile Foundation Analysis Schematic" if get_language() == "en" else "桩基计算原理示意图"
                ax.set_title(
                    title_text,
                    fontsize=12,
                    fontweight='bold',
                    pad=10,
                    fontfamily='Times New Roman' if get_language() == "en" else None,
                )
                fig.tight_layout(pad=0.5)
                
                                 
                canvas = FigureCanvas(fig)
                canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                
                                      
                toolbar = NavigationToolbar(canvas, None)
                toolbar.setStyleSheet("""
                    QToolBar {
                        background-color: #f0f0f0;
                        border: 1px solid #ccc;
                        border-radius: 3px;
                        spacing: 3px;
                        padding: 2px;
                    }
                """)
                
                layout.addWidget(toolbar)
                layout.addWidget(canvas)
                
                            
                self.diagram_canvas = canvas
                self.diagram_figure = fig
                return
                
            except Exception as e:
                logger.error(f"创建交互式示意图失败: {e}")
        
                                    
        pixmap = None
        if diagram_path:
            if file_type in ('ai', 'pdf'):
                try:
                    import fitz
                    doc = fitz.open(str(diagram_path))
                    if doc.page_count > 0:
                        page = doc[0]
                        zoom = 6.0
                        mat = fitz.Matrix(zoom, zoom)
                        pix = page.get_pixmap(matrix=mat, alpha=False)
                        img_data = pix.tobytes("png")
                        pixmap = QPixmap()
                        pixmap.loadFromData(img_data)
                    doc.close()
                except:
                    pass
            
            if pixmap is None:
                pixmap = QPixmap(str(diagram_path))
                if pixmap.isNull():
                    pixmap = None
        
                
        self.diagram_label = ScalableImageLabel()
        self.diagram_label.setMinimumHeight(200)
        
        if pixmap and not pixmap.isNull():
            self.diagram_label.setOriginalPixmap(pixmap)
        else:
            self.diagram_label.setText(
                "示意图文件未找到或加载失败\n\n"
                "支持格式: AI、PDF、PNG\n"
                "请将文件放置在程序目录下"
            )
            self.diagram_label.setStyleSheet(
                "color: #888888; font-size: 12px; "
                "background-color: #f0f0f0; padding: 20px;"
            )
        
        layout.addWidget(self.diagram_label)

    def _set_diagram_placeholder(self, message: str):
        self.diagram_label.setText(message)
        self.diagram_label.setStyleSheet(
            "color: #888888; font-size: 12px; "
            "background-color: #f0f0f0; padding: 20px;"
        )

    def _setup_plot_tabs(self):
                       
        plot_3d_widget = QWidget()
        plot_3d_layout = QVBoxLayout(plot_3d_widget)
        plot_3d_layout.setContentsMargins(5, 5, 5, 5)
        
        self.plot_3d_area = QLabel("计算完成后将显示桩基三维布置图")
        self.plot_3d_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.plot_3d_area.setStyleSheet(
            "font-size: 14px; color: #888; background-color: #f5f5f5;"
        )
        self.plot_3d_area.setMinimumHeight(150)
        self.plot_3d_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        plot_3d_layout.addWidget(self.plot_3d_area)
        self.plot_tabs.addTab(plot_3d_widget, "立体布置图")
        
                   
        plot_response_widget = QWidget()
        plot_response_layout = QVBoxLayout(plot_response_widget)
        plot_response_layout.setContentsMargins(5, 5, 5, 5)
        
        self.plot_response_area = QLabel("计算完成后将显示桩基响应曲线")
        self.plot_response_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.plot_response_area.setStyleSheet(
            "font-size: 14px; color: #888; background-color: #f5f5f5;"
        )
        self.plot_response_area.setMinimumHeight(150)
        self.plot_response_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        plot_response_layout.addWidget(self.plot_response_area)
        self.plot_tabs.addTab(plot_response_widget, "桩身响应图")

    def _create_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        guide_group = QGroupBox("快速上手指南")
        guide_layout = QVBoxLayout(guide_group)
        guide_label = QLabel()
        guide_label.setWordWrap(True)
        guide_label.setText(
            "1.选择工况类型（现有/新建）\n"
            "2.选择计算模式\n"
            "3.填写参数 → 定义桩类型 → 添加桩位坐标\n"
            "4.点击【开始计算】\n"
        )
        guide_layout.addWidget(guide_label)
        layout.addWidget(guide_group)

                             
        self.selection_stack = QStackedWidget()
        layout.addWidget(self.selection_stack)
        
                  
        self.case_selection_page = self._create_case_selection_page()
        self.selection_stack.addWidget(self.case_selection_page)
        
                  
        self.mode_selection_page = self._create_mode_selection_page()
        self.selection_stack.addWidget(self.mode_selection_page)

                      
        self.wizard_stack = QStackedWidget()
        layout.addWidget(self.wizard_stack, 1)

               
        placeholder = QWidget()
        placeholder_layout = QVBoxLayout(placeholder)
        self.placeholder_label = QLabel("↑ 请选择工况类型")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet("font-size: 18px; color: gray;")
        placeholder_layout.addWidget(self.placeholder_label)
        self.wizard_stack.addWidget(placeholder)

                
        wizard_page = QWidget()
        wizard_layout = QVBoxLayout(wizard_page)
        wizard_layout.setContentsMargins(0, 0, 0, 0)

                      
        self.parameter_tabs = QTabWidget()
        self.parameter_tabs.setTabPosition(QTabWidget.TabPosition.North)
        
               
        self.load_disp_page = self._create_load_disp_page()
        self.pile_type_page = self._create_pile_type_page()
        self.pile_list_page = self._create_pile_list_page()
        
        wizard_layout.addWidget(self.parameter_tabs, 1)

                               
        nav_widget = QWidget()
        nav_layout = QHBoxLayout(nav_widget)
        
        nav_layout.addStretch()

                           
        self.save_case_button = QPushButton("保存工况")
        self.save_case_button.clicked.connect(self.save_case)
        self.save_case_button.setEnabled(False)
        self.save_case_button.setVisible(False)
        self.save_case_button.setToolTip("生成DAT文件保存工况，但不进行计算")
        nav_layout.addWidget(self.save_case_button)

                                
        self.export_case_button = QPushButton("保存并导出")
        self.export_case_button.clicked.connect(self.save_case)
        self.export_case_button.setEnabled(False)
        self.export_case_button.setVisible(False)
        self.export_case_button.setToolTip("将修改后的工况导出为DAT文件")
        nav_layout.addWidget(self.export_case_button)

        self.calculate_button = QPushButton("开始计算")
        self.calculate_button.clicked.connect(self.start_calculation)
        self.calculate_button.setEnabled(False)
        
        nav_layout.addWidget(self.calculate_button)
        wizard_layout.addWidget(nav_widget)
        
        self.wizard_stack.addWidget(wizard_page)

        return panel
    
    def _create_case_selection_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        
        case_group = QGroupBox("工况选择")
        case_layout = QHBoxLayout(case_group)
        
                         
        self.case_button_group = QButtonGroup(self)
        
              
        existing_case_rb = QRadioButton("现有工况")
        self.case_button_group.addButton(existing_case_rb, 0)
        case_layout.addWidget(existing_case_rb)
        
              
        new_case_rb = QRadioButton("新建工况")
        self.case_button_group.addButton(new_case_rb, 1)
        case_layout.addWidget(new_case_rb)
        
        self.case_button_group.idClicked.connect(self._on_case_type_selected)
        
        layout.addWidget(case_group)
        layout.addStretch()
        
        return page
    
    def _create_mode_selection_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        
        mode_group = QGroupBox("计算模式选择")
        mode_layout = QVBoxLayout(mode_group)
        
                
        mode_grid = QGridLayout()
        self.mode_button_group = QButtonGroup(self)
        
                  
        self.mode_names = [
            "模式一：群桩刚度",
            "模式二：单桩刚度",
            "模式三：桩基反算"
        ]
        
                      
        mode_tooltips = [
            "计算群桩基础的刚度矩阵（JCTR=2）",
            "计算单桩的刚度矩阵（JCTR=3）",
            "完整的荷载-位移非线性分析（JCTR=1）"
        ]
        
        for i, name in enumerate(self.mode_names):
            rb = QRadioButton(name)
            rb.setToolTip(mode_tooltips[i] if i < len(mode_tooltips) else "")
            self.mode_button_group.addButton(rb, i)
            mode_grid.addWidget(rb, 0, i)                  
        
        self.mode_button_group.idClicked.connect(self._on_mode_selected)
        mode_layout.addLayout(mode_grid)
        
                  
        back_case_btn = QPushButton("返回工况选择")
        back_case_btn.clicked.connect(self._back_to_case_selection)
        mode_layout.addWidget(back_case_btn)
        
                         
        self.import_widget = QWidget()
        import_layout = QVBoxLayout(self.import_widget)
        import_layout.setContentsMargins(0, 0, 0, 0)
        
        self.import_button = QPushButton("导入已有工况（dat文件）")
        self.import_button.clicked.connect(self._import_dat_file)
        self.import_button.setToolTip("请选择包含工况的dat文件")
        import_layout.addWidget(self.import_button)
        
        self.import_status_label = QLabel("")
        self.import_status_label.setStyleSheet("color: #333333; font-weight: bold;")
        self.import_status_label.setVisible(False)
        import_layout.addWidget(self.import_status_label)
        
                                     
        self.view_modify_button = QPushButton("查看与修改")
        self.view_modify_button.clicked.connect(self._show_parameter_tabs)
        self.view_modify_button.setVisible(False)
        import_layout.addWidget(self.view_modify_button)
        
        self.direct_calc_button = QPushButton("直接计算")
        self.direct_calc_button.clicked.connect(self.start_calculation)
        self.direct_calc_button.setVisible(False)
        import_layout.addWidget(self.direct_calc_button)
        
        mode_layout.addWidget(self.import_widget)
        self.import_widget.setVisible(False)        
        
        layout.addWidget(mode_group)
        layout.addStretch()
        
        return page
    
    def _on_case_type_selected(self, case_id: int):
        self.case_type = "现有工况" if case_id == 0 else "新建工况"
        self.case_imported = False
        
                   
        self.selection_stack.setCurrentWidget(self.mode_selection_page)
        
                         
        if self.case_type == "现有工况":
            self.import_widget.setVisible(True)
            self.import_status_label.setVisible(False)
            self.view_modify_button.setVisible(False)
            self.direct_calc_button.setVisible(False)            
            self.import_button.setVisible(True)
                     
            self.placeholder_label.setText("↑ 请选择计算模式并导入现有工况")
        else:        
            self.import_widget.setVisible(False)
                     
            self.placeholder_label.setText("↑ 请选择计算模式并设置工况")
        
                
        if self.mode_button_group.checkedButton():
            self.mode_button_group.setExclusive(False)
            self.mode_button_group.checkedButton().setChecked(False)
            self.mode_button_group.setExclusive(True)
        
        self.wizard_stack.setCurrentIndex(0)         
        self.calculate_button.setEnabled(False)
    
    def _back_to_case_selection(self):
        self.selection_stack.setCurrentWidget(self.case_selection_page)
        self.case_type = None
        self.case_imported = False
        self.wizard_stack.setCurrentIndex(0)
        self.calculate_button.setEnabled(False)
        
                
        if self.case_button_group.checkedButton():
            self.case_button_group.setExclusive(False)
            self.case_button_group.checkedButton().setChecked(False)
            self.case_button_group.setExclusive(True)
    
    def _show_parameter_tabs(self):
        self.wizard_stack.setCurrentIndex(1)
        self.calculate_button.setEnabled(True)
                  
        self.direct_calc_button.setVisible(False)
                     
        self.export_case_button.setVisible(True)
        self.export_case_button.setEnabled(True)
        
                                         
        self.view_modify_button.setText("更换文件")
        self.view_modify_button.setToolTip("重新导入新的DAT文件 (当前未保存的修改将丢失)")
        self.view_modify_button.setVisible(True)          
        
                       
        if hasattr(self, '_imported_filename') and self._imported_filename:
            if get_language() == "en":
                filename = _translate_to_english(os.path.basename(self._imported_filename))
                self.import_status_label.setText(f"✓ Imported existing case: {filename}")
            else:
                filename = _translate_to_english(os.path.basename(self._imported_filename)) if get_language() == "en" else self._imported_filename
                self.import_status_label.setText(
                    f"✓ Imported existing case: {filename}" if get_language() == "en" else f"✓ 已导入现有工况: {self._imported_filename}"
                )
        
                     
        try:
            self.view_modify_button.clicked.disconnect()
        except TypeError:
            pass              
        self.view_modify_button.clicked.connect(self._on_change_file_clicked)

    def _on_change_file_clicked(self):
                                 
        self._import_dat_file()

    def _create_load_disp_page(self) -> QWidget:
                
        outer_widget = QWidget()
        outer_layout = QVBoxLayout(outer_widget)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        
                
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
                
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

                                                                                   
                            
                                                                                   
        self.case_type_group = QGroupBox("荷载数量")
        case_type_layout = QHBoxLayout(self.case_type_group)
        
        self.single_case_radio = QRadioButton("单荷载")
        self.multi_case_radio = QRadioButton("多荷载（同时作用）")
        self.single_case_radio.setChecked(True)         
        
              
        self.single_case_radio.toggled.connect(self._on_case_type_changed)
        
        case_type_layout.addWidget(self.single_case_radio)
        case_type_layout.addWidget(self.multi_case_radio)
        case_type_layout.addStretch()
        
        layout.addWidget(self.case_type_group)

                                                                                   
                      
                                                                                   
        self.load_group = QGroupBox("承台中心荷载 (正算模式)")
        load_form = QFormLayout(self.load_group)
        self.loads: Dict[str, QLineEdit] = {}
        
                   
        coord_layout = QHBoxLayout()
        self.load_x_input = QLineEdit()
        self.load_x_input.setPlaceholderText("0.0")
        self.load_x_input.setText("0.0")
        self._setup_lineedit_enter_navigation(self.load_x_input)
        
        self.load_y_input = QLineEdit()
        self.load_y_input.setPlaceholderText("0.0")
        self.load_y_input.setText("0.0")
        self._setup_lineedit_enter_navigation(self.load_y_input)
        
        coord_layout.addWidget(QLabel("X:"))
        coord_layout.addWidget(self.load_x_input)
        coord_layout.addWidget(QLabel("Y:"))
        coord_layout.addWidget(self.load_y_input)
        coord_layout.addStretch()
        load_form.addRow("荷载作用点 (m):", coord_layout)
        
        load_params = [
            ("Nx", "nx", "KN"),
            ("Ny", "ny", "KN"),
            ("Nz", "nz", "KN"),
            ("Mx", "mx", "KN·m"),
            ("My", "my", "KN·m"),
            ("Mz", "mz", "KN·m"),
        ]
        for label_text, key, unit in load_params:
            line_edit = QLineEdit()
            line_edit.setPlaceholderText(f"请输入数值，单位: {unit}")
            self._setup_lineedit_enter_navigation(line_edit)
            self.loads[key] = line_edit
            load_form.addRow(f"{label_text} ({unit}):", line_edit)

        layout.addWidget(self.load_group)

                                                                                   
                      
                                                                                   
        self.disp_group = QGroupBox("承台中心位移 (反算模式)")
        disp_form = QFormLayout(self.disp_group)
        self.disps: Dict[str, QLineEdit] = {}
        
                   
        disp_coord_layout = QHBoxLayout()
        self.disp_x_input = QLineEdit()
        self.disp_x_input.setPlaceholderText("0.0")
        self.disp_x_input.setText("0.0")
        self._setup_lineedit_enter_navigation(self.disp_x_input)
        
        self.disp_y_input = QLineEdit()
        self.disp_y_input.setPlaceholderText("0.0")
        self.disp_y_input.setText("0.0")
        self._setup_lineedit_enter_navigation(self.disp_y_input)
        
        disp_coord_layout.addWidget(QLabel("X:"))
        disp_coord_layout.addWidget(self.disp_x_input)
        disp_coord_layout.addWidget(QLabel("Y:"))
        disp_coord_layout.addWidget(self.disp_y_input)
        disp_coord_layout.addStretch()
        disp_form.addRow("参考点 (m):", disp_coord_layout)
        
        disp_params = [
            ("Ux", "ux", "m"),
            ("Uy", "uy", "m"),
            ("Uz", "uz", "m"),
            ("θx", "thetax", "rad"),
            ("θy", "thetay", "rad"),
            ("θz", "thetaz", "rad"),
        ]
        for label_text, key, unit in disp_params:
            line_edit = QLineEdit()
            line_edit.setPlaceholderText(f"请输入数值，单位: {unit}")
            self._setup_lineedit_enter_navigation(line_edit)
            self.disps[key] = line_edit
            disp_form.addRow(f"{label_text} ({unit}):", line_edit)

        layout.addWidget(self.disp_group)
        
                                                                                   
                                      
                                                                                   
        self.multi_case_group = QGroupBox("多荷载输入")
        multi_case_layout = QVBoxLayout(self.multi_case_group)
        
                         
        self.multi_case_table = QTableWidget(0, 6)
        self.multi_case_table.horizontalHeader().setVisible(False)
        self.multi_case_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.multi_case_table.verticalHeader().setVisible(False)
        self.multi_case_table.setAlternatingRowColors(True)
        self.multi_case_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #cccccc;
                background-color: white;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: #000000;
            }
        """)
        
                            
        self.multi_case_delegate = MultiCaseTableDelegate(
            self.multi_case_table, 
            add_case_callback=self._add_load_case_row
        )
        self.multi_case_table.setItemDelegate(self.multi_case_delegate)
        
        multi_case_layout.addWidget(self.multi_case_table)
        
               
        multi_case_btn_layout = QHBoxLayout()
        multi_case_btn_layout.addStretch()
        
        self.btn_add_case = QPushButton("添加工况")
        self.btn_add_case.clicked.connect(self._add_load_case_row)
        self.btn_del_case = QPushButton("删除工况")
        self.btn_del_case.clicked.connect(self._delete_load_case_row)
        
        multi_case_btn_layout.addWidget(self.btn_add_case)
        multi_case_btn_layout.addWidget(self.btn_del_case)
        multi_case_layout.addLayout(multi_case_btn_layout)
        
        self.multi_case_group.setVisible(False)        
        layout.addWidget(self.multi_case_group)

        layout.addStretch()
        
                     
        scroll_area.setWidget(page)
        outer_layout.addWidget(scroll_area)

        return outer_widget
    
    @Slot(bool)
    def _on_case_type_changed(self, checked=None):
        is_single = self.single_case_radio.isChecked()
        
                                                                                                                      
        is_full_analysis = (self.current_mode_index == 2)
        
                                                                                             
                                                                 
        
               
        if is_single:
                                                       
            self.load_group.setVisible(is_full_analysis)
                                                  
            self.disp_group.setVisible(False)
            self.multi_case_group.setVisible(False)
        else:
                                          
            self.load_group.setVisible(False)
            self.disp_group.setVisible(False)
            self.multi_case_group.setVisible(is_full_analysis)
            
            if is_full_analysis:
                                   
                if self.multi_case_table.rowCount() == 0:
                    self._add_load_case_row()
                else:
                                  
                    self._update_multi_case_headers()
                
                self.multi_case_group.setTitle(
                    "Multiple Load Input (Simultaneous Action)" if get_language() == "en" else "多荷载输入（同时作用）"
                )
    
    @Slot()
    def _add_load_case_row(self):
                
        current_rows = self.multi_case_table.rowCount()
        group_index = (current_rows // 4) + 1
        base_row = current_rows
        
              
        for _ in range(4):
            self.multi_case_table.insertRow(self.multi_case_table.rowCount())
        
              
        header_brush = QBrush(QColor("#f5f5f5"))
        header_font = QFont()
        header_font.setBold(True)
        small_height = 25
        normal_height = 30
        
                             
        self.multi_case_table.setRowHeight(base_row, small_height)
        
        if get_language() == "en":
            headers_geo = ["Load Case", "X Coordinate (m)", "Y Coordinate (m)"]
        else:
            headers_geo = ["荷载编号", "X 坐标 (m)", "Y 坐标 (m)"]
        for i, text in enumerate(headers_geo):
            col = i * 2
            item = QTableWidgetItem(text)
            item.setFlags(Qt.ItemIsEnabled)
            item.setBackground(header_brush)
            item.setFont(header_font)
            item.setTextAlignment(Qt.AlignCenter)
            self.multi_case_table.setItem(base_row, col, item)
            self.multi_case_table.setSpan(base_row, col, 1, 2)
        
                            
        self.multi_case_table.setRowHeight(base_row + 1, normal_height)
        
                  
        item_no_text = f"Load {group_index}" if get_language() == "en" else f"荷载 {group_index}"
        item_no = QTableWidgetItem(item_no_text)
        item_no.setFlags(Qt.ItemIsEnabled)
        item_no.setTextAlignment(Qt.AlignCenter)
        self.multi_case_table.setItem(base_row + 1, 0, item_no)
        self.multi_case_table.setSpan(base_row + 1, 0, 1, 2)
        
                 
        item_x = QTableWidgetItem("0.0")
        item_x.setTextAlignment(Qt.AlignCenter)
        self.multi_case_table.setItem(base_row + 1, 2, item_x)
        self.multi_case_table.setSpan(base_row + 1, 2, 1, 2)
        
                 
        item_y = QTableWidgetItem("0.0")
        item_y.setTextAlignment(Qt.AlignCenter)
        self.multi_case_table.setItem(base_row + 1, 4, item_y)
        self.multi_case_table.setSpan(base_row + 1, 4, 1, 2)
        
                             
        self.multi_case_table.setRowHeight(base_row + 2, small_height)
        
        headers_val = ["Nx (KN)", "Ny (KN)", "Nz (KN)", "Mx (KN·m)", "My (KN·m)", "Mz (KN·m)"]
        
        for i, text in enumerate(headers_val):
            item = QTableWidgetItem(text)
            item.setFlags(Qt.ItemIsEnabled)
            item.setBackground(header_brush)
            item.setFont(header_font)
            item.setTextAlignment(Qt.AlignCenter)
            self.multi_case_table.setItem(base_row + 2, i, item)
        
                            
        self.multi_case_table.setRowHeight(base_row + 3, normal_height)
        
        for i in range(6):
            item = QTableWidgetItem("0.0")
            item.setTextAlignment(Qt.AlignCenter)
            self.multi_case_table.setItem(base_row + 3, i, item)
        
                   
        self._update_case_select_combo()
    
    @Slot()
    def _delete_load_case_row(self):
        current_row = self.multi_case_table.currentRow()
        row_count = self.multi_case_table.rowCount()
        
        if row_count < 4:
            return
        
        target_base_row = -1
        
        if current_row < 0:
                        
            target_base_row = row_count - 4
        else:
                               
            target_base_row = (current_row // 4) * 4
        
        if target_base_row >= 0:
                    
            for _ in range(4):
                self.multi_case_table.removeRow(target_base_row)
            
                    
            new_row_count = self.multi_case_table.rowCount()
            for base in range(target_base_row, new_row_count, 4):
                idx = (base // 4) + 1
                item = self.multi_case_table.item(base + 1, 0)
                if item:
                    item.setText(f"Load {idx}" if get_language() == "en" else f"荷载 {idx}")
            
                       
            self._update_case_select_combo()
    
    def _update_case_select_combo(self):
                              
        pass
    
    def _update_multi_case_headers(self):
        row_count = self.multi_case_table.rowCount()
        
                          
        headers_val = ["Nx (KN)", "Ny (KN)", "Nz (KN)", "Mx (KN·m)", "My (KN·m)", "Mz (KN·m)"]
        
            
        header_brush = QBrush(QColor("#f5f5f5"))
        header_font = QFont()
        header_font.setBold(True)
        
                                            
        for base_row in range(0, row_count, 4):
            header_row = base_row + 2
            if header_row < row_count:
                for i, text in enumerate(headers_val):
                    item = self.multi_case_table.item(header_row, i)
                    if item:
                        item.setText(text)
                    else:
                                    
                        item = QTableWidgetItem(text)
                        item.setFlags(Qt.ItemIsEnabled)
                        item.setBackground(header_brush)
                        item.setFont(header_font)
                        item.setTextAlignment(Qt.AlignCenter)
                        self.multi_case_table.setItem(header_row, i, item)

                                                                             
           
                                                                             

    def _create_pile_type_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        mgmt_group = QGroupBox("桩类型管理")
        mgmt_layout = QHBoxLayout(mgmt_group)

        mgmt_layout.addWidget(QLabel("当前编辑:"))
        self.pile_type_combo = QComboBox()
        self.pile_type_combo.setMinimumWidth(150)
        self.pile_type_combo.currentTextChanged.connect(self._on_pile_type_changed)
        mgmt_layout.addWidget(self.pile_type_combo, 1)

        btn_new = QPushButton("新建")
        btn_new.clicked.connect(self._add_pile_type)
        btn_del = QPushButton("删除")
        btn_del.clicked.connect(self._delete_pile_type)
        btn_rename = QPushButton("重命名")
        btn_rename.clicked.connect(self._rename_pile_type)

        mgmt_layout.addWidget(btn_new)
        mgmt_layout.addWidget(btn_del)
        mgmt_layout.addWidget(btn_rename)

        layout.addWidget(mgmt_group)

        self.pile_type_editor_stack = QStackedWidget()

        empty_widget = QWidget()
        empty_layout = QVBoxLayout(empty_widget)
        empty_label = QLabel("请先点击【新建】创建一个桩类型")
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_label.setStyleSheet("font-size: 14px; color: gray;")
        empty_layout.addWidget(empty_label)
        self.pile_type_editor_stack.addWidget(empty_widget)

        layout.addWidget(self.pile_type_editor_stack, 1)

        return page

                                                                             
            
                                                                             

    def _update_table_height(self, table: QTableWidget, min_units: int = 2, rows_per_unit: int = 1):
        def do_update():
            try:
                                    
                table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                
                         
                header_h = 0
                                                                                                     
                if not table.horizontalHeader().isHidden():
                    header_h = table.horizontalHeader().height()
                    if header_h <= 0:                       
                        header_h = 30                        
                
                         
                content_h = 0
                row_count = table.rowCount()
                
                            
                default_row_h = 30
                if row_count > 0:
                     h = table.rowHeight(0)
                     if h > 0: default_row_h = h

                if row_count > 0:
                    for i in range(row_count):
                        h = table.rowHeight(i)
                        content_h += h if h > 0 else default_row_h
                
                           
                            
                current_units = row_count // rows_per_unit
                if current_units < min_units:
                    missing_units = min_units - current_units
                    content_h += missing_units * rows_per_unit * default_row_h
                    
                          
                total_h = header_h + content_h + 4 
                
                                     
                           
                total_h = max(total_h, 50)
                
                table.setFixedHeight(int(total_h))
                                  
                table.setMinimumHeight(int(total_h))
                
            except Exception as e:
                logger.error(f"调整表格高度失败: {e}")

                                                        
        QTimer.singleShot(0, do_update)
                                         
        QTimer.singleShot(100, do_update)

    def _create_pile_list_page(self) -> QWidget:
                       
        outer_container = QWidget()
        outer_layout = QVBoxLayout(outer_container)
        outer_layout.setContentsMargins(0, 0, 0, 0)

              
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
              
        page = QWidget()
        layout = QVBoxLayout(page)

        self.single_pile_widget = QWidget()
        single_layout = QHBoxLayout(self.single_pile_widget)
        single_layout.setContentsMargins(0, 0, 0, 10)
        single_layout.addWidget(QLabel("计算桩号:"))
        self.pile_ino_input = QSpinBox()
        self.pile_ino_input.setRange(1, 300)
        self.pile_ino_input.setValue(1)
        single_layout.addWidget(self.pile_ino_input)
        single_layout.addStretch()
        layout.addWidget(self.single_pile_widget)
        self.single_pile_widget.hide()

        group = QGroupBox("桩位布置与类型分配")
        group_layout = QVBoxLayout(group)

        self.pile_table = QTableWidget(0, 4)
                                      
        self.pile_table.setHorizontalHeaderLabels([
            "桩号", "X 坐标 (m)", "Y 坐标 (m)", "桩类型"
        ])
        self.pile_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        
                          
        self.pile_coordinate_delegate = PileCoordinateDelegate(self.pile_table)
        self.pile_table.setItemDelegateForColumn(1, self.pile_coordinate_delegate)
        self.pile_table.setItemDelegateForColumn(2, self.pile_coordinate_delegate)
        
                              
        self.pile_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #cccccc;
                background-color: white;
                alternate-background-color: #f9f9f9;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #e8e8e8;
                color: #000000;
            }
            QTableWidget::item:focus {
                background-color: #e0e0e0;
                color: #000000;
                border: 1px solid #555555;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 5px;
                border: 1px solid #cccccc;
                font-weight: bold;
            }
        """)
        self.pile_table.setAlternatingRowColors(True)
        
                        
        self.pile_table.installEventFilter(self)
        
        group_layout.addWidget(self.pile_table)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_add = QPushButton("添加桩")
        btn_add.clicked.connect(self._add_pile_row)
        btn_del = QPushButton("删除桩")
        btn_del.clicked.connect(self._delete_pile_row)
        btn_batch = QPushButton("批量添加...")
        btn_batch.clicked.connect(self._batch_add_piles)

        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_del)
        btn_layout.addWidget(btn_batch)
        group_layout.addLayout(btn_layout)


    
        self._update_table_height(self.pile_table, min_units=0, rows_per_unit=1)
        self._update_pile_count_limit()
        
        layout.addWidget(group)

                                                                                   
                                     
                                                                                   
        self.simu_group = QGroupBox("模拟桩 (虚拟桩) 设置")
        self.simu_group.setCheckable(False)
        simu_layout = QVBoxLayout(self.simu_group)

                          
        simu_header_layout = QHBoxLayout()
        self.use_simulative_pile_checkbox = QCheckBox("启用模拟桩")
        self.use_simulative_pile_checkbox.setStyleSheet("QCheckBox { color: #333333; font-weight: bold; }")
        self.use_simulative_pile_checkbox.setChecked(False)
        self.use_simulative_pile_checkbox.stateChanged.connect(self._on_simulative_pile_toggled)
        
        simu_help_btn = QToolButton()
        simu_help_btn.setText("?")
        simu_help_btn.setFixedSize(16, 16)
        simu_help_btn.setStyleSheet("""
            QToolButton { background-color: #2196F3; color: white; border-radius: 8px; font-weight: bold; font-size: 9px; }
            QToolButton:hover { background-color: #1976D2; }
        """)
        simu_help_btn.setToolTip("点击查看虚拟桩说明")
        simu_help_text = (
            "<h3>模拟桩 (虚拟桩) 说明</h3>"
            "<p><b>模拟桩</b>用于将参与受力的结构因素（如岸边支承、地基土抗力等）简化为具有特定刚度的虚拟节点。</p>"
            "<p><b>刚度输入类型：</b></p>"
            "<ul>"
            "<li><b>对角线模式</b>: 输入6个刚度值 (Kx, Ky, Kz, Rx, Ry, Rz)，适用于独立刚度</li>"
            "<li><b>全矩阵模式</b>: 输入6×6刚度矩阵，适用于有耦合效应的情况</li>"
            "</ul>"
            "<p><b>参数说明：</b></p>"
            "<ul>"
            "<li><b>X, Y</b>: 模拟桩的空间位置坐标 (m)</li>"
            "<li><b>Kx, Ky, Kz</b>: 平动刚度 (kN/m)</li>"
            "<li><b>Rx, Ry, Rz</b>: 转动刚度 (kN·m/rad)</li>"
            "</ul>"
            "<p><i>注：模拟桩仅提供刚度贡献，不进行实体桩的内力分析。</i></p>"
        )
        simu_help_btn.clicked.connect(lambda: QMessageBox.information(self, "模拟桩说明", simu_help_text))

        simu_header_layout.addWidget(self.use_simulative_pile_checkbox)
        simu_header_layout.addWidget(simu_help_btn)
        simu_header_layout.addStretch()
        simu_layout.addLayout(simu_header_layout)

                  
        self.simu_type_widget = QWidget()
        simu_type_layout = QHBoxLayout(self.simu_type_widget)
        simu_type_layout.setContentsMargins(0, 5, 0, 5)
        
        simu_type_label = QLabel("刚度输入类型:")
        simu_type_label.setStyleSheet("font-weight: bold;")
        self.simu_type_diagonal_radio = QRadioButton("对角线模式")
        self.simu_type_matrix_radio = QRadioButton("全矩阵模式")
        self.simu_type_diagonal_radio.setChecked(True)           
        
                                             
        self.simu_type_diagonal_radio.toggled.connect(self._on_simu_type_changed)
        self.simu_type_matrix_radio.toggled.connect(self._on_simu_type_changed)
        
        simu_type_layout.addWidget(simu_type_label)
        simu_type_layout.addWidget(self.simu_type_diagonal_radio)
        simu_type_layout.addWidget(self.simu_type_matrix_radio)
        simu_type_layout.addStretch()
        
        self.simu_type_widget.setVisible(False)                 
        simu_layout.addWidget(self.simu_type_widget)

        self.simu_pile_table = QTableWidget(0, 6)
                                      
        
                           
        self.simu_pile_table.horizontalHeader().setVisible(False)
        self.simu_pile_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.simu_pile_table.verticalHeader().setVisible(False)
        
        self.simu_pile_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #cccccc;
                background-color: white;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: #000000;
            }
        """)
        self.simu_pile_table.setAlternatingRowColors(True) 
        self.simu_pile_table.installEventFilter(self)         
        
                         
        self.simu_pile_delegate = SimuPileDelegate(self.simu_pile_table)
        self.simu_pile_table.setItemDelegate(self.simu_pile_delegate)

        simu_layout.addWidget(self.simu_pile_table)

                 
        simu_btn_layout = QHBoxLayout()
        simu_btn_layout.addStretch()
        
               
        self._update_table_height(self.simu_pile_table, min_units=2, rows_per_unit=4)

        btn_add_simu = QPushButton("添加模拟桩")
        btn_add_simu.clicked.connect(self._add_simu_pile_row)
        btn_del_simu = QPushButton("删除模拟桩")
        btn_del_simu.clicked.connect(self._delete_simu_pile_row)
        
        simu_btn_layout.addWidget(btn_add_simu)
        simu_btn_layout.addWidget(btn_del_simu)
        simu_layout.addLayout(simu_btn_layout)

                              
        self.simu_pile_table.setVisible(False)
        btn_add_simu.setVisible(False)
        btn_del_simu.setVisible(False)
        
                          
        self.btn_add_simu = btn_add_simu
        self.btn_del_simu = btn_del_simu

        layout.addWidget(self.simu_group)
        layout.addStretch()                                             

                  
        scroll_area.setWidget(page)
        outer_layout.addWidget(scroll_area)

        return outer_container


    @Slot(int)
    def _on_mode_selected(self, index: int):
                             
        old_mode_index = self.current_mode_index
        
        self.current_mode_index = index
                                             
        if hasattr(self, 'mode_names') and 0 <= index < len(self.mode_names):
             self.update_status(f"已选择: {self.mode_names[index]}")
        
                      
                                        
                                         
                                              
        
        is_foundation = (index == 0)
        is_single_pile = (index == 1)
        is_full_analysis = (index == 2)

                     
                 
        while self.parameter_tabs.count() > 0:
            self.parameter_tabs.removeTab(0)
        
                      
        if is_full_analysis:
                                               
            self.parameter_tabs.addTab(self.load_disp_page, "荷载输入")
            self.parameter_tabs.addTab(self.pile_type_page, "桩基定义")
            self.parameter_tabs.addTab(self.pile_list_page, "桩基布置")
            self.parameter_tabs.setCurrentIndex(0)
        else:
                                                  
                         
            self.parameter_tabs.addTab(self.pile_type_page, "桩基定义")
            self.parameter_tabs.addTab(self.pile_list_page, "桩基布置")
            self.parameter_tabs.setCurrentIndex(0)
        
                                
        self.case_type_group.setVisible(is_full_analysis)
        
                                        
        if not is_full_analysis:
            self.single_case_radio.setChecked(True)
                                                                
        
                             
        is_single_case = self.single_case_radio.isChecked()
        if is_full_analysis:
            if is_single_case:
                self.load_group.setVisible(True)
                self.disp_group.setVisible(False)                                                                    
                self.multi_case_group.setVisible(False)
            else:
                self.load_group.setVisible(False)
                self.disp_group.setVisible(False)
                self.multi_case_group.setVisible(True)
                self.multi_case_group.setTitle(
                    "Multiple Load Input (Simultaneous Action)" if get_language() == "en" else "多荷载输入（同时作用）"
                )
                self._update_multi_case_headers()
        else:
                                                   
            self.load_group.setVisible(False)
            self.disp_group.setVisible(False)
            self.multi_case_group.setVisible(False)
        
                             
        self.single_pile_widget.setVisible(is_single_pile)
        

        show_simu = True 
        
        self.simu_group.setVisible(show_simu)
        self.use_simulative_pile_checkbox.setVisible(show_simu)
        
                                     
        if is_foundation:
             self.use_simulative_pile_checkbox.setText("启用模拟桩（刚度模式）")
             self.disp_group.setTitle("承台中心位移")
        elif is_single_pile:
             self.use_simulative_pile_checkbox.setText("启用模拟桩（单桩刚度）")
             self.disp_group.setTitle("承台中心位移")
        else:
             self.use_simulative_pile_checkbox.setText("启用承台土抗力模拟")
             self.disp_group.setTitle("承台中心位移")

        
                        
                        
        if self.case_type == "新建工况":
            self.wizard_stack.setCurrentIndex(1)
            self.calculate_button.setEnabled(True)
            self.save_case_button.setVisible(True)
            self.save_case_button.setEnabled(True)
            self.export_case_button.setVisible(False)
        elif self.case_type == "现有工况" and self.case_imported:
                     
            self.calculate_button.setEnabled(True)
            self.save_case_button.setVisible(False)
                         
            self.export_case_button.setVisible(True)
            self.export_case_button.setEnabled(True)
            
                                         
            if is_single_pile:
                self.wizard_stack.setCurrentIndex(1)
                self.parameter_tabs.setCurrentIndex(1)            
                self.direct_calc_button.setVisible(False)            
            
        else:
                            
            self.wizard_stack.setCurrentIndex(0)
            self.calculate_button.setEnabled(False)
            self.save_case_button.setVisible(False)
            self.export_case_button.setVisible(False)

    def _add_cap_row_with_help(self, form_layout, label_text, widget, help_text):
        row_layout = QHBoxLayout()
        row_layout.addWidget(widget)
        help_btn = QToolButton()
        help_btn.setText("?")
        help_btn.setFixedSize(16, 16)
        help_btn.setStyleSheet("""
            QToolButton {
                background-color: #2196F3;
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 9px;
                padding: 0px;
            }
            QToolButton:hover {
                background-color: #1976D2;
            }
        """)
        help_btn.setToolTip("点击查看参数说明")
        help_btn.clicked.connect(lambda: QMessageBox.information(self, "参数说明", help_text))
        row_layout.addWidget(help_btn)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_widget = QWidget()
        row_widget.setLayout(row_layout)
        form_layout.addRow(label_text, row_widget)

                                                          


    def _generate_virtual_pile_data(self) -> Dict:
        try:
                      
            kx = float(self.stiffness_inputs['kx'].text() or 0)
            ky = float(self.stiffness_inputs['ky'].text() or 0)
            kz = float(self.stiffness_inputs['kz'].text() or 0)
            rx = float(self.stiffness_inputs['rx'].text() or 0)
            ry = float(self.stiffness_inputs['ry'].text() or 0)
            rz = float(self.stiffness_inputs['rz'].text() or 0)
            
                      
            virtual_pile = {
                'x': 0.0,
                'y': 0.0,
                'control_id': -1,                  
                'stiffness_diagonal': [kx, ky, kz, rx, ry, rz]
            }
            
            logger.info(f"模拟桩刚度: {[kx, ky, kz, rx, ry, rz]}")
            return virtual_pile
            
        except ValueError as e:
            logger.error(f"刚度数据格式错误: {e}")
            raise ValueError("模拟桩刚度数值格式错误")
        
        return virtual_pile

                         

    @Slot()
    def _add_pile_type(self):
                   
        help_text = (
            "桩类型命名建议：\n\n"
            "• 按几何尺寸：D150-L30 (直径1.5m，长30m)\n"
            "• 按位置功能：左桥墩桩、桥台桩\n"
            "• 按受力特性：摩擦桩、端承桩\n\n"
            "请输入有意义的名称，方便后续管理。"
        )
        
        name, ok = QInputDialog.getText(
            self, "新建桩类型", 
            help_text + "\n" + "-" * 50 + "\n请输入类型名称:"
        )
        
        if ok and name:
            name = name.strip()
            if not name:
                QMessageBox.warning(self, "错误", "类型名称不能为空")
                return
            if name in self.pile_type_names:
                QMessageBox.warning(self, "错误", f"类型 '{name}' 已存在")
                return
            
            self.pile_type_names.append(name)
            
            editor = PileTypeEditor()
            self.pile_type_editors[name] = editor
            self.pile_type_editor_stack.addWidget(editor)
            
            self.pile_type_combo.addItem(name)
            self.pile_type_combo.setCurrentText(name)
            
            self._update_pile_table_combos()
            logger.info(f"创建桩类型: {name}")
            
                      
            QMessageBox.information(
                self, "创建成功",
                f"已创建桩类型 '{name}'\n\n"
                f"请在下方编辑器中完善该类型的详细参数。\n"
                f"单击参数名称旁的 ? 按钮可查看参考值。"
            )

    @Slot()
    def _delete_pile_type(self):
        name = self.pile_type_combo.currentText()
        if not name:
            return

        if len(self.pile_type_names) <= 1:
            QMessageBox.warning(self, "错误", "至少需要保留一个桩类型")
            return

        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除桩类型 '{name}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            idx = self.pile_type_names.index(name)
            self.pile_type_names.remove(name)

            editor = self.pile_type_editors.pop(name)
            self.pile_type_editor_stack.removeWidget(editor)
            editor.deleteLater()

            self.pile_type_combo.removeItem(idx)
            self._update_pile_table_combos()
            logger.info(f"删除桩类型: {name}")

    @Slot()
    def _rename_pile_type(self):
        old_name = self.pile_type_combo.currentText()
        if not old_name:
            return
        
        new_name, ok = QInputDialog.getText(
            self, "重命名桩类型", 
            f"当前名称: {old_name}\n\n请输入新名称:",
            text=old_name
        )
        
        if ok and new_name:
            new_name = new_name.strip()
            if new_name == old_name:
                return
            if not new_name:
                QMessageBox.warning(self, "错误", "类型名称不能为空")
                return
            if new_name in self.pile_type_names:
                QMessageBox.warning(self, "错误", f"类型 '{new_name}' 已存在")
                return
            
            idx = self.pile_type_names.index(old_name)
            self.pile_type_names[idx] = new_name
            
            self.pile_type_editors[new_name] = self.pile_type_editors.pop(old_name)
            self.pile_type_combo.setItemText(idx, new_name)
            
            self._update_pile_table_combos()
            logger.info(f"重命名桩类型: {old_name} -> {new_name}")

    @Slot(str)
    def _on_pile_type_changed(self, name: str):
        if name in self.pile_type_editors:
            editor = self.pile_type_editors[name]
            idx = self.pile_type_editor_stack.indexOf(editor)
            if idx >= 0:
                self.pile_type_editor_stack.setCurrentIndex(idx)

    def _update_pile_table_combos(self):
        for row in range(self.pile_table.rowCount()):
            widget = self.pile_table.cellWidget(row, 3)
            if widget and isinstance(widget, QComboBox):
                current = widget.currentText()
                widget.clear()
                widget.addItems(self.pile_type_names)
                if current in self.pile_type_names:
                    widget.setCurrentText(current)
                elif self.pile_type_names:
                    widget.setCurrentIndex(0)

    @Slot()
    def _add_pile_row(self):
        row = self.pile_table.rowCount()
        self.pile_table.insertRow(row)

        item0 = QTableWidgetItem(str(row + 1))
        item0.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pile_table.setItem(row, 0, item0)

        item1 = QTableWidgetItem("0.0")
        item1.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pile_table.setItem(row, 1, item1)

        item2 = QTableWidgetItem("0.0")
        item2.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pile_table.setItem(row, 2, item2)

        combo = QComboBox()
        combo.addItems(self.pile_type_names)
        self.pile_table.setCellWidget(row, 3, combo)
        
        self._update_table_height(self.pile_table, min_units=0, rows_per_unit=1)
        self._update_pile_count_limit()

    @Slot()
    def _delete_pile_row(self):
        rows = set(item.row() for item in self.pile_table.selectedItems())
        for row in sorted(rows, reverse=True):
            self.pile_table.removeRow(row)

        for row in range(self.pile_table.rowCount()):
            item = self.pile_table.item(row, 0)
            if item:
                item.setText(str(row + 1))
        
        self._update_table_height(self.pile_table, min_units=0, rows_per_unit=1)
        self._update_pile_count_limit()

    def _update_pile_count_limit(self):
        if not hasattr(self, 'pile_ino_input'):
            return
            
        count = self.pile_table.rowCount()
                                                
                            
        max_val = max(1, count)
        
                         
        old_max = self.pile_ino_input.maximum()
        
        if old_max != max_val:
            self.pile_ino_input.setMaximum(max_val)
            
                                            
            if self.pile_ino_input.value() > max_val:
                self.pile_ino_input.setValue(max_val)
            
                                       
            if self.pile_ino_input.value() == 0 and count > 0:
                 self.pile_ino_input.setValue(1)

    @Slot()
    def _add_simu_pile_row(self):
        is_matrix_mode = self.simu_type_matrix_radio.isChecked()
        
        if is_matrix_mode:
            self._add_simu_pile_matrix_row()
        else:
            self._add_simu_pile_diagonal_row()
    
    def _add_simu_pile_diagonal_row(self):
                
        current_rows = self.simu_pile_table.rowCount()
        group_index = (current_rows // 4) + 1
        base_row = current_rows
        
              
        for _ in range(4):
            self.simu_pile_table.insertRow(self.simu_pile_table.rowCount())
            
              
        header_brush = QBrush(QColor("#f5f5f5"))
        header_font = QFont()
        header_font.setBold(True)
        small_height = 25
        normal_height = 30
        
                                        
        self.simu_pile_table.setRowHeight(base_row, small_height)
        
        headers_geo = ["模拟桩号", "X 坐标 (m)", "Y 坐标 (m)"]
        for i, text in enumerate(headers_geo):
            col = i * 2
            item = QTableWidgetItem(text)
            item.setFlags(Qt.ItemIsEnabled)
            item.setBackground(header_brush)
            item.setFont(header_font)
            item.setTextAlignment(Qt.AlignCenter)
            self.simu_pile_table.setItem(base_row, col, item)
            self.simu_pile_table.setSpan(base_row, col, 1, 2)
            
                                        
        self.simu_pile_table.setRowHeight(base_row + 1, normal_height)
        
                    
        item_no = QTableWidgetItem(f"No. {group_index} [对角线]")
        item_no.setFlags(Qt.ItemIsEnabled)
        item_no.setTextAlignment(Qt.AlignCenter)
        self.simu_pile_table.setItem(base_row + 1, 0, item_no)
        self.simu_pile_table.setSpan(base_row + 1, 0, 1, 2)
        
                 
        item_x = QTableWidgetItem("0.0")
        item_x.setTextAlignment(Qt.AlignCenter)
        item_x.setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsSelectable)
        self.simu_pile_table.setItem(base_row + 1, 2, item_x)
        self.simu_pile_table.setSpan(base_row + 1, 2, 1, 2)
        
                 
        item_y = QTableWidgetItem("0.0")
        item_y.setTextAlignment(Qt.AlignCenter)
        item_y.setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsSelectable)
        self.simu_pile_table.setItem(base_row + 1, 4, item_y)
        self.simu_pile_table.setSpan(base_row + 1, 4, 1, 2)
        
                                         
        self.simu_pile_table.setRowHeight(base_row + 2, small_height)
        
        headers_stiff = ["Kx", "Ky", "Kz", "Rx", "Ry", "Rz"]
        for i, text in enumerate(headers_stiff):
            item = QTableWidgetItem(text)
            item.setFlags(Qt.ItemIsEnabled)
            item.setBackground(header_brush)
            item.setFont(header_font)
            item.setTextAlignment(Qt.AlignCenter)
            self.simu_pile_table.setItem(base_row + 2, i, item)
            
                                         
        self.simu_pile_table.setRowHeight(base_row + 3, normal_height)
        
        for i in range(6):
            item = QTableWidgetItem("0.0")
            item.setTextAlignment(Qt.AlignCenter)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsSelectable)
            self.simu_pile_table.setItem(base_row + 3, i, item)

        self._update_table_height(self.simu_pile_table, min_units=2, rows_per_unit=4)
    
    def _add_simu_pile_matrix_row(self):
                
        current_rows = self.simu_pile_table.rowCount()
        group_index = (current_rows // 9) + 1
        base_row = current_rows
        
                                     
        for _ in range(9):
            self.simu_pile_table.insertRow(self.simu_pile_table.rowCount())
            
              
        header_brush = QBrush(QColor("#f5f5f5"))
        header_font = QFont()
        header_font.setBold(True)
        small_height = 25
        normal_height = 28
        
                                        
        self.simu_pile_table.setRowHeight(base_row, small_height)
        
        headers_geo = ["模拟桩号", "X 坐标 (m)", "Y 坐标 (m)"]
        for i, text in enumerate(headers_geo):
            col = i * 2
            item = QTableWidgetItem(text)
            item.setFlags(Qt.ItemIsEnabled)
            item.setBackground(header_brush)
            item.setFont(header_font)
            item.setTextAlignment(Qt.AlignCenter)
            self.simu_pile_table.setItem(base_row, col, item)
            self.simu_pile_table.setSpan(base_row, col, 1, 2)
            
                                        
        self.simu_pile_table.setRowHeight(base_row + 1, normal_height)
        
                    
        item_no = QTableWidgetItem(f"No. {group_index} [全矩阵]")
        item_no.setFlags(Qt.ItemIsEnabled)
        item_no.setTextAlignment(Qt.AlignCenter)
        self.simu_pile_table.setItem(base_row + 1, 0, item_no)
        self.simu_pile_table.setSpan(base_row + 1, 0, 1, 2)
        
                 
        item_x = QTableWidgetItem("0.0")
        item_x.setTextAlignment(Qt.AlignCenter)
        item_x.setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsSelectable)
        self.simu_pile_table.setItem(base_row + 1, 2, item_x)
        self.simu_pile_table.setSpan(base_row + 1, 2, 1, 2)
        
                 
        item_y = QTableWidgetItem("0.0")
        item_y.setTextAlignment(Qt.AlignCenter)
        item_y.setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsSelectable)
        self.simu_pile_table.setItem(base_row + 1, 4, item_y)
        self.simu_pile_table.setSpan(base_row + 1, 4, 1, 2)
        
                                              
        self.simu_pile_table.setRowHeight(base_row + 2, small_height)
        
                        
        item_title = QTableWidgetItem("全量刚度矩阵 (6×6)")
        item_title.setFlags(Qt.ItemIsEnabled)
        item_title.setBackground(header_brush)
        item_title.setFont(header_font)
        item_title.setTextAlignment(Qt.AlignCenter)
        self.simu_pile_table.setItem(base_row + 2, 0, item_title)
        self.simu_pile_table.setSpan(base_row + 2, 0, 1, 6)        
            
                                                 
        for row_idx in range(6):
            actual_row = base_row + 3 + row_idx
            self.simu_pile_table.setRowHeight(actual_row, normal_height)
            
            for col_idx in range(6):
                                
                default_val = "0.0"
                item = QTableWidgetItem(default_val)
                item.setTextAlignment(Qt.AlignCenter)
                          
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsSelectable)
                self.simu_pile_table.setItem(actual_row, col_idx, item)

        self._update_table_height(self.simu_pile_table, min_units=2, rows_per_unit=9)

    @Slot()
    def _delete_simu_pile_row(self):
        is_matrix_mode = self.simu_type_matrix_radio.isChecked()
        rows_per_pile = 9 if is_matrix_mode else 4
        
        current_row = self.simu_pile_table.currentRow()
        row_count = self.simu_pile_table.rowCount()
        
        if row_count < rows_per_pile:
            return

        target_base_row = -1
        
        if current_row < 0:
                        
            target_base_row = row_count - rows_per_pile
        else:
                               
            target_base_row = (current_row // rows_per_pile) * rows_per_pile
            
        if target_base_row >= 0:
                      
            for _ in range(rows_per_pile):
                self.simu_pile_table.removeRow(target_base_row)
                
                  
            new_row_count = self.simu_pile_table.rowCount()
            type_label = "[全矩阵]" if is_matrix_mode else "[对角线]"
            for base in range(target_base_row, new_row_count, rows_per_pile):
                idx = (base // rows_per_pile) + 1
                            
                item = self.simu_pile_table.item(base + 1, 0)
                if item:
                    item.setText(f"No. {idx} {type_label}")

        self._update_table_height(self.simu_pile_table, min_units=2, rows_per_unit=rows_per_pile)

    @Slot(int)
    def _on_simulative_pile_toggled(self, state):
                            
        is_checked = self.use_simulative_pile_checkbox.isChecked()
        
                      
        self.simu_type_widget.setVisible(is_checked)
        self.simu_pile_table.setVisible(is_checked)
        
        if hasattr(self, 'btn_add_simu'):
            self.btn_add_simu.setVisible(is_checked)
        if hasattr(self, 'btn_del_simu'):
            self.btn_del_simu.setVisible(is_checked)
        
                          
        if is_checked and self.simu_pile_table.rowCount() == 0:
            self._add_simu_pile_row()
    
    @Slot(bool)
    def _on_simu_type_changed(self, checked):
        if not checked:
            return             
        
               
        is_new_matrix = self.simu_type_matrix_radio.isChecked()
        
                       
        saved_piles = []
        row_count = self.simu_pile_table.rowCount()
        
        if row_count > 0:
                                   
            first_label = self.simu_pile_table.item(1, 0)
            is_old_matrix = first_label and "[全矩阵]" in first_label.text() if first_label else False
            old_rows_per_pile = 9 if is_old_matrix else 4
            
            pile_count = row_count // old_rows_per_pile
            
            for pile_idx in range(pile_count):
                base_row = pile_idx * old_rows_per_pile
                pile_data = {'x': 0.0, 'y': 0.0, 'stiffness': [0.0] * 6, 'matrix': [[0.0] * 6 for _ in range(6)]}
                
                try:
                                                         
                    x_item = self.simu_pile_table.item(base_row + 1, 2)
                    y_item = self.simu_pile_table.item(base_row + 1, 4)
                    pile_data['x'] = float(x_item.text()) if x_item else 0.0
                    pile_data['y'] = float(y_item.text()) if y_item else 0.0
                    
                    if is_old_matrix:
                                                         
                        for i in range(6):
                            for j in range(6):
                                item = self.simu_pile_table.item(base_row + 3 + i, j)
                                pile_data['matrix'][i][j] = float(item.text()) if item else 0.0
                               
                        pile_data['stiffness'] = [pile_data['matrix'][i][i] for i in range(6)]
                    else:
                                              
                        for i in range(6):
                            item = self.simu_pile_table.item(base_row + 3, i)
                            pile_data['stiffness'][i] = float(item.text()) if item else 0.0
                                
                        for i in range(6):
                            pile_data['matrix'][i][i] = pile_data['stiffness'][i]
                except Exception as e:
                    logger.warning(f"读取模拟桩{pile_idx+1}数据失败: {e}")
                
                saved_piles.append(pile_data)
        
              
        self.simu_pile_table.setRowCount(0)
        
                        
        if len(saved_piles) == 0:
            saved_piles = [{'x': 0.0, 'y': 0.0, 'stiffness': [0.0] * 6, 'matrix': [[0.0] * 6 for _ in range(6)]}]
        
        for pile_data in saved_piles:
            if is_new_matrix:
                self._add_simu_pile_matrix_row()
                      
                row_count = self.simu_pile_table.rowCount()
                base_row = row_count - 9
                
                    
                x_item = self.simu_pile_table.item(base_row + 1, 2)
                y_item = self.simu_pile_table.item(base_row + 1, 4)
                if x_item:
                    x_item.setText(f"{pile_data['x']:.4f}")
                if y_item:
                    y_item.setText(f"{pile_data['y']:.4f}")
                
                     
                for i in range(6):
                    for j in range(6):
                        item = self.simu_pile_table.item(base_row + 3 + i, j)
                        if item:
                            item.setText(f"{pile_data['matrix'][i][j]:.4f}")
            else:
                self._add_simu_pile_diagonal_row()
                      
                row_count = self.simu_pile_table.rowCount()
                base_row = row_count - 4
                
                    
                x_item = self.simu_pile_table.item(base_row + 1, 2)
                y_item = self.simu_pile_table.item(base_row + 1, 4)
                if x_item:
                    x_item.setText(f"{pile_data['x']:.4f}")
                if y_item:
                    y_item.setText(f"{pile_data['y']:.4f}")
                
                      
                for i in range(6):
                    item = self.simu_pile_table.item(base_row + 3, i)
                    if item:
                        item.setText(f"{pile_data['stiffness'][i]:.4f}")
    
    def _get_simu_pile_count(self):
        row_count = self.simu_pile_table.rowCount()
        if self.simu_type_diagonal_radio.isChecked():
            return row_count // 4                
        else:
            return row_count // 9                

    def _batch_add_piles(self):

        dialog = QDialog(self)
        dialog.setWindowTitle("批量添加桩位")
        dialog.setMinimumWidth(350)
        layout = QFormLayout(dialog)

        rows_spin = QSpinBox()
        rows_spin.setRange(1, 20)
        rows_spin.setValue(2)
        layout.addRow("行数:", rows_spin)

        cols_spin = QSpinBox()
        cols_spin.setRange(1, 20)
        cols_spin.setValue(2)
        layout.addRow("列数:", cols_spin)

        spacing_x = QDoubleSpinBox()
        spacing_x.setRange(0.1, 100)
        spacing_x.setValue(3.0)
        spacing_x.setSuffix(" m")
        layout.addRow("X 方向间距:", spacing_x)

        spacing_y = QDoubleSpinBox()
        spacing_y.setRange(0.1, 100)
        spacing_y.setValue(3.0)
        spacing_y.setSuffix(" m")
        layout.addRow("Y 方向间距:", spacing_y)

        center_x = QDoubleSpinBox()
        center_x.setRange(-1000, 1000)
        center_x.setValue(0.0)
        center_x.setSuffix(" m")
        layout.addRow("中心 X:", center_x)

        center_y = QDoubleSpinBox()
        center_y.setRange(-1000, 1000)
        center_y.setValue(0.0)
        center_y.setSuffix(" m")
        layout.addRow("中心 Y:", center_y)

        type_combo = QComboBox()
        if self.pile_type_names:
            type_combo.addItems(self.pile_type_names)
        else:
            type_combo.addItem("(无类型)")
        layout.addRow("桩类型:", type_combo)

        clear_existing = QComboBox()
        clear_existing.addItems(["清空现有桩位", "追加到现有桩位"])
        layout.addRow("添加方式:", clear_existing)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            n_rows = rows_spin.value()
            n_cols = cols_spin.value()
            dx = spacing_x.value()
            dy = spacing_y.value()
            cx = center_x.value()
            cy = center_y.value()
            pile_type = type_combo.currentText()
            should_clear = (clear_existing.currentIndex() == 0)

            if should_clear:
                self.pile_table.setRowCount(0)

            start_x = cx - (n_cols - 1) * dx / 2
            start_y = cy - (n_rows - 1) * dy / 2

            start_no = self.pile_table.rowCount() + 1

            for i in range(n_rows):
                for j in range(n_cols):
                    x = start_x + j * dx
                    y = start_y + i * dy

                    row = self.pile_table.rowCount()
                    self.pile_table.insertRow(row)

                    item0 = QTableWidgetItem(str(start_no + i * n_cols + j))
                    item0.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.pile_table.setItem(row, 0, item0)

                    item1 = QTableWidgetItem(f"{x:.3f}")
                    item1.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.pile_table.setItem(row, 1, item1)

                    item2 = QTableWidgetItem(f"{y:.3f}")
                    item2.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.pile_table.setItem(row, 2, item2)

                    combo = QComboBox()
                    combo.addItems(self.pile_type_names)
                    if pile_type in self.pile_type_names:
                        combo.setCurrentText(pile_type)
                    self.pile_table.setCellWidget(row, 3, combo)
            
                            
                            
            self._update_table_height(self.pile_table, min_units=0, rows_per_unit=1)
            self._update_pile_count_limit()
            logger.info(f"批量添加 {n_rows * n_cols} 个桩位")

    @Slot()

    
                                                                             
          
                                                                             

    @Slot()
    def _import_dat_file(self, filename: str = None):
        dat_file = filename
        
        if not dat_file:
            dat_file, _ = QFileDialog.getOpenFileName(
                self,
                "选择要导入的DAT文件",
                str(Path.cwd()),
                "DAT文件 (*.dat);;所有文件 (*)"
            )
        
        if not dat_file:
                                        
            return
        
        try:
            from dat_parser import DATParser
            
            self.update_status(f"正在验证 {Path(dat_file).name}...")
            with open(dat_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if '[CONTRAL]' not in content and '[CONTROL]' not in content:
                QMessageBox.warning(
                    self, "格式错误",
                    f"文件格式不正确:\n"
                    f"{Path(dat_file).name}\n\n"
                    f"这不是有效的桩基分析输入文件\n"
                    f"(缺少必要的控制块)"
                )
                self.update_status("导入已取消")
                return
            
            if '[ARRANGE]' not in content:
                QMessageBox.warning(
                    self, "格式错误",
                    f"文件格式不正确:\n"
                    f"{Path(dat_file).name}\n\n"
                    f"缺少 [ARRANGE] 块（桩位布置）"
                )
                self.update_status("导入已取消")
                return
            
            self.update_status(f"正在解析 {Path(dat_file).name}...")
            parser = DATParser()
            gui_data = parser.parse_file(dat_file)
            
            if not gui_data.get('piles'):
                QMessageBox.warning(
                    self, "解析失败",
                    f"未能从文件中解析出桩位数据\n"
                    f"{Path(dat_file).name}\n\n"
                    f"请检查文件格式是否正确"
                )
                self.update_status("导入失败")
                return
            
            if not gui_data.get('pile_types'):
                QMessageBox.warning(
                    self, "解析失败",
                    f"未能从文件中解析出桩类型定义\n"
                    f"{Path(dat_file).name}\n\n"
                    f"请检查 [NO_SIMU] 块是否完整"
                )
                self.update_status("导入失败")
                return
            
            simu_str = "启用" if gui_data.get('has_simulative') else "未启用"
            if gui_data.get('has_simulative') and gui_data.get('simulative_piles'):
                 simu_str += f" ({len(gui_data.get('simulative_piles', []))}根)"

            reply = QMessageBox.question(
                self, "确认导入",
                f"即将导入以下数据:\n\n"
                f"• 文件名称: {Path(dat_file).name}\n"
                f"• 计算模式: {self.mode_names[gui_data['mode']]}\n"
                f"• 桩基数量: {len(gui_data['piles'])} 根\n"
                f"• 模拟桩基: {simu_str}\n\n"
                f"注意：导入将覆盖当前未保存的设置，是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                self.update_status("导入已取消")
                return
            
            self._load_gui_data(gui_data)
            
                           
            self.case_imported = True
            self._imported_filename = Path(dat_file).name
            
                             
            is_first_import = not hasattr(self, '_has_ever_imported') or not self._has_ever_imported
            self._has_ever_imported = True
            
                          
            if get_language() == "en":
                filename = _translate_to_english(os.path.basename(self._imported_filename))
                self.import_status_label.setText(f"✓ Imported existing case: {filename}")
            else:
                filename = _translate_to_english(os.path.basename(self._imported_filename)) if get_language() == "en" else self._imported_filename
                self.import_status_label.setText(
                    f"✓ Imported existing case: {filename}" if get_language() == "en" else f"✓ 已导入现有工况: {self._imported_filename}"
                )
            self.import_status_label.setVisible(True)
            self.import_button.setVisible(False)          
            
                                                
                                           
            
                                
            self.view_modify_button.setText("查看与修改")
            self.view_modify_button.setToolTip("查看或修改导入的工况参数")
            self.view_modify_button.setVisible(True)
            self.direct_calc_button.setVisible(True)
            
                    
            try:
                self.view_modify_button.clicked.disconnect()
            except TypeError:
                pass
            self.view_modify_button.clicked.connect(self._show_parameter_tabs)
            
                                     
            self.wizard_stack.setCurrentIndex(0)
            self.calculate_button.setEnabled(False)                  
            self.export_case_button.setVisible(False)
            
                     
            self.placeholder_label.setText("↑ 请点击【查看与修改】或【直接计算】")
            
                                    
            if not is_first_import:
                logger.info("更换文件，重置UI状态")
            
                      
            simu_info = ""
            if gui_data.get('has_simulative'):
                simu_count = len(gui_data.get('simulative_piles', []))
                simu_info = f"- 模拟桩: {simu_count} 根 (已自动启用承台土抗力模拟)\n"
            
            QMessageBox.information(
                self, "导入成功",
                f"已成功导入:\n"
                f"- 计算模式: {self.mode_names[gui_data['mode']]}\n"
                f"- 桩数量: {len(gui_data['piles'])}\n"
                f"- 桩类型数: {len(gui_data['pile_types'])}\n"
                f"{simu_info}\n"
                f"点击【查看与修改】编辑参数\n"
                f"或点击【直接计算】开始计算"
            )
            
            imported_name = _translate_to_english(Path(dat_file).name) if get_language() == "en" else Path(dat_file).name
            self.update_status(
                f"Imported {imported_name}" if get_language() == "en" else f"已导入 {Path(dat_file).name}"
            )
            logger.info(f"成功导入DAT文件: {dat_file}")
            
        except ImportError:
            QMessageBox.critical(
                self, "错误",
                "无法导入 dat_parser 模块\n"
                "请确保 dat_parser.py 在程序目录下"
            )
            self.update_status("导入失败")
        except UnicodeDecodeError:
            QMessageBox.critical(
                self, "编码错误",
                f"无法读取文件:\n"
                f"{Path(dat_file).name}\n\n"
                f"文件编码不是UTF-8，可能是二进制文件或其他编码"
            )
            self.update_status("导入失败")
        except Exception as e:
            logger.exception("导入DAT文件失败")
            QMessageBox.critical(
                self, "导入失败",
                f"无法导入DAT文件:\n"
                f"{Path(dat_file).name}\n\n"
                f"错误详情: {str(e)}\n\n"
                f"请检查:\n"
                f"1. 文件格式是否正确\n"
                f"2. 文件是否完整\n"
                f"3. 查看日志获取详细信息"
            )
            self.update_status("导入失败")
    
    def _load_gui_data(self, gui_data: Dict[str, Any]):
        mode = gui_data.get('mode', 0)
        self.mode_button_group.button(mode).setChecked(True)
        self._on_mode_selected(mode)
        
        while self.pile_type_names:
            name = self.pile_type_names[0]
            editor = self.pile_type_editors.pop(name)
            self.pile_type_editor_stack.removeWidget(editor)
            editor.deleteLater()
            self.pile_type_names.remove(name)
        self.pile_type_combo.clear()
        
        for type_name, params in gui_data['pile_types'].items():
            self.pile_type_names.append(type_name)
            editor = PileTypeEditor()
            editor.set_data(params)
            self.pile_type_editors[type_name] = editor
            self.pile_type_editor_stack.addWidget(editor)
            self.pile_type_combo.addItem(type_name)
        
        if self.pile_type_names:
            self.pile_type_combo.setCurrentIndex(0)
        
        self.pile_table.setRowCount(0)
        for pile in gui_data['piles']:
            row = self.pile_table.rowCount()
            self.pile_table.insertRow(row)
            
            item0 = QTableWidgetItem(str(pile['no']))
            item0.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.pile_table.setItem(row, 0, item0)
            
            item1 = QTableWidgetItem(f"{pile['x']:.3f}")
            item1.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.pile_table.setItem(row, 1, item1)
            
            item2 = QTableWidgetItem(f"{pile['y']:.3f}")
            item2.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.pile_table.setItem(row, 2, item2)
            
            combo = QComboBox()
            combo.addItems(self.pile_type_names)
            if pile['type'] in self.pile_type_names:
                combo.setCurrentText(pile['type'])
            self.pile_table.setCellWidget(row, 3, combo)
        
                                                    
        self._update_table_height(self.pile_table, min_units=0, rows_per_unit=1)
        self._update_pile_count_limit()
        
                
        if hasattr(self, 'pile_ino_input'):
            try:
                          
                pile_no = int(gui_data.get('calc_pile_no', 1))
                max_val = self.pile_ino_input.maximum()
                if pile_no > max_val:
                    pile_no = max_val
                if pile_no < 1 and max_val >= 1:
                    pile_no = 1
                self.pile_ino_input.setValue(pile_no)
            except Exception:
                pass
        
                  
        is_multi_case = gui_data.get('is_multi_case', False)
        load_cases = gui_data.get('load_cases', [])
        
        if is_multi_case and len(load_cases) > 1:
                   
            self.multi_case_radio.setChecked(True)
            self.single_case_radio.setChecked(False)
            self._on_case_type_changed(True)                 
            
                                    
            self.multi_case_table.setRowCount(0)
            
                                 
                                                                                          
            is_full_analysis = (mode == 2)
            if is_full_analysis:
                keys = ['fx', 'fy', 'fz', 'mx', 'my', 'mz']
            else:
                                                                                     
                                                                         
                keys = ['ux', 'uy', 'uz', 'thetax', 'thetay', 'thetaz']
            
            for idx, case in enumerate(load_cases, 1):
                                                
                self._add_load_case_row()
                
                base_row = (idx - 1) * 4
                
                                                      
                x_item = self.multi_case_table.item(base_row + 1, 2)
                if x_item:
                    x_item.setText(str(case.get('x', 0.0)))
                
                y_item = self.multi_case_table.item(base_row + 1, 4)
                if y_item:
                    y_item.setText(str(case.get('y', 0.0)))
                
                                                   
                for col, key in enumerate(keys):
                    item = self.multi_case_table.item(base_row + 3, col)
                    if item:
                        item.setText(str(case.get(key, 0.0)))
            
                       
            self._update_case_select_combo()
            
                     
            mode_desc = "荷载" if is_full_analysis else "刚度"
            QMessageBox.information(self, "导入成功", f"已导入 {len(load_cases)} 个{mode_desc}工况")
        else:
                   
            self.single_case_radio.setChecked(True)
            self.multi_case_radio.setChecked(False)
        
        if 'loads' in gui_data:
            loads = gui_data['loads']
                     
            self.load_x_input.setText(str(loads.get('x', 0.0)))
            self.load_y_input.setText(str(loads.get('y', 0.0)))
            
            self.loads['nx'].clear()
            self.loads['nx'].setText(str(loads.get('fx', 0.0)))
            self.loads['ny'].clear()
            self.loads['ny'].setText(str(loads.get('fy', 0.0)))
            self.loads['nz'].clear()
            self.loads['nz'].setText(str(loads.get('fz', 0.0)))
            self.loads['mx'].clear()
            self.loads['mx'].setText(str(loads.get('mx', 0.0)))
            self.loads['my'].clear()
            self.loads['my'].setText(str(loads.get('my', 0.0)))
            self.loads['mz'].clear()
            self.loads['mz'].setText(str(loads.get('mz', 0.0)))
        
        if 'disps' in gui_data:
            disps = gui_data['disps']
                     
            self.disp_x_input.setText(str(disps.get('x', 0.0)))
            self.disp_y_input.setText(str(disps.get('y', 0.0)))
            
            for key in ['ux', 'uy', 'uz', 'thetax', 'thetay', 'thetaz']:
                if key in self.disps:
                    self.disps[key].clear()
                    self.disps[key].setText(str(disps.get(key, 0.0)))
        
        if 'cap' in gui_data:
            cap = gui_data['cap']
            has_cap_data = False
            if cap.get('length', 0.0) > 0:
                self.cap_length_input.setValue(cap['length'])
                has_cap_data = True
            if cap.get('width', 0.0) > 0:
                self.cap_width_input.setValue(cap['width'])
                has_cap_data = True
            if cap.get('thickness', 0.0) > 0:
                self.cap_thickness_input.setValue(cap['thickness'])
                has_cap_data = True
            if cap.get('soil_coef_h', 0.0) > 0:
                self.soil_coef_h_input.setValue(cap['soil_coef_h'])
                has_cap_data = True
            if cap.get('soil_coef_v', 0.0) > 0:
                self.soil_coef_v_input.setValue(cap['soil_coef_v'])
                has_cap_data = True
            
            if has_cap_data and self.current_mode_index == 0:
                              
                self.use_simulative_pile_checkbox.blockSignals(True)
                self.use_simulative_pile_checkbox.setChecked(True)
                self.use_simulative_pile_checkbox.blockSignals(False)
        
                      
        self.simu_pile_table.setRowCount(0)
        self.use_simulative_pile_checkbox.blockSignals(True)
        self.use_simulative_pile_checkbox.setChecked(False)
        self.use_simulative_pile_checkbox.blockSignals(False)
        
                            
        if gui_data.get('has_simulative', False) and gui_data.get('simulative_piles'):
            self._load_simulative_pile_data(gui_data)
        
        logger.info(f"GUI数据加载完成: {len(gui_data['piles'])}根桩, {len(gui_data['pile_types'])}种类型")
    
    def _load_simulative_pile_data(self, gui_data: Dict[str, Any]):
        simu_piles = gui_data.get('simulative_piles', [])
        
                      
        if not simu_piles:
            self.use_simulative_pile_checkbox.setChecked(False)
            return

        try:
                              
            self.simu_pile_table.setRowCount(0)
            
                               
            has_matrix = any(sp.get('type') == 'matrix' or sp.get('stiffness_matrix') for sp in simu_piles)
            has_diagonal = any(sp.get('type') == 'diagonal' or sp.get('stiffness_diagonal') for sp in simu_piles)
            
                                       
            use_matrix_mode = has_matrix
            
                                       
            self.simu_type_diagonal_radio.blockSignals(True)
            self.simu_type_matrix_radio.blockSignals(True)
            if use_matrix_mode:
                self.simu_type_matrix_radio.setChecked(True)
            else:
                self.simu_type_diagonal_radio.setChecked(True)
            self.simu_type_diagonal_radio.blockSignals(False)
            self.simu_type_matrix_radio.blockSignals(False)
            
                                       
            self.use_simulative_pile_checkbox.blockSignals(True)
            self.use_simulative_pile_checkbox.setChecked(True)
            self.use_simulative_pile_checkbox.blockSignals(False)
            
            self.simu_group.setVisible(True)
            self.simu_type_widget.setVisible(True)
            self.simu_pile_table.setVisible(True)
            if hasattr(self, 'btn_add_simu'):
                self.btn_add_simu.setVisible(True)
            if hasattr(self, 'btn_del_simu'):
                self.btn_del_simu.setVisible(True)
            
            for simu_pile in simu_piles:
                self._add_simu_pile_row()
                
                if use_matrix_mode:
                                 
                    base_row = self.simu_pile_table.rowCount() - 9
                    
                                          
                    self.simu_pile_table.item(base_row + 1, 2).setText(str(simu_pile.get('x', 0.0)))
                    self.simu_pile_table.item(base_row + 1, 4).setText(str(simu_pile.get('y', 0.0)))
                    
                                                      
                    matrix = simu_pile.get('stiffness_matrix') or simu_pile.get('stiffness')
                    if matrix and isinstance(matrix, list) and len(matrix) >= 6:
                        for row_idx in range(6):
                            if isinstance(matrix[row_idx], list) and len(matrix[row_idx]) >= 6:
                                for col_idx in range(6):
                                    val = matrix[row_idx][col_idx]
                                    self.simu_pile_table.item(base_row + 3 + row_idx, col_idx).setText(str(val))
                            else:
                                                
                                if row_idx < len(matrix):
                                    val = matrix[row_idx] if not isinstance(matrix[row_idx], list) else matrix[row_idx][0]
                                    self.simu_pile_table.item(base_row + 3 + row_idx, row_idx).setText(str(val))
                else:
                                 
                    base_row = self.simu_pile_table.rowCount() - 4
                    
                                          
                    self.simu_pile_table.item(base_row + 1, 2).setText(str(simu_pile.get('x', 0.0)))
                    self.simu_pile_table.item(base_row + 1, 4).setText(str(simu_pile.get('y', 0.0)))
                    
                                          
                    stiffness = simu_pile.get('stiffness_diagonal') or simu_pile.get('stiffness')
                    
                                         
                    if stiffness and isinstance(stiffness, list):
                        if len(stiffness) >= 6 and isinstance(stiffness[0], list):
                                              
                            diagonal = [stiffness[i][i] if i < len(stiffness[i]) else 0.0 for i in range(6)]
                            stiffness = diagonal
                        
                        if len(stiffness) >= 6:
                            for i in range(6):
                                val = stiffness[i] if not isinstance(stiffness[i], list) else stiffness[i][0]
                                self.simu_pile_table.item(base_row + 3, i).setText(str(val))
            
                                       
            rows_per_pile = 9 if use_matrix_mode else 4
            self._update_table_height(self.simu_pile_table, min_units=0, rows_per_unit=rows_per_pile)
            
            logger.info(f"成功加载 {len(simu_piles)} 个模拟桩 (模式: {'全矩阵' if use_matrix_mode else '对角线'})")
            
        except Exception as e:
            logger.error(f"加载模拟桩数据失败: {e}")
            import traceback
            traceback.print_exc()
            self.use_simulative_pile_checkbox.setChecked(False)
        return




                                                                             
             
                                                                             

    def _collect_gui_data(self):
        pile_types = {}
        for type_name in self.pile_type_names:
            if type_name in self.pile_type_editors:
                pile_types[type_name] = self.pile_type_editors[type_name].get_data()

        if not pile_types:
            raise ValueError("请至少定义一个桩类型")

        piles = []
        for row in range(self.pile_table.rowCount()):
            item0 = self.pile_table.item(row, 0)
            item1 = self.pile_table.item(row, 1)
            item2 = self.pile_table.item(row, 2)
            widget = self.pile_table.cellWidget(row, 3)

            if not (item0 and item1 and item2):
                raise ValueError(f"第 {row + 1} 行桩位数据不完整")

            try:
                no = int(item0.text())
                x = float(item1.text())
                y = float(item2.text())
                pile_type = ""
                if widget and isinstance(widget, QComboBox):
                    pile_type = widget.currentText()

                if pile_type not in pile_types:
                    raise ValueError(
                        f"第 {row + 1} 行桩位使用了未定义的类型: '{pile_type}'"
                    )

                piles.append({'no': no, 'x': x, 'y': y, 'type': pile_type})
            except ValueError as e:
                raise ValueError(f"第 {row + 1} 行桩位数据错误: {e}")

        if not piles:
            raise ValueError("请至少添加一个桩位")

        cap_params = {}

                     
        is_multi_case = self.multi_case_radio.isChecked()
        load_cases = []
        
        if is_multi_case and self.multi_case_table.rowCount() > 0:
                              
                                                                      
            is_full_analysis = self.current_mode_index == 2
            row_count = self.multi_case_table.rowCount()
            
            for base_row in range(0, row_count, 4):
                if base_row + 3 >= row_count:
                    break
                
                try:
                                                       
                    x_item = self.multi_case_table.item(base_row + 1, 2)
                    y_item = self.multi_case_table.item(base_row + 1, 4)
                    x_val = float(x_item.text()) if x_item else 0.0
                    y_val = float(y_item.text()) if y_item else 0.0
                    
                                                     
                    values = []
                    for col in range(6):
                        item = self.multi_case_table.item(base_row + 3, col)
                        val = float(item.text()) if item else 0.0
                        values.append(val)
                    
                    if is_full_analysis:
                              
                        load_cases.append({
                            'x': x_val, 'y': y_val,
                            'fx': values[0], 'fy': values[1], 'fz': values[2],
                            'mx': values[3], 'my': values[4], 'mz': values[5]
                        })
                    else:
                              
                        load_cases.append({
                            'x': x_val, 'y': y_val,
                            'ux': values[0], 'uy': values[1], 'uz': values[2],
                            'thetax': values[3], 'thetay': values[4], 'thetaz': values[5]
                        })
                except ValueError:
                    logger.warning(f"工况 {(base_row//4) + 1} 数据格式错误，已跳过")
                    continue
        else:
                             
            loads_raw = {}
            for key, widget in self.loads.items():
                try:
                    loads_raw[key] = float(widget.text() or 0)
                except ValueError:
                    raise ValueError(f"荷载 {key} 格式错误")
            
                     
            try:
                load_x = float(self.load_x_input.text() or 0)
                load_y = float(self.load_y_input.text() or 0)
            except ValueError:
                load_x, load_y = 0.0, 0.0
            
            loads = {
                'x': load_x,
                'y': load_y,
                'fx': loads_raw.get('nx', 0),
                'fy': loads_raw.get('ny', 0),
                'fz': loads_raw.get('nz', 0),
                'mx': loads_raw.get('mx', 0),
                'my': loads_raw.get('my', 0),
                'mz': loads_raw.get('mz', 0)
            }
            load_cases.append(loads)

                      
        disps = {}
        for key, widget in self.disps.items():
            try:
                disps[key] = float(widget.text() or 0)
            except ValueError:
                raise ValueError(f"位移 {key} 格式错误")
        
                 
        try:
            disp_x = float(self.disp_x_input.text() or 0)
            disp_y = float(self.disp_y_input.text() or 0)
        except ValueError:
            disp_x, disp_y = 0.0, 0.0
        disps['x'] = disp_x
        disps['y'] = disp_y


                                   
        simulative_piles = []
        if self.use_simulative_pile_checkbox.isChecked():
            is_matrix_mode = self.simu_type_matrix_radio.isChecked()
            rows_per_pile = 9 if is_matrix_mode else 4
            row_count = self.simu_pile_table.rowCount()
            
            for base_row in range(0, row_count, rows_per_pile):
                if base_row + rows_per_pile - 1 >= row_count:
                    break
                    
                try:
                                          
                    item_x = self.simu_pile_table.item(base_row + 1, 2)
                    item_y = self.simu_pile_table.item(base_row + 1, 4)
                    
                    x_val = float(item_x.text()) if item_x else 0.0
                    y_val = float(item_y.text()) if item_y else 0.0
                    
                    if is_matrix_mode:
                                                                    
                        matrix = []
                        for row_idx in range(6):
                            row_data = []
                            for col_idx in range(6):
                                item = self.simu_pile_table.item(base_row + 3 + row_idx, col_idx)
                                val = float(item.text()) if item else 0.0
                                row_data.append(val)
                            matrix.append(row_data)
                        
                        sim_pile = {
                            'x': x_val,
                            'y': y_val,
                            'control_id': 1,           
                            'type': 'matrix',
                            'stiffness_matrix': matrix
                        }
                    else:
                                                      
                        stiffness = []
                        for col in range(6):
                            item = self.simu_pile_table.item(base_row + 3, col)
                            val = float(item.text()) if item else 0.0
                            stiffness.append(val)
                        
                        sim_pile = {
                            'x': x_val,
                            'y': y_val,
                            'control_id': -1,           
                            'type': 'diagonal',
                            'stiffness_diagonal': stiffness
                        }
                    
                    simulative_piles.append(sim_pile)
                    
                except ValueError:
                    logger.warning(f"模拟桩第 {(base_row//rows_per_pile) + 1} 组数据格式错误，已跳过")
                    continue
            
            if not simulative_piles:
                logger.warning("模拟桩已启用但未添加有效行")

        return {
            'mode': self.current_mode_index,
            'pile_types': pile_types,
            'piles': piles,
            'load_cases': load_cases,           
            'is_multi_case': is_multi_case,
            'loads': load_cases[0] if load_cases else {},         
            'displacements': disps,
            'cap_params': cap_params,
            'simulative_piles': simulative_piles,
            'has_simulative': self.use_simulative_pile_checkbox.isChecked(),
                     
            'calc_pile_no': self.pile_ino_input.value()
        }

                                                                             
            
                                                                             

    @Slot()
    def save_case(self):
        if self.current_mode_index < 0:
            QMessageBox.warning(self, "错误", "请先选择计算模式")
            return

        if not HAS_DAT_GENERATOR or DATGenerator is None:
            QMessageBox.critical(
                self, "错误",
                "输入生成模块 (dat_generator) 不可用，无法保存工况。"
            )
            return

        gui_data = None
        try:
            gui_data = self._collect_gui_data()
        except ValueError as e:
                                  
            reply = QMessageBox.question(
                self, "数据不完整",
                f"数据收集时发现问题:\n{str(e)}\n\n是否仍然保存？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            
                            
            try:
                pass 
            except:
                pass

                                
        if gui_data is None:
            try:
                                           
                gui_data = {
                    'mode': self.current_mode_index,
                    'calc_pile_no': self.pile_ino_input.value(),
                    'piles': [],
                    'pile_types': {},
                    'cap': {},
                    'loads': {},
                    'disps': {},
                    'simulative_piles': [],
                }
            except:
                return

                            
        mode_name = self.mode_names[self.current_mode_index].replace(":", "-").replace("→", "to")
        timestamp = QDateTime.currentDateTime().toString('yyyyMMdd_HHmmss')
        default_name = f"工况_{mode_name}_{timestamp}.dat"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存工况文件",
            str(Path.cwd() / default_name),
            "DAT文件 (*.dat);;所有文件 (*)"
        )
        
        if not save_path:
            return

        try:
            generator = DATGenerator()
                             
            generator.generate_from_gui_data(gui_data, save_path, skip_validation=True)
            logger.info(f"工况已保存至: {save_path}")
            
                     
            is_multi = gui_data.get('is_multi_case', False)
            load_cases = gui_data.get('load_cases', [])
            case_count = len(load_cases) if load_cases else 1
            case_info = f"工况数: {case_count}" if is_multi else "单工况模式"
            
            QMessageBox.information(
                self, "保存成功",
                f"工况已成功保存至:\n{save_path}\n\n"
                f"模式: {self.mode_names[self.current_mode_index]}\n"
                f"{case_info}\n"
                f"提示: 此文件可能包含未完成的数据，请稍后继续编辑"
            )
            self.update_status(f"已保存工况: {Path(save_path).name}")
        except Exception as e:
            logger.exception("保存工况失败")
            QMessageBox.critical(self, "错误", f"保存工况失败:\n{e}")

    def _collect_single_case_data(self, case_idx: int) -> dict:
                   
        gui_data = self._collect_gui_data()
        
                        
        base_row = case_idx * 4
        is_forward = self.current_mode_index == 0
        
        try:
                
            x_item = self.multi_case_table.item(base_row + 1, 2)
            y_item = self.multi_case_table.item(base_row + 1, 4)
            x_val = float(x_item.text()) if x_item else 0.0
            y_val = float(y_item.text()) if y_item else 0.0
            
                    
            values = []
            for col in range(6):
                item = self.multi_case_table.item(base_row + 3, col)
                val = float(item.text()) if item else 0.0
                values.append(val)
            
            if is_forward:
                single_case = {
                    'x': x_val, 'y': y_val,
                    'fx': values[0], 'fy': values[1], 'fz': values[2],
                    'mx': values[3], 'my': values[4], 'mz': values[5]
                }
                          
                gui_data['load_cases'] = [single_case]
                gui_data['loads'] = single_case
            else:
                                                  
                single_case = {
                    'x': x_val, 'y': y_val,
                    'ux': values[0], 'uy': values[1], 'uz': values[2],
                    'thetax': values[3], 'thetay': values[4], 'thetaz': values[5]
                }
                                          
                gui_data['displacements'] = {
                    'x': x_val, 'y': y_val,
                    'ux': values[0], 'uy': values[1], 'uz': values[2],
                    'thetax': values[3], 'thetay': values[4], 'thetaz': values[5]
                }
                gui_data['load_cases'] = [single_case]
            
            gui_data['is_multi_case'] = False
            
        except Exception as e:
            logger.error(f"收集工况 {case_idx + 1} 数据失败: {e}")
        
        return gui_data

    def _get_case_load_data(self, case_idx: int) -> dict:
        base_row = case_idx * 4
        is_forward = self.current_mode_index == 0
        
        try:
                
            x_item = self.multi_case_table.item(base_row + 1, 2)
            y_item = self.multi_case_table.item(base_row + 1, 4)
            x_val = float(x_item.text()) if x_item else 0.0
            y_val = float(y_item.text()) if y_item else 0.0
            
                    
            values = []
            for col in range(6):
                item = self.multi_case_table.item(base_row + 3, col)
                val = float(item.text()) if item else 0.0
                values.append(val)
            
            if is_forward:
                return {
                    'x': x_val, 'y': y_val,
                    'fx': values[0], 'fy': values[1], 'fz': values[2],
                    'mx': values[3], 'my': values[4], 'mz': values[5],
                    'is_forward': True
                }
            else:
                return {
                    'x': x_val, 'y': y_val,
                    'ux': values[0], 'uy': values[1], 'uz': values[2],
                    'thetax': values[3], 'thetay': values[4], 'thetaz': values[5],
                    'is_forward': False
                }
        except Exception as e:
            logger.warning(f"获取工况 {case_idx + 1} 荷载数据失败: {e}")
            return {'x': 0.0, 'y': 0.0, 'is_forward': is_forward}

    def _calculate_single_case_sync(self, gui_data: dict, case_idx: int) -> bool:
        try:
            generator = DATGenerator()
            
                           
            if gui_data.get('mode') == 1:           
                                          
                return self._calculate_reverse_case_sync(gui_data, case_idx, generator)
            else:
                      
                dat_file = self.work_dir / f"input_case_{case_idx + 1}.dat"
                generator.generate_from_gui_data(gui_data, str(dat_file))
                
                                                
                result = self.async_engine.engine.run_calculation(str(dat_file))
                
                if result.success and result.out_file and Path(result.out_file).exists():
                                         
                    self._process_results_for_batch(result.out_file, case_idx)
                    return True
                else:
                    logger.error(f"工况 {case_idx + 1} 计算失败：{result.message if result else '无输出文件'}")
                    return False
                
        except Exception as e:
            logger.exception(f"工况 {case_idx + 1} 计算异常")
            return False
    
    def _calculate_reverse_case_sync(self, gui_data: dict, case_idx: int, generator) -> bool:
        import numpy as np
        import copy
        
        try:
                              
            success, stiffness_dat, displacement_vector = generator.generate_for_reverse_calculation(
                gui_data, str(self.work_dir)
            )
            
            if not success or not stiffness_dat:
                logger.error(f"工况 {case_idx + 1} 生成刚度计算文件失败")
                return False
            
            logger.info(f"工况 {case_idx + 1} 反算步骤1：计算刚度矩阵")
            logger.info(f"位移向量: {displacement_vector}")
            
                      
            result = self.async_engine.engine.run_calculation(stiffness_dat)
            
            if not result.success or not result.out_file:
                logger.error(f"工况 {case_idx + 1} 刚度矩阵计算失败")
                return False
            
                              
            stiffness_matrix = self._parse_stiffness_matrix_from_output(result.out_file)
            
            if stiffness_matrix is None:
                logger.error(f"工况 {case_idx + 1} 无法解析刚度矩阵")
                return False
            
                             
            K = np.array(stiffness_matrix)
            u = np.array(displacement_vector)
            F = K @ u
            force_list = F.tolist()
            
            logger.info(f"工况 {case_idx + 1} 反算荷载: {force_list}")
            
                                      
            verify_success = self._run_forward_verification_sync(gui_data, force_list, case_idx)
            
                      
            self._append_reverse_result_summary(case_idx, displacement_vector, force_list, stiffness_matrix)
            
            return True
            
        except Exception as e:
            logger.exception(f"工况 {case_idx + 1} 反算异常")
            return False
    
    def _run_forward_verification_sync(self, original_gui_data: dict, calculated_forces: list, case_idx: int) -> bool:
        import copy
        
        try:
                     
            verify_data = copy.deepcopy(original_gui_data)
            
                                        
            verify_data['mode'] = 0
            
                       
            verify_data['loads'] = {
                'x': verify_data.get('displacements', {}).get('x', 0),
                'y': verify_data.get('displacements', {}).get('y', 0),
                'fx': calculated_forces[0],
                'fy': calculated_forces[1],
                'fz': calculated_forces[2],
                'mx': calculated_forces[3],
                'my': calculated_forces[4],
                'mz': calculated_forces[5],
            }
            verify_data['load_cases'] = [verify_data['loads']]
            verify_data['is_multi_case'] = False
            
            logger.info(f"工况 {case_idx + 1} 正向验算荷载: {verify_data['loads']}")
            
                           
            generator = DATGenerator()
            verify_dat = str(self.work_dir / f"reverse_verify_case_{case_idx + 1}.dat")
            success = generator.generate_from_gui_data(verify_data, verify_dat)
            
            if not success:
                logger.error(f"工况 {case_idx + 1} 生成验算文件失败")
                return False
            
                      
            result = self.async_engine.engine.run_calculation(verify_dat)
            
            if not result.success or not result.out_file or not Path(result.out_file).exists():
                logger.error(f"工况 {case_idx + 1} 正向验算计算失败")
                return False
            
                             
            from result_parser import ResultParser
            parser = ResultParser()
            parse_success = parser.parse_out_file(result.out_file)
            
            if parse_success and parser.pile_results:
                             
                self.parser = parser
                
                                
                if hasattr(self, 'case_plot_widgets') and case_idx < len(self.case_plot_widgets):
                    self._plot_results_to_tab(case_idx)
                
                logger.info(f"工况 {case_idx + 1} 正向验算成功，获得 {len(parser.pile_results)} 根桩的响应数据")
                return True
            else:
                logger.warning(f"工况 {case_idx + 1} 验算结果解析失败或无桩数据")
                return False
                
        except Exception as e:
            logger.exception(f"工况 {case_idx + 1} 正向验算异常")
            return False
    
    def _append_reverse_result_summary(self, case_idx: int, displacement_vector: list, load_vector: list, stiffness_matrix: list):
        separator = "\n" + "=" * 70 + "\n"
        case_header = f"【工况 {case_idx + 1}】反算结果"
        
               
        summary_lines = [
            case_header,
            separator,
            "输入位移向量:",
            f"  Ux = {displacement_vector[0]:.6E} m  ({displacement_vector[0]*1000:.4f} mm)",
            f"  Uy = {displacement_vector[1]:.6E} m  ({displacement_vector[1]*1000:.4f} mm)",
            f"  Uz = {displacement_vector[2]:.6E} m  ({displacement_vector[2]*1000:.4f} mm)",
            f"  θx = {displacement_vector[3]:.6E} rad  ({displacement_vector[3]*1000:.6f} mrad)",
            f"  θy = {displacement_vector[4]:.6E} rad  ({displacement_vector[4]*1000:.6f} mrad)",
            f"  θz = {displacement_vector[5]:.6E} rad  ({displacement_vector[5]*1000:.6f} mrad)",
            "",
            "计算得到的荷载:",
            f"  Fx = {load_vector[0]:12.2f} kN",
            f"  Fy = {load_vector[1]:12.2f} kN",
            f"  Fz = {load_vector[2]:12.2f} kN",
            f"  Mx = {load_vector[3]:12.2f} kN·m",
            f"  My = {load_vector[4]:12.2f} kN·m",
            f"  Mz = {load_vector[5]:12.2f} kN·m",
        ]
        
                            
        if self.parser and self.parser.pile_results:
            summary_lines.append("")
            summary_lines.append("-" * 50)
            summary_lines.append("验算结果 - 桩顶响应:")
            summary_lines.append("-" * 50)
            
                    
            if self.parser.cap_result and self.parser.cap_result.displacement:
                d = self.parser.cap_result.displacement
                summary_lines.append(f"  承台中心位移: Ux={d.x*1000:.4f}mm, Uy={d.y*1000:.4f}mm, Uz={d.z*1000:.4f}mm")
            
            summary_lines.append(f"  桩基数量: {len(self.parser.pile_results)}")
            
                              
            for pile in self.parser.pile_results:
                f = pile.top.force
                d = pile.top.displacement
                summary_lines.append(f"  桩{pile.pile_no}: Ux={d.x*1000:.4f}mm, Uy={d.y*1000:.4f}mm, Nz={f.z:.2f}kN")
        
        summary_text = "\n".join(summary_lines)
        
                 
        current_summary = self.summary_text.toPlainText()
        if current_summary:
            new_summary = current_summary + separator + summary_text
        else:
            new_summary = summary_text
        self.summary_text.setText(new_summary)
        
                         
        raw_lines = [
            case_header,
            separator,
            "刚度矩阵 (6x6):"
        ]
        for i, row in enumerate(stiffness_matrix):
            row_str = "  " + "  ".join([f"{v:.4E}" for v in row])
            raw_lines.append(row_str)
        
        raw_lines.extend([
            "",
            "位移向量: " + str(displacement_vector),
            "荷载向量: " + str([f"{v:.6E}" for v in load_vector])
        ])
        
        raw_text = "\n".join(raw_lines)
        
        current_raw = self.raw_output_text.toPlainText()
        if current_raw:
            new_raw = current_raw + separator + raw_text
        else:
            new_raw = raw_text
        self.raw_output_text.setText(new_raw)
    
    def _parse_stiffness_matrix_from_output(self, out_file: str) -> list:
        try:
            from result_parser import ResultParser
            parser = ResultParser()
            success = parser.parse_out_file(out_file)
            
            if success and parser.stiffness_matrix is not None:
                                                     
                return parser.stiffness_matrix.data
            return None
        except Exception as e:
            logger.error(f"解析刚度矩阵失败: {e}")
            return None

    def _process_results_for_batch(self, out_file: str, case_idx: int = 0):
        import re
        
        def filter_bcad_pile_info(text):
            pattern = re.compile(r"[+]{10,}[\s\S]*?Copyright[\s\S]*?[+]{10,}[\s\S]*?Welcome to use the BCAD_PILE program[\s\S]*?P\.R\.of China", re.MULTILINE)
            text = re.sub(pattern, '', text)
            text = re.sub(r"BCAD[-_ ]?PILE[\s\S]*?Copyright[\s\S]*?Version[\s\S]*?\n", '', text, flags=re.IGNORECASE)
            text = re.sub(r"Welcome to use the BCAD_PILE program[\s\S]*?Tongji University[\s\S]*?P\.R\.of China", '', text, flags=re.IGNORECASE)
            text = re.sub(r"\n{3,}", '\n\n', text)
                    
            text = text.replace('(t*m)', '(kN·m)')
            text = text.replace('(t/m2)', '(kN/m²)')
            text = text.replace('(t)', '(kN)')
            return text.strip()
        
               
        separator = "\n" + "=" * 70 + "\n"
        case_header = f"【工况 {case_idx + 1}】"
        
        if self.parser:
            try:
                success = self.parser.parse_out_file(out_file)
                if success:
                    filtered = filter_bcad_pile_info(self.parser.raw_output)
                                                 
                    summary = self._generate_summary(batch_case_idx=case_idx)
                    
                             
                    current_raw = self.raw_output_text.toPlainText()
                    if current_raw:
                        new_raw = current_raw + separator + case_header + separator + filtered
                    else:
                        new_raw = case_header + separator + filtered
                    self.raw_output_text.setText(new_raw)
                    
                             
                    current_summary = self.summary_text.toPlainText()
                    if current_summary:
                        new_summary = current_summary + separator + case_header + separator + summary
                    else:
                        new_summary = case_header + separator + summary
                    self.summary_text.setText(new_summary)
                    
                    logger.info(f"工况 {case_idx + 1} 结果解析成功")
                else:
                                 
                    filtered = filter_bcad_pile_info(self.parser.raw_output)
                    current_raw = self.raw_output_text.toPlainText()
                    if current_raw:
                        new_raw = current_raw + separator + case_header + " (解析失败)" + separator + filtered
                    else:
                        new_raw = case_header + " (解析失败)" + separator + filtered
                    self.raw_output_text.setText(new_raw)
                    logger.warning(f"工况 {case_idx + 1} 结果解析失败")
            except Exception as e:
                logger.exception(f"解析工况 {case_idx + 1} 结果文件时发生异常")
        
                       
        self._plot_results_to_tab(case_idx)

    def _plot_results_to_tab(self, case_idx: int):
                        
        if not hasattr(self, 'case_plot_widgets') or case_idx >= len(self.case_plot_widgets):
            logger.warning(f"工况 {case_idx + 1} 的绘图控件引用不存在")
            return
        
        plot_widgets = self.case_plot_widgets[case_idx]
        plot_tabs = plot_widgets.get('plot_tabs')
        plot_3d_area = plot_widgets.get('plot_3d_area')
        plot_response_area = plot_widgets.get('plot_response_area')
        
        if not plot_tabs or not plot_3d_area or not plot_response_area:
            logger.warning(f"工况 {case_idx + 1} 的绘图控件无效")
            return
        
                      
        orig_tabs = self.plot_tabs
        orig_3d = self.plot_3d_area
        orig_resp = self.plot_response_area
        
        try:
            self.plot_tabs = plot_tabs
            self.plot_3d_area = plot_3d_area
            self.plot_response_area = plot_response_area
            self._plot_results()
        finally:
                    
            self.plot_tabs = orig_tabs
            self.plot_3d_area = orig_3d
            self.plot_response_area = orig_resp

    @Slot()
    def start_calculation(self):
                  
        self.set_calc_status("计算中")
        
                              
        if hasattr(self, 'case_plot_widgets'):
            del self.case_plot_widgets
        if hasattr(self, 'all_case_results'):
            del self.all_case_results
        if hasattr(self, 'all_case_parsers'):
            del self.all_case_parsers
        
        if self.current_mode_index < 0:
            QMessageBox.warning(self, "提示", "请先选择一种计算模式，然后继续。")
            self.set_calc_status("准备就绪")
            return

        if not HAS_DAT_GENERATOR or DATGenerator is None:
            QMessageBox.critical(
                self, "组建缺失",
                "核心组件 'dat_generator' 未加载。\n\n"
                "请尝试重启程序。如果问题持续，可能是文件缺失。"
            )
            self.set_calc_status("准备就绪")
            return

        if not HAS_ENGINE or self.async_engine is None:
            QMessageBox.critical(
                self, "组建缺失",
                "计算引擎 'pile_engine' 未加载。\n\n"
                "无法执行计算。"
            )
            self.set_calc_status("准备就绪")
            return

        if not self.async_engine.engine.is_ready:
            current_exe = self.async_engine.engine.exe_path if self.async_engine.engine.exe_path else "未配置"
            QMessageBox.critical(
                self, "引擎未就绪",
                f"计算核心程序无法启动。\n"
                f"当前路径配置: {current_exe}\n\n"
                "常见解决方案：\n"
                "1. 确认 'BCAD-PILE.exe' 与本程序在同一目录\n"
                "2. 检查杀毒软件是否拦截了计算程序\n"
                "3. 尝试重启计算机"
            )
            return

        if self.async_engine.is_running:
            QMessageBox.warning(self, "提示", "计算正在进行中，请稍候...")
            return

        try:
            gui_data = self._collect_gui_data()
        except ValueError as e:
            QMessageBox.warning(self, "数据错误", str(e))
            return

                                            


        dat_file = self.work_dir / "input.dat"

        try:
            generator = DATGenerator()
            generator.generate_from_gui_data(gui_data, str(dat_file))
            logger.info(f"已生成输入文件: {dat_file}")
        except Exception as e:
            logger.exception("生成输入文件失败")
            QMessageBox. critical(self, "错误", f"生成输入文件失败:\n{e}")
            return

        self.progress_dialog = QProgressDialog("正在计算...", "取消", 0, 0, self)
        self.progress_dialog.setWindowTitle("计算中")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.canceled.connect(self._cancel_calculation)
        self.progress_dialog.show()

        self.update_status("计算中...")

        def safe_on_complete(result):
            logger.info(f"工作线程计算完成，发射信号: success={result.success}")
            self.calculation_finished.emit(result)
        
        def safe_on_progress(message):
            logger.debug(f"进度更新: {message}")
            self.calculation_progress.emit(message)

        self.async_engine.run_async(
            dat_file=str(dat_file),
            work_dir=str(self.work_dir),
            timeout=300,
            on_complete=safe_on_complete,
            on_progress=safe_on_progress
        )


                                                                             
                     
                                                                             

    def _start_reverse_calculation(self, gui_data):
        self.update_status("反算模式：步骤1 - 计算刚度矩阵...")
        
        try:
            generator = DATGenerator()
            success, stiffness_dat, displacement_vector = generator.generate_for_reverse_calculation(
                gui_data, str(self.work_dir)
            )
            
            if not success or not stiffness_dat:
                QMessageBox.critical(self, "错误", "生成刚度计算文件失败")
                return
            
            logger.info(f"步骤1：生成刚度计算文件 {stiffness_dat}")
            logger.info(f"位移向量: {displacement_vector}")
            
            self.progress_dialog = QProgressDialog("反算步骤1: 计算刚度矩阵...", "取消", 0, 0, self)
            self.progress_dialog.setWindowTitle("反算计算中")
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress_dialog.setMinimumDuration(0)
            self.progress_dialog.canceled.connect(self._cancel_calculation)
            self.progress_dialog.show()
            
            self._reverse_displacement = displacement_vector
            self._reverse_gui_data = gui_data
            
            def on_stiffness_complete(result):
                logger.info(f"刚度计算完成: success={result.success}")
                                       
                self.stiffness_calc_finished.emit(result)
            
            self.async_engine.run_async(
                dat_file=stiffness_dat,
                work_dir=str(self.work_dir),
                timeout=300,
                on_complete=on_stiffness_complete,
                on_progress=lambda msg: self.calculation_progress.emit(f"步骤1: {msg}")
            )
            
        except Exception as e:
            logger.exception("反算准备失败")
            QMessageBox.critical(self, "错误", f"反算准备失败:\n{e}")
    
    @Slot(object)
    def _on_stiffness_calc_finished(self, result):
        logger.info(f"_on_stiffness_calc_finished 被调用（主线程），is_running={self.async_engine.is_running}")
                                   
                      
        import time
        time.sleep(0.1)
        logger.info(f"等待后 is_running={self.async_engine.is_running}")
        self._on_reverse_stiffness_calculated(result)
    
    def _on_reverse_stiffness_calculated(self, result):
        if not result.success:
            if self.progress_dialog:
                self.progress_dialog.close()
            
            error_details = f"刚度矩阵计算失败:\n{result.message}\n"
            error_details += f"\n退出代码: {result.return_code}\n"
            
            if result.stdout:
                error_details += f"\n标准输出:\n{result.stdout[:1000]}\n"
            if result.stderr:
                error_details += f"\n错误输出:\n{result.stderr[:500]}\n"
            
            dat_file = self.work_dir / "reverse_step1_stiffness.dat"
            if dat_file.exists():
                error_details += f"\nDAT文件已生成: {dat_file}\n"
                try:
                    with open(dat_file, 'r', encoding='ascii') as f:
                        dat_content = f.read()
                    error_details += f"\nDAT文件内容:\n{dat_content}\n"
                except Exception as e:
                    error_details += f"\n无法读取DAT文件: {e}\n"
            else:
                error_details += f"\nDAT文件未生成: {dat_file}\n"
            
            logger.error(error_details)
            
            dialog = QDialog(self)
            dialog.setWindowTitle("反算计算失败 - 详细信息")
                      
            dialog_width = min(800, int(self._screen_width * 0.5))
            dialog_height = min(600, int(self._screen_height * 0.5))
            dialog.resize(dialog_width, dialog_height)
            layout = QVBoxLayout(dialog)
            
            text_edit = QTextEdit()
            text_edit.setPlainText(error_details)
            text_edit.setReadOnly(True)
            text_edit.setFont(QFont("Courier New", 9))
            layout.addWidget(text_edit)
            
            btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            btn_box.accepted.connect(dialog.accept)
            layout.addWidget(btn_box)
            
            dialog.exec()
            return
        
        if not result.out_file or not os.path.exists(result.out_file):
            if self.progress_dialog:
                self.progress_dialog.close()
            QMessageBox.critical(self, "错误", "未找到刚度计算输出文件")
            return
        
        try:
            from result_parser import ResultParser
            logger.info(f"开始解析刚度矩阵文件: {result.out_file}")
            
            parser = ResultParser()
            success = parser.parse_out_file(result.out_file)
            
            if not success or parser.stiffness_matrix is None:
                raise ValueError("无法解析刚度矩阵")
            
            stiffness_matrix = parser.stiffness_matrix
            logger.info("成功解析6x6刚度矩阵")
            
            logger.info(f"开始计算荷载向量，位移={self._reverse_displacement}")
            
            if self.progress_dialog:
                self.progress_dialog.setLabelText("反算步骤2: 计算荷载向量...")
                QApplication.processEvents()
            
            force_vector = stiffness_matrix.multiply_vector(self._reverse_displacement)
            
            logger.info(f"反算得到荷载: {force_vector}")
            
                              
            self._reverse_stiffness_matrix = stiffness_matrix
            self._reverse_force_vector = force_vector
            
                             
            self._run_forward_verification(force_vector, self._reverse_gui_data)
            
        except Exception as e:
            logger.exception("反算处理失败")
            if self.progress_dialog:
                self.progress_dialog.close()
                self.progress_dialog = None
            self.calculation_progress.emit(f"错误: {e}")

    def _run_forward_verification(self, calculated_forces: List[float], original_gui_data: Dict):
        logger.info("===== 反算步骤3: 启动正向验算 =====")
        logger.info(f"验算荷载: {calculated_forces}")
        
        if self.progress_dialog:
            self.progress_dialog.setLabelText("反算步骤3: 正向验算获取桩身响应...")
            QApplication.processEvents()
        
        try:
                     
            verify_data = copy.deepcopy(original_gui_data)
            
                                        
            verify_data['mode'] = 0
            
                                       
            disp_x = verify_data.get('displacements', {}).get('x', 0)
            disp_y = verify_data.get('displacements', {}).get('y', 0)
            
                             
            verify_data['loads'] = {
                'x': disp_x,
                'y': disp_y,
                'fx': calculated_forces[0],      
                'fy': calculated_forces[1],      
                'fz': calculated_forces[2],      
                'mx': calculated_forces[3],      
                'my': calculated_forces[4],      
                'mz': calculated_forces[5],      
            }
            verify_data['load_cases'] = [verify_data['loads']]
            verify_data['is_multi_case'] = False
            
            logger.info(f"验算荷载数据: {verify_data['loads']}")
            logger.info(f"验算load_cases: {verify_data['load_cases']}")
            
                           
            generator = DATGenerator()
            verify_dat = str(self.work_dir / "reverse_verify.dat")
            success = generator.generate_from_gui_data(verify_data, verify_dat)
            
            if not success:
                raise ValueError("生成验算文件失败")
            
            logger.info(f"生成验算文件: {verify_dat}")
            
                              
            try:
                with open(verify_dat, 'r', encoding='ascii') as f:
                    dat_content = f.read()
                logger.info(f"验算DAT文件内容:\n{dat_content[:1000]}")
            except Exception as e:
                logger.warning(f"无法读取验算文件: {e}")
            
                                        
            self._verification_forces = calculated_forces
            
                                 
            import time
            wait_count = 0
            while self.async_engine.is_running and wait_count < 50:
                time.sleep(0.1)
                wait_count += 1
                QApplication.processEvents()
            
                                
            time.sleep(0.3)
            QApplication.processEvents()
            
            if self.async_engine.is_running:
                logger.warning("上一个计算未结束，跳过验算步骤")
                raise ValueError("计算引擎忙")
            
                    
            def on_verification_complete(result):
                logger.info(f"验算计算完成: success={result.success}")
                            
                self.verification_finished.emit(result, self._verification_forces)
            
            started = self.async_engine.run_async(
                dat_file=verify_dat,
                work_dir=str(self.work_dir),
                timeout=300,
                on_complete=on_verification_complete,
                on_progress=lambda msg: self.calculation_progress.emit(f"验算: {msg}")
            )
            
            if not started:
                raise ValueError("无法启动验算计算（引擎忙）")
            
        except Exception as e:
            logger.exception("正向验算准备失败")
                                  
            logger.warning("验算失败，将只显示反算结果（无桩身响应曲线）")
            self.reverse_finished.emit(
                self._reverse_stiffness_matrix,
                self._reverse_displacement,
                self._reverse_force_vector
            )

    @Slot(object, object)
    def _on_verification_finished(self, result, calculated_forces):
        logger.info("_on_verification_finished 被调用（主线程）")
        if result.success and result.out_file and os.path.exists(result.out_file):
            try:
                                 
                from result_parser import ResultParser
                logger.info(f"解析验算结果: {result.out_file}")
                
                self.parser = ResultParser()
                success = self.parser.parse_out_file(result.out_file)
                
                if success:
                    logger.info(f"验算结果解析成功，获得 {len(self.parser.pile_results or [])} 根桩的响应数据")
                else:
                    logger.warning("验算结果解析失败，桩身响应数据不可用")
                    
            except Exception as e:
                logger.exception(f"解析验算结果失败: {e}")
        else:
            logger.warning(f"验算计算失败或输出文件不存在: {result.message}")
        
                            
        logger.info("===== 反算流程完成，发送信号到主线程 =====")
        self.reverse_finished.emit(
            self._reverse_stiffness_matrix,
            self._reverse_displacement,
            self._reverse_force_vector
        )
    
    def _on_reverse_finished(self, stiffness_matrix, displacement, force_vector):
        logger.info("_on_reverse_finished 被调用（主线程）")
        
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
        
                                          
        if self.parser is None:
            from result_parser import ResultParser
            self.parser = ResultParser()
                                         
        self.parser.stiffness_matrix = stiffness_matrix
        logger.info(f"反算完成: pile_results={len(self.parser.pile_results) if self.parser.pile_results else 0}根桩")
        
        self._show_reverse_calculation_result(stiffness_matrix, displacement, force_vector)
        
                
        self._plot_results()
        
                      
        self.results_tabs.setCurrentIndex(0)
        
        self.update_status("反算完成！")
        QMessageBox.information(
            self, "成功",
            f"反算完成！\n请查看结果。"
        )
    
    def _show_reverse_calculation_result(self, stiffness_matrix, displacement, force):
        logger.info("构建结果文本...")
        
                      
        try:
            ref_x = float(self.disp_x_input.text() or 0)
            ref_y = float(self.disp_y_input.text() or 0)
        except ValueError:
            ref_x, ref_y = 0.0, 0.0
        
                                               
                     
                                     
                                
                                  
                                         
        fx, fy, fz = force[0], force[1], force[2]
        mx_center, my_center, mz_center = force[3], force[4], force[5]
        
        mx_point = mx_center - fz * ref_y
        my_point = my_center + fz * ref_x
        mz_point = mz_center - fy * ref_x + fx * ref_y
        
        summary_text = "=" * 70 + "\n"
        summary_text += "桩基反算结果 (位移 → 荷载)\n"
        summary_text += "=" * 70 + "\n\n"
        
        summary_text += "【输入位移】\n"
        summary_text += f"  参考点坐标: X = {ref_x:.4f} m, Y = {ref_y:.4f} m\n"
        summary_text += f"  X方向位移: {displacement[0]*1000:10.4f} mm\n"
        summary_text += f"  Y方向位移: {displacement[1]*1000:10.4f} mm\n"
        summary_text += f"  竖向沉降:   {displacement[2]*1000:10.4f} mm\n"
        summary_text += f"  绕X轴转角: {displacement[3]*1000:10.6f} mrad\n"
        summary_text += f"  绕Y轴转角: {displacement[4]*1000:10.6f} mrad\n"
        summary_text += f"  绕Z轴转角: {displacement[5]*1000:10.6f} mrad\n\n"
        
                            
        summary_text += f"【反算荷载 - 作用点 ({ref_x:.2f}, {ref_y:.2f})】\n"
        summary_text += f"  FX = {fx:12.2f} kN\n"
        summary_text += f"  FY = {fy:12.2f} kN\n"
        summary_text += f"  FZ = {fz:12.2f} kN\n"
        summary_text += f"  MX = {mx_point:12.2f} kN·m\n"
        summary_text += f"  MY = {my_point:12.2f} kN·m\n"
        summary_text += f"  MZ = {mz_point:12.2f} kN·m\n\n"
        
                                 
        if abs(ref_x) > 1e-6 or abs(ref_y) > 1e-6:
            summary_text += "【反算荷载 - 承台中心 (0, 0)】\n"
            summary_text += f"  FX = {fx:12.2f} kN\n"
            summary_text += f"  FY = {fy:12.2f} kN\n"
            summary_text += f"  FZ = {fz:12.2f} kN\n"
            summary_text += f"  MX = {mx_center:12.2f} kN·m\n"
            summary_text += f"  MY = {my_center:12.2f} kN·m\n"
            summary_text += f"  MZ = {mz_center:12.2f} kN·m\n"
            summary_text += "  (注: 两处荷载是同一力系在不同参考点的等效表达)\n\n"
        
                                       
        if self.parser and self.parser.pile_results:
            summary_text += "-" * 70 + "\n"
            summary_text += "【验算结果 - 桩身响应】\n"
            summary_text += "-" * 70 + "\n"
            
                          
            if self.parser.cap_result and self.parser.cap_result.displacement:
                d = self.parser.cap_result.displacement
                summary_text += "\n承台中心位移:\n"
                summary_text += f"  X方向位移: {d.x * 1000:10.4f} mm\n"
                summary_text += f"  Y方向位移: {d.y * 1000:10.4f} mm\n"
                summary_text += f"  竖向沉降:   {d.z * 1000:10.4f} mm\n"
                summary_text += f"  绕X轴转角: {d.rx * 1000:10.6f} mrad\n"
                summary_text += f"  绕Y轴转角: {d.ry * 1000:10.6f} mrad\n"
                summary_text += f"  绕Z轴转角: {d.rz * 1000:10.6f} mrad\n"
            
            summary_text += f"\n桩基数量: {len(self.parser.pile_results)}\n"
            summary_text += "-" * 70 + "\n"
            
                            
            for pile in self.parser.pile_results:
                summary_text += f"\n桩 {pile.pile_no}\n"
                summary_text += "  桩顶位移:\n"
                summary_text += f"    UX={pile.top.displacement.x*1000:8.4f} mm, UY={pile.top.displacement.y*1000:8.4f} mm, UZ={pile.top.displacement.z*1000:8.4f} mm\n"
                summary_text += "  桩顶内力:\n"
                summary_text += f"    NX={pile.top.force.x:8.2f} kN,  NY={pile.top.force.y:8.2f} kN,  NZ={pile.top.force.z:8.2f} kN\n"
                summary_text += f"    MX={pile.top.force.rx:8.2f} kN·m, MY={pile.top.force.ry:8.2f} kN·m\n"
        else:
            summary_text += "-" * 70 + "\n"
            summary_text += "（验算未完成，无桩身响应数据）\n"
        
        summary_text += "\n" + "=" * 70 + "\n"
        
              
        raw_text = "=" * 70 + "\n"
        raw_text += "反算详细信息\n"
        raw_text += "=" * 70 + "\n\n"
        
        raw_text += "步骤1: 生成刚度计算文件，调用计算内核\n\n"
        
        raw_text += "步骤2: 提取6×6刚度矩阵 [K]:\n"
        raw_text += "-" * 70 + "\n"
        logger.info("格式化刚度矩阵...")
        try:
            raw_text += stiffness_matrix.to_string(precision=2) + "\n"
        except Exception as e:
            logger.error(f"格式化刚度矩阵失败: {e}")
            raw_text += "[格式化失败]\n"
        raw_text += "-" * 70 + "\n\n"
        
        raw_text += "步骤3: 矩阵乘法计算荷载向量\n\n"
        raw_text += "运算公式:\n"
        raw_text += "  {F} = [K] {Δ}\n\n"
        raw_text += "其中:\n"
        raw_text += "  {F} = [FX, FY, FZ, MX, MY, MZ]ᵀ  (荷载向量)\n"
        raw_text += "  [K] = 6×6 刚度矩阵\n"
        raw_text += "  {Δ} = [UX, UY, UZ, θX, θY, θZ]ᵀ  (位移向量)\n\n"
        
        raw_text += "计算结果:\n"
        raw_text += f"  位移向量 {{Δ}} = [{displacement[0]:.6f}, {displacement[1]:.6f}, {displacement[2]:.6f}, "
        raw_text += f"{displacement[3]:.6f}, {displacement[4]:.6f}, {displacement[5]:.6f}]ᵀ\n"
        raw_text += f"  荷载向量 {{F}} = [{force[0]:.2f}, {force[1]:.2f}, {force[2]:.2f}, "
        raw_text += f"{force[3]:.2f}, {force[4]:.2f}, {force[5]:.2f}]ᵀ\n\n"
        
                        
        if self.parser and self.parser.raw_output:
            raw_text += "=" * 70 + "\n"
            raw_text += "步骤4: 正向验算原始输出\n"
            raw_text += "=" * 70 + "\n\n"
                                   
            verify_output = self.parser.raw_output
            start_marker = "DISPLACEMENTS AT THE CAP CENTER"
            marker_pos = verify_output.find(start_marker)
            if marker_pos > 0:
                                   
                search_start = max(0, marker_pos - 100)
                star_line_pos = verify_output.rfind("***", search_start, marker_pos)
                if star_line_pos > 0:
                                  
                    line_start = verify_output.rfind("\n", 0, star_line_pos)
                    verify_output = verify_output[line_start + 1:] if line_start >= 0 else verify_output[star_line_pos:]
            raw_text += verify_output
        
        raw_text += "\n" + "=" * 70 + "\n"
        
        logger.info("设置结果文本到UI...")
        self.summary_text.setText(summary_text)
        logger.info("设置原始输出...")
        self.raw_output_text.setText(raw_text)
        
        self.results_tabs.setCurrentIndex(0)
        
        logger.info("反算结果显示完成")

    @Slot()
    def _cancel_calculation(self):
        if self.async_engine and self.async_engine.is_running:
            self.async_engine.cancel()
            self.update_status("正在取消计算...")
            logger.info("用户请求取消计算")

    def _on_calc_progress(self, message):
        if self.progress_dialog:
            self.progress_dialog.setLabelText(message)
        logger.debug(f"计算进度: {message}")

                                                                             
               
                                                                             

    def _on_calc_finished(self, result):
        logger.info(f"_on_calc_finished 被调用: success={result.success}")
        
        self.set_calc_status("计算完成")
        
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        if not result.success:
            error_msg = result.message or "未知错误"
            QMessageBox.critical(self, "计算失败", f"计算失败:\n{error_msg}")
            self.set_calc_status("准备就绪")
            logger.error(f"计算失败: {error_msg}")
            return

        self.update_status("计算完成，正在解析结果...")
        logger.info(f"计算完成，耗时: {result.elapsed_time:.2f} 秒")

        if result.out_file and os.path.exists(result.out_file):
            self._process_results(result.out_file, result.pos_file)
            self.update_status("计算完成！")
            
            self.visual_tabs.setCurrentIndex(1)
            self.results_tabs.setCurrentIndex(0)
            self.placeholder_label.setText("← 计算完成，请查看结果")
            
            QMessageBox.information(
                self, "成功",
                f"计算完成！\n耗时: {result.elapsed_time:.2f} 秒\n请查看结果。"
            )
        else:
            QMessageBox.warning(self, "警告", "计算完成但未找到输出文件")
            self.update_status("未找到输出文件")

    def _generate_summary(self, batch_case_idx: int = None):
        if not self.parser:
            return "解析器不可用"
        
        mode_names_cn = {
            OutputMode.FULL_ANALYSIS: "桩基反算",           
            OutputMode.FOUNDATION_STIFFNESS: "群桩刚度",            
            OutputMode.SINGLE_PILE_STIFFNESS: "单桩刚度",
            OutputMode.UNKNOWN: "未知模式"
        }
        
        lines = []
        lines.append("=" * 60)
        lines.append("计算结果摘要")
        lines.append("=" * 60)
        lines.append(f"\n计算模式: {mode_names_cn.get(self.parser.mode, str(self.parser.mode))}")
        lines.append("")
        
        if self.parser.mode == OutputMode.FULL_ANALYSIS:
                             
            if self.multi_case_radio.isChecked():
                                 
                case_count = self.multi_case_table.rowCount() // 4
                if case_count > 0:
                    lines.append(f"共 {case_count} 个荷载:")
                    for case_idx in range(case_count):
                        base_row = case_idx * 4
                        try:
                                                       
                            x_item = self.multi_case_table.item(base_row + 1, 2)
                            y_item = self.multi_case_table.item(base_row + 1, 4)
                            load_x = float(x_item.text()) if x_item else 0.0
                            load_y = float(y_item.text()) if y_item else 0.0
                            
                                               
                            values = []
                            for col in range(6):
                                item = self.multi_case_table.item(base_row + 3, col)
                                val = float(item.text()) if item else 0.0
                                values.append(val)
                            fx, fy, fz, mx, my, mz = values
                            
                                    
                            cn_nums = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
                            cn_idx = cn_nums[case_idx] if case_idx < 10 else str(case_idx + 1)
                            
                            lines.append(f"\n【荷载{cn_idx}】")
                            lines.append(f"  作用位置: X = {load_x:.3f} m, Y = {load_y:.3f} m")
                            loads_info = []
                            for val, label, unit in [(fx, 'FX', 'kN'), (fy, 'FY', 'kN'), (fz, 'FZ', 'kN'),
                                                      (mx, 'MX', 'kN·m'), (my, 'MY', 'kN·m'), (mz, 'MZ', 'kN·m')]:
                                if abs(val) > 1e-10:
                                    loads_info.append(f"{label}={val:.2f}{unit}")
                            if loads_info:
                                lines.append(f"  荷载值: {', '.join(loads_info)}")
                        except Exception as e:
                            logger.warning(f"读取荷载{case_idx+1}数据失败: {e}")
            else:
                              
                try:
                    load_x = float(self.load_x_input.text() or 0)
                    load_y = float(self.load_y_input.text() or 0)
                    lines.append(f"荷载作用位置: X = {load_x:.4f} m, Y = {load_y:.4f} m")
                except:
                    pass
                
                        
                try:
                    loads_info = []
                    for key, widget in self.loads.items():
                        val = float(widget.text() or 0)
                        if abs(val) > 1e-10:
                            unit = "kN" if key.startswith('n') else "kN·m"
                            label = key.upper().replace('N', 'F')
                            loads_info.append(f"{label}={val:.2f} {unit}")
                    if loads_info:
                        lines.append(f"输入荷载: {', '.join(loads_info)}")
                except:
                    pass
            lines.append("")
            
            if self.parser.cap_result and self.parser.cap_result.displacement:
                d = self.parser.cap_result.displacement
                lines.append("承台中心位移:")
                lines.append(f"  X方向位移: {d.x * 1000:10.4f} mm")
                lines.append(f"  Y方向位移: {d.y * 1000:10.4f} mm")
                lines.append(f"  竖向沉降:   {d.z * 1000:10.4f} mm")
                lines.append(f"  绕X轴转角: {d.rx * 1000:10.6f} mrad")
                lines.append(f"  绕Y轴转角: {d.ry * 1000:10.6f} mrad")
                lines.append(f"  绕Z轴转角: {d.rz * 1000:10.6f} mrad")
                lines.append("")
            else:
                lines.append("未能解析承台位移数据\n")
            
            if self.parser.pile_results:
                lines.append(f"桩基数量: {len(self.parser.pile_results)}")
                lines.append("-" * 60)
                
                for pile in self.parser.pile_results:
                    lines.append(f"\n桩 {pile.pile_no}")
                    lines.append("  桩顶位移:")
                    lines.append(f"    UX={pile.top.displacement.x*1000:8.4f} mm, UY={pile.top.displacement.y*1000:8.4f} mm, UZ={pile.top.displacement.z*1000:8.4f} mm")
                    lines.append("  桩顶内力:")
                    lines.append(f"    NX={pile.top.force.x:8.2f} kN,  NY={pile.top.force.y:8.2f} kN,  NZ={pile.top.force.z:8.2f} kN")
                    lines.append(f"    MX={pile.top.force.rx:8.2f} kN·m, MY={pile.top.force.ry:8.2f} kN·m")
            else:
                lines.append("\n未解析到桩的详细信息")
        
        elif self.parser.mode == OutputMode.FOUNDATION_STIFFNESS:
            lines.append("承台整体刚度矩阵")
            if self.parser.stiffness_matrix:
                k = self.parser.stiffness_matrix
                labels = ["    X", "    Y", "    Z", "   RX", "   RY", "   RZ"]
                row_labels = ["X  ", "Y  ", "Z  ", "RX ", "RY ", "RZ "]
                diag_labels = ["KX (kN/m)", "KY (kN/m)", "KZ (kN/m)", 
                              "KRX (kN·m/rad)", "KRY (kN·m/rad)", "KRZ (kN·m/rad)"]
                
                         
                lines.append("\n提示: 可点击菜单栏导出按钮，导出刚度矩阵CSV，供后续分析使用")
                
                            
                lines.append("\n【原始刚度矩阵】(Z轴向下)")
                lines.append("-" * 60)
                lines.append("       " + "  ".join(labels))
                lines.append("-" * 60)
                for i in range(6):
                    row_data = [f"{k[i, j]:9.2e}" for j in range(6)]
                    lines.append(f"{row_labels[i]} " + " ".join(row_data))
                lines.append("-" * 60)
                
                            
                lines.append("\n主对角线刚度:")
                for i in range(6):
                    lines.append(f"  {diag_labels[i]:15s}: {k[i, i]:12.4e}")
                
                              
                k_converted = self._convert_stiffness_z_up(k)
                lines.append("\n【转换刚度矩阵】(Z轴向上)")
                lines.append("-" * 60)
                lines.append("       " + "  ".join(labels))
                lines.append("-" * 60)
                for i in range(6):
                    row_data = [f"{k_converted[i, j]:9.2e}" for j in range(6)]
                    lines.append(f"{row_labels[i]} " + " ".join(row_data))
                lines.append("-" * 60)
                
                            
                lines.append("\n主对角线刚度:")
                for i in range(6):
                    lines.append(f"  {diag_labels[i]:15s}: {k_converted[i, i]:12.4e}")
        
        elif self.parser.mode == OutputMode.SINGLE_PILE_STIFFNESS:
            lines.append(f"单桩刚度计算 - 桩号: {self.parser.single_pile_no or '1'}")
            if self.parser.stiffness_matrix:
                k = self.parser.stiffness_matrix
                labels = ["    X", "    Y", "    Z", "   RX", "   RY", "   RZ"]
                row_labels = ["X  ", "Y  ", "Z  ", "RX ", "RY ", "RZ "]
                diag_labels = ["KX (kN/m)", "KY (kN/m)", "KZ (kN/m)", 
                              "KRX (kN·m/rad)", "KRY (kN·m/rad)", "KRZ (kN·m/rad)"]
                
                         
                lines.append("\n提示: 可点击菜单栏导出按钮，导出刚度矩阵CSV，供后续分析使用")
                
                            
                lines.append("\n【原始刚度矩阵】(Z轴向下)")
                lines.append("-" * 60)
                lines.append("       " + "  ".join(labels))
                lines.append("-" * 60)
                for i in range(6):
                    row_data = [f"{k[i, j]:9.2e}" for j in range(6)]
                    lines.append(f"{row_labels[i]} " + " ".join(row_data))
                lines.append("-" * 60)
                
                            
                lines.append("\n主对角线刚度:")
                for i in range(6):
                    lines.append(f"  {diag_labels[i]:15s}: {k[i, i]:12.4e}")
                
                              
                k_converted = self._convert_stiffness_z_up(k)
                lines.append("\n【转换刚度矩阵】(Z轴向上)")
                lines.append("-" * 60)
                lines.append("       " + "  ".join(labels))
                lines.append("-" * 60)
                for i in range(6):
                    row_data = [f"{k_converted[i, j]:9.2e}" for j in range(6)]
                    lines.append(f"{row_labels[i]} " + " ".join(row_data))
                lines.append("-" * 60)
                
                            
                lines.append("\n主对角线刚度:")
                for i in range(6):
                    lines.append(f"  {diag_labels[i]:15s}: {k_converted[i, i]:12.4e}")
        
        lines.append("\n" + "=" * 60)
        return "\n".join(lines)
    
    def _convert_stiffness_z_up(self, k):
        import numpy as np
        
                
        if hasattr(k, 'data'):
            k_array = np.array(k.data)
        elif isinstance(k, np.ndarray):
            k_array = k.copy()
        else:
            k_array = np.array([[k[i, j] for j in range(6)] for i in range(6)])
        
                                              
                                      
        T = np.diag([1.0, 1.0, -1.0, -1.0, -1.0, 1.0])
        
                              
        k_converted = T @ k_array @ T
        
        return k_converted
    
    def _export_stiffness_csv(self):
        if not self.parser or self.parser.stiffness_matrix is None:
            QMessageBox.warning(self, "警告", "没有可导出的刚度矩阵数据\n\n请先运行模式一(群桩刚度)或模式二(单桩刚度)计算")
            return
        
        from PySide6.QtWidgets import QFileDialog
        from datetime import datetime
        import csv
        
               
        if self.parser.mode == OutputMode.SINGLE_PILE_STIFFNESS:
            default_name = f"单桩刚度矩阵_桩{self.parser.single_pile_no or '1'}.csv"
            matrix_type = "单桩刚度矩阵"
            pile_info = f"桩号: {self.parser.single_pile_no or '1'}"
        else:
            default_name = "承台整体刚度矩阵.csv"
            matrix_type = "承台整体刚度矩阵"
            pile_info = f"桩数量: {self.pile_table.rowCount()}"
        
                
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出刚度矩阵CSV",
            str(Path.home() / "Desktop" / default_name),
            "CSV文件 (*.csv);;所有文件 (*.*)"
        )
        
        if not file_path:
            return
        
        try:
                         
            k_original = self.parser.stiffness_matrix
            k_converted = self._convert_stiffness_z_up(k_original)
            
                      
            import numpy as np
            if hasattr(k_original, 'data'):
                k_orig_array = np.array(k_original.data)
            elif isinstance(k_original, np.ndarray):
                k_orig_array = k_original
            else:
                k_orig_array = np.array([[k_original[i, j] for j in range(6)] for i in range(6)])
            
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                
                         
                writer.writerow(["桩基分析 刚度矩阵导出文件"])
                writer.writerow([f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
                writer.writerow([f"矩阵类型: {matrix_type}"])
                writer.writerow([f"{pile_info}"])
                writer.writerow(["单位: 力-kN, 长度-m, 角度-rad"])
                writer.writerow([])
                
                              
                writer.writerow(["【转换刚度矩阵】Z轴向上"])
                header = ["", "UX (m)", "UY (m)", "UZ (m)", "RX (rad)", "RY (rad)", "RZ (rad)"]
                writer.writerow(header)
                row_labels = ["FX (kN)", "FY (kN)", "FZ (kN)", "MX (kN·m)", "MY (kN·m)", "MZ (kN·m)"]
                for i in range(6):
                    row = [row_labels[i]] + [f"{k_converted[i, j]:.6e}" for j in range(6)]
                    writer.writerow(row)
                
                writer.writerow([])
                
                              
                writer.writerow(["【原始刚度矩阵】Z轴向下"])
                writer.writerow(header)
                for i in range(6):
                    row = [row_labels[i]] + [f"{k_orig_array[i, j]:.6e}" for j in range(6)]
                    writer.writerow(row)
            
            QMessageBox.information(self, "导出成功", 
                f"刚度矩阵已导出到:\n{file_path}\n\n"
                f"坐标系: Z轴向上\n"
                f"可直接导入SAP2000/MIDAS/ETABS等软件")
            
                      
                               
                                                                 
            
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出刚度矩阵失败:\n{e}")

    def _export_summary_csv(self):
                    
        if not self.parser:
            QMessageBox.warning(self, "警告", "没有可导出的结果数据\n\n请先运行计算")
            return
        
                            
                                      
        if self.current_mode_index not in (2,): 
                                         
                          
             pass
        
                     
        if not self.parser.pile_results or len(self.parser.pile_results) == 0:
            QMessageBox.warning(self, "警告", "没有桩身响应数据\n(仅模式三：桩基反算 会生成详细桩身响应)\n\n请先完成计算")
            return
        
        from PySide6.QtWidgets import QFileDialog
        from datetime import datetime
        import csv
        
                        
        has_multi_case_results = (hasattr(self, 'all_case_results') and 
                                  self.all_case_results and 
                                  len(self.all_case_results) > 1)
        
               
        mode_names = ["群桩刚度", "单桩刚度", "桩基反算"]
        mode_name = mode_names[self.current_mode_index] if self.current_mode_index < len(mode_names) else "未知模式"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if has_multi_case_results:
            default_name = f"桩基{mode_name}_多工况结果_{len(self.all_case_results)}工况_{timestamp}.csv"
        else:
            default_name = f"桩基{mode_name}_结果摘要_{timestamp}.csv"
        
                
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出结果摘要CSV",
            str(Path.home() / "Desktop" / default_name),
            "CSV文件 (*.csv);;所有文件 (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                
                         
                writer.writerow(["桩基分析 结果摘要导出文件"])
                writer.writerow([f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
                writer.writerow([f"计算模式: {mode_name}"])
                
                if has_multi_case_results:
                                                   
                    writer.writerow([f"工况总数: {len(self.all_case_results)}"])
                    writer.writerow([])
                    
                    for case_data in self.all_case_results:
                        case_idx = case_data.get('case_idx', 1)
                        cap_result = case_data.get('cap_result')
                        pile_results = case_data.get('pile_results', [])
                        
                        if not pile_results:
                            continue
                        
                               
                        writer.writerow(["=" * 60])
                        writer.writerow([f"【工况 {case_idx}】"])
                        writer.writerow(["=" * 60])
                        writer.writerow([f"桩基数量: {len(pile_results)}"])
                        writer.writerow([])
                        
                                          
                        if cap_result and cap_result.displacement:
                            d = cap_result.displacement
                            writer.writerow(["【承台中心位移】"])
                            writer.writerow(["项目", "数值", "单位"])
                            writer.writerow(["X方向位移", f"{d.x * 1000:.4f}", "mm"])
                            writer.writerow(["Y方向位移", f"{d.y * 1000:.4f}", "mm"])
                            writer.writerow(["竖向沉降", f"{d.z * 1000:.4f}", "mm"])
                            writer.writerow(["绕X轴转角", f"{d.rx * 1000:.6f}", "mrad"])
                            writer.writerow(["绕Y轴转角", f"{d.ry * 1000:.6f}", "mrad"])
                            writer.writerow(["绕Z轴转角", f"{d.rz * 1000:.6f}", "mrad"])
                            writer.writerow([])
                        
                                          
                        writer.writerow(["【桩顶位移汇总】"])
                        writer.writerow(["桩号", "UX (mm)", "UY (mm)", "UZ (mm)"])
                        for pile in pile_results:
                            writer.writerow([
                                pile.pile_no,
                                f"{pile.top.displacement.x * 1000:.4f}",
                                f"{pile.top.displacement.y * 1000:.4f}",
                                f"{pile.top.displacement.z * 1000:.4f}"
                            ])
                        writer.writerow([])
                        
                                          
                        writer.writerow(["【桩顶内力汇总】"])
                        writer.writerow(["桩号", "NX (kN)", "NY (kN)", "NZ (kN)", "MX (kN·m)", "MY (kN·m)"])
                        for pile in pile_results:
                            writer.writerow([
                                pile.pile_no,
                                f"{pile.top.force.x:.2f}",
                                f"{pile.top.force.y:.2f}",
                                f"{pile.top.force.z:.2f}",
                                f"{pile.top.force.rx:.2f}",
                                f"{pile.top.force.ry:.2f}"
                            ])
                        writer.writerow([])
                        
                                        
                        writer.writerow(["【各桩桩顶响应详细数据】"])
                        writer.writerow(["桩号", "UX (mm)", "UY (mm)", "UZ (mm)", "NX (kN)", "NY (kN)", "NZ (kN)", "MX (kN·m)", "MY (kN·m)"])
                        for pile in pile_results:
                            writer.writerow([
                                pile.pile_no,
                                f"{pile.top.displacement.x * 1000:.4f}",
                                f"{pile.top.displacement.y * 1000:.4f}",
                                f"{pile.top.displacement.z * 1000:.4f}",
                                f"{pile.top.force.x:.2f}",
                                f"{pile.top.force.y:.2f}",
                                f"{pile.top.force.z:.2f}",
                                f"{pile.top.force.rx:.2f}",
                                f"{pile.top.force.ry:.2f}"
                            ])
                        writer.writerow([])
                    
                    QMessageBox.information(self, "导出成功", 
                        f"多工况结果已导出到:\n{file_path}\n\n"
                        f"共导出 {len(self.all_case_results)} 个工况的数据\n\n"
                        f"每个工况包含:\n"
                        f"• 承台中心位移\n"
                        f"• 桩顶位移汇总\n"
                        f"• 桩顶内力汇总\n"
                        f"• 各桩桩顶响应详细数据")
                else:
                                                      
                    writer.writerow([f"桩基数量: {len(self.parser.pile_results)}"])
                    writer.writerow([])
                    
                                          
                                              
                    if self.current_mode_index == 2:        
                        if self.multi_case_radio.isChecked():
                                   
                            case_count = self.multi_case_table.rowCount() // 4
                            if case_count > 0:
                                writer.writerow(["【输入荷载】"])
                                writer.writerow([f"共 {case_count} 个荷载工况"])
                                writer.writerow([])
                                
                                cn_nums = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
                                for case_idx in range(case_count):
                                    base_row = case_idx * 4
                                    try:
                                        x_item = self.multi_case_table.item(base_row + 1, 2)
                                        y_item = self.multi_case_table.item(base_row + 1, 4)
                                        load_x = float(x_item.text()) if x_item else 0.0
                                        load_y = float(y_item.text()) if y_item else 0.0
                                        
                                        values = []
                                        for col in range(6):
                                            item = self.multi_case_table.item(base_row + 3, col)
                                            val = float(item.text()) if item else 0.0
                                            values.append(val)
                                        
                                        cn_idx = cn_nums[case_idx] if case_idx < 10 else str(case_idx + 1)
                                        writer.writerow([f"荷载{cn_idx}"])
                                        writer.writerow(["作用位置X (m)", "作用位置Y (m)", "FX (kN)", "FY (kN)", "FZ (kN)", "MX (kN·m)", "MY (kN·m)", "MZ (kN·m)"])
                                        writer.writerow([f"{load_x:.3f}", f"{load_y:.3f}", 
                                                        f"{values[0]:.2f}", f"{values[1]:.2f}", f"{values[2]:.2f}",
                                                        f"{values[3]:.2f}", f"{values[4]:.2f}", f"{values[5]:.2f}"])
                                        writer.writerow([])
                                    except Exception as e:
                                        logger.warning(f"读取荷载{case_idx+1}数据失败: {e}")
                        else:
                                   
                            try:
                                load_x = float(self.load_x_input.text() or 0)
                                load_y = float(self.load_y_input.text() or 0)
                                writer.writerow(["【输入荷载】"])
                                writer.writerow(["作用位置X (m)", "作用位置Y (m)"])
                                writer.writerow([f"{load_x:.3f}", f"{load_y:.3f}"])
                                writer.writerow([])
                                writer.writerow(["FX (kN)", "FY (kN)", "FZ (kN)", "MX (kN·m)", "MY (kN·m)", "MZ (kN·m)"])
                                loads_row = []
                                for key in ['nx', 'ny', 'nz', 'mx', 'my', 'mz']:
                                    val = float(self.loads[key].text() or 0)
                                    loads_row.append(f"{val:.2f}")
                                writer.writerow(loads_row)
                                writer.writerow([])
                            except Exception as e:
                                logger.warning(f"读取荷载数据失败: {e}")

                    
                                      
                    if self.parser.cap_result and self.parser.cap_result.displacement:
                        d = self.parser.cap_result.displacement
                        writer.writerow(["【承台中心位移】"])
                        writer.writerow(["项目", "数值", "单位"])
                        writer.writerow(["X方向位移", f"{d.x * 1000:.4f}", "mm"])
                        writer.writerow(["Y方向位移", f"{d.y * 1000:.4f}", "mm"])
                        writer.writerow(["竖向沉降", f"{d.z * 1000:.4f}", "mm"])
                        writer.writerow(["绕X轴转角", f"{d.rx * 1000:.6f}", "mrad"])
                        writer.writerow(["绕Y轴转角", f"{d.ry * 1000:.6f}", "mrad"])
                        writer.writerow(["绕Z轴转角", f"{d.rz * 1000:.6f}", "mrad"])
                        writer.writerow([])
                    
                                      
                    writer.writerow(["【桩顶位移汇总】"])
                    writer.writerow(["桩号", "UX (mm)", "UY (mm)", "UZ (mm)"])
                    for pile in self.parser.pile_results:
                        writer.writerow([
                            pile.pile_no,
                            f"{pile.top.displacement.x * 1000:.4f}",
                            f"{pile.top.displacement.y * 1000:.4f}",
                            f"{pile.top.displacement.z * 1000:.4f}"
                        ])
                    writer.writerow([])
                    
                                      
                    writer.writerow(["【桩顶内力汇总】"])
                    writer.writerow(["桩号", "NX (kN)", "NY (kN)", "NZ (kN)", "MX (kN·m)", "MY (kN·m)"])
                    for pile in self.parser.pile_results:
                        writer.writerow([
                            pile.pile_no,
                            f"{pile.top.force.x:.2f}",
                            f"{pile.top.force.y:.2f}",
                            f"{pile.top.force.z:.2f}",
                            f"{pile.top.force.rx:.2f}",
                            f"{pile.top.force.ry:.2f}"
                        ])
                    writer.writerow([])
                    
                                            
                    writer.writerow(["【各桩桩顶响应详细数据】"])
                    writer.writerow(["桩号", "UX (mm)", "UY (mm)", "UZ (mm)", "NX (kN)", "NY (kN)", "NZ (kN)", "MX (kN·m)", "MY (kN·m)"])
                    for pile in self.parser.pile_results:
                        writer.writerow([
                            pile.pile_no,
                            f"{pile.top.displacement.x * 1000:.4f}",
                            f"{pile.top.displacement.y * 1000:.4f}",
                            f"{pile.top.displacement.z * 1000:.4f}",
                            f"{pile.top.force.x:.2f}",
                            f"{pile.top.force.y:.2f}",
                            f"{pile.top.force.z:.2f}",
                            f"{pile.top.force.rx:.2f}",
                            f"{pile.top.force.ry:.2f}"
                        ])
                
                    QMessageBox.information(self, "导出成功", 
                        f"结果摘要已导出到:\n{file_path}\n\n"
                        f"包含数据表格:\n"
                        f"• 承台中心位移\n"
                        f"• 桩顶位移汇总\n"
                        f"• 桩顶内力汇总\n"
                        f"• 各桩桩顶响应详细数据")
            
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出结果摘要CSV失败:\n{e}")


    def _process_results(self, out_file, pos_file):
        def filter_bcad_pile_info(text):
            import re
            pattern = re.compile(r"[+]{10,}[\s\S]*?Copyright[\s\S]*?[+]{10,}[\s\S]*?Welcome to use the BCAD_PILE program[\s\S]*?P\.R\.of China", re.MULTILINE)
            text = re.sub(pattern, '', text)
            text = re.sub(r"BCAD[-_ ]?PILE[\s\S]*?Copyright[\s\S]*?Version[\s\S]*?\n", '', text, flags=re.IGNORECASE)
            text = re.sub(r"Welcome to use the BCAD_PILE program[\s\S]*?Tongji University[\s\S]*?P\.R\.of China", '', text, flags=re.IGNORECASE)
            text = re.sub(r"\n{3,}", '\n\n', text)
            
                                                        
            text = text.replace('(t*m)', '(kN·m)')
            text = text.replace('(t/m2)', '(kN/m²)')
            text = text.replace('(t)', '(kN)')
            
            return text.strip()

        if self.parser:
            try:
                success = self.parser.parse_out_file(out_file)
                if success:
                    filtered = filter_bcad_pile_info(self.parser.raw_output)
                    self.raw_output_text.setText(filtered)

                    summary = self._generate_summary()
                    self.summary_text.setText(summary)

                    logger.info(f"结果解析成功，模式: {self.parser.mode}")
                else:
                    filtered = filter_bcad_pile_info(self.parser.raw_output)
                    self.raw_output_text.setText(filtered)
                    self.summary_text.setText("结果解析失败，请查看原始输出")
                    logger.warning("结果解析失败")
            except Exception as e:
                logger.exception("解析结果文件时发生异常")
                self.summary_text.setText(f"解析错误: {e}")

                try:
                    with open(out_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        filtered = filter_bcad_pile_info(content)
                        self.raw_output_text.setText(filtered)
                except Exception:
                    pass
        else:
            try:
                with open(out_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    filtered = filter_bcad_pile_info(content)
                    self.raw_output_text.setText(filtered)
                    self.summary_text.setText("解析器不可用，请查看原始输出")
            except Exception as e:
                self.raw_output_text.setText(f"无法读取输出文件: {e}")

        self._plot_results()

                                                                             
           
                                                                             

    def _plot_results(self):
        plotter = getattr(self, "plotter", None)
        if not HAS_PLOTTER or not plotter or bytesio_to_qpixmap is None:
            for area_name in ("plot_3d_area", "plot_response_area", "plot_force_area"):
                area = getattr(self, area_name, None)
                if area is not None and hasattr(area, "setText"):
                    area.setText("绘图模块不可用")
            return

                            
        plot_tabs = getattr(self, "plot_tabs", None)
        if plot_tabs is None:
            logger.warning("plot_tabs 不存在，跳过绘图")
            return
        plot_tabs.clear()

                           
                         
        pile_types_data = {}
        for type_name in self.pile_type_names:
            if type_name in self.pile_type_editors:
                pile_types_data[type_name] = self.pile_type_editors[type_name].get_data()
        
        piles = []
        for row in range(self.pile_table.rowCount()):
            item0 = self.pile_table.item(row, 0)
            item1 = self.pile_table.item(row, 1)
            item2 = self.pile_table.item(row, 2)
            widget = self.pile_table.cellWidget(row, 3)

            if item0 and item1 and item2:
                try:
                    pile_data = {
                        'no': item0.text(),
                        'x': float(item1.text()),
                        'y': float(item2.text()),
                    }
                    if widget and isinstance(widget, QComboBox):
                        type_name = widget.currentText()
                        pile_data['type'] = type_name
                                    
                        if type_name in pile_types_data:
                            angle_cosines = pile_types_data[type_name].get('angle', [0, 0, 1])
                            if len(angle_cosines) >= 3:
                                                       
                                az = angle_cosines[2]                                 
                                az = max(-1.0, min(1.0, az))                        
                                angle_deg = math.acos(az) * 180 / math.pi
                                pile_data['angle'] = angle_deg
                    piles.append(pile_data)
                except ValueError:
                    pass

        if not piles:
                         
            empty_label = QLabel("无桩位数据可供绘图")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.plot_tabs.addTab(empty_label, "提示")
            return

                                
        loads = {}
        
                                        
                                                           
        if self.current_mode_index == 2 and hasattr(self, '_reverse_force_vector') and self._reverse_force_vector:
            f = self._reverse_force_vector
            loads = {
                'nx': f[0], 'ny': f[1], 'nz': f[2],
                'mx': f[3], 'my': f[4], 'mz': f[5]
            }
        
                                      
        elif hasattr(self, 'multi_case_radio') and self.multi_case_radio.isChecked():
            loads_list = []
            
            row_count = self.multi_case_table.rowCount()
                                       
            num_cases = row_count // 4
            for i in range(num_cases):
                base_row = i * 4
                try:
                                               
                    cx = float(self.multi_case_table.item(base_row + 1, 2).text() or 0)
                    cy = float(self.multi_case_table.item(base_row + 1, 4).text() or 0)
                                         
                    name = self.multi_case_table.item(base_row + 1, 0).text() or f"荷载 {i+1}"
                                                                    
                    load_data = {
                        'cx': cx,
                        'cy': cy,
                        'name': name,
                        'nx': float(self.multi_case_table.item(base_row + 3, 0).text() or 0),
                        'ny': float(self.multi_case_table.item(base_row + 3, 1).text() or 0),
                        'nz': float(self.multi_case_table.item(base_row + 3, 2).text() or 0),
                        'mx': float(self.multi_case_table.item(base_row + 3, 3).text() or 0),
                        'my': float(self.multi_case_table.item(base_row + 3, 4).text() or 0),
                        'mz': float(self.multi_case_table.item(base_row + 3, 5).text() or 0),
                    }
                    loads_list.append(load_data)
                except Exception:
                    pass
            
            loads = loads_list if loads_list else {}
        
                         
        else:
            for key, widget in self.loads.items():
                try:
                    val = float(widget.text() or 0)
                                             
                    loads[key] = val
                except ValueError:
                    loads[key] = 0


                                       
        fig_3d = None
        fig_2d = None
        fig_stiffness = None
                           
        plot_area_size = self.plot_tabs.size()
        plot_width = max(plot_area_size.width(), 800)
        plot_height = max(plot_area_size.height(), 600)
                  
        target_dpi = self._get_adaptive_dpi() + 80              
                            
        figsize_3d = self._get_adaptive_figsize(10, 8)
        figsize_2d = self._get_adaptive_figsize(10, 8)

                                      
        try:
            fig_3d = self.plotter.plot_pile_3d(
                piles=piles,
                loads=None,
                pile_depth=15,
                cap_margin=1.5,
                cap_thickness=0.8,
                pile_radius=0.35,
                title="桩基三维布置图",
                figsize=figsize_3d,
                dpi=target_dpi,
                show_loads=False,
                show_pile_numbers=True,
                return_fig=True,
                pile_types_data=pile_types_data           
            )
        except Exception as e:
            logger.warning(f"3D 绘图失败: {e}")
            fig_3d = None

                    
        highlight_pile_no = None
        if self.current_mode_index == 3:
            highlight_pile_no = self.pile_ino_input.value()

                              
        try:
            fig_2d = self.plotter.plot_pile_layout(
                piles=piles,
                loads=loads,             
                title="桩基平面布置图",
                highlight_pile_no=highlight_pile_no,
                figsize=figsize_2d,
                return_fig=True,
                pile_types_data=pile_types_data,           
                simulated_piles=self._collect_simulative_piles_for_plot()           
            )
        except Exception as e:
            logger.warning(f"平面图绘制失败: {e}")
            fig_2d = None

                           
        def get_stiffness_figure(title, matrix_type):
            return self._generate_stiffness_pixmap(title, matrix_type)

                              
        target_tab_index = 0
        logger.info(f"_plot_results: current_mode_index={self.current_mode_index}, parser={self.parser is not None}, pile_results={len(self.parser.pile_results) if self.parser and self.parser.pile_results else 0}")
        if self.current_mode_index in [0, 1]:
            self._add_plot_tab(fig_3d, "立体布置图")
            self._add_plot_tab(fig_2d, "平面布置图")
            if self._create_pile_response_tabs():
                target_tab_index = 2
            if self.current_mode_index == 1:
                fig_stiffness = get_stiffness_figure("承台刚度矩阵（反算使用）", "foundation")
                if fig_stiffness:
                    self._add_plot_tab(fig_stiffness, "刚度矩阵")
        elif self.current_mode_index == 2:
            self._add_plot_tab(fig_3d, "立体布置图")
            self._add_plot_tab(fig_2d, "平面布置图")
                                      
            if self.parser and self.parser.pile_results:
                if self._create_pile_response_tabs():
                    target_tab_index = 2
        elif self.current_mode_index == 3:
            self._add_plot_tab(fig_3d, "立体布置图")
            self._add_plot_tab(fig_2d, f"平面布置图 (桩{highlight_pile_no}高亮)")
        else:
            self._add_plot_tab(fig_3d, "立体布置图")
            self._add_plot_tab(fig_2d, "平面布置图")

                             
        self.visual_tabs.setCurrentIndex(1)            
        if self.plot_tabs.count() > target_tab_index:
            self.plot_tabs.setCurrentIndex(target_tab_index)

    def _generate_pile_response_pixmap(self):
        if not self.parser or not self.parser.pile_results:
            logger.warning("无桩身响应数据")
            return None
        
        try:
            first_pile = self.parser.pile_results[0]
            buf_response = self.plotter.plot_pile_results(
                pile_result=first_pile,
                plot_type='all',
                figsize=(14, 10)
            )
            return bytesio_to_qpixmap(buf_response)
        except Exception as e:
            logger.error(f"绘制桩身响应失败: {e}")
            return None

    def _find_critical_pile(self, pile_results) -> str:
        if not pile_results:
            return None
        
        max_score = 0
        critical_pile_no = pile_results[0].pile_no
        
        for pile_result in pile_results:
            try:
                        
                ux_list, uy_list = pile_result.get_displacements()
                max_ux = max(abs(v) for v in ux_list) if ux_list else 0
                max_uy = max(abs(v) for v in uy_list) if uy_list else 0
                
                        
                mx_list, my_list = pile_result.get_moments()
                max_mx = max(abs(v) for v in mx_list) if mx_list else 0
                max_my = max(abs(v) for v in my_list) if my_list else 0
                
                                     
                                 
                score = (max_ux * 1000 + max_uy * 1000) * 2 + (max_mx + max_my)
                
                if score > max_score:
                    max_score = score
                    critical_pile_no = pile_result.pile_no
            except Exception as e:
                logger.warning(f"评估桩{pile_result.pile_no}时出错: {e}")
                continue
        
        logger.info(f"最不利响应桩: {critical_pile_no}")
        return critical_pile_no

    def _create_pile_response_tabs(self) -> bool:
        logger.info("_create_pile_response_tabs 被调用")
        
        if not self.parser:
            logger.warning("parser 为空，无法创建动态Tab")
            return False
            
        if not self.parser.pile_results:
            logger.warning(f"pile_results 为空，无法创建动态Tab")
            return False
        
        logger.info(f"准备为 {len(self.parser.pile_results)} 根桩创建响应Tab")
        
        pile_results = self.parser.pile_results
        
                                   
        critical_pile_no = self._find_critical_pile(pile_results)
        
                            
        piles = []
        for row in range(self.pile_table.rowCount()):
            item0 = self.pile_table.item(row, 0)
            item1 = self.pile_table.item(row, 1)
            item2 = self.pile_table.item(row, 2)
            if item0 and item1 and item2:
                try:
                    piles.append({
                        'no': item0.text(),
                        'x': float(item1.text()),
                        'y': float(item2.text()),
                    })
                except ValueError:
                    pass
        
                           
        pile_response_container = QTabWidget()
        pile_response_container.setTabPosition(QTabWidget.TabPosition.North)
        
        for pile_result in pile_results:
            pile_no = pile_result.pile_no
            is_critical = (str(pile_no) == str(critical_pile_no))
            logger.info(f"创建桩{pile_no}的响应Tab" + (" [最不利桩]" if is_critical else ""))
            
            try:
                                               
                pile_tab = QTabWidget()
                pile_tab.setTabPosition(QTabWidget.TabPosition.North)
                
                              
                tab_disp = self._create_chart_tab(pile_result, piles, 'force_displacement', is_critical)
                pile_tab.addTab(tab_disp, "位移")
                
                              
                tab_axial = self._create_chart_tab(pile_result, piles, 'axial_force', is_critical)
                pile_tab.addTab(tab_axial, "轴力")
                
                           
                tab_moment = self._create_chart_tab(pile_result, piles, 'moment', is_critical)
                pile_tab.addTab(tab_moment, "弯矩")
                
                                            
                tab_name = f"桩{pile_no}"
                if is_critical:
                    tab_name = f"★桩{pile_no}"
                pile_response_container.addTab(pile_tab, tab_name)
                
            except Exception as e:
                logger.error(f"创建桩{pile_no}的响应Tab失败: {e}")
                continue
        
                                       
        if pile_response_container.count() > 0:
            tab_index = self.plot_tabs.addTab(pile_response_container, "桩身响应")
            logger.info(f"桩身响应Tab创建成功，共 {pile_response_container.count()} 个桩Tab")
            return True
        else:
            logger.warning("没有成功创建任何桩的响应Tab")
            return False

    def _create_chart_tab(self, pile_result, piles: list, chart_type: str, is_critical: bool = False) -> QWidget:
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)
        tab_layout.setContentsMargins(2, 2, 2, 2)
        tab_layout.setSpacing(2)
        
        pile_no = pile_result.pile_no
        
                    
        figsize = self._get_adaptive_figsize(9, 3.5)
        
        try:
                                               
            if HAS_MATPLOTLIB_QT:
                                           
                if chart_type == 'force_displacement':
                    fig = self.plotter.create_pile_force_displacement_figure(
                        pile_result, piles=piles, figsize=figsize, is_critical=is_critical
                    )
                elif chart_type == 'axial_force':
                    fig = self.plotter.create_pile_axial_force_figure(
                        pile_result, piles=piles, figsize=figsize, is_critical=is_critical
                    )
                elif chart_type == 'moment':
                    fig = self.plotter.create_pile_moment_figure(
                        pile_result, piles=piles, figsize=figsize, is_critical=is_critical
                    )
                else:
                    raise ValueError(f"未知图表类型: {chart_type}")
                
                                 
                canvas = FigureCanvas(fig)
                canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                
                                      
                toolbar = NavigationToolbar(canvas, tab_widget)
                toolbar.setStyleSheet("""
                    QToolBar {
                        background-color: #f0f0f0;
                        border: 1px solid #ccc;
                        border-radius: 3px;
                        spacing: 3px;
                        padding: 2px;
                    }
                """)
                
                       
                tab_layout.addWidget(toolbar)
                tab_layout.addWidget(canvas)
                
            else:
                           
                chart_label = ScalableImageLabel()
                chart_label.setStyleSheet("background-color: #f8f8f8;")
                
                dpi = self._get_adaptive_dpi()
                
                if chart_type == 'force_displacement':
                    buf = self.plotter.plot_pile_force_displacement(
                        pile_result, piles=piles, figsize=figsize, dpi=dpi, is_critical=is_critical
                    )
                elif chart_type == 'axial_force':
                    buf = self.plotter.plot_pile_axial_force(
                        pile_result, piles=piles, figsize=figsize, dpi=dpi, is_critical=is_critical
                    )
                elif chart_type == 'moment':
                    buf = self.plotter.plot_pile_moment(
                        pile_result, piles=piles, figsize=figsize, dpi=dpi, is_critical=is_critical
                    )
                else:
                    raise ValueError(f"未知图表类型: {chart_type}")
                
                pixmap = bytesio_to_qpixmap(buf)
                if pixmap and not pixmap.isNull():
                    chart_label.setOriginalPixmap(pixmap)
                else:
                    chart_label.setText(f"桩{pile_no} 图像生成失败")
                    chart_label.setStyleSheet("font-size: 14px; color: #888; background-color: #f8f8f8;")
                
                tab_layout.addWidget(chart_label)
                
        except Exception as e:
            logger.error(f"生成桩{pile_no}图表失败: {e}")
            error_label = QLabel(f"桩{pile_no}: {e}")
            error_label.setStyleSheet("font-size: 14px; color: #c00; background-color: #f8f8f8;")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tab_layout.addWidget(error_label)
        
        return tab_widget

    def _generate_stiffness_pixmap(self, title: str, matrix_type: str):
        if not self.parser or self.parser.stiffness_matrix is None:
            logger.warning(f"刚度矩阵数据不可用: {title}")
            return None
        
        try:
            import numpy as np
            
            stiffness_matrix = self.parser.stiffness_matrix
            if hasattr(stiffness_matrix, 'data'):
                k_array = stiffness_matrix.data
            elif isinstance(stiffness_matrix, np.ndarray):
                k_array = stiffness_matrix
            else:
                k_array = np.array([[stiffness_matrix[i, j] for j in range(6)] for i in range(6)])
            
            buf_stiffness = self.plotter.plot_stiffness_matrix(
                stiffness_matrix=k_array,
                title=title,
                matrix_type=matrix_type,
                figsize=(12, 10)
            )
            return bytesio_to_qpixmap(buf_stiffness)
        except Exception as e:
            logger.error(f"绘制刚度矩阵失败: {e}")
            return None

    def _plot_response_by_mode(self):
        pass

    def _plot_pile_response(self):
        if not self.parser or not self.parser.pile_results:
            self.plot_response_area.setText("无桩身响应数据\n\n仅荷载→内力变形模式可查看桩身详细响应")
            logger.warning("模式1但无桩身响应数据")
            return
        
        try:
                          
            first_pile = self.parser.pile_results[0]
            buf_response = self.plotter.plot_pile_results(
                pile_result=first_pile,
                plot_type='all',
                figsize=(14, 10)
            )
            pixmap_response = bytesio_to_qpixmap(buf_response)
            self._display_plot(pixmap_response, target='response')
            logger.info(f"已绘制第 {first_pile.pile_no} 号桩的响应曲线")
        except Exception as e:
            logger.error(f"绘制桩身响应失败: {e}")
            self.plot_response_area.setText(f"桩身响应绘制失败: {e}")

    def _plot_stiffness_visualization(self, stiffness_matrix, title: str, matrix_type: str):
        try:
            import numpy as np
            
                          
            if hasattr(stiffness_matrix, 'data'):
                k_array = stiffness_matrix.data
            elif isinstance(stiffness_matrix, np.ndarray):
                k_array = stiffness_matrix
            else:
                                   
                k_array = np.array([[stiffness_matrix[i, j] for j in range(6)] for i in range(6)])
            
            buf_stiffness = self.plotter.plot_stiffness_matrix(
                stiffness_matrix=k_array,
                title=title,
                matrix_type=matrix_type,
                figsize=(12, 10)
            )
            pixmap_stiffness = bytesio_to_qpixmap(buf_stiffness)
            self._display_plot(pixmap_stiffness, target='response')
            logger.info(f"已绘制刚度矩阵可视化: {title}")
        except Exception as e:
            logger.error(f"绘制刚度矩阵失败: {e}")
            self.plot_response_area.setText(f"刚度矩阵可视化失败: {e}")

    def _display_plot(self, pixmap, target='3d'):
                 
        title_map = {
            '3d': '立体布置图',
            'response': '桩身响应',
            'force': '受力分析图'
        }
        title = title_map.get(target, '绘图')
        
        if pixmap is None or pixmap.isNull():
                           
            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)
            tab_layout.setContentsMargins(5, 5, 5, 5)
            
            error_label = QLabel(f"{title}: 图像生成失败")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_label.setStyleSheet("font-size: 14px; color: #888; background-color: #f5f5f5;")
            
            tab_layout.addWidget(error_label)
            tab_index = self.plot_tabs.addTab(tab_widget, title)
        else:
                                   
            tab_index = self._add_plot_tab(pixmap, title)
        
                       
        self.visual_tabs.setCurrentIndex(1)
                      
        self.plot_tabs.setCurrentIndex(tab_index)

    def _add_plot_tab(self, plot_obj, title: str) -> int:
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)
        tab_layout.setContentsMargins(5, 5, 5, 5)
        tab_layout.setSpacing(0)

              
        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_qtagg import FigureCanvas, NavigationToolbar2QT as NavigationToolbar
        except ImportError:
            Figure = None
            FigureCanvas = None
            NavigationToolbar = None

        if Figure is not None and isinstance(plot_obj, Figure):
            canvas = FigureCanvas(plot_obj)
            toolbar = NavigationToolbar(canvas, tab_widget)
            tab_layout.addWidget(toolbar)
            tab_layout.addWidget(canvas)
        else:
                           
            plot_label = ScalableImageLabel()
            plot_label.setStyleSheet(
                "font-size: 14px; color: #888; background-color: #f5f5f5;"
            )
            if plot_obj and hasattr(plot_obj, 'isNull') and not plot_obj.isNull():
                plot_label.setOriginalPixmap(plot_obj)
            else:
                plot_label.setText(f"{title}: 图像生成失败")
            tab_layout.addWidget(plot_label)

        tab_index = self.plot_tabs.addTab(tab_widget, title)
        return tab_index

                                                                             
             
                                                                             

    def _export_all_results(self, plots_only=False, text_only=False):
        from PySide6.QtWidgets import QFileDialog
        from datetime import datetime
        
                    
        piles = self._collect_pile_data_for_plot()
        has_plots = HAS_PLOTTER and self.plotter and piles
        has_summary = bool(self.summary_text.toPlainText().strip())
        has_raw = bool(self.raw_output_text.toPlainText().strip())
        has_text = has_summary or has_raw
        has_pile_results = self.parser and self.parser.pile_results and len(self.parser.pile_results) > 0
        
        if plots_only and not has_plots:
            QMessageBox.warning(self, "警告", "没有桩位数据，无法生成图片")
            return
        
        if text_only and not has_text:
            QMessageBox.warning(self, "警告", "没有计算结果可导出")
            return
        
        if not has_plots and not has_text:
            QMessageBox.warning(self, "警告", "没有可导出的内容")
            return
        
                
        save_dir = QFileDialog.getExistingDirectory(
            self, "选择导出目录", 
            str(Path.home() / "Desktop"),
            QFileDialog.Option.ShowDirsOnly
        )
        
        if not save_dir:
            return        
        
                         
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mode_names = ["荷载分析", "位移反算", "承台刚度", "单桩刚度"]
        mode_name = mode_names[self.current_mode_index] if 0 <= self.current_mode_index < 4 else "分析"
        folder_name = f"桩基{mode_name}_{timestamp}"
        export_folder = Path(save_dir) / folder_name
        export_folder.mkdir(parents=True, exist_ok=True)
        
        exported_files = []
        errors = []
        
                
        total_steps = 0
        if not text_only and has_plots:
            total_steps += 2             
            if has_pile_results:
                total_steps += len(self.parser.pile_results) * 3          
            if self.parser and self.parser.stiffness_matrix is not None:
                total_steps += 1        
        if not plots_only and has_text:
            total_steps += 2             
        
               
        progress = QProgressDialog("正在导出...", "取消", 0, total_steps, self)
        progress.setWindowTitle("导出结果")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        current_step = 0
        
                
        export_dpi = 300
        export_figsize_large = (14, 10)
        export_figsize_response = (12, 5)
        
                       
        pile_types_data = {}
        for type_name in self.pile_type_names:
            if type_name in self.pile_type_editors:
                pile_types_data[type_name] = self.pile_type_editors[type_name].get_data()
        
        try:
                          
            if not text_only and has_plots:
                             
                progress.setLabelText("正在导出 3D 立体布置图...")
                QApplication.processEvents()
                if progress.wasCanceled():
                    return
                
                try:
                    buf_3d = self.plotter.plot_pile_3d(
                        piles=piles,
                        loads=None,
                        pile_depth=15,
                        cap_margin=1.5,
                        cap_thickness=0.8,
                        pile_radius=0.35,
                        title="桩基三维布置图",
                        figsize=export_figsize_large,
                        dpi=export_dpi,
                        show_loads=False,
                        show_pile_numbers=True,
                        pile_types_data=pile_types_data           
                    )
                    file_3d = export_folder / "01_立体布置图.png"
                    with open(file_3d, 'wb') as f:
                        f.write(buf_3d.getvalue())
                    exported_files.append(("图片", "01_立体布置图.png"))
                except Exception as e:
                    errors.append(f"3D立体图: {e}")
                
                current_step += 1
                progress.setValue(current_step)
                
                             
                progress.setLabelText("正在导出 2D 平面布置图...")
                QApplication.processEvents()
                if progress.wasCanceled():
                    return
                
                try:
                    highlight_pile_no = None
                    if self.current_mode_index == 3:
                        highlight_pile_no = self.pile_ino_input.value()
                    
                    buf_2d = self.plotter.plot_pile_layout(
                        piles=piles,
                        loads=None,
                        title="桩基平面布置图",
                        figsize=export_figsize_large,
                        highlight_pile_no=highlight_pile_no,
                        pile_types_data=pile_types_data,           
                        simulated_piles=self._collect_simulative_piles_for_plot()           
                    )
                    file_2d = export_folder / "02_平面布置图.png"
                    with open(file_2d, 'wb') as f:
                        f.write(buf_2d.getvalue())
                    exported_files.append(("图片", "02_平面布置图.png"))
                except Exception as e:
                    errors.append(f"2D平面图: {e}")
                
                current_step += 1
                progress.setValue(current_step)
                
                                         
                if has_pile_results:
                    for pile_result in self.parser.pile_results:
                        pile_no = pile_result.pile_no
                        pile_folder = export_folder / f"桩{pile_no}"
                        pile_folder.mkdir(parents=True, exist_ok=True)
                        
                                   
                        progress.setLabelText(f"正在导出桩{pile_no}的位移分布图...")
                        QApplication.processEvents()
                        if progress.wasCanceled():
                            return
                        
                        try:
                            buf_disp = self.plotter.plot_pile_force_displacement(
                                pile_result=pile_result,
                                piles=piles,
                                figsize=export_figsize_response,
                                dpi=export_dpi
                            )
                            file_disp = pile_folder / "位移分布.png"
                            with open(file_disp, 'wb') as f:
                                f.write(buf_disp.getvalue())
                            exported_files.append(("图片", f"桩{pile_no}/位移分布.png"))
                        except Exception as e:
                            errors.append(f"桩{pile_no}位移图: {e}")
                        
                        current_step += 1
                        progress.setValue(current_step)
                        
                                   
                        progress.setLabelText(f"正在导出桩{pile_no}的轴力分布图...")
                        QApplication.processEvents()
                        if progress.wasCanceled():
                            return
                        
                        try:
                            buf_axial = self.plotter.plot_pile_axial_force(
                                pile_result=pile_result,
                                piles=piles,
                                figsize=export_figsize_response,
                                dpi=export_dpi
                            )
                            file_axial = pile_folder / "轴力分布.png"
                            with open(file_axial, 'wb') as f:
                                f.write(buf_axial.getvalue())
                            exported_files.append(("图片", f"桩{pile_no}/轴力分布.png"))
                        except Exception as e:
                            errors.append(f"桩{pile_no}轴力图: {e}")
                        
                        current_step += 1
                        progress.setValue(current_step)
                        
                                   
                        progress.setLabelText(f"正在导出桩{pile_no}的弯矩分布图...")
                        QApplication.processEvents()
                        if progress.wasCanceled():
                            return
                        
                        try:
                            buf_moment = self.plotter.plot_pile_moment(
                                pile_result=pile_result,
                                piles=piles,
                                figsize=export_figsize_response,
                                dpi=export_dpi
                            )
                            file_moment = pile_folder / "弯矩分布.png"
                            with open(file_moment, 'wb') as f:
                                f.write(buf_moment.getvalue())
                            exported_files.append(("图片", f"桩{pile_no}/弯矩分布.png"))
                        except Exception as e:
                            errors.append(f"桩{pile_no}弯矩图: {e}")
                        
                        current_step += 1
                        progress.setValue(current_step)
                
                          
                if self.parser and self.parser.stiffness_matrix is not None:
                    progress.setLabelText("正在导出刚度矩阵图...")
                    QApplication.processEvents()
                    if progress.wasCanceled():
                        return
                    
                    try:
                        import numpy as np
                        stiffness_matrix = self.parser.stiffness_matrix
                        if hasattr(stiffness_matrix, 'data'):
                            k_array = stiffness_matrix.data
                        elif isinstance(stiffness_matrix, np.ndarray):
                            k_array = stiffness_matrix
                        else:
                            k_array = np.array([[stiffness_matrix[i, j] for j in range(6)] for i in range(6)])
                        
                        if self.current_mode_index == 3:
                            title = f"单桩刚度矩阵（桩号: {self.parser.single_pile_no or '1'}）"
                            matrix_type = "single_pile"
                        else:
                            title = "承台整体刚度矩阵"
                            matrix_type = "foundation"
                        
                        buf_stiffness = self.plotter.plot_stiffness_matrix(
                            stiffness_matrix=k_array,
                            title=title,
                            matrix_type=matrix_type,
                            figsize=(14, 12)
                        )
                        file_stiffness = export_folder / "03_刚度矩阵.png"
                        with open(file_stiffness, 'wb') as f:
                            f.write(buf_stiffness.getvalue())
                        exported_files.append(("图片", "03_刚度矩阵.png"))
                    except Exception as e:
                        errors.append(f"刚度矩阵: {e}")
                    
                    current_step += 1
                    progress.setValue(current_step)
            
                            
            if not plots_only and has_text:
                      
                progress.setLabelText("正在导出结果摘要...")
                QApplication.processEvents()
                if progress.wasCanceled():
                    return
                
                if has_summary:
                    try:
                        summary_file = export_folder / "结果摘要.txt"
                        with open(summary_file, 'w', encoding='utf-8') as f:
                            f.write("=" * 70 + "\n")
                            f.write(f"桩基分析结果摘要\n")
                            f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                            f.write(f"计算模式: {mode_name}\n")
                            f.write("=" * 70 + "\n\n")
                            f.write(self.summary_text.toPlainText())
                        exported_files.append(("文本", "结果摘要.txt"))
                    except Exception as e:
                        errors.append(f"结果摘要: {e}")
                
                current_step += 1
                progress.setValue(current_step)
                
                      
                progress.setLabelText("正在导出原始输出...")
                QApplication.processEvents()
                if progress.wasCanceled():
                    return
                
                if has_raw:
                    try:
                        raw_file = export_folder / "原始输出.txt"
                        with open(raw_file, 'w', encoding='utf-8') as f:
                            f.write("=" * 70 + "\n")
                            f.write(f"计算内核原始输出\n")
                            f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                            f.write("=" * 70 + "\n\n")
                            f.write(self.raw_output_text.toPlainText())
                        exported_files.append(("文本", "原始输出.txt"))
                    except Exception as e:
                        errors.append(f"原始输出: {e}")
                
                current_step += 1
                progress.setValue(current_step)
            
                               
            if not plots_only:
                progress.setLabelText("正在导出 CSV 数据...")
                QApplication.processEvents()
                csv_results = self._export_results_csv(export_folder)
                exported_files.extend(csv_results)
            
        finally:
            progress.close()
        
              
        if exported_files:
            result_msg = f"成功导出到文件夹:\n{export_folder}\n\n"
            
                  
            plot_files = [f[1] for f in exported_files if f[0] == "图片"]
            text_files = [f[1] for f in exported_files if f[0] == "文本"]
            csv_files = [f[1] for f in exported_files if f[0] == "CSV"]
            
                      
            pile_count = 0
            if has_pile_results:
                pile_count = len(self.parser.pile_results)
            
            if plot_files:
                result_msg += "图片文件:\n"
                                  
                main_plots = [f for f in plot_files if '桩' not in f or '/' not in f]
                for f in main_plots:
                    result_msg += f"  • {f}\n"
                if pile_count > 0:
                    result_msg += f"  • 桩身响应图: {pile_count}根桩 × 3张 = {pile_count * 3}张\n"
                    result_msg += f"    (每根桩独立文件夹，含位移/轴力/弯矩)\n"
            
            if text_files:
                result_msg += "\n文本文件:\n"
                for f in text_files:
                    result_msg += f"  • {f}\n"

            if csv_files:
                result_msg += "\n数据表格 (CSV):\n"
                for f in csv_files:
                    result_msg += f"  • {f}\n"
            
            if errors:
                result_msg += f"\n导出失败:\n"
                for err in errors:
                    result_msg += f"  • {err}\n"
            
            QMessageBox.information(self, "导出完成", result_msg)
            
                     
                               
                                                             
        else:
            QMessageBox.warning(self, "导出失败", "没有成功导出任何内容\n\n" + "\n".join(errors))

    def _export_results_csv(self, export_folder: Path) -> list:
        import csv
        exported = []
        
                         
        if self.parser and self.parser.cases:
            csv_file = export_folder / "Analysis_Results.csv"
            try:
                with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                            
                    headers = [
                        "Case ID", "Item Type", "ID", 
                        "Disp X (m)", "Disp Y (m)", "Disp Z (m)", 
                        "Rot X (rad)", "Rot Y (rad)", "Rot Z (rad)",
                        "Force X (kN)", "Force Y (kN)", "Force Z (kN)", 
                        "Moment X (kN.m)", "Moment Y (kN.m)", "Moment Z (kN.m)"
                    ]
                    writer.writerow(headers)
                    
                    for case in self.parser.cases:
                        case_id = case.case_id
                        
                                    
                        if case.cap_result:
                            d = case.cap_result.displacement
                            row = [
                                case_id, "Cap", "Center",
                                f"{d.x:.6e}", f"{d.y:.6e}", f"{d.z:.6e}",
                                f"{d.rx:.6e}", f"{d.ry:.6e}", f"{d.rz:.6e}",
                                "", "", "", "", "", ""
                            ]
                            writer.writerow(row)
                            
                                            
                        for pile in case.pile_results:
                            d = pile.top.displacement
                            f_val = pile.top.force
                            row = [
                                case_id, "Pile Top", pile.pile_no,
                                f"{d.x:.6e}", f"{d.y:.6e}", f"{d.z:.6e}",
                                f"{d.rx:.6e}", f"{d.ry:.6e}", f"{d.rz:.6e}",
                                f"{f_val.x:.6e}", f"{f_val.y:.6e}", f"{f_val.z:.6e}",
                                f"{f_val.rx:.6e}", f"{f_val.ry:.6e}", f"{f_val.rz:.6e}"
                            ]
                            writer.writerow(row)
                exported.append(("CSV", "Analysis_Results.csv"))
            except Exception as e:
                logger.error(f"导出分析结果 CSV 失败: {e}")

                   
        if self.parser and self.parser.stiffness_matrix is not None:
            csv_file = export_folder / "Stiffness_Matrix.csv"
            try:
                with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Stiffness Matrix (6x6)"])
                    
                    stiffness_matrix = self.parser.stiffness_matrix
                    data = []
                    
                          
                    if hasattr(stiffness_matrix, 'data'):
                         data = stiffness_matrix.data
                    else:
                                                              
                         try:
                             for i in range(6):
                                 row = []
                                 for j in range(6):
                                     row.append(stiffness_matrix[i, j])
                                 data.append(row)
                         except:
                             pass
                    
                    for row in data:
                        writer.writerow([f"{val:.6e}" for val in row])
                
                exported.append(("CSV", "Stiffness_Matrix.csv"))
            except Exception as e:
                logger.error(f"导出刚度矩阵 CSV 失败: {e}")

        return exported
    
    def _collect_pile_data_for_plot(self) -> list:
        pile_types_data = {}
        for type_name in self.pile_type_names:
            if type_name in self.pile_type_editors:
                pile_types_data[type_name] = self.pile_type_editors[type_name].get_data()
        
        piles = []
        for row in range(self.pile_table.rowCount()):
            item0 = self.pile_table.item(row, 0)
            item1 = self.pile_table.item(row, 1)
            item2 = self.pile_table.item(row, 2)
            widget = self.pile_table.cellWidget(row, 3)

            if item0 and item1 and item2:
                try:
                    pile_data = {
                        'no': item0.text(),
                        'x': float(item1.text()),
                        'y': float(item2.text()),
                    }
                    if widget and isinstance(widget, QComboBox):
                        type_name = widget.currentText()
                        pile_data['type'] = type_name
                        if type_name in pile_types_data:
                            angle_cosines = pile_types_data[type_name].get('angle', [0, 0, 1])
                            if len(angle_cosines) >= 3:
                                az = angle_cosines[2]
                                az = max(-1.0, min(1.0, az))
                                angle_deg = math.acos(az) * 180 / math.pi
                                pile_data['angle'] = angle_deg
                    piles.append(pile_data)
                except ValueError:
                    pass
        return piles

    def _collect_simulative_piles_for_plot(self) -> list:
        simulative_piles = []
        if self.use_simulative_pile_checkbox.isChecked():
                       
            is_matrix_mode = self.simu_type_matrix_radio.isChecked()
            rows_per_pile = 9 if is_matrix_mode else 4
            row_count = self.simu_pile_table.rowCount()
            
            for base_row in range(0, row_count, rows_per_pile):
                if base_row + rows_per_pile - 1 >= row_count:
                    break
                    
                try:
                                          
                    item_x = self.simu_pile_table.item(base_row + 1, 2)
                    item_y = self.simu_pile_table.item(base_row + 1, 4)
                    
                    x_val = float(item_x.text()) if item_x else 0.0
                    y_val = float(item_y.text()) if item_y else 0.0
                    
                    simulative_piles.append({
                        'x': x_val,
                        'y': y_val,
                        'no': f"SIMU{(base_row//rows_per_pile) + 1}"
                    })
                    
                except ValueError:
                    pass
        return simulative_piles

    @staticmethod
    def show_parameter_reference():
        help_dialog = QDialog()
        help_dialog.setWindowTitle("桩基分析 参数参考值")
        
                  
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.availableGeometry()
            dialog_width = min(900, int(screen_geo.width() * 0.55))
            dialog_height = min(700, int(screen_geo.height() * 0.65))
        else:
            dialog_width, dialog_height = 900, 700
        help_dialog.resize(dialog_width, dialog_height)
        
        layout = QVBoxLayout(help_dialog)
        
                         
        tabs = QTabWidget()
        
                       
        m_value_widget = QTextEdit()
        m_value_widget.setReadOnly(True)
        m_value_widget.setHtml("""
        <h2>非岩石类土的 m 值参考表</h2>
        <p><b>适用参数：</b>PMT (桩侧土), PMB (当 KSU=1,2 时)</p>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <tr style="background-color: #1976D2; color: white;">
                <th>土的名称</th>
                <th>状态 (液性指数 I<sub>L</sub>)</th>
                <th>m 值范围 (kN/m⁴)</th>
            </tr>
            <tr><td>流塑粘性土、淤泥</td><td>I<sub>L</sub> ≥ 1</td><td>3,000 ~ 5,000</td></tr>
            <tr style="background-color: #E3F2FD;"><td>软塑粘性土、粉砂</td><td>1 > I<sub>L</sub> ≥ 0.5</td><td>5,000 ~ 10,000</td></tr>
            <tr><td>硬塑粘性土、细/中砂</td><td>0.5 > I<sub>L</sub> ≥ 0</td><td>10,000 ~ 20,000</td></tr>
            <tr style="background-color: #E3F2FD;"><td>坚硬粘性土、粗砂</td><td>I<sub>L</sub> < 0</td><td>20,000 ~ 30,000</td></tr>
            <tr><td>砾砂、碎石、卵石</td><td>-</td><td>30,000 ~ 80,000</td></tr>
            <tr style="background-color: #E3F2FD;"><td>密实卵石、漂石</td><td>-</td><td>80,000 ~ 120,000</td></tr>
        </table>
        """)
        tabs.addTab(m_value_widget, "土的 m 值")
        
                       
        c0_widget = QTextEdit()
        c0_widget.setReadOnly(True)
        c0_widget.setHtml("""
        <h2>岩石地基系数 c₀ 参考表</h2>
        <p><b>适用参数：</b>PMB (仅当 KSU=3,4 时)</p>
        <p style="color: red;"><b>注意：单位是 kN/m³ (立方米)，与土的 m 值单位不同！</b></p>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <tr style="background-color: #1976D2; color: white;">
                <th>岩石强度描述</th>
                <th>单轴极限抗压 R<sub>a</sub> (kPa)</th>
                <th>c₀ 参考值 (kN/m³)</th>
            </tr>
            <tr><td>极软岩</td><td>1,000</td><td>3.0 × 10⁵</td></tr>
            <tr style="background-color: #E3F2FD;"><td>软岩</td><td>5,000</td><td>≈ 2.75 × 10⁶</td></tr>
            <tr><td>较硬岩</td><td>15,000</td><td>≈ 8.8 × 10⁶</td></tr>
            <tr style="background-color: #E3F2FD;"><td>坚硬岩</td><td>≥ 25,000</td><td>1.5 × 10⁷</td></tr>
        </table>
        """)
        tabs.addTab(c0_widget, "岩石 c₀ 值")
        
                     
        friction_widget = QTextEdit()
        friction_widget.setReadOnly(True)
        friction_widget.setHtml("""
        <h2>土的内摩擦角 φ 参考表</h2>
        <p><b>适用参数：</b>PFI (桩侧土)</p>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <tr style="background-color: #1976D2; color: white;">
                <th>土类</th>
                <th>密实度/状态</th>
                <th>容重 γ (kN/m³)</th>
                <th>内摩擦角 φ (°)</th>
            </tr>
            <tr><td rowspan="2">粗砂</td><td>密实</td><td>20.5</td><td>42</td></tr>
            <tr style="background-color: #E3F2FD;"><td>松散</td><td>19.0</td><td>38</td></tr>
            <tr><td rowspan="2">中砂</td><td>密实</td><td>20.5</td><td>40</td></tr>
            <tr style="background-color: #E3F2FD;"><td>松散</td><td>19.0</td><td>36</td></tr>
            <tr><td rowspan="2">细砂</td><td>密实</td><td>20.5</td><td>38</td></tr>
            <tr style="background-color: #E3F2FD;"><td>松散</td><td>19.0</td><td>32</td></tr>
            <tr><td rowspan="2">粉砂</td><td>密实</td><td>20.5</td><td>36</td></tr>
            <tr style="background-color: #E3F2FD;"><td>松散</td><td>19.0</td><td>28</td></tr>
            <tr><td rowspan="2">粘土</td><td>硬塑</td><td>20.0</td><td>22</td></tr>
            <tr style="background-color: #E3F2FD;"><td>软塑</td><td>17.5</td><td>15</td></tr>
            <tr><td rowspan="2">亚粘土</td><td>硬塑</td><td>21.0</td><td>25</td></tr>
            <tr style="background-color: #E3F2FD;"><td>软塑</td><td>18.0</td><td>17</td></tr>
        </table>
        """)
        tabs.addTab(friction_widget, "内摩擦角 φ")
        
                        
        concrete_widget = QTextEdit()
        concrete_widget.setReadOnly(True)
        concrete_widget.setHtml("""
        <h2>混凝土弹性模量参考表</h2>
        <p><b>适用参数：</b>PEH (桩身材料)</p>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <tr style="background-color: #1976D2; color: white;">
                <th>混凝土强度等级</th>
                <th>弹性模量 E<sub>c</sub> (kN/m²)</th>
                <th>抗压强度 f<sub>c</sub> (MPa)</th>
            </tr>
            <tr><td>C20</td><td>2.55 × 10⁷</td><td>13.4</td></tr>
            <tr style="background-color: #E3F2FD;"><td>C25</td><td>2.80 × 10⁷</td><td>16.7</td></tr>
            <tr><td>C30</td><td>3.00 × 10⁷</td><td>20.1</td></tr>
            <tr style="background-color: #E3F2FD;"><td>C35</td><td>3.15 × 10⁷</td><td>23.4</td></tr>
            <tr><td>C40</td><td>3.25 × 10⁷</td><td>26.8</td></tr>
            <tr style="background-color: #E3F2FD;"><td>C45</td><td>3.35 × 10⁷</td><td>29.6</td></tr>
            <tr><td>C50</td><td>3.45 × 10⁷</td><td>32.4</td></tr>
        </table>
        <br>
        <p><b>刚度折减系数 PKE 建议：</b></p>
        <ul>
            <li>钻孔灌注桩：0.80 ~ 0.85</li>
            <li>预制桩：0.95 ~ 1.0</li>
            <li>考虑裂缝影响时可适当降低</li>
        </ul>
        """)
        tabs.addTab(concrete_widget, "混凝土参数")
        
                      
        ksu_widget = QTextEdit()
        ksu_widget.setReadOnly(True)
        ksu_widget.setHtml("""
        <h2>桩端约束类型 (KSU) 详解</h2>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <tr style="background-color: #1976D2; color: white;">
                <th>代码</th>
                <th>桩基类型中文名称</th>
                <th>说明</th>
                <th>对应底部参数 (PMB) 输入</th>
            </tr>
            <tr>
                <td><b>1</b></td>
                <td>钻孔灌注摩擦桩</td>
                <td>依靠侧摩阻力为主，钻孔施工</td>
                <td>输入 m₀ (桩底土比例系数)</td>
            </tr>
            <tr style="background-color: #E3F2FD;">
                <td><b>2</b></td>
                <td>打入或振动下沉摩擦桩</td>
                <td>依靠侧摩阻力为主，打入施工</td>
                <td>输入 m₀ (桩底土比例系数)</td>
            </tr>
            <tr>
                <td><b>3</b></td>
                <td>柱承桩 (桩底非嵌固)</td>
                <td>端承桩，桩底视为铰接/简支</td>
                <td>输入 c₀ (岩石地基系数)</td>
            </tr>
            <tr style="background-color: #E3F2FD;">
                <td><b>4</b></td>
                <td>柱承桩 (桩底嵌固)</td>
                <td>端承桩，桩底视为固定/固结</td>
                <td>输入 c₀ (岩石地基系数)</td>
            </tr>
        </table>
        <br>
        <ul>
            <li>选择 KSU=1,2 时，PMB 输入的是 m₀ 值，单位为 kN/m⁴</li>
            <li>选择 KSU=3,4 时，PMB 输入的是 c₀ 值，单位为 kN/m³ (注意是立方)</li>
            <li>务必根据实际桩型和地质条件正确选择！</li>
        </ul>
        """)
        tabs.addTab(ksu_widget, "KSU 说明")
        
        layout.addWidget(tabs)
        
                
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(help_dialog.close)
        close_btn.setMinimumWidth(80)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        
        help_dialog.exec()
    
                                                                             
           
                                                                             

    def _show_about(self):
        QMessageBox.about(
            self, "关于 桩基分析程序",
            "<h3>桩基分析程序 (PileAnalysis) v3.0</h3>"
            "<p>基于Pyside6开发的桩基有限元分析的前后处理程序。</p>"
            "<p><b>作者：</b>汪灿，郭军军</p>"
            "<p><b>单位：</b>北京交通大学 土木建筑工程学院</p>" \
            "<p><b>说明：</b>本程序计算内核基于同济大学编写的fortran内核求解器</p>"
            "<p>Copyright © 2026</p>"
        )

    def _show_tutorial_dialog(self):
        try:
            dialog = TutorialDialog(self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开教程对话框:\n{str(e)}\n\n{traceback.format_exc()}")
            logger.error(f"打开教程对话框失败: {e}", exc_info=True)
        
    def _load_tutorial_case(self, mode_idx: int):
                    
        filenames = {
            1: "模式一算例.dat",
            2: "模式二算例.dat",
            3: "模式三算例.dat"
        }
        
        target_file = filenames.get(mode_idx)
        if not target_file:
            return
            
                
        file_path = None
        possible_paths = [
            Path.cwd() / target_file,
            Path(__file__).parent / target_file,
            Path(__file__).parent / "源代码以及图表等原始文件" / target_file
        ]
        
        for p in possible_paths:
            if p.exists():
                file_path = str(p)
                break
        
        if not file_path:
            QMessageBox.warning(self, "文件丢失", f"未找到算例文件: {target_file}")
            return
            
                     
        self.case_button_group.button(0).setChecked(True)
        self._on_case_type_selected(0)
        
              
        self._import_dat_file(filename=file_path)
        
                                     
        if self.case_imported:
            self.update_status(f"已加载算例：{target_file}，请查看参数")
            self._show_parameter_tabs()

    def _load_pile_manual_case(self, case_idx: int):
                  
        filenames = {
            1: "pile说明书算例1_12桩双工况.dat",
            2: "pile说明书算例2_4桩带模拟桩.dat",
            3: "pile说明书算例3_16桩斜桩差异化.dat",
            4: "pile说明书算例4_3桩非中心模拟桩.dat"
        }
        
        target_file = filenames.get(case_idx)
        if not target_file:
            return
            
                
        file_path = None
        possible_paths = [
            Path.cwd() / target_file,
            Path(__file__).parent / target_file,
            Path(__file__).parent / "源代码以及图表等原始文件" / target_file
        ]
        
                             
        if hasattr(sys, '_MEIPASS'):
            possible_paths.insert(0, Path(sys._MEIPASS) / target_file)
        
        for p in possible_paths:
            if p.exists():
                file_path = str(p)
                break
        
        if not file_path:
            QMessageBox.warning(self, "文件丢失", f"未找到算例文件: {target_file}")
            return
            
                     
        self.case_button_group.button(0).setChecked(True)
        self._on_case_type_selected(0)
        
              
        self._import_dat_file(filename=file_path)
        
                                     
        if self.case_imported:
            self.update_status(f"已加载说明书算例：{target_file}")
            self._show_parameter_tabs()
    def update_status(self, message):
        pass
    
    def set_calc_status(self, status: str):
        self.calc_status_label.setText(status)
        self.calc_status_label.setStyleSheet("""
            QLabel {
                color: #666666;
                padding: 2px 10px;
                border-left: 1px solid #cccccc;
            }
        """)

    def closeEvent(self, event):
        if self.async_engine and self.async_engine.is_running:
            reply = QMessageBox.question(
                self, "确认退出",
                "计算正在进行中，确定要退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            self.async_engine.cancel()

        logger.info("程序退出")
        event.accept()


                                                                         
     
                                                                         

_EN_REPLACEMENTS = [
    ("Pile Response?", "Pile Response"),
    ("Pile Response ?", "Pile Response"),
    ("3D Layout?", "3D Layout"),
    ("Plan Layout?", "Plan Layout"),
    ("??Summary?????...", "Result summary will be displayed here..."),
    ("Summary?????...", "Result summary will be displayed here..."),
    ("Raw Output?????...", "Raw stiffness matrix and solver output will be displayed here..."),
    ("Completed???????????", "The 3D pile-group layout will be displayed after the calculation is complete"),
    ("Completed??????????", "Response curves will be displayed after the calculation is complete"),
    ("???/New?", "(existing or new)"),
    ("Add Pile???", "add pile coordinates"),
    ("PileAnalysis - 桩基分析程序", "PileAnalysis - M-Method"),
    ("导出(&E)", "Export (&E)"),
    ("导出全部结果", "Export All Results"),
    ("仅导出图片", "Export Plots Only"),
    ("仅导出文本结果", "Export Text Results Only"),
    ("导出刚度矩阵CSV", "Export Stiffness Matrix CSV"),
    ("导出结果摘要CSV", "Export Summary CSV"),
    ("帮助(&H)", "Help (&H)"),
    ("参数参考值", "Parameter Reference"),
    ("关于", "About"),
    ("教程(&T)", "Tutorial (&T)"),
    ("模式一算例：群桩刚度", "Mode 1 Example: Group Pile Stiffness"),
    ("模式二算例：单桩刚度", "Mode 2 Example: Single Pile Stiffness"),
    ("模式三算例：桩基反算", "Mode 3 Example: Back Analysis"),
    ("PILE说明书算例 (导入)", "PILE Manual Examples (Import)"),
    ("算例1: 12桩双工况", "Example 1: 12-Pile Dual Load Cases"),
    ("算例2: 4桩带模拟桩", "Example 2: 4 Piles with Simulated Pile"),
    ("算例3: 16桩斜桩差异化", "Example 3: 16 Inclined Piles with Variation"),
    ("算例4: 3桩非中心模拟桩", "Example 4: 3-Pile Off-Center Simulated Pile"),
    ("算例详解与说明表", "Example Notes and Commentary"),
    ("PILE说明书算例解析", "PILE Manual Example Review"),
    ("点击查看参数说明", "Click to view parameter notes"),
    ("参数说明", "Parameter Notes"),
    ("点击查看虚拟桩说明", "Click to view simulated pile notes"),
    ("模拟桩说明", "Simulated Pile Notes"),
    ("批量添加桩位", "Batch Add Pile Coordinates"),
    ("立体布置图", "3D Layout"),
    ("平面布置图", "Plan Layout"),
    ("桩身响应", "Pile Response"),
    ("位移", "Displacement"),
    ("轴力", "Axial Force"),
    ("弯矩", "Bending Moment"),
    ("荷载编号", "Load Case"),
    ("荷载", "Load"),
    ("结果摘要", "Summary"),
    ("原始输出", "Raw Output"),
    ("计算结果输出区", "Result Output"),
    ("计算原理示意图", "Analysis Schematic"),
    ("图形绘制区", "Plot Area"),
    ("最不利", "Critical"),
    ("错误", "Error"),
    ("警告", "Warning"),
    ("提示", "Notice"),
    ("导出成功", "Export Completed"),
    ("导出失败", "Export Failed"),
    ("计算失败", "Calculation Failed"),
    ("计算中", "Running Analysis"),
    ("反算计算中", "Running Back Analysis"),
    ("反算计算失败 - 详细信息", "Back Analysis Failed - Details"),
    ("导入成功", "Import Completed"),
]


def _translate_to_english(text):
    if not text:
        return text
    translated = text
    for src, dst in _EN_REPLACEMENTS:
        translated = translated.replace(src, dst)
    translated = translated.replace("确认导入", "Confirm Import")
    translated = translated.replace("即将导入以下数据:", "The following data will be imported:")
    translated = translated.replace("文件名称:", "File name:")
    translated = translated.replace("模式一算例.dat", "mode_1_example.dat")
    translated = translated.replace("模式二算例.dat", "mode_2_example.dat")
    translated = translated.replace("模式三算例.dat", "mode_3_example.dat")
    translated = translated.replace("pile说明书算例1_12桩双工况.dat", "pile_manual_example_01_12_pile_dual_case.dat")
    translated = translated.replace("pile说明书算例2_4桩带模拟桩.dat", "pile_manual_example_02_4_piles_with_simulated_pile.dat")
    translated = translated.replace("pile说明书算例3_16桩斜桩差异化.dat", "pile_manual_example_03_16_inclined_piles.dat")
    translated = translated.replace("pile说明书算例4_3桩非中心模拟桩.dat", "pile_manual_example_04_3_pile_eccentric_simulated.dat")
    translated = translated.replace("计算模式:", "Analysis mode:")
    translated = translated.replace("桩基数量:", "Number of piles:")
    translated = translated.replace("模式一：群桩刚度", "Mode 1: Group Pile Stiffness")
    translated = translated.replace("模式二：单桩刚度", "Mode 2: Single Pile Stiffness")
    translated = translated.replace("模式三：桩基反算", "Mode 3: Back Analysis")
    translated = translated.replace("模式一：群Pile刚度", "Mode 1: Group Pile Stiffness")
    translated = translated.replace("模式二：单Pile刚度", "Mode 2: Single Pile Stiffness")
    translated = translated.replace("模式三：Pile基反算", "Mode 3: Back Analysis")
    translated = translated.replace("模式一算例：", "Mode 1 Example: ")
    translated = translated.replace("模式二算例：", "Mode 2 Example: ")
    translated = translated.replace("模式三算例：", "Mode 3 Example: ")
    translated = translated.replace("群桩刚度", "Group Pile Stiffness")
    translated = translated.replace("单桩刚度", "Single Pile Stiffness")
    translated = translated.replace("桩基反算", "Back Analysis")
    translated = translated.replace("群Pile刚度", "Group Pile Stiffness")
    translated = translated.replace("单Pile刚度", "Single Pile Stiffness")
    translated = translated.replace("Pile基反算", "Back Analysis")
    translated = translated.replace("模拟桩基:", "Simulated piles:")
    translated = translated.replace("未启用", "Not enabled")
    translated = translated.replace("注意：导入将覆盖当前未保存的设置，是否继续？", "Note: the import will overwrite the current unsaved settings. Do you want to continue?")
    translated = translated.replace("无法导入DAT文件:", "Unable to import the DAT file:")
    translated = translated.replace("错误详情:", "Error details:")
    translated = translated.replace("请检查:", "Please check:")
    translated = translated.replace("1. 文件格式是否正确", "1. Whether the file format is correct")
    translated = translated.replace("2. 文件是否完整", "2. Whether the file is complete")
    translated = translated.replace("3. 查看日志获取详细信息", "3. Check the log for detailed information")
    translated = translated.replace("请输入数值，单位: ", "Please enter a value, unit: ")
    translated = translated.replace("圆形截面", "Circular Section")
    translated = translated.replace("方形截面", "Square Section")
    translated = translated.replace("钻孔灌注摩擦桩", "Bored Friction Pile")
    translated = translated.replace("打入或振动下沉摩擦桩", "Driven or Vibratory Friction Pile")
    translated = translated.replace("柱承桩(桩底非嵌固)", "End-Bearing Pile (Tip Not Socketed)")
    translated = translated.replace("柱承桩(桩底嵌固)", "End-Bearing Pile (Tip Socketed)")
    translated = translated.replace("单荷载", "Single Load")
    translated = translated.replace("多荷载（同时作用）", "Multiple Loads (Simultaneous)")
    translated = translated.replace("荷载数量", "Load Count")
    translated = translated.replace("多荷载输入（同时作用）", "Multiple Load Input (Simultaneous Action)")
    translated = translated.replace("当前编辑:", "Currently Editing:")
    translated = translated.replace("桩类型管理", "Pile Type Management")
    translated = translated.replace("基本参数", "Basic Parameters")
    translated = translated.replace("桩身材料参数", "Pile Material Parameters")
    translated = translated.replace("地上部分（自由段） - 可选    方向从上往下", "Above-Ground Segment (Free Segment) - Optional")
    translated = translated.replace("地上部分（自由段）- 可选    方向从上往下", "Above-Ground Segment (Free Segment) - Optional")
    translated = translated.replace("地上部分（自由段）- 可选  方向从上往下", "Above-Ground Segment (Free Segment) - Optional")
    translated = translated.replace("归一化", "Normalize")
    translated = translated.replace("请选择工况Type", "Please select a case type")
    translated = translated.replace("请选择工况类型", "Please select a case type")
    translated = translated.replace("创建一个桩Type", "create a pile type")
    translated = translated.replace("桩Type", "pile type")
    translated = translated.replace("Type 名称", "type name")
    translated = translated.replace("模拟桩号", "Simulated Pile No.")
    translated = translated.replace("\u8ba1\u7b97Pile\u53f7:", "Pile No.:")
    translated = translated.replace("荷载编号", "Load Case")
    translated = translated.replace("荷载 ", "Load ")
    translated = translated.replace(" 根", " piles")
    translated = translated.replace("X 坐标 (m)", "X Coordinate (m)")
    translated = translated.replace("Y 坐标 (m)", "Y Coordinate (m)")
    translated = translated.replace("[对角线]", "[Diagonal]")
    translated = translated.replace("[全矩阵]", "[Full Matrix]")
    translated = translated.replace("承台中心荷载 (正算模式)", "Cap-Center Load (Forward Mode)")
    translated = translated.replace("承台中心荷载(正算模式)", "Cap-Center Load (Forward Mode)")
    translated = translated.replace("多荷载输入（同时作用）", "Multiple Load Input (Simultaneous Action)")
    translated = translated.replace("多荷载输入", "Multiple Load Input")
    translated = translated.replace("Import Existing Case （dat文件）", "Import Existing Case (.dat)")
    translated = translated.replace("Import Existing Case (dat文件)", "Import Existing Case (.dat)")
    translated = translated.replace("承台中心位移", "Cap-Center Displacement")
    translated = translated.replace("荷载作用位置", "Load Application Position")
    translated = translated.replace("输入荷载", "Input Loads")
    translated = translated.replace("计算结果摘要", "Analysis Summary")
    translated = translated.replace("结果解析失败，请查看原始输出", "Result parsing failed. Please review the raw output.")
    translated = translated.replace("解析错误:", "Parsing error:")
    translated = translated.replace("解析器不可用，请查看原始输出", "The parser is unavailable. Please review the raw output.")
    translated = translated.replace("计算失败", "Calculation Failed")
    translated = translated.replace("计算完成", "Calculation Completed")
    translated = translated.replace("成功", "Success")
    translated = translated.replace("耗时", "Elapsed time")
    translated = translated.replace("秒", "s")
    translated = translated.replace("请查看结果。", "Please review the results.")
    translated = translated.replace("请查看结果", "Please review the results")
    translated = translated.replace("计算完成！", "Calculation completed.")
    translated = translated.replace("Calculation Completed!", "Calculation completed.")
    translated = translated.replace("未找到输出文件", "Output file not found")
    translated = translated.replace("结果摘要", "Summary")
    translated = translated.replace("原始输出", "Raw Output")
    translated = translated.replace("结果输出区", "Result Output")
    translated = translated.replace("新建桩类型", "New Pile Type")
    translated = translated.replace("重命名桩类型", "Rename Pile Type")
    translated = translated.replace("桩类型命名建议", "Pile Type Naming Suggestions")
    translated = translated.replace("请输入有意义的名称，方便后续管理。", "Enter a meaningful name for easier follow-up management.")
    translated = translated.replace("请输入类型名称:", "Enter the type name:")
    translated = translated.replace("当前名称:", "Current name:")
    translated = translated.replace("请输入新名称:", "Enter the new name:")
    translated = translated.replace("按几何尺寸：", "By geometry:")
    translated = translated.replace("按位置功能：", "By location/function:")
    translated = translated.replace("按受力特性：", "By load-transfer behavior:")
    translated = translated.replace("左桥墩桩、桥台桩", "left-pier pile, abutment pile")
    translated = translated.replace("摩擦桩、端承桩", "friction pile, end-bearing pile")
    translated = translated.replace("D150-L30 (直径1.5m，长30m)", "D150-L30 (diameter 1.5 m, length 30 m)")
    translated = translated.replace("模拟Pile(虚拟Pile) 设置", "Simulated Pile Settings")
    translated = translated.replace("模拟Pile（虚拟Pile）设置", "Simulated Pile Settings")
    translated = translated.replace("模拟Pile (虚拟Pile) 设置", "Simulated Pile Settings")
    translated = translated.replace("启用模拟Pile（刚度模式）", "Enable Simulated Pile (Stiffness Mode)")
    translated = translated.replace("启用模拟Pile（单桩刚度）", "Enable Simulated Pile (Single-Pile Stiffness)")
    translated = translated.replace("启用模拟Pile", "Enable Simulated Pile")
    translated = translated.replace("Load作用位置", "Load Position")
    translated = translated.replace("输入Load", "Input Load")
    translated = translated.replace("计算完成后将显示桩基Response曲线", "Response curves will be displayed after the calculation is complete")
    translated = translated.replace("计算完成后将显示桩基响应曲线", "Response curves will be displayed after the calculation is complete")
    translated = translated.replace("请选择计算模式并导入Existing Case", "Please select an analysis mode and import an existing case")
    translated = translated.replace("类型名称不能为空", "Type name cannot be empty")
    translated = translated.replace("至少需要保留一个桩类型", "At least one pile type must be retained")
    translated = translated.replace("类型 '", "Type '")
    translated = translated.replace("' 已存在", "' already exists")
    translated = translated.replace(" 作用位置:", " position:")
    translated = translated.replace(" 荷载值:", " loads:")
    if translated.startswith("★桩"):
        translated = translated.replace("★桩", "★Pile ")
    elif translated.startswith("桩"):
        translated = translated.replace("桩", "Pile ", 1)
    translated = translated.replace("PILE说明书", "PILE Manual")
    translated = translated.replace("PILE说明书算例 (导入)", "PILE Manual Examples (Import)")
    translated = translated.replace("模式一算例：群Pile刚度", "Mode 1 Example: Group Pile Stiffness")
    translated = translated.replace("模式二算例：单Pile刚度", "Mode 2 Example: Single Pile Stiffness")
    translated = translated.replace("模式三算例：Pile基反算", "Mode 3 Example: Back Analysis")
    translated = translated.replace("算例1: 12Pile双工况", "Example 1: 12-Pile Dual Load Cases")
    translated = translated.replace("算例2: 4Pile带模拟Pile", "Example 2: 4 Piles with Simulated Pile")
    translated = translated.replace("算例3: 16Pile斜Pile差异化", "Example 3: 16 Inclined Piles with Variation")
    translated = translated.replace("算例4: 3Pile非中心模拟Pile", "Example 4: 3-Pile Off-Center Simulated Pile")
    translated = translated.replace("仅Export图片", "Export Plots Only")
    translated = translated.replace("Export刚度矩阵CSV", "Export Stiffness Matrix CSV")
    translated = translated.replace("Export Results摘要CSV", "Export Summary CSV")
    translated = translated.replace("Export ResultsOnly", "Export Text Results Only")
    translated = translated.replace("Delete工况", "Delete Case")
    translated = translated.replace("添加工况", "Add Case")
    translated = translated.replace("è®¡ç®—Summary", "Analysis Summary")
    translated = translated.replace("æ‰¿å°æ•´ä½“åˆšåº¦çŸ©é˜µ", "Global Cap Stiffness Matrix")
    translated = translated.replace("Notice: å¯ç‚¹å‡»èœå•æ å¯¼å‡ºæŒ‰é’®ï¼ŒExport Stiffness Matrix CSVï¼Œä¾›åŽç»­åˆ†æžä½¿ç”¨", "Notice: Click Export Stiffness Matrix CSV in the menu bar to export the matrix for subsequent analysis.")
    translated = translated.replace("ã€åŽŸå§‹åˆšåº¦çŸ©é˜µã€‘(Zè½´å‘ä¸‹)", "[Original Stiffness Matrix] (Z Axis Downward)")
    translated = translated.replace("ã€è½¬æ¢åˆšåº¦çŸ©é˜µã€‘(Zè½´å‘ä¸Š)", "[Converted Stiffness Matrix] (Z Axis Upward)")
    translated = translated.replace("ä¸»å¯¹è§’çº¿åˆšåº¦:", "Principal Diagonal Stiffness:")
    translated = translated.replace("å…± ", "Total ")
    translated = translated.replace(" ä¸ªLoad:", " load cases:")
    translated = translated.replace("ã€Loadä¸€ã€‘", "[Load 1]")
    translated = translated.replace("ã€LoadäºŒã€‘", "[Load 2]")
    translated = translated.replace("Loadå€¼", "Loads")
    translated = translated.replace("å·²æˆåŠŸå¯¼å…¥:", "Successfully imported:")
    translated = translated.replace("- è®¡ç®—æ¨¡å¼:", "- Analysis mode:")
    translated = translated.replace("- æ¡©æ•°é‡:", "- Number of piles:")
    translated = translated.replace("- æ¡©ç±»åž‹æ•°:", "- Number of pile types:")
    translated = translated.replace("- æ¨¡æ‹Ÿæ¡©:", "- Simulated piles:")
    translated = translated.replace("ç‚¹å‡»ã€æŸ¥çœ‹ä¸Žä¿®æ”¹ã€‘ç¼–è¾‘å‚æ•°", "Click [View and Edit] to edit the parameters")
    translated = translated.replace("æˆ–ç‚¹å‡»ã€ç›´æŽ¥è®¡ç®—ã€‘å¼€å§‹è®¡ç®—", "or click [Run Directly] to start the calculation")
    translated = translated.replace("å·²å¯¼å…¥çŽ°æœ‰å·¥å†µ:", "Imported existing case:")
    translated = translated.replace("å·²å¯¼å…¥ ", "Imported ")
    translated = translated.replace("ä¸ªè·è½½å·¥å†µ", " load cases")
    translated = translated.replace("ä¸ªåˆšåº¦å·¥å†µ", " stiffness cases")
    translated = translated.replace("è§£æžå¤±è´¥", "Parsing Failed")
    translated = translated.replace("æœªèƒ½ä»Žæ–‡ä»¶ä¸­è§£æžå‡ºæ¡©ç±»åž‹å®šä¹‰", "Failed to parse pile-type definitions from the file")
    translated = translated.replace("è¯·æ£€æŸ¥ [NO_SIMU] å—æ˜¯å¦å®Œæ•´", "Please check whether the [NO_SIMU] block is complete")
    translated = translated.replace("æ‰¿å°ä¸­å¿ƒDisplacement:", "Cap-Center Displacement:")
    translated = translated.replace("Xæ–¹å‘Displacement:", "X-Direction Displacement:")
    translated = translated.replace("Yæ–¹å‘Displacement:", "Y-Direction Displacement:")
    translated = translated.replace("ç«–å‘æ²‰é™:", "Vertical Settlement:")
    translated = translated.replace("ç»•Xè½´è½¬è§’:", "Rotation about X Axis:")
    translated = translated.replace("ç»•Yè½´è½¬è§’:", "Rotation about Y Axis:")
    translated = translated.replace("ç»•Zè½´è½¬è§’:", "Rotation about Z Axis:")
    translated = translated.replace("æ¡©é¡¶Displacement:", "Pile-Head Displacement:")
    translated = translated.replace("æ¡©é¡¶å†…åŠ›:", "Pile-Head Internal Forces:")
    translated = translated.replace("Single Pile Stiffnessè®¡ç®— - æ¡©å·:", "Single Pile Stiffness Calculation - Pile No.:")
    translated = translated.replace("å·²å¯¼å…¥ ", "Imported ")
    translated = translated.replace(" ä¸ªLoadå·¥å†µ", " load cases")
    translated = translated.replace("â†‘ è¯·ç‚¹å‡»ã€æŸ¥çœ‹ä¸Žä¿®æ”¹ã€‘æˆ–ã€Run Directlyã€‘", "-> Please click [View and Edit] or [Run Directly]")
    translated = translated.replace("â†‘ è¯·ç‚¹å‡»ã€æŸ¥çœ‹ä¸Žä¿®æ”¹ã€‘æˆ–ã€ç›´æŽ¥è®¡ç®—ã€‘", "-> Please click [View and Edit] or [Run Directly]")
    translated = translated.replace("Pile åº•å‚æ•°", "Pile-Tip Parameters")
    translated = translated.replace("Pile ç«¯çº¦æŸ (KSU):", "Pile-End Constraint (KSU):")
    translated = translated.replace("Pile Ã¥Âºâ€¢Ã¥Å“Â°Ã¥Å¸ÂºÃ§Â³Â»Ã¦â€¢Â° mÃ¢â€šâ‚¬ (KN/mÃ¢ÂÂ´):", "Pile-Tip Foundation Coefficient m0 (kN/m^4):")
    translated = translated.replace("Pile åº•åœ°åŸºç³»æ•° câ‚€ (KN/mÂ³):", "Pile-Tip Foundation Coefficient c0 (kN/m^3):")
    translated = translated.replace("å±‚åŽš H (m)", "Layer Thickness H (m)")
    translated = translated.replace("ç›´å¾„ D (m)", "Diameter D (m)")
    translated = translated.replace("m å€¼ (KN/mâ´)", "m Value (kN/m^4)")
    translated = translated.replace("å†…æ‘©æ“¦è§’ Ï† (Â°)", "Internal Friction Angle φ (°)")
    translated = translated.replace("åˆ†æ®µæ•° N", "Subdivision Count N")
    translated = translated.replace("æ®µé•¿ H (m)", "Segment Length H (m)")
    translated = translated.replace("ç›´å¾„/è¾¹é•¿ D (m)", "Diameter / Side Length D (m)")
    translated = translated.replace("已成功导入:", "Successfully imported:")
    translated = translated.replace("已Success导入:", "Successfully imported:")
    translated = translated.replace("- 计算模式:", "- Analysis mode:")
    translated = translated.replace("- 桩数量:", "- Number of piles:")
    translated = translated.replace("- 桩类型数:", "- Number of pile types:")
    translated = translated.replace("- 模拟桩:", "- Simulated piles:")
    translated = translated.replace("点击【查看与修改】编辑参数", "Click [View and Edit] to edit the parameters")
    translated = translated.replace("或点击【直接计算】开始计算", "or click [Run Directly] to start the calculation")
    translated = translated.replace("查看与修改", "View and Edit")
    translated = translated.replace("承台中心Load (正算模式)", "Cap-Center Load (Forward Mode)")
    translated = translated.replace("Pile 底参数", "Pile-Tip Parameters")
    translated = translated.replace("Pile 底地基系数", "Pile-Tip Foundation Coefficient")
    translated = translated.replace("Pileåº•åœ°åŸºç³»æ•° co (KN/m³):", "Pile-Tip Foundation Coefficient c0 (kN/m^3):")
    translated = translated.replace("Pileåº•åœ°åŸºç³»æ•° c0 (KN/m³):", "Pile-Tip Foundation Coefficient c0 (kN/m^3):")
    translated = translated.replace("Pileåº•åœ°åŸºç³»æ•° m0 (KN/m⁴):", "Pile-Tip Foundation Coefficient m0 (kN/m^4):")
    translated = translated.replace("层厚 H (m)", "Layer Thickness H (m)")
    translated = translated.replace("直径 D (m)", "Diameter D (m)")
    translated = translated.replace("m 值 (KN/m⁴)", "m Value (kN/m^4)")
    translated = translated.replace("m 值 (KN/m4)", "m Value (kN/m^4)")
    translated = translated.replace("内摩擦角 φ (°)", "Internal Friction Angle φ (°)")
    translated = translated.replace("分段数 N", "Subdivision Count N")
    translated = translated.replace("段长 H (m)", "Segment Length H (m)")
    translated = translated.replace("直径/边长 D (m)", "Diameter / Side Length D (m)")
    return translated


_ORIGINAL_QMESSAGEBOX_INFORMATION = QMessageBox.information
_ORIGINAL_QMESSAGEBOX_WARNING = QMessageBox.warning
_ORIGINAL_QMESSAGEBOX_CRITICAL = QMessageBox.critical
_ORIGINAL_QMESSAGEBOX_QUESTION = QMessageBox.question
_ORIGINAL_QMESSAGEBOX_ABOUT = QMessageBox.about
_ORIGINAL_QINPUTDIALOG_GETTEXT = QInputDialog.getText


def _translate_message_args(args):
    if get_language() != "en":
        return args
    translated = list(args)
    if len(translated) >= 2:
        translated[1] = _translate_to_english(translated[1])
    if len(translated) >= 3 and isinstance(translated[2], str):
        translated[2] = _translate_summary_output(_translate_to_english(translated[2]))
    return tuple(translated)


def _bilingual_information(*args, **kwargs):
    return _ORIGINAL_QMESSAGEBOX_INFORMATION(*_translate_message_args(args), **kwargs)


def _bilingual_warning(*args, **kwargs):
    return _ORIGINAL_QMESSAGEBOX_WARNING(*_translate_message_args(args), **kwargs)


def _bilingual_critical(*args, **kwargs):
    return _ORIGINAL_QMESSAGEBOX_CRITICAL(*_translate_message_args(args), **kwargs)


def _bilingual_question(*args, **kwargs):
    return _ORIGINAL_QMESSAGEBOX_QUESTION(*_translate_message_args(args), **kwargs)


def _bilingual_about(*args, **kwargs):
    return _ORIGINAL_QMESSAGEBOX_ABOUT(*_translate_message_args(args), **kwargs)


def _bilingual_get_text(*args, **kwargs):
    if get_language() == "en":
        args = list(args)
        if len(args) >= 2:
            args[1] = _translate_to_english(args[1])
        if len(args) >= 3:
            args[2] = _translate_to_english(args[2])
    return _ORIGINAL_QINPUTDIALOG_GETTEXT(*args, **kwargs)


QMessageBox.information = _bilingual_information
QMessageBox.warning = _bilingual_warning
QMessageBox.critical = _bilingual_critical
QMessageBox.question = _bilingual_question
QMessageBox.about = _bilingual_about
QInputDialog.getText = _bilingual_get_text


class EnglishTutorialDialog(TutorialDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PileAnalysis - Tutorial Examples")
        self._apply_english_texts()

    def _apply_english_texts(self):
        layout = self.layout()
        if layout and layout.count() > 0:
            top_hint = layout.itemAt(0).widget()
            if isinstance(top_hint, QLabel):
                top_hint.setText(
                    "<div style='border: 1px solid #FFEEBA; padding: 10px; color: red;'>"
                    "<b>Note:</b> This dialog keeps the original tutorial layout. "
                    "Only the visible text has been translated into English. The DAT preview and page structure remain unchanged."
                    "</div>"
                )

        tutorial_titles = [
            "Mode 1 Example: Group Pile Stiffness",
            "Mode 2 Example: Single Pile Stiffness",
            "Mode 3 Example: Back Analysis",
        ]
        tutorial_html = [
            """
            <h4 style='color: black;'>Mode 1: Group Pile Stiffness Solver</h4>
            <p>This example demonstrates the global stiffness calculation of a pile group and the resulting 6x6 stiffness matrix.</p>
            <p><b>Recommended use:</b> Review the input structure, verify the stiffness output, and compare the cap-level response.</p>
            <hr>
            <p><b>Main output</b></p>
            <ul>
            <li><b>Global stiffness matrix and grouped response output</b></li>
            <li><b>Result set:</b> six coupled stiffness terms at the cap center (Kx, Ky, Kz, KRx, KRy, KRz)</li>
            </ul>
            <br>
            <div style='padding: 10px; border-left: 5px solid #1976D2;'>
            <p><b>Example notes</b></p>
            <p>This tutorial uses <b>2 pile types</b> so that the stiffness contrast between different pile definitions can be checked clearly.</p>
            <p><b>Pile-response setting:</b> the example keeps a 2.0 m pile spacing and a representative soil stiffness range for comparison.</p>
            </div>
            """,
            """
            <h4 style='color: black;'>Mode 2: Single Pile Stiffness Analysis</h4>
            <p>This example focuses on one selected pile and evaluates its individual stiffness contribution and local response.</p>
            <p><b>Recommended use:</b> Use this case when you need to inspect one pile in detail rather than the full pile group.</p>
            <hr>
            <p><b>Input highlights</b></p>
            <ul>
            <li><b>[CALC_PILE]</b>: specifies the target pile number for the single-pile calculation</li>
            <li>All remaining input sections follow the same overall format as Mode 1</li>
            </ul>
            <br>
            <div style='padding: 10px; border-left: 5px solid #1976D2;'>
            <p><b>Example notes</b></p>
            <p>The physical model is consistent with Mode 1.</p>
            <p><b>Target pile:</b> the tutorial selects <b>Pile No. 2</b> as the pile to be reviewed in detail.</p>
            </div>
            """,
            """
            <h4 style='color: black;'>Mode 3: Back Analysis of the Pile Foundation</h4>
            <p>This example starts from cap-level displacement or equivalent load information and reconstructs the response of the pile foundation.</p>
            <p><b>Recommended use:</b> Use this case when the back-analysis workflow is required.</p>
            <hr>
            <p><b>Key parameter sections</b></p>
            <ul>
            <li><b>[LOADS]</b>: cap-center loads (Fx, Fy, Fz, Mx, My, Mz)</li>
            <li><b>[P_TYPE]</b>: pile-type definition including stiffness-related parameters and segment data</li>
            <li><b>[ARRANGE]</b>: pile coordinates and pile-type assignment</li>
            </ul>
            <br>
            <div style='padding: 10px; border-left: 5px solid #1976D2;'>
            <p><b>Example notes</b></p>
            <p>This tutorial contains <b>4 piles</b> and highlights the eccentric response under combined cap actions.</p>
            <p><b>Load feature:</b> the cap center is subjected to a dominant vertical load together with horizontal force and moment components.</p>
            <p><b>Pile-response setting:</b> the example keeps representative pile spacing, pile length, and soil stiffness variation for back-analysis verification.</p>
            </div>
            """,
        ]

        for index, title in enumerate(tutorial_titles):
            if index >= self.tabs.count():
                continue
            self.tabs.setTabText(index, title)
            tab = self.tabs.widget(index)
            browser = tab.findChild(QTextBrowser)
            if browser is not None:
                browser.setHtml(tutorial_html[index])

        for button in self.findChildren(QPushButton):
            if button.text() == "关闭":
                button.setText("Close")


class EnglishPileManualDialog(PileManualDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PILE Manual Example Review")
        self._apply_english_texts()

    def _apply_english_texts(self):
        header = self.findChild(QLabel)
        if isinstance(header, QLabel):
            header.setText("PILE Manual Example Review")

        tab_widget = getattr(self, "pile_manual_tabs", None)
        if tab_widget is None:
            tab_widget = getattr(self, "tabs", None)
        if tab_widget is None:
            return

        titles = [
            "Example 1: 12-Pile Dual Load Cases",
            "Example 2: 4 Piles with Simulated Pile",
            "Example 3: 16 Inclined Piles with Variation",
            "Example 4: 3-Pile Off-Center Simulated Pile",
        ]
        descriptions = [
            """
            <h4>Example 1: 12-pile group under dual load cases</h4>
            <p><b>Purpose:</b> This case demonstrates a 12-pile group subjected to two representative cap load cases and is suitable for checking group stiffness output.</p>
            <ul>
            <li><b>Load case 1:</b> combined cap load with horizontal and moment components</li>
            <li><b>Load case 2:</b> an alternative loading condition for comparison</li>
            </ul>
            <p>Use this example to review how the same pile-group model responds to different cap actions while keeping the pile arrangement unchanged.</p>
            """,
            """
            <h4>Example 2: 4 piles with a simulated pile definition</h4>
            <p><b>Purpose:</b> This example illustrates how a compact 4-pile system can include a simulated pile and still be solved within the same workflow.</p>
            <p><b>Simulated pile note:</b> The simulated pile is introduced through stiffness input so that the response can be compared with the explicit pile definition.</p>
            """,
            """
            <h4>Example 3: 16 inclined piles with variation</h4>
            <p><b>Purpose:</b> This example emphasizes inclined-pile definition, directional stiffness change, and the effect of pile orientation on the global response.</p>
            <p><b>Key points</b><br>
            1. Check the pile-axis definition and the pile-coordinate arrangement.<br>
            2. Compare the response trend when pile orientation changes.
            </p>
            """,
            """
            <h4>Example 4: 3-pile off-center load with simulated pile</h4>
            <p><b>Purpose:</b> This example studies a three-pile configuration under off-center action while also including a simulated-pile definition.</p>
            <p>It is useful for checking eccentric response, coordinate definition, and the interaction between simulated stiffness input and the physical pile arrangement.</p>
            """,
        ]

        for index, title in enumerate(titles):
            if index >= tab_widget.count():
                continue
            tab_widget.setTabText(index, title)
            tab = tab_widget.widget(index)
            groups = tab.findChildren(QGroupBox)
            if len(groups) >= 2:
                groups[0].setTitle("Reference Figure and Notes")
                groups[1].setTitle("DAT File Analysis and Notes")
            if len(groups) >= 3:
                groups[2].setTitle("DAT Input File")
            browser = tab.findChild(QTextBrowser)
            if browser is not None:
                browser.setHtml(descriptions[index])

        for text_edit in self.findChildren(QTextEdit):
            content = text_edit.toPlainText().strip()
            if content == "文件未找到":
                text_edit.setPlainText("File not found")
            elif content.startswith("图片未找到:"):
                text_edit.setPlainText(content.replace("图片未找到:", "Image not found: ", 1))


_ORIGINAL_PILETYPEEDITOR_INIT = PileTypeEditor.__init__
_ORIGINAL_PILETYPEEDITOR_CREATE_HELP_BUTTON = PileTypeEditor._create_help_button
_ORIGINAL_PILETYPEEDITOR_ADD_ROW_WITH_HELP = PileTypeEditor._add_row_with_help

_ORIGINAL_MAINWINDOW_INIT = MainWindow.__init__
_ORIGINAL_SHOW_PARAMETER_TABS = MainWindow._show_parameter_tabs
_ORIGINAL_PLOT_RESULTS = MainWindow._plot_results
_ORIGINAL_LOAD_TUTORIAL_CASE = MainWindow._load_tutorial_case
_ORIGINAL_LOAD_PILE_MANUAL_CASE = MainWindow._load_pile_manual_case
_ORIGINAL_ON_CASE_TYPE_SELECTED = MainWindow._on_case_type_selected
_ORIGINAL_ON_MODE_SELECTED = MainWindow._on_mode_selected
_ORIGINAL_BACK_TO_CASE_SELECTION = MainWindow._back_to_case_selection
_ORIGINAL_IMPORT_DAT_FILE = MainWindow._import_dat_file
_ORIGINAL_START_CALCULATION = MainWindow.start_calculation
_ORIGINAL_ON_CALC_FINISHED = MainWindow._on_calc_finished
_ORIGINAL_GENERATE_SUMMARY = MainWindow._generate_summary
_ORIGINAL_SHOW_TUTORIAL_DIALOG = MainWindow._show_tutorial_dialog
_ORIGINAL_SHOW_PILE_MANUAL_DIALOG = MainWindow._show_pile_manual_dialog
_ORIGINAL_EXPORT_SUMMARY_CSV = MainWindow._export_summary_csv
_ORIGINAL_EXPORT_STIFFNESS_CSV = MainWindow._export_stiffness_csv
_ORIGINAL_PILETYPE_SHOW_ABOVE_SEGMENT_HELP = PileTypeEditor._show_above_segment_help
_ORIGINAL_PILETYPE_SHOW_BELOW_SEGMENT_HELP = PileTypeEditor._show_below_segment_help
_ORIGINAL_SHOW_PARAMETER_REFERENCE = MainWindow.show_parameter_reference


def _bilingual_piletypeeditor_init(self, *args, **kwargs):
    _ORIGINAL_PILETYPEEDITOR_INIT(self, *args, **kwargs)
    if get_language() == "en":
        _apply_english_pile_type_editor(self)


def _bilingual_piletypeeditor_create_help_button(self, help_text, label_text=""):
    return _bilingual_create_help_button(self, help_text, label_text)


def _bilingual_piletypeeditor_add_row_with_help(self, form_layout, label_text, widget, help_text):
    return _bilingual_add_row_with_help(self, form_layout, label_text, widget, help_text)


def _english_help_text(label_text, help_text):
    label_text = label_text or ""
    if "弹性模量" in label_text or "PEH" in help_text:
        return (
            "<h3>[PEH] Concrete Elastic Modulus</h3>"
            "<p><b>Reference values (GB 50010):</b></p>"
            "<ul>"
            "<li>C20: 2.55 × 10<sup>7</sup> kN/m<sup>2</sup></li>"
            "<li>C25: 2.80 × 10<sup>7</sup> kN/m<sup>2</sup></li>"
            "<li>C30: 3.00 × 10<sup>7</sup> kN/m<sup>2</sup></li>"
            "<li>C35: 3.15 × 10<sup>7</sup> kN/m<sup>2</sup></li>"
            "<li>C40: 3.25 × 10<sup>7</sup> kN/m<sup>2</sup></li>"
            "</ul>"
        )
    if "惯性矩修正系数" in label_text or "PKE" in help_text:
        return (
            "<h3>[PKE] Stiffness Reduction Factor</h3>"
            "<p>The factor is used to adjust the effective pile stiffness.</p>"
            "<ul>"
            "<li>Cast-in-place piles: 0.80 - 0.85</li>"
            "<li>Precast piles: 0.95 - 1.00</li>"
            "<li>Use 1.00 when no reduction is required.</li>"
            "</ul>"
        )
    if "桩底地基系数" in label_text or "PMB" in help_text:
        return (
            "<h3>[PMB] Pile-Tip Foundation Coefficient</h3>"
            "<p>Choose the parameter meaning according to the selected KSU type:</p>"
            "<p><b>KSU = 1, 2 (friction pile):</b><br>"
            "Input m<sub>0</sub> (pile-tip soil proportional coefficient), unit: kN/m<sup>4</sup><br>"
            "Soft plastic soil: 5,000-15,000<br>"
            "Plastic soil: 15,000-30,000<br>"
            "Dense sand: 30,000-50,000</p>"
            "<p><b>KSU = 3, 4 (end-bearing pile):</b><br>"
            "Input c<sub>0</sub> (rock foundation coefficient), unit: kN/m<sup>3</sup><br>"
            "Strongly weathered rock: 50,000-200,000<br>"
            "Moderately weathered rock: 200,000-500,000<br>"
            "Slightly weathered rock: 500,000-1,000,000</p>"
        )
    return _translate_to_english(help_text)


def _bilingual_create_help_button(self, help_text, label_text=""):
    help_btn = QToolButton()
    help_btn.setText("?")
    help_btn.setFixedSize(16, 16)
    help_btn.setStyleSheet(
        """
        QToolButton {
            background-color: #4A90E2;
            color: white;
            border: 1px solid #2E6FB8;
            border-radius: 8px;
            font-weight: bold;
        }
        QToolButton:hover {
            background-color: #3B7DCC;
        }
        """
    )

    if get_language() == "en":
        help_btn.setToolTip("Click to view parameter notes")
        help_btn.clicked.connect(lambda: QMessageBox.information(self, "Parameter Notes", _english_help_text(label_text, help_text)))
    else:
        help_btn.setToolTip("点击查看参数说明")
        help_btn.clicked.connect(lambda: QMessageBox.information(self, "参数说明", help_text))
    return help_btn


def _bilingual_add_row_with_help(self, form_layout, label_text, widget, help_text):
    row_widget = QWidget()
    row_layout = QHBoxLayout(row_widget)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(6)
    label = QLabel(_translate_to_english(label_text) if get_language() == "en" else label_text)
    row_layout.addWidget(label)
    row_layout.addStretch()
    row_layout.addWidget(self._create_help_button(help_text, label_text))
    form_layout.addRow(row_widget, widget)


def _bilingual_add_cap_row_with_help(self, form_layout, label_text, widget, help_text):
    row_widget = QWidget()
    row_layout = QHBoxLayout(row_widget)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(6)
    label = QLabel(_translate_to_english(label_text) if get_language() == "en" else label_text)
    row_layout.addWidget(label)
    row_layout.addStretch()
    row_layout.addWidget(self._create_help_button(help_text, label_text))
    form_layout.addRow(row_widget, widget)


def _english_show_above_segment_help(self):
    dialog = QMessageBox(self)
    dialog.setWindowTitle("Above-Ground Segment Parameter Notes")
    icon_path = Path(__file__).parent / "app_icon.ico"
    if icon_path.exists():
        dialog.setWindowIcon(QIcon(str(icon_path)))
        dialog.setIconPixmap(QIcon(str(icon_path)).pixmap(64, 64))
    dialog.setTextFormat(Qt.TextFormat.RichText)
    dialog.setText(
        "<h3>Above-Ground Segment (Free Segment) - Optional Parameters</h3>"
        "<p><b>Definition:</b> the portion of the pile above the scour line or ground surface.</p>"
        "<hr>"
        "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse;'>"
        "<tr style='background-color: #1976D2; color: white;'><th>Parameter</th><th>Variable</th><th>Unit</th><th>Description</th></tr>"
        "<tr><td><b>Segment Length H</b></td><td>HFR</td><td>m</td><td>Height of the free segment<br>Typical range: 1.0-10.0 m</td></tr>"
        "<tr style='background-color: #E3F2FD;'><td><b>Diameter / Side Length D</b></td><td>DOF</td><td>m</td><td>Pile cross-section size<br>&bull; Circular pile: diameter<br>&bull; Square pile: side length<br>Typical range: 0.5-2.0 m</td></tr>"
        "<tr><td><b>Subdivision Count N</b></td><td>NSF</td><td>-</td><td>Number of output points for displacement and internal-force output<br>Recommended value: 2-5</td></tr>"
        "</table>"
        "<br><p><b>Typical applications:</b></p>"
        "<ul><li>Bridge pier piles: from ground surface to the bottom of the cap</li>"
        "<li>Wharf piles: from seabed to the bottom of the cap</li>"
        "<li>Scour consideration: the portion above the scour line</li></ul>"
        "<p style='color: #666;'><i>Note: if the pile head is directly embedded at the ground surface, this section may be left blank.</i></p>"
    )
    dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
    dialog.exec()


def _english_show_below_segment_help(self):
    dialog = QDialog(self)
    dialog.setWindowTitle("Embedded Segment Parameter Notes")
    icon_path = Path(__file__).parent / "app_icon.ico"
    if icon_path.exists():
        dialog.setWindowIcon(QIcon(str(icon_path)))
    dialog.resize(860, 760)

    layout = QVBoxLayout(dialog)

    text_browser = QTextBrowser(dialog)
    text_browser.setOpenExternalLinks(False)
    text_browser.setReadOnly(True)
    text_browser.setStyleSheet(
        "QTextBrowser { background: white; border: none; padding: 8px; }"
    )
    text_browser.setHtml(
        "<h3>Embedded Segment (Soil Layer Parameters) - Required</h3>"
        "<p><b>Definition:</b> the pile segment embedded in the soil below the scour line or ground surface.</p>"
        "<hr>"
        "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse; width: 100%;'>"
        "<tr style='background-color: #1976D2; color: white;'><th>Parameter</th><th>Variable</th><th>Unit</th><th>Description</th></tr>"
        "<tr><td><b>Layer Thickness H</b></td><td>HBL</td><td>m</td><td>Thickness of the soil layer (pile length within this layer)<br>Define it layer by layer according to the geotechnical report.</td></tr>"
        "<tr style='background-color: #E3F2FD;'><td><b>Diameter D</b></td><td>DOB</td><td>m</td><td>Pile diameter / side length in this layer<br>Variable-section piles are supported.</td></tr>"
        "<tr><td><b>m Value</b></td><td>PMT</td><td>kN/m<sup>4</sup></td><td><b style='color: red;'>Key parameter!</b> Horizontal subgrade-reaction coefficient of the soil.<br>"
        "&bull; Soft plastic clay: 5,000-10,000<br>&bull; Plastic clay: 10,000-20,000<br>&bull; Hard plastic clay: 20,000-30,000<br>&bull; Medium-dense sand: 15,000-30,000<br>&bull; Dense sand: 30,000-80,000<br>"
        "See <b>Help - Parameter Reference</b> for the detailed table.</td></tr>"
        "<tr style='background-color: #E3F2FD;'><td><b>Internal Friction Angle φ</b></td><td>PFI</td><td>deg (°)</td><td>Internal friction angle used in the ultimate-resistance calculation.<br>"
        "&bull; Clay: 10-25°<br>&bull; Silt: 15-30°<br>&bull; Sand: 25-40°<br>See <b>Help - Parameter Reference</b>.</td></tr>"
        "<tr><td><b>Subdivision Count N</b></td><td>NSG</td><td>-</td><td>Number of output points<br>Recommended value: 2-5</td></tr>"
        "</table><br>"
        "<p><b style='color: red;'>Important notes:</b></p>"
        "<ul><li>Define at least <b>one soil layer</b>.</li>"
        "<li>It is recommended to define layers according to the <b>soil stratification</b> in the geotechnical report.</li>"
        "<li>The <b>m value</b> has the strongest influence on the results and should be determined from geotechnical tests.</li>"
        "<li>The sum of all layer thicknesses should equal the <b>effective embedment depth</b> of the pile.</li></ul>"
        "<p style='color: #666;'><i>Tip: press F1 to open the parameter-reference table quickly.</i></p>"
    )
    layout.addWidget(text_browser)

    button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
    button_box.accepted.connect(dialog.accept)
    layout.addWidget(button_box)

    dialog.exec()


def _translate_export_csv_text(text):
    if not isinstance(text, str):
        return text
    translated = text
    replacements = [
        ("桩基分析 结果摘要导出文件", "Pile Foundation Analysis Summary Export"),
        ("导出时间:", "Export time:"),
        ("计算模式:", "Analysis mode:"),
        ("桩基反算", "Back Analysis"),
        ("群桩刚度", "Group Pile Stiffness"),
        ("单桩刚度", "Single Pile Stiffness"),
        ("输入荷载", "Input Loads"),
        ("共 ", "Total "),
        (" 个荷载工况", " load cases"),
        ("荷载一", "Load 1"),
        ("荷载二", "Load 2"),
        ("荷载三", "Load 3"),
        ("荷载四", "Load 4"),
        ("荷载五", "Load 5"),
        ("荷载六", "Load 6"),
        ("荷载七", "Load 7"),
        ("荷载八", "Load 8"),
        ("荷载九", "Load 9"),
        ("荷载十", "Load 10"),
        ("作用位置X (m)", "Load Position X (m)"),
        ("作用位置Y (m)", "Load Position Y (m)"),
        ("承台中心位移", "Cap-Center Displacement"),
        ("项目", "Item"),
        ("数值", "Value"),
        ("单位", "Unit"),
        ("X方向位移", "X-Direction Displacement"),
        ("Y方向位移", "Y-Direction Displacement"),
        ("竖向沉降", "Vertical Settlement"),
        ("绕X轴转角", "Rotation about X Axis"),
        ("绕Y轴转角", "Rotation about Y Axis"),
        ("绕Z轴转角", "Rotation about Z Axis"),
        ("桩顶位移汇总", "Pile-Head Displacement Summary"),
        ("桩顶内力汇总", "Pile-Head Internal Force Summary"),
        ("各桩桩顶响应详细数据", "Detailed Pile-Head Response Data"),
        ("桩号", "Pile No."),
        ("桩基数量:", "Number of piles:"),
        ("工况总数:", "Total number of cases:"),
        ("【工况 ", "[Case "),
        ("】", "]"),
    ]
    for src, dst in replacements:
        translated = translated.replace(src, dst)
    return translated


def _bilingual_show_above_segment_help(self):
    if get_language() == "en":
        return _english_show_above_segment_help(self)
    return _ORIGINAL_PILETYPE_SHOW_ABOVE_SEGMENT_HELP(self)


def _bilingual_show_below_segment_help(self):
    if get_language() == "en":
        return _english_show_below_segment_help(self)
    return _ORIGINAL_PILETYPE_SHOW_BELOW_SEGMENT_HELP(self)


def _bilingual_export_summary_csv(self, *args, **kwargs):
    if get_language() != "en":
        return _ORIGINAL_EXPORT_SUMMARY_CSV(self, *args, **kwargs)

    import csv as _csv_module

    original_writer = _csv_module.writer

    class _TranslatedCsvWriter:
        def __init__(self, wrapped):
            self._wrapped = wrapped

        def writerow(self, row):
            translated_row = [
                _translate_export_csv_text(cell) if isinstance(cell, str) else cell
                for cell in row
            ]
            return self._wrapped.writerow(translated_row)

        def writerows(self, rows):
            for row in rows:
                self.writerow(row)

        def __getattr__(self, name):
            return getattr(self._wrapped, name)

    def _writer_factory(*factory_args, **factory_kwargs):
        return _TranslatedCsvWriter(original_writer(*factory_args, **factory_kwargs))

    _csv_module.writer = _writer_factory
    try:
        return _ORIGINAL_EXPORT_SUMMARY_CSV(self, *args, **kwargs)
    finally:
        _csv_module.writer = original_writer



def _bilingual_export_stiffness_csv(self, *args, **kwargs):
    if get_language() != "en":
        return _ORIGINAL_EXPORT_STIFFNESS_CSV(self, *args, **kwargs)

    if not self.parser or self.parser.stiffness_matrix is None:
        QMessageBox.warning(
            self,
            "Warning",
            "No stiffness matrix data are available to export.\n\n"
            "Please run Mode 1 (Group Pile Stiffness) or Mode 2 (Single Pile Stiffness) first.",
        )
        return

    from PySide6.QtWidgets import QFileDialog
    from datetime import datetime
    import csv
    import numpy as np

    if self.parser.mode == OutputMode.SINGLE_PILE_STIFFNESS:
        pile_no = self.parser.single_pile_no or "1"
        default_name = f"Single_Pile_Stiffness_Matrix_Pile_{pile_no}.csv"
        matrix_type = "Single Pile Stiffness Matrix"
        pile_info = f"Pile No.: {pile_no}"
    else:
        default_name = "Global_Cap_Stiffness_Matrix.csv"
        matrix_type = "Global Cap Stiffness Matrix"
        pile_info = f"Number of piles: {self.pile_table.rowCount()}"

    file_path, _ = QFileDialog.getSaveFileName(
        self,
        "Export Stiffness Matrix CSV",
        str(Path.home() / "Desktop" / default_name),
        "CSV Files (*.csv);;All Files (*.*)",
    )
    if not file_path:
        return

    try:
        k_original = self.parser.stiffness_matrix
        k_converted = self._convert_stiffness_z_up(k_original)

        if hasattr(k_original, "data"):
            k_orig_array = np.array(k_original.data)
        elif isinstance(k_original, np.ndarray):
            k_orig_array = k_original
        else:
            k_orig_array = np.array([[k_original[i, j] for j in range(6)] for i in range(6)])

        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["Pile Foundation Analysis Stiffness Matrix Export"])
            writer.writerow([f"Export time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
            writer.writerow([f"Matrix type: {matrix_type}"])
            writer.writerow([pile_info])
            writer.writerow(["Units: force-kN, length-m, angle-rad"])
            writer.writerow([])

            header = ["", "UX (m)", "UY (m)", "UZ (m)", "RX (rad)", "RY (rad)", "RZ (rad)"]
            row_labels = ["FX (kN)", "FY (kN)", "FZ (kN)", "MX (kN*m)", "MY (kN*m)", "MZ (kN*m)"]

            writer.writerow(["[Converted Stiffness Matrix] Z Axis Upward"])
            writer.writerow(header)
            for i in range(6):
                writer.writerow([row_labels[i]] + [f"{k_converted[i, j]:.6e}" for j in range(6)])

            writer.writerow([])
            writer.writerow(["[Original Stiffness Matrix] Z Axis Downward"])
            writer.writerow(header)
            for i in range(6):
                writer.writerow([row_labels[i]] + [f"{k_orig_array[i, j]:.6e}" for j in range(6)])

        QMessageBox.information(
            self,
            "Export Completed",
            f"The stiffness matrix has been exported to:\n{file_path}\n\n"
            "Coordinate system: Z axis upward\n"
            "The CSV can be imported into SAP2000, MIDAS, ETABS, and similar software.",
        )
    except Exception as e:
        QMessageBox.critical(self, "Export Failed", f"Failed to export the stiffness matrix CSV:\n{e}")
def _english_show_about(self):
    dialog = QMessageBox(self)
    dialog.setWindowTitle("About")
    icon_path = Path(__file__).parent / "app_icon.ico"
    if icon_path.exists():
        dialog.setWindowIcon(QIcon(str(icon_path)))
        dialog.setIconPixmap(QIcon(str(icon_path)).pixmap(72, 72))
    dialog.setTextFormat(Qt.TextFormat.RichText)
    dialog.setText(
        "<h3>PileAnalysis - M-Method Module</h3>"
        "<p>A pre- and post-processing program for pile-foundation finite-element analysis developed with PySide6.</p>"
        "<p><b>Authors:</b> Can Wang, Junjun Guo</p>"
        "<p><b>Affiliation:</b> School of Civil Engineering, Beijing Jiaotong University</p>"
        "<p><b>Note:</b> The computational kernel is based on the Fortran solver developed at Tongji University.</p>"
        "<p>Copyright &copy; 2026</p>"
    )
    dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
    dialog.exec()


def _english_show_parameter_reference():
    help_dialog = QDialog()
    help_dialog.setWindowTitle("PileAnalysis Parameter Reference")

    screen = QApplication.primaryScreen()
    if screen:
        screen_geo = screen.availableGeometry()
        dialog_width = min(900, int(screen_geo.width() * 0.55))
        dialog_height = min(700, int(screen_geo.height() * 0.65))
    else:
        dialog_width, dialog_height = 900, 700
    help_dialog.resize(dialog_width, dialog_height)

    layout = QVBoxLayout(help_dialog)
    tabs = QTabWidget()

    tab_specs = [
        (
            "Soil m Value",
            """
            <h2>Reference Table for the Soil m Value</h2>
            <p><b>Related parameters:</b> PMT for embedded layers and PMB when KSU = 1 or 2.</p>
            <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #1976D2; color: white;">
                    <th>Soil condition</th>
                    <th>Liquidity-index range</th>
                    <th>Suggested m value (kN/m<sup>4</sup>)</th>
                </tr>
                <tr><td>Very soft to soft clay</td><td>I<sub>L</sub> &gt; 1</td><td>3,000 - 5,000</td></tr>
                <tr style="background-color: #E3F2FD;"><td>Plastic clay</td><td>1 &gt; I<sub>L</sub> &gt; 0.5</td><td>5,000 - 10,000</td></tr>
                <tr><td>Firm clay / silty clay</td><td>0.5 &gt; I<sub>L</sub> &gt; 0</td><td>10,000 - 20,000</td></tr>
                <tr style="background-color: #E3F2FD;"><td>Stiff clay</td><td>I<sub>L</sub> &lt; 0</td><td>20,000 - 30,000</td></tr>
                <tr><td>Dense sand or gravelly soil</td><td>-</td><td>30,000 - 80,000</td></tr>
                <tr style="background-color: #E3F2FD;"><td>Weathered rock-like soil</td><td>-</td><td>80,000 - 120,000</td></tr>
            </table>
            """,
        ),
        (
            "Rock c0 Value",
            """
            <h2>Reference Table for the Rock c0 Value</h2>
            <p><b>Related parameter:</b> PMB when KSU = 3 or 4.</p>
            <p style="color: red;"><b>The unit is kN/m<sup>3</sup>, which differs from the soil m value used in ordinary layers.</b></p>
            <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #1976D2; color: white;">
                    <th>Rock condition</th>
                    <th>Typical bearing resistance R<sub>a</sub> (kPa)</th>
                    <th>Suggested c<sub>0</sub> value (kN/m<sup>3</sup>)</th>
                </tr>
                <tr><td>Weak rock</td><td>1,000</td><td>3.0 × 10<sup>4</sup></td></tr>
                <tr style="background-color: #E3F2FD;"><td>Moderately weathered rock</td><td>5,000</td><td>2.75 × 10<sup>5</sup></td></tr>
                <tr><td>Slightly weathered rock</td><td>15,000</td><td>8.8 × 10<sup>5</sup></td></tr>
                <tr style="background-color: #E3F2FD;"><td>Fresh rock</td><td>25,000 or above</td><td>1.5 × 10<sup>6</sup></td></tr>
            </table>
            """,
        ),
        (
            "Internal Friction Angle β",
            """
            <h2>Reference Table for the Internal Friction Angle β</h2>
            <p><b>Related parameter:</b> PFI for embedded layers.</p>
            <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #1976D2; color: white;">
                    <th>Soil type</th>
                    <th>Density / state</th>
                    <th>Unit weight γ (kN/m<sup>3</sup>)</th>
                    <th>Internal friction angle β (deg)</th>
                </tr>
                <tr><td rowspan="2">Coarse sand</td><td>Dense</td><td>20.5</td><td>42</td></tr>
                <tr style="background-color: #E3F2FD;"><td>Medium dense</td><td>19.0</td><td>38</td></tr>
                <tr><td rowspan="2">Medium sand</td><td>Dense</td><td>20.5</td><td>40</td></tr>
                <tr style="background-color: #E3F2FD;"><td>Medium dense</td><td>19.0</td><td>36</td></tr>
                <tr><td rowspan="2">Fine sand</td><td>Dense</td><td>20.5</td><td>38</td></tr>
                <tr style="background-color: #E3F2FD;"><td>Medium dense</td><td>19.0</td><td>32</td></tr>
                <tr><td rowspan="2">Silty sand</td><td>Dense</td><td>20.5</td><td>36</td></tr>
                <tr style="background-color: #E3F2FD;"><td>Medium dense</td><td>19.0</td><td>28</td></tr>
                <tr><td rowspan="2">Clay</td><td>Stiff</td><td>20.0</td><td>22</td></tr>
                <tr style="background-color: #E3F2FD;"><td>Plastic</td><td>17.5</td><td>15</td></tr>
                <tr><td rowspan="2">Silty clay</td><td>Stiff</td><td>21.0</td><td>25</td></tr>
                <tr style="background-color: #E3F2FD;"><td>Plastic</td><td>18.0</td><td>17</td></tr>
            </table>
            """,
        ),
        (
            "Concrete Parameters",
            """
            <h2>Reference Table for Concrete Parameters</h2>
            <p><b>Related parameter:</b> PEH for pile material properties.</p>
            <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #1976D2; color: white;">
                    <th>Concrete grade</th>
                    <th>Elastic modulus E<sub>c</sub> (kN/m<sup>2</sup>)</th>
                    <th>Compressive strength f<sub>c</sub> (MPa)</th>
                </tr>
                <tr><td>C20</td><td>2.55 × 10<sup>7</sup></td><td>13.4</td></tr>
                <tr style="background-color: #E3F2FD;"><td>C25</td><td>2.80 × 10<sup>7</sup></td><td>16.7</td></tr>
                <tr><td>C30</td><td>3.00 × 10<sup>7</sup></td><td>20.1</td></tr>
                <tr style="background-color: #E3F2FD;"><td>C35</td><td>3.15 × 10<sup>7</sup></td><td>23.4</td></tr>
                <tr><td>C40</td><td>3.25 × 10<sup>7</sup></td><td>26.8</td></tr>
                <tr style="background-color: #E3F2FD;"><td>C45</td><td>3.35 × 10<sup>7</sup></td><td>29.6</td></tr>
                <tr><td>C50</td><td>3.45 × 10<sup>7</sup></td><td>32.4</td></tr>
            </table>
            <br>
            <p><b>Recommended range for the stiffness reduction factor PKE</b></p>
            <ul>
                <li>Cast-in-place piles: 0.80 - 0.85</li>
                <li>Precast piles: 0.95 - 1.00</li>
                <li>Adjust the value according to the actual construction quality and material condition.</li>
            </ul>
            """,
        ),
        (
            "KSU Notes",
            """
            <h2>Notes on the End-Resistance Model Selection (KSU)</h2>
            <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #1976D2; color: white;">
                    <th>KSU</th>
                    <th>Meaning</th>
                    <th>Recommended use</th>
                </tr>
                <tr><td>1</td><td>Soil m-value model</td><td>Use the ordinary soil-layer definition and the PMB m-based end coefficient.</td></tr>
                <tr style="background-color: #E3F2FD;"><td>2</td><td>Soil m-value variant</td><td>Use when the same soil-based framework is needed with an alternative end treatment.</td></tr>
                <tr><td>3</td><td>Rock c<sub>0</sub> model</td><td>Use when the pile tip is supported by rock and the c<sub>0</sub> coefficient is required.</td></tr>
                <tr style="background-color: #E3F2FD;"><td>4</td><td>Rock c<sub>0</sub> variant</td><td>Use for the rock-based end-resistance option in the corresponding formulation.</td></tr>
            </table>
            <br>
            <p><b>Practical note:</b> Keep the selected KSU mode consistent with the parameter unit system shown in the other reference tabs.</p>
            """,
        ),
    ]

    for tab_title, html in tab_specs:
        widget = QTextEdit()
        widget.setReadOnly(True)
        widget.setHtml(html)
        tabs.addTab(widget, tab_title)

    layout.addWidget(tabs)

    button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    button_box.rejected.connect(help_dialog.accept)
    layout.addWidget(button_box)

    help_dialog.exec()


def _english_show_tutorial_dialog(self):
    EnglishTutorialDialog(self).exec()


def _english_show_pile_manual_dialog(self):
    try:
        EnglishPileManualDialog(self).exec()
    except Exception as exc:
        QMessageBox.critical(self, "PILE Manual Example Review", f"Failed to open the PILE manual dialog.\n\n{exc}")


def _bilingual_show_tutorial_dialog(self):
    if get_language() == "en":
        return _english_show_tutorial_dialog(self)
    return _ORIGINAL_SHOW_TUTORIAL_DIALOG(self)


def _bilingual_show_pile_manual_dialog(self):
    if get_language() == "en":
        return _english_show_pile_manual_dialog(self)
    return _ORIGINAL_SHOW_PILE_MANUAL_DIALOG(self)


def _bilingual_show_parameter_reference():
    if get_language() == "en":
        return _english_show_parameter_reference()
    return _ORIGINAL_SHOW_PARAMETER_REFERENCE()


def _english_close_event(self, event):
    if self.async_engine and self.async_engine.is_running:
        reply = QMessageBox.question(
            self,
            "Confirm Exit",
            "A calculation is still running. Do you want to exit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            event.ignore()
            return
        self.async_engine.cancel()
    event.accept()


def _apply_english_overlay(widget):
    translate_widget_tree(widget, "en")
    translate_menu_bar(widget, "en")
    _apply_english_font(widget)
    if isinstance(widget, MainWindow):
        _translate_menu_actions(widget)
        _force_english_menu_titles(widget)
        _apply_english_mainwindow_texts(widget)


def _apply_english_font(widget):
    for child in [widget] + widget.findChildren(QWidget):
        try:
            font = child.font()
            if font.family() != "Times New Roman":
                font.setFamily("Times New Roman")
                child.setFont(font)
        except Exception:
            pass


def _set_groupbox_title(widget, zh_text, en_text):
    for group in widget.findChildren(QGroupBox):
        if group.title() == zh_text:
            group.setTitle(en_text)


def _set_label_text(widget, zh_text, en_text):
    for label in widget.findChildren(QLabel):
        if label.text() == zh_text:
            label.setText(en_text)


def _set_label_contains(widget, zh_fragment, en_text):
    for label in widget.findChildren(QLabel):
        text = label.text()
        if text and zh_fragment in text:
            label.setText(en_text)


def _set_button_text(widget, zh_text, en_text):
    for button in widget.findChildren(QPushButton):
        if button.text() == zh_text:
            button.setText(en_text)


def _set_radio_text(widget, zh_text, en_text):
    for radio in widget.findChildren(QRadioButton):
        if radio.text() == zh_text:
            radio.setText(en_text)


def _set_checkbox_text(widget, zh_text, en_text):
    for checkbox in widget.findChildren(QCheckBox):
        if checkbox.text() == zh_text:
            checkbox.setText(en_text)


def _translate_label_widgets(widget):
    for label in widget.findChildren(QLabel):
        text = label.text()
        if text and "<" not in text:
            translated = _translate_to_english(text)
            if translated != text:
                label.setText(translated)


def _translate_button_widgets(widget):
    for button in widget.findChildren(QPushButton):
        text = button.text()
        if text:
            translated = _translate_to_english(text)
            if translated != text:
                button.setText(translated)


def _translate_radio_widgets(widget):
    for radio in widget.findChildren(QRadioButton):
        text = radio.text()
        if text:
            translated = _translate_to_english(text)
            if translated != text:
                radio.setText(translated)


def _translate_checkbox_widgets(widget):
    for checkbox in widget.findChildren(QCheckBox):
        text = checkbox.text()
        if text:
            translated = _translate_to_english(text)
            if translated != text:
                checkbox.setText(translated)


def _translate_groupbox_titles(widget):
    for group in widget.findChildren(QGroupBox):
        title = group.title()
        if title:
            translated = _translate_to_english(title)
            if translated != title:
                group.setTitle(translated)


def _translate_lineedit_placeholders(widget):
    for line_edit in widget.findChildren(QLineEdit):
        placeholder = line_edit.placeholderText()
        if placeholder:
            translated = _translate_to_english(placeholder)
            if translated != placeholder:
                line_edit.setPlaceholderText(translated)


def _translate_tabwidget_texts(widget):
    for tab_widget in widget.findChildren(QTabWidget):
        for index in range(tab_widget.count()):
            text = tab_widget.tabText(index)
            if not text:
                continue
            translated = _translate_to_english(text)
            if translated != text:
                tab_widget.setTabText(index, translated)


def _translate_menu_actions(widget):
    menu_bar = widget.menuBar() if hasattr(widget, "menuBar") else None
    if menu_bar is None:
        return

    def _translate_action(action):
        text = action.text()
        if text:
            translated = _translate_to_english(text)
            translated = translated.replace("Parameter Reference值", "Parameter Reference")
            if translated != text:
                action.setText(translated)
        menu = action.menu()
        if menu is not None:
            menu_text = menu.title()
            if menu_text:
                translated_menu = _translate_to_english(menu_text)
                if translated_menu != menu_text:
                    menu.setTitle(translated_menu)
            for child_action in menu.actions():
                _translate_action(child_action)

    for action in menu_bar.actions():
        _translate_action(action)


def _force_english_menu_titles(window):
    menu_bar = window.menuBar() if hasattr(window, "menuBar") else None
    if menu_bar is None:
        return

    top_level_map = {
        "文件(&F)": "File(&F)",
        "编辑(&E)": "Edit(&E)",
        "教程(&T)": "Examples(&T)",
        "导航": "Navigate",
        "启动台": "Navigate",
        "语言": "Language",
        "帮助(&H)": "Help(&H)",
    }
    action_map = {
        "模式一算例：群Pile刚度": "Mode 1 Example: Group Pile Stiffness",
        "模式二算例：单Pile刚度": "Mode 2 Example: Single Pile Stiffness",
        "模式三算例：Pile基反算": "Mode 3 Example: Back Analysis",
        "PILE Manual Examples (Import)": "PILE Manual Examples (Import)",
        "算例1: 12Pile双工况": "Example 1: 12-Pile Dual Load Cases",
        "算例2: 4Pile带模拟Pile": "Example 2: 4 Piles with Simulated Pile",
        "算例3: 16Pile斜Pile差异化": "Example 3: 16 Inclined Piles with Variation",
        "算例4: 3Pile非中心模拟Pile": "Example 4: 3-Pile Off-Center Simulated Pile",
        "Example Notes and Commentary": "Example Notes and Commentary",
        "PILE Manual Example Review": "PILE Manual Example Review",
    }

    def _normalize_text(value: str) -> str:
        return (value or "").replace("&", "").replace(" ", "").strip()

    for action in menu_bar.actions():
        menu = action.menu()
        current_text = action.text()
        normalized = _normalize_text(current_text)
        for source, target in top_level_map.items():
            if normalized == _normalize_text(source):
                action.setText(target)
                if menu is not None:
                    menu.setTitle(target)
                break

        if menu is not None:
            for child_action in menu.actions():
                child_menu = child_action.menu()
                child_text = child_action.text()
                child_normalized = _normalize_text(child_text)
                for source, target in action_map.items():
                    if child_normalized == _normalize_text(source):
                        child_action.setText(target)
                        if child_menu is not None:
                            child_menu.setTitle(target)
                        break

                if child_menu is not None:
                    for grandchild_action in child_menu.actions():
                        grandchild_text = grandchild_action.text()
                        grandchild_normalized = _normalize_text(grandchild_text)
                        for source, target in action_map.items():
                            if grandchild_normalized == _normalize_text(source):
                                grandchild_action.setText(target)
                                break


def _apply_english_pile_type_editor(editor):
    _translate_groupbox_titles(editor)
    _translate_label_widgets(editor)
    _translate_button_widgets(editor)
    _translate_lineedit_placeholders(editor)

    if hasattr(editor, "ksh_combo"):
        ksh_items = ["Circular Section (0)", "Square Section (1)"]
        for index, text in enumerate(ksh_items):
            if index < editor.ksh_combo.count():
                editor.ksh_combo.setItemText(index, text)
        editor.ksh_combo.setToolTip("KSH: pile cross-section shape")

    if hasattr(editor, "ksu_combo"):
        ksu_items = [
            "1 - Bored Friction Pile",
            "2 - Driven or Vibratory Friction Pile",
            "3 - End-Bearing Pile (Tip Not Socketed)",
            "4 - End-Bearing Pile (Tip Socketed)",
        ]
        for index, text in enumerate(ksu_items):
            if index < editor.ksu_combo.count():
                editor.ksu_combo.setItemText(index, text)
        editor.ksu_combo.setToolTip("KSU: pile tip constraint / pile type")

    if hasattr(editor, "pmb_label"):
        current = editor.pmb_label.text()
        editor.pmb_label.setText(_translate_to_english(current))

    for label in editor.findChildren(QLabel):
        text = label.text().strip()
        if not text:
            continue
        if text.startswith("请先点击"):
            label.setText("Please click [New] to create a pile type first")
        elif text.startswith("截面形状"):
            label.setText("Section Shape (KSH):")
        elif text.startswith("桩端约束"):
            label.setText("Pile Tip Constraint (KSU):")
        elif text.startswith("方向余弦"):
            label.setText("Direction Cosines (AGL):")
        elif text.startswith("弹性模量"):
            label.setText("Elastic Modulus E (kN/m²):")
        elif text.startswith("惯性矩修正系数"):
            label.setText("Inertia Correction Factor:")

    for button in editor.findChildren(QToolButton):
        if button.text() == "?":
            button.setToolTip("Click to view parameter notes")


def _translate_combo_items(widget):
    for combo in widget.findChildren(QComboBox):
        for index in range(combo.count()):
            text = combo.itemText(index).strip()
            if not text:
                continue
            translated = _translate_to_english(text)
            if translated != text:
                combo.setItemText(index, translated)
        tool_tip = combo.toolTip()
        if tool_tip:
            translated_tip = _translate_to_english(tool_tip)
            if translated_tip != tool_tip:
                combo.setToolTip(translated_tip)


def _set_table_headers(table, labels):
    if table is None:
        return
    for index, label in enumerate(labels):
        item = table.horizontalHeaderItem(index)
        if item is None:
            item = QTableWidgetItem(label)
            table.setHorizontalHeaderItem(index, item)
        else:
            item.setText(label)


def _english_simulated_pile_help_html():
    return (
        "<h3>Simulated Pile Notes</h3>"
        "<p><b>Simulated piles</b> are used to represent structural restraints that participate in the system response "
        "(such as riverbank supports or soil resistance beneath the cap) by equivalent stiffness entries.</p>"
        "<p><b>Stiffness input type:</b></p>"
        "<ul>"
        "<li><b>Diagonal mode</b>: input six uncoupled stiffness values (Kx, Ky, Kz, Rx, Ry, Rz).</li>"
        "<li><b>Full matrix mode</b>: input a 6×6 stiffness matrix when coupling effects need to be considered.</li>"
        "</ul>"
        "<p><b>Parameter notes:</b></p>"
        "<ul>"
        "<li><b>X, Y</b>: spatial coordinates of the simulated pile (m)</li>"
        "<li><b>Kx, Ky, Kz</b>: translational stiffness (kN/m)</li>"
        "<li><b>Rx, Ry, Rz</b>: rotational stiffness (kN·m/rad)</li>"
        "</ul>"
        "<p><i>Note: simulated piles contribute stiffness only and do not perform internal-force analysis as physical piles.</i></p>"
    )


def _apply_english_parameter_page_texts(window):
    if hasattr(window, "pile_type_page"):
        _apply_english_pile_type_editor(window.pile_type_page)

    if hasattr(window, "parameter_tabs"):
        tab_count = window.parameter_tabs.count()
        if tab_count == 3:
            window.parameter_tabs.setTabText(0, "Load Input")
            window.parameter_tabs.setTabText(1, "Pile Definition")
            window.parameter_tabs.setTabText(2, "Pile Arrangement")
        elif tab_count == 2:
            window.parameter_tabs.setTabText(0, "Pile Definition")
            window.parameter_tabs.setTabText(1, "Pile Arrangement")

    if hasattr(window, "pile_table"):
        _set_table_headers(window.pile_table, ["Pile No.", "X Coordinate (m)", "Y Coordinate (m)", "Pile Type"])

    if hasattr(window, "ksh_combo"):
        ksh_items = ["Circular Section (0)", "Square Section (1)"]
        for index, text in enumerate(ksh_items):
            if index < window.ksh_combo.count():
                window.ksh_combo.setItemText(index, text)

    if hasattr(window, "ksu_combo"):
        ksu_items = [
            "1 - Bored Friction Pile",
            "2 - Driven or Vibratory Friction Pile",
            "3 - End-Bearing Pile (Tip Not Socketed)",
            "4 - End-Bearing Pile (Tip Socketed)",
        ]
        for index, text in enumerate(ksu_items):
            if index < window.ksu_combo.count():
                window.ksu_combo.setItemText(index, text)

    _set_groupbox_title(window, "桩位布置与类型分配", "Pile Layout and Type Assignment")
    _set_groupbox_title(window, "模拟桩 (虚拟桩) 设置", "Simulated Pile Settings")
    _set_groupbox_title(window, "桩类型管理", "Pile Type Management")
    _set_groupbox_title(window, "基本参数", "Basic Parameters")
    _set_groupbox_title(window, "桩身材料参数", "Pile Material Parameters")
    _set_groupbox_title(window, "地上部分（自由段）- 可选  方向从上往下", "Above-Ground Segment (Free Segment) - Optional")
    _set_groupbox_title(window, "地上部分（自由段）- 可选   方向从上往下", "Above-Ground Segment (Free Segment) - Optional")
    _set_groupbox_title(window, "地上部分（自由段） - 可选    方向从上往下", "Above-Ground Segment (Free Segment) - Optional")
    _set_groupbox_title(window, "荷载数量", "Load Count")
    _set_groupbox_title(window, "承台中心荷载(正算模式)", "Cap-Center Load (Forward Mode)")
    _set_groupbox_title(window, "多荷载输入（同时作用）", "Multiple Load Input (Simultaneous Action)")
    _set_groupbox_title(window, "多荷载输入", "Multiple Load Input (Simultaneous Action)")
    _set_groupbox_title(window, "地下部分（土层参数） - 必填    方向从上往下", "Embedded Segment (Soil Layer Parameters) - Required")
    _set_groupbox_title(window, "桩底参数", "Pile-Tip Parameters")

    _set_label_text(window, "当前编辑:", "Currently Editing:")
    _set_label_text(window, "计算桩号:", "Pile No.:")
    _set_label_text(window, "\u8ba1\u7b97Pile\u53f7:", "Pile No.:")
    _set_label_text(window, "刚度输入类型:", "Stiffness Input Type:")
    _set_label_text(window, "截面形状 (KSH):", "Section Shape (KSH):")
    _set_label_text(window, "桩端约束 (KSU):", "Pile Tip Constraint (KSU):")
    _set_label_text(window, "方向余弦 (AGL):", "Direction Cosines (AGL):")
    _set_label_text(window, "弹性模量 E (KN/m²):", "Elastic Modulus E (kN/m²):")
    _set_label_text(window, "惯性矩修正系数:", "Inertia Correction Factor:")
    _set_label_text(window, "荷载作用点 (m):", "Load Application Point (m):")
    _set_label_contains(window, "承台中心Load", "Cap-Center Load (Forward Mode)")
    _set_label_contains(window, "Pile 底参数", "Pile-Tip Parameters")
    _set_label_contains(window, "Pile 底地基系数", "Pile-Tip Foundation Coefficient")
    _set_label_contains(window, "Pile 端约束 (KSU):", "Pile Tip Constraint (KSU):")
    _set_label_contains(window, "层厚 H (m)", "Layer Thickness H (m)")
    _set_label_contains(window, "直径 D (m)", "Diameter D (m)")
    _set_label_contains(window, "m 值 (KN/m⁴)", "m Value (kN/m^4)")
    _set_label_contains(window, "内摩擦角 φ (°)", "Internal Friction Angle φ (°)")
    _set_label_contains(window, "分段数 N", "Subdivision Count N")
    _set_label_contains(window, "段长 H (m)", "Segment Length H (m)")
    _set_label_contains(window, "直径/边长 D (m)", "Diameter / Side Length D (m)")

    _set_button_text(window, "添加桩", "Add Pile")
    _set_button_text(window, "删除桩", "Delete Pile")
    _set_button_text(window, "批量添加...", "Batch Add...")
    _set_button_text(window, "添加模拟桩", "Add Simulated Pile")
    _set_button_text(window, "删除模拟桩", "Delete Simulated Pile")
    _set_button_text(window, "添加工况", "Add Case")
    _set_button_text(window, "Delete工况", "Delete Case")
    _set_button_text(window, "归一化", "Normalize")
    _set_button_text(window, "参数说明", "Parameter Notes")
    _set_button_text(window, "+ 添加段", "+ Add Segment")
    _set_button_text(window, "+ 添加层", "+ Add Layer")
    _set_button_text(window, "- 删除", "- Delete")

    _set_checkbox_text(window, "启用模拟桩", "Enable Simulated Pile")
    _set_checkbox_text(window, "启用模拟桩（刚度模式）", "Enable Simulated Pile (Stiffness Mode)")
    _set_checkbox_text(window, "启用模拟桩（单桩刚度）", "Enable Simulated Pile (Single-Pile Stiffness)")
    _set_checkbox_text(window, "启用承台土抗力模拟", "Enable Cap-Soil Resistance Simulation")
    _set_radio_text(window, "单荷载", "Single Load")
    _set_radio_text(window, "多荷载（同时作用）", "Multiple Loads (Simultaneous)")

    _set_radio_text(window, "对角线模式", "Diagonal Mode")
    _set_radio_text(window, "全矩阵模式", "Full Matrix Mode")

    _translate_label_widgets(window)
    _translate_button_widgets(window)
    _translate_radio_widgets(window)
    _translate_checkbox_widgets(window)
    _translate_groupbox_titles(window)
    _translate_lineedit_placeholders(window)
    _translate_tabwidget_texts(window)

    for button in window.findChildren(QPushButton):
        if button.text() == "Parameter Notes":
            button.setMinimumWidth(150)
            button.setMaximumWidth(220)
            button.adjustSize()

    for group in window.findChildren(QGroupBox):
        title = group.title()
        if "多荷载输入" in title:
            group.setTitle("Multiple Load Input (Simultaneous Action)")
        elif "承台中心荷载" in title:
            group.setTitle("Cap-Center Load (Forward Mode)")
        elif "地下部分" in title:
            group.setTitle("Embedded Segment (Soil Layer Parameters) - Required")
        elif "桩底参数" in title:
            group.setTitle("Pile-Tip Parameters")
        elif "Pile 底参数" in title:
            group.setTitle("Pile-Tip Parameters")

    if hasattr(window, "below_table"):
        _set_table_headers(window.below_table, ["Layer Thickness H (m)", "Diameter D (m)", "m Value (kN/m^4)", "Internal Friction Angle φ (°)", "Subdivision Count N"])
    if hasattr(window, "above_table"):
        _set_table_headers(window.above_table, ["Segment Length H (m)", "Diameter / Side Length D (m)", "Subdivision Count N"])
    if hasattr(window, "multi_case_table"):
        _set_table_headers(window.multi_case_table, ["Load Case", "X Coordinate (m)", "Y Coordinate (m)", "", "", ""])

    try:
        if hasattr(window, "below_table"):
            english_headers = [
                "Layer Thickness H (m)",
                "Diameter D (m)",
                "m Value (kN/m^4)",
                "Internal Friction Angle φ (°)",
                "Subdivision Count N",
            ]
            for index, header in enumerate(english_headers):
                item = window.below_table.horizontalHeaderItem(index)
                if item is None:
                    item = QTableWidgetItem(header)
                    window.below_table.setHorizontalHeaderItem(index, item)
                else:
                    item.setText(header)
        if hasattr(window, "above_table"):
            english_headers = [
                "Segment Length H (m)",
                "Diameter / Side Length D (m)",
                "Subdivision Count N",
            ]
            for index, header in enumerate(english_headers):
                item = window.above_table.horizontalHeaderItem(index)
                if item is None:
                    item = QTableWidgetItem(header)
                    window.above_table.setHorizontalHeaderItem(index, item)
                else:
                    item.setText(header)
    except Exception:
        pass

    for table in window.findChildren(QTableWidget):
        for column in range(table.columnCount()):
            header_item = table.horizontalHeaderItem(column)
            if header_item is not None:
                header_item.setText(_translate_to_english(header_item.text()))

    if hasattr(window, "simu_group"):
        for button in window.simu_group.findChildren(QToolButton):
            if button.text() != "?":
                continue
            button.setToolTip("Click to view simulated pile notes")
            try:
                button.clicked.disconnect()
            except Exception:
                pass
            button.clicked.connect(
                lambda _checked=False, parent=window: QMessageBox.information(
                    parent,
                    "Simulated Pile Notes",
                    _english_simulated_pile_help_html(),
                )
            )
            break

                                                                             
    for group in window.findChildren(QGroupBox):
        title = (group.title() or "").strip()
        if "地下部分" in title or "土层参数" in title:
            group.setTitle("Embedded Segment (Soil Layer Parameters) - Required")
        elif "地上部分" in title or "自由段" in title:
            group.setTitle("Above-Ground Segment (Free Segment) - Optional")
        elif "桩底参数" in title or "Pile 底参数" in title:
            group.setTitle("Pile-Tip Parameters")
        elif "承台中心" in title:
            group.setTitle("Cap-Center Load (Forward Mode)")
        elif "多荷载" in title:
            group.setTitle("Multiple Load Input (Simultaneous Action)")

    for label in window.findChildren(QLabel):
        text = (label.text() or "").strip()
        if "Pile 底参数" in text or text == "桩底参数":
            label.setText("Pile-Tip Parameters")
        elif text.startswith("Pile") and ("KN/m" in text or "kN/m" in text) and ("\u7cfb\u6570" in text or "\u00e5\u0153\u00b0\u00e5\u0178\u00ba\u00e7\u00b3\u00bb" in text):
            if "c" in text.lower() or "co" in text.lower():
                label.setText("Pile-Tip Foundation Coefficient c0 (kN/m^3):")
            else:
                label.setText("Pile-Tip Foundation Coefficient m0 (kN/m^4):")
        elif "Pile 端约束" in text:
            label.setText("Pile Tip Constraint (KSU):")
        elif "承台中心Load" in text:
            label.setText("Cap-Center Load (Forward Mode)")

    for button in window.findChildren(QPushButton):
        text = (button.text() or "").strip()
        if "参数说明" in text or "arameter" in text:
            button.setText("Parameter Notes")
            button.setMinimumWidth(150)
            button.setMaximumWidth(220)
            button.adjustSize()
        elif "添加段" in text:
            button.setText("+ Add Segment")
        elif "添加层" in text:
            button.setText("+ Add Layer")
        elif text.startswith("-") and "删除" in text:
            button.setText("- Delete")

    if hasattr(window, "below_table"):
        _set_table_headers(
            window.below_table,
            [
                "Layer Thickness H (m)",
                "Diameter D (m)",
                "m Value (kN/m^4)",
                "Internal Friction Angle φ (°)",
                "Subdivision Count N",
            ],
        )

    if hasattr(window, "above_table"):
        _set_table_headers(
            window.above_table,
            [
                "Segment Length H (m)",
                "Diameter / Side Length D (m)",
                "Subdivision Count N",
            ],
        )


def _apply_english_mainwindow_texts(window):
    window.setWindowTitle("PileAnalysis - M-Method")

    if hasattr(window, "visual_tabs"):
        if window.visual_tabs.count() >= 2:
            window.visual_tabs.setTabText(0, "Analysis Schematic")
            window.visual_tabs.setTabText(1, "Plot Area")

    if hasattr(window, "plot_tabs"):
        if window.plot_tabs.count() >= 1:
            window.plot_tabs.setTabText(0, "3D Layout")
        if window.plot_tabs.count() >= 2:
            window.plot_tabs.setTabText(1, "Plan Layout")

    if hasattr(window, "results_tabs"):
        if window.results_tabs.count() >= 2:
            window.results_tabs.setTabText(0, "Summary")
            window.results_tabs.setTabText(1, "Raw Output")

    if hasattr(window, "summary_text"):
        window.summary_text.setPlaceholderText("Result summary will be displayed here...")
        current_summary = window.summary_text.toPlainText().strip()
        if current_summary in {
            "",
            "\u8ba1\u7b97\u7ed3\u679c\u6458\u8981\u5c06\u663e\u793a\u5728\u6b64...",
            "\u8ba1\u7b97Summary\u5c06\u663e\u793a\u5728\u6b64...",
            "Summary",
        }:
            window.summary_text.setPlainText("Result summary will be displayed here...")
    if hasattr(window, "raw_output_text"):
        window.raw_output_text.setPlaceholderText("Raw stiffness matrix and solver output will be displayed here...")

    if hasattr(window, "plot_3d_area"):
        text = window.plot_3d_area.text().strip()
        if not text or "\u663e\u793a" in text or "\u5b8c\u6210" in text or "Complete" in text:
            window.plot_3d_area.setText("The 3D pile-group layout will be displayed after the calculation is complete")

    if hasattr(window, "plot_response_area"):
        text = window.plot_response_area.text().strip()
        if "\u7ed8\u56fe\u6a21\u5757\u4e0d\u53ef\u7528" in text:
            window.plot_response_area.setText("Plotting module is unavailable")
        elif "\u65e0\u6869\u8eab\u54cd\u5e94\u6570\u636e" in text:
            window.plot_response_area.setText("No pile response data are available.\n\nDetailed pile response curves are only available in the load-to-internal-force deformation mode.")
        else:
            window.plot_response_area.setText("Response curves will be displayed after the calculation is complete")

    if hasattr(window, "placeholder_label"):
        placeholder_map = {
            "\u2191 \u8bf7\u9009\u62e9\u5de5\u51b5\u7c7b\u578b": "\u2191 Please select a case type",
            "\u2191 \u8bf7\u9009\u62e9\u5de5\u51b5\u7c7b\u578b\u5e76\u7ee7\u7eed": "\u2191 Please select a case type and continue",
            "\u2191 \u8bf7\u9009\u62e9\u8ba1\u7b97\u6a21\u5f0f\u5e76\u5bfc\u5165\u73b0\u6709\u5de5\u51b5": "\u2191 Please select an analysis mode and import an existing case",
            "\u2191 \u8bf7\u9009\u62e9\u8ba1\u7b97\u6a21\u5f0f\u5e76\u8bbe\u7f6e\u5de5\u51b5": "\u2191 Please select an analysis mode and define the case",
            "\u2191 \u8bf7\u70b9\u51fb\u3010\u67e5\u770b\u4e0e\u4fee\u6539\u3011\u6216\u3010\u76f4\u63a5\u8ba1\u7b97\u3011": "\u2191 Click [View and Edit] or [Run Directly]",
            "\u2191 \u8ba1\u7b97\u5b8c\u6210\uff0c\u8bf7\u67e5\u770b\u7ed3\u679c": "\u2191 The analysis is complete. Please review the results",
        }
        current_text = window.placeholder_label.text().strip()
        window.placeholder_label.setText(placeholder_map.get(current_text, _translate_to_english(current_text)))

    _set_groupbox_title(window, "\u8ba1\u7b97\u7ed3\u679c\u8f93\u51fa\u533a", "Result Output")
    _set_groupbox_title(window, "\u5feb\u901f\u4e0a\u624b\u6307\u5357", "Quick Start Guide")
    _set_groupbox_title(window, "\u5de5\u51b5\u9009\u62e9", "Case Selection")
    _set_groupbox_title(window, "\u8ba1\u7b97\u6a21\u5f0f\u9009\u62e9", "Analysis Mode Selection")
    _apply_english_parameter_page_texts(window)

    quick_start_zh = (
        "\u0031.\u9009\u62e9\u5de5\u51b5\u7c7b\u578b\uff08\u73b0\u6709/\u65b0\u5efa\uff09\n"
        "\u0032.\u9009\u62e9\u8ba1\u7b97\u6a21\u5f0f\n"
        "\u0033.\u586b\u5199\u53c2\u6570 -> \u5b9a\u4e49\u6869\u7c7b\u578b -> \u6dfb\u52a0\u6869\u4f4d\u5750\u6807\n"
        "\u0034.\u70b9\u51fb\u3010\u5f00\u59cb\u8ba1\u7b97\u3011"
    )
    quick_start_en = (
        "1. Select the case type (existing or new)\n"
        "2. Select the analysis mode\n"
        "3. Fill in parameters -> define pile types -> add pile coordinates\n"
        "4. Click [Run]"
    )
    _set_label_text(window, quick_start_zh, quick_start_en)
    for label in window.findChildren(QLabel):
        text = label.text().strip()
        if text.startswith("1.") and ("Run" in text or "工况" in text or "Type" in text):
            label.setText(quick_start_en)

    _set_radio_text(window, "\u73b0\u6709\u5de5\u51b5", "Existing Case")
    _set_radio_text(window, "\u65b0\u5efa\u5de5\u51b5", "New Case")
    _set_radio_text(window, "\u6a21\u5f0f\u4e00\uff1a\u7fa4\u6869\u521a\u5ea6", "Mode 1: Group Pile Stiffness")
    _set_radio_text(window, "\u6a21\u5f0f\u4e8c\uff1a\u5355\u6869\u521a\u5ea6", "Mode 2: Single Pile Stiffness")
    _set_radio_text(window, "\u6a21\u5f0f\u4e09\uff1a\u6869\u57fa\u53cd\u7b97", "Mode 3: Back Analysis")
    for radio in window.findChildren(QRadioButton):
        text = radio.text().strip()
        if "模式一" in text:
            radio.setText("Mode 1: Group Pile Stiffness")
        elif "模式二" in text:
            radio.setText("Mode 2: Single Pile Stiffness")
        elif "模式三" in text:
            radio.setText("Mode 3: Back Analysis")

    _set_button_text(window, "\u8fd4\u56de\u5de5\u51b5\u9009\u62e9", "Back to Case Selection")
    _set_button_text(window, "\u5bfc\u5165\u5df2\u6709\u5de5\u51b5\uff08dat\u6587\u4ef6\uff09", "Import Existing Case (.dat)")
    _set_button_text(window, "\u67e5\u770b\u4e0e\u4fee\u6539", "View and Edit")
    _set_button_text(window, "\u76f4\u63a5\u8ba1\u7b97", "Run Directly")
    _set_button_text(window, "\u4fdd\u5b58\u5de5\u51b5", "Save Case")
    _set_button_text(window, "\u4fdd\u5b58\u5e76\u5bfc\u51fa", "Save and Export")
    _set_button_text(window, "\u5f00\u59cb\u8ba1\u7b97", "Run")
    _set_button_text(window, "\u66f4\u6362\u6587\u4ef6", "Change File")
    for button in window.findChildren(QPushButton):
        text = button.text().strip()
        if "dat文件" in text or "DAT文件" in text:
            button.setText("Import Existing Case (.dat)")

    if hasattr(window, "import_button"):
        window.import_button.setToolTip("Select and import an existing DAT case file")
    if hasattr(window, "view_modify_button"):
        if hasattr(window, "_imported_filename") and getattr(window, "_imported_filename", None):
            window.view_modify_button.setText("View and Edit")
            window.view_modify_button.setToolTip("Review and edit the imported case parameters")
        elif window.view_modify_button.isVisible():
            window.view_modify_button.setText("View and Edit")
            window.view_modify_button.setToolTip("Review and edit the imported case parameters")
    if hasattr(window, "direct_calc_button"):
        window.direct_calc_button.setToolTip("Run the imported case directly")
    if hasattr(window, "calculate_button"):
        window.calculate_button.setToolTip("Run the current analysis")

    if hasattr(window, "import_status_label"):
        if hasattr(window, "_imported_filename") and getattr(window, "_imported_filename", None):
            filename = _translate_to_english(os.path.basename(window._imported_filename))
            window.import_status_label.setText(f"\u2713 Imported existing case: {filename}")
        else:
            current_text = window.import_status_label.text().strip()
            if current_text:
                window.import_status_label.setText(_translate_summary_output(_translate_to_english(current_text)))

    if hasattr(window, "author_label"):
        window.author_label.setText("Authors: Can Wang, Junjun Guo")
    if hasattr(window, "email_label"):
        window.email_label.setText("Contact: 24231238@bjtu.edu.cn / jjguo2@bjtu.edu.cn")
    if hasattr(window, "version_label"):
        window.version_label.setText("Version: 3.0")
    if hasattr(window, "download_label"):
        window.download_label.setText(
            "<a href='https://github.com/CanWang-BJTU/PileAnalysis' style='color: #000000; text-decoration: none;'>Update</a>"
        )
    if hasattr(window, "calc_status_label"):
        status_map = {
            "\u51c6\u5907\u5c31\u7eea": "Preparation Complete",
            "\u8ba1\u7b97\u4e2d": "Running...",
            "\u8ba1\u7b97\u5b8c\u6210": "Completed",
        }
        current_status = window.calc_status_label.text().strip()
        if current_status in status_map:
            window.calc_status_label.setText(status_map[current_status])



def _bilingual_mainwindow_init(self, *args, **kwargs):
    _ORIGINAL_MAINWINDOW_INIT(self, *args, **kwargs)
    if not hasattr(self, "parser"):
        self.parser = None
    if not hasattr(self, "plotter"):
        self.plotter = None
    if get_language() == "en":
        self.setWindowTitle("PileAnalysis - M-Method")
        _apply_english_overlay(self)
        if self.centralWidget() and hasattr(self.centralWidget(), "setSizes"):
            width = max(self.width(), 1)
            self.centralWidget().setSizes([int(width * 0.49), max(width - int(width * 0.49), 1)])


def _bilingual_show_parameter_tabs(self, *args, **kwargs):
    result = _ORIGINAL_SHOW_PARAMETER_TABS(self, *args, **kwargs)
    if get_language() == "en":
        _apply_english_overlay(self)
    return result


def _bilingual_on_case_type_selected(self, *args, **kwargs):
    result = _ORIGINAL_ON_CASE_TYPE_SELECTED(self, *args, **kwargs)
    if get_language() == "en":
        _apply_english_overlay(self)
    return result


def _bilingual_on_mode_selected(self, *args, **kwargs):
    result = _ORIGINAL_ON_MODE_SELECTED(self, *args, **kwargs)
    if get_language() == "en":
        _apply_english_overlay(self)
    return result


def _bilingual_back_to_case_selection(self, *args, **kwargs):
    result = _ORIGINAL_BACK_TO_CASE_SELECTION(self, *args, **kwargs)
    if get_language() == "en":
        _apply_english_overlay(self)
    return result


def _bilingual_import_dat_file(self, *args, **kwargs):
    result = _ORIGINAL_IMPORT_DAT_FILE(self, *args, **kwargs)
    if get_language() == "en":
        if hasattr(self, "import_status_label"):
            current_text = self.import_status_label.text().strip()
            if current_text:
                current_text = _translate_summary_output(_translate_to_english(current_text))
                self.import_status_label.setText(current_text)
        if hasattr(self, "placeholder_label"):
            current_text = self.placeholder_label.text().strip()
            if current_text:
                self.placeholder_label.setText(_translate_summary_output(_translate_to_english(current_text)))
        _apply_english_overlay(self)
    return result


def _bilingual_start_calculation(self, *args, **kwargs):
    result = _ORIGINAL_START_CALCULATION(self, *args, **kwargs)
    if get_language() == "en":
        _apply_english_overlay(self)
    return result


def _bilingual_generate_summary(self, *args, **kwargs):
    summary = _ORIGINAL_GENERATE_SUMMARY(self, *args, **kwargs)
    if get_language() == "en" and isinstance(summary, str):
        return _translate_summary_output(_translate_to_english(summary))
    return summary


def _translate_summary_output(text):
    if not text:
        return text

    translated = _translate_to_english(text)
    replacements = [
        ("计算Summary", "Analysis Summary"),
        ("承台整体刚度矩阵", "Global Cap Stiffness Matrix"),
        ("Notice: 可点击菜单栏导出按钮，Export Stiffness Matrix CSV，供后续分析使用", "Notice: Click Export Stiffness Matrix CSV in the menu bar to export the matrix for subsequent analysis."),
        ("【原始刚度矩阵】(Z轴向下)", "[Original Stiffness Matrix] (Z Axis Downward)"),
        ("【转换刚度矩阵】(Z轴向上)", "[Converted Stiffness Matrix] (Z Axis Upward)"),
        ("主对角线刚度:", "Principal Diagonal Stiffness:"),
        ("共 ", "Total "),
        (" 个Load:", " load cases:"),
        ("【Load一】", "[Load 1]"),
        ("【Load二】", "[Load 2]"),
        ("【Load三】", "[Load 3]"),
        ("【Load四】", "[Load 4]"),
        ("position:", "Position:"),
        ("Load值:", "Loads:"),
        ("承台中心Displacement:", "Cap-Center Displacement:"),
        ("X方向Displacement:", "X-Direction Displacement:"),
        ("Y方向Displacement:", "Y-Direction Displacement:"),
        ("竖向沉降:", "Vertical Settlement:"),
        ("绕X轴转角:", "Rotation about X Axis:"),
        ("绕Y轴转角:", "Rotation about Y Axis:"),
        ("绕Z轴转角:", "Rotation about Z Axis:"),
        ("桩顶Displacement:", "Pile-Head Displacement:"),
        ("桩顶内力:", "Pile-Head Internal Forces:"),
        ("Single Pile Stiffness计算 - 桩号:", "Single Pile Stiffness Calculation - Pile No.:"),
        ("桩 ", "Pile "),
    ]
    for src, dst in replacements:
        translated = translated.replace(src, dst)
    return translated


def _bilingual_on_calc_finished(self, *args, **kwargs):
    result = _ORIGINAL_ON_CALC_FINISHED(self, *args, **kwargs)
    if get_language() == "en":
        if hasattr(self, "summary_text"):
            current_summary = self.summary_text.toPlainText()
            if current_summary:
                self.summary_text.setPlainText(_translate_summary_output(current_summary))
        if hasattr(self, "raw_output_text"):
            current_raw = self.raw_output_text.toPlainText()
            if current_raw:
                self.raw_output_text.setPlainText(_translate_summary_output(current_raw))
        _apply_english_overlay(self)
    return result


def _bilingual_plot_results(self, *args, **kwargs):
    result = _ORIGINAL_PLOT_RESULTS(self, *args, **kwargs)
    if get_language() == "en":
        _apply_english_overlay(self)
    return result


def _bilingual_load_tutorial_case(self, *args, **kwargs):
    result = _ORIGINAL_LOAD_TUTORIAL_CASE(self, *args, **kwargs)
    if get_language() == "en":
        _apply_english_overlay(self)
    return result


def _bilingual_load_pile_manual_case(self, *args, **kwargs):
    result = _ORIGINAL_LOAD_PILE_MANUAL_CASE(self, *args, **kwargs)
    if get_language() == "en":
        _apply_english_overlay(self)
    return result


MainWindow.__init__ = _bilingual_mainwindow_init
MainWindow._show_parameter_tabs = _bilingual_show_parameter_tabs
MainWindow._on_case_type_selected = _bilingual_on_case_type_selected
MainWindow._on_mode_selected = _bilingual_on_mode_selected
MainWindow._back_to_case_selection = _bilingual_back_to_case_selection
MainWindow._import_dat_file = _bilingual_import_dat_file
MainWindow.start_calculation = _bilingual_start_calculation
MainWindow._generate_summary = _bilingual_generate_summary
MainWindow._on_calc_finished = _bilingual_on_calc_finished
MainWindow._plot_results = _bilingual_plot_results
MainWindow._load_tutorial_case = _bilingual_load_tutorial_case
MainWindow._load_pile_manual_case = _bilingual_load_pile_manual_case
MainWindow._create_help_button = _bilingual_create_help_button
MainWindow._add_row_with_help = _bilingual_add_row_with_help
MainWindow._add_cap_row_with_help = _bilingual_add_cap_row_with_help
MainWindow._show_tutorial_dialog = _bilingual_show_tutorial_dialog
MainWindow._show_pile_manual_dialog = _bilingual_show_pile_manual_dialog
MainWindow.show_parameter_reference = staticmethod(_bilingual_show_parameter_reference)
MainWindow._export_summary_csv = _bilingual_export_summary_csv
MainWindow._export_stiffness_csv = _bilingual_export_stiffness_csv
PileTypeEditor.__init__ = _bilingual_piletypeeditor_init
PileTypeEditor._create_help_button = _bilingual_piletypeeditor_create_help_button
PileTypeEditor._add_row_with_help = _bilingual_piletypeeditor_add_row_with_help
PileTypeEditor._show_above_segment_help = _bilingual_show_above_segment_help
PileTypeEditor._show_below_segment_help = _bilingual_show_below_segment_help


def _patched_dialog_find_resource_path(self, filename):
    return _find_existing_resource(
        filename,
        extra_dirs=[CASE_SAMPLES_DIR, GUI_MODULES_DIR, FRAMEWORK_DIR]
    )


def _patched_init_calculation_modules(self):
    self.async_engine = None
    self.exe_path = ""

    if HAS_ENGINE and AsyncPileEngine is not None:
        try:
            bcad_pile_exe = _find_bcad_pile_executable()
            self.async_engine = AsyncPileEngine()

            if bcad_pile_exe and bcad_pile_exe.exists():
                success = self.async_engine.engine.set_executable_path(str(bcad_pile_exe))
                if success:
                    self.exe_path = str(bcad_pile_exe)
                    logger.info(f"Executable ready: {self.exe_path}")
                    QTimer.singleShot(100, lambda: self.update_status(f"Calculation engine ready: {Path(self.exe_path).name}"))
                else:
                    logger.warning(f"Failed to initialize executable: {bcad_pile_exe}")
                    QTimer.singleShot(100, lambda: self.update_status("Calculation engine initialization failed"))
            elif self.async_engine.engine.exe_path:
                self.exe_path = self.async_engine.engine.exe_path
                logger.info(f"Using engine executable from engine settings: {self.exe_path}")
                QTimer.singleShot(100, lambda: self.update_status(f"Calculation engine ready: {Path(self.exe_path).name}"))
            else:
                logger.warning("BCAD-PILE.exe was not found in the current framework layout")
                QTimer.singleShot(100, lambda: self.update_status("BCAD-PILE.exe was not found"))
        except Exception as e:
            logger.error(f"Failed to initialize calculation engine: {e}")
            self.async_engine = None
            QTimer.singleShot(100, lambda: self.update_status(f"Calculation engine error: {e}"))

    self.parser = None
    if HAS_PARSER and ResultParser is not None:
        self.parser = ResultParser()

    self.plotter = None
    if HAS_PLOTTER and PilePlotter is not None:
        try:
            self.plotter = PilePlotter()
        except Exception as e:
            logger.error(f"Failed to initialize plotter: {e}")
            self.plotter = None


def _patched_load_tutorial_case(self, mode_idx: int):
    filenames = {
        1: "mode_1_example.dat",
        2: "mode_2_example.dat",
        3: "mode_3_example.dat",
    }

    target_file = filenames.get(mode_idx)
    if not target_file:
        return

    file_path = _find_existing_resource(target_file, extra_dirs=[CASE_SAMPLES_DIR])
    if not file_path:
        QMessageBox.warning(self, "File Missing", f"Tutorial case file was not found:\n{target_file}")
        return

    self.case_button_group.button(0).setChecked(True)
    self._on_case_type_selected(0)
    self._import_dat_file(filename=str(file_path))

    if self.case_imported:
        self.update_status(f"Imported tutorial case: {target_file}")
        self._show_parameter_tabs()


def _patched_load_pile_manual_case(self, case_idx: int):
    filenames = {
        1: "pile_manual_example_01_12_pile_dual_case.dat",
        2: "pile_manual_example_02_4_piles_with_simulated_pile.dat",
        3: "pile_manual_example_03_16_inclined_piles.dat",
        4: "pile_manual_example_04_3_pile_eccentric_simulated.dat",
    }

    target_file = filenames.get(case_idx)
    if not target_file:
        return

    file_path = _find_existing_resource(target_file, extra_dirs=[CASE_SAMPLES_DIR])
    if not file_path:
        QMessageBox.warning(self, "File Missing", f"PILE tutorial case file was not found:\n{target_file}")
        return

    self.case_button_group.button(0).setChecked(True)
    self._on_case_type_selected(0)
    self._import_dat_file(filename=str(file_path))

    if self.case_imported:
        self.update_status(f"Imported tutorial case: {target_file}")
        self._show_parameter_tabs()


def _patched_load_schematic_diagram(self, layout: QVBoxLayout):
    possible_paths = _iter_schematic_candidates(get_language())

    diagram_path = None
    file_type = None
    for path, ftype in possible_paths:
        if path.exists():
            diagram_path = path
            file_type = ftype
            break

    image_data = None

    if diagram_path and file_type in ("ai", "pdf"):
        try:
            import fitz

            doc = fitz.open(str(diagram_path))
            if doc.page_count > 0:
                page = doc[0]
                mat = fitz.Matrix(6.0, 6.0)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                image_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                    pix.height, pix.width, pix.n
                )
                logger.info(f"Loaded schematic via PyMuPDF: {diagram_path}")
            doc.close()
        except ImportError:
            logger.warning("PyMuPDF is unavailable, schematic will fall back to normal image loading")
        except Exception as e:
            logger.error(f"Failed to render schematic via PyMuPDF: {e}")

    if diagram_path and image_data is None:
        try:
            import matplotlib.pyplot as plt

            image_data = plt.imread(str(diagram_path))
            logger.info(f"Loaded schematic image: {diagram_path}")
        except Exception as e:
            logger.error(f"Failed to load schematic image: {e}")

    if HAS_MATPLOTLIB_QT and image_data is not None:
        try:
            fig = Figure(figsize=(10, 8), facecolor="white")
            ax = fig.add_subplot(111)
            ax.imshow(image_data)
            ax.axis("off")
            ax.set_title(
                "Pile Foundation Analysis Schematic" if get_language() == "en" else "桩基础计算原理示意图",
                fontsize=12,
                fontweight="bold",
                pad=10,
                **_get_plot_title_kwargs(get_language()),
            )
            fig.tight_layout(pad=0.5)

            canvas = FigureCanvas(fig)
            canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            toolbar = NavigationToolbar(canvas, None)
            toolbar.setStyleSheet(
                """
                QToolBar {
                    background-color: #f0f0f0;
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    spacing: 3px;
                    padding: 2px;
                }
                """
            )

            layout.addWidget(toolbar)
            layout.addWidget(canvas)
            self.diagram_canvas = canvas
            self.diagram_figure = fig
            return
        except Exception as e:
            logger.error(f"Failed to show schematic on interactive canvas: {e}")

    pixmap = None
    if diagram_path and file_type in ("ai", "pdf"):
        try:
            import fitz

            doc = fitz.open(str(diagram_path))
            if doc.page_count > 0:
                page = doc[0]
                pix = page.get_pixmap(matrix=fitz.Matrix(6.0, 6.0), alpha=False)
                pixmap = QPixmap()
                pixmap.loadFromData(pix.tobytes("png"))
            doc.close()
        except Exception:
            pixmap = None

    if pixmap is None and diagram_path:
        pixmap = QPixmap(str(diagram_path))
        if pixmap.isNull():
            pixmap = None

    self.diagram_label = ScalableImageLabel()
    self.diagram_label.setMinimumHeight(200)

    if pixmap and not pixmap.isNull():
        self.diagram_label.setOriginalPixmap(pixmap)
    else:
        self.diagram_label.setText(
            "Schematic file was not found.\n\nExpected files include:\n"
            "pile_foundation_schematic.ai\n"
            "pile_foundation_schematic_en.ai\n"
            "schematic.png"
        )
        self.diagram_label.setStyleSheet(
            "color: #888888; font-size: 12px; background-color: #f0f0f0; padding: 20px;"
        )

    layout.addWidget(self.diagram_label)


PileManualDialog._find_resource_path = _patched_dialog_find_resource_path
TutorialDialog._find_resource_path = _patched_dialog_find_resource_path
MainWindow._init_calculation_modules = _patched_init_calculation_modules
MainWindow._load_tutorial_case = _patched_load_tutorial_case
MainWindow._load_pile_manual_case = _patched_load_pile_manual_case
MainWindow._load_schematic_diagram = _patched_load_schematic_diagram

if get_language() == "en":
    MainWindow._show_about = _english_show_about
    MainWindow.closeEvent = _english_close_event


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

            
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.argv[0]))
    else:
        base_path = os.path.dirname(__file__)
    icon_path = os.path.join(base_path, 'app_icon.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    app.setApplicationName("PileAnalysis")
    app.setApplicationVersion("3.0")
    app.setOrganizationName("BJTU")

    window = MainWindow()

    screen = app.primaryScreen()
    if screen:
        screen_geo = screen.geometry()
        x = (screen_geo.width() - window.width()) // 2
        y = (screen_geo.height() - window.height()) // 2
        window.move(x, y)

    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()










