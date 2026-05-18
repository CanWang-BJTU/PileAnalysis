# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from core.mesh_spec import DEFAULT_ELEMENT_COUNT, default_mesh_settings, normalize_mesh_settings
from language_manager import get_language
from ui_localization import translate_text


class MeshSettingsWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._change_callback: Optional[Callable[[], None]] = None
        self._total_length_provider: Optional[Callable[[], float]] = None
        self._loading = False

        def tr(text: str) -> str:
            if get_language() != "zh":
                return text
            translations = {
                "Enable advanced mesh settings": "启用高级网格设置",
                "Mesh control": "网格控制",
                "Mesh type:": "网格类型:",
                "Element number": "单元数量",
                "Element length": "单元长度",
                "User define": "自定义",
                "Element length (m)": "单元长度 (m)",
                "Start (m)": "起点 (m)",
                "End (m)": "终点 (m)",
                "Top length (m)": "顶部长度 (m)",
                "Bottom length (m)": "底部长度 (m)",
                "Add Segment": "添加分段",
                "Delete Segment": "删除分段",
                "For user-defined mesh, fill start/end and element number. Top/bottom lengths are optional and control linear grading.": "自定义网格时，请填写起点、终点和单元数。顶部/底部长度为可选项，可用于控制线性渐变。",
            }
            return translations.get(text, text)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        self.advanced_enabled = QCheckBox(tr("Enable advanced mesh settings"))
        root.addWidget(self.advanced_enabled)

        self.advanced_box = QGroupBox(tr("Mesh control"))
        box_layout = QVBoxLayout(self.advanced_box)
        box_layout.setContentsMargins(10, 10, 10, 10)
        box_layout.setSpacing(6)

        mesh_type_row = QHBoxLayout()
        mesh_type_row.addWidget(QLabel(tr("Mesh type:")))
        self.mode_number = QRadioButton(tr("Element number"))
        self.mode_length = QRadioButton(tr("Element length"))
        self.mode_user = QRadioButton(tr("User define"))
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.mode_number)
        self.mode_group.addButton(self.mode_length)
        self.mode_group.addButton(self.mode_user)
        self.mode_number.setChecked(True)
        mesh_type_row.addWidget(self.mode_number)
        mesh_type_row.addWidget(self.mode_length)
        mesh_type_row.addWidget(self.mode_user)
        mesh_type_row.addStretch()
        box_layout.addLayout(mesh_type_row)

        self.uniform_widget = QWidget()
        uniform_form = QFormLayout(self.uniform_widget)
        uniform_form.setContentsMargins(0, 0, 0, 0)
        uniform_form.setHorizontalSpacing(10)
        uniform_form.setVerticalSpacing(6)
        self.uniform_count = QSpinBox()
        self.uniform_count.setRange(1, 200000)
        self.uniform_count.setValue(DEFAULT_ELEMENT_COUNT)
        self.uniform_length = QDoubleSpinBox()
        self.uniform_length.setRange(0.0001, 1000.0)
        self.uniform_length.setDecimals(4)
        self.uniform_length.setValue(0.1)
        uniform_form.addRow(tr("Element number"), self.uniform_count)
        uniform_form.addRow(tr("Element length (m)"), self.uniform_length)
        box_layout.addWidget(self.uniform_widget)

        self.custom_widget = QWidget()
        custom_layout = QVBoxLayout(self.custom_widget)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.setSpacing(6)
        self.custom_table = QTableWidget(0, 5)
        self.custom_table.setHorizontalHeaderLabels(
            [tr("Start (m)"), tr("End (m)"), tr("Element number"), tr("Top length (m)"), tr("Bottom length (m)")]
        )
        self.custom_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.custom_table.verticalHeader().setVisible(False)
        custom_layout.addWidget(self.custom_table)
        custom_tools = QHBoxLayout()
        self.add_segment_btn = QPushButton(tr("Add Segment"))
        self.del_segment_btn = QPushButton(tr("Delete Segment"))
        custom_tools.addWidget(self.add_segment_btn)
        custom_tools.addWidget(self.del_segment_btn)
        custom_tools.addStretch()
        custom_layout.addLayout(custom_tools)
        self.custom_note = QLabel(tr("For user-defined mesh, fill start/end and element number. Top/bottom lengths are optional and control linear grading."))
        self.custom_note.setWordWrap(True)
        self.custom_note.setStyleSheet("color: #808080;")
        custom_layout.addWidget(self.custom_note)
        box_layout.addWidget(self.custom_widget)

        root.addWidget(self.advanced_box)

        self.advanced_enabled.toggled.connect(self._on_controls_changed)
        self.mode_number.toggled.connect(self._on_controls_changed)
        self.mode_length.toggled.connect(self._on_controls_changed)
        self.mode_user.toggled.connect(self._on_controls_changed)
        self.uniform_count.valueChanged.connect(lambda *_: self._on_controls_changed())
        self.uniform_length.valueChanged.connect(lambda *_: self._on_controls_changed())
        self.custom_table.itemChanged.connect(lambda *_: self._emit_changed())
        self.add_segment_btn.clicked.connect(self._add_segment_row)
        self.del_segment_btn.clicked.connect(self._delete_segment_row)

        self._refresh_ui()

    def set_change_callback(self, callback: Optional[Callable[[], None]]):
        self._change_callback = callback

    def set_total_length_provider(self, provider: Optional[Callable[[], float]]):
        self._total_length_provider = provider
        self._refresh_ui()

    def get_settings(self) -> Dict:
        settings = default_mesh_settings()
        settings["advanced_enabled"] = self.advanced_enabled.isChecked()
        settings["mesh_type"] = self._current_mesh_type()
        settings["uniform_element_count"] = self.uniform_count.value()
        settings["uniform_element_length_m"] = self.uniform_length.value()
        settings["segments"] = self._read_segments()
        return normalize_mesh_settings(settings)

    def set_settings(self, settings: Optional[Dict]):
        spec = normalize_mesh_settings(settings)
        self._loading = True
        self.advanced_enabled.setChecked(spec["advanced_enabled"])
        mesh_type = spec["mesh_type"]
        self.mode_number.setChecked(mesh_type == "element_number")
        self.mode_length.setChecked(mesh_type == "element_length")
        self.mode_user.setChecked(mesh_type == "user_define")
        self.uniform_count.setValue(spec["uniform_element_count"])
        if spec["uniform_element_length_m"] > 0.0:
            self.uniform_length.setValue(spec["uniform_element_length_m"])
        self.custom_table.setRowCount(0)
        for segment in spec.get("segments", []):
            self._append_segment_row(
                float(segment.get("start_m", 0.0)),
                float(segment.get("end_m", 0.0)),
                int(segment.get("element_count", 1)),
                segment.get("top_length_m"),
                segment.get("bottom_length_m"),
            )
        self._loading = False
        self._refresh_ui()

    def validate_custom_segments(self) -> Optional[str]:
        def tr_msg(message: str) -> str:
            return str(translate_text(message, get_language()))

        if not (self.advanced_enabled.isChecked() and self.mode_user.isChecked()):
            return None

        segments = self._read_segments()
        if not segments:
            return tr_msg("Custom mesh table is empty.")

        total_length = self._current_total_length()
        if abs(float(segments[0]["start_m"])) > 1.0e-6:
            return tr_msg("Custom mesh must start at 0.0 m.")
        if total_length > 0.0 and abs(float(segments[-1]["end_m"]) - total_length) > 1.0e-6:
            return tr_msg(f"Custom mesh must end exactly at the pile length {total_length:.4f} m.")

        cursor = 0.0
        for idx, segment in enumerate(segments, start=1):
            start = float(segment["start_m"])
            end = float(segment["end_m"])
            count = int(segment["element_count"])
            top_length = segment.get("top_length_m")
            bottom_length = segment.get("bottom_length_m")

            if abs(start - cursor) > 1.0e-6:
                return tr_msg(f"Custom mesh segment {idx} is not continuous with the previous segment.")
            if end <= start:
                return tr_msg(f"Custom mesh segment {idx} has an invalid start/end range.")
            if count < 1:
                return tr_msg(f"Custom mesh segment {idx} must have at least 1 element.")
            if (top_length is None) != (bottom_length is None):
                return tr_msg(f"Custom mesh segment {idx} must fill both top length and bottom length, or leave both blank.")
            if top_length is not None and top_length <= 0.0:
                return tr_msg(f"Custom mesh segment {idx} top length must be positive.")
            if bottom_length is not None and bottom_length <= 0.0:
                return tr_msg(f"Custom mesh segment {idx} bottom length must be positive.")
            cursor = end
        return None

    def _current_mesh_type(self) -> str:
        if self.mode_length.isChecked():
            return "element_length"
        if self.mode_user.isChecked():
            return "user_define"
        return "element_number"

    def _read_segments(self) -> List[Dict]:
        segments: List[Dict] = []
        for row in range(self.custom_table.rowCount()):
            try:
                start = self._read_float(row, 0)
                end = self._read_float(row, 1)
                count = max(int(round(self._read_float(row, 2))), 0)
                top_length = self._read_optional_float(row, 3)
                bottom_length = self._read_optional_float(row, 4)
            except ValueError:
                continue
            segments.append(
                {
                    "start_m": start,
                    "end_m": end,
                    "element_count": count,
                    "top_length_m": top_length,
                    "bottom_length_m": bottom_length,
                }
            )
        return segments

    def _read_float(self, row: int, col: int) -> float:
        item = self.custom_table.item(row, col)
        return float(item.text()) if item and item.text() else 0.0

    def _read_optional_float(self, row: int, col: int) -> float | None:
        item = self.custom_table.item(row, col)
        if item is None:
            return None
        text = item.text().strip()
        if not text:
            return None
        value = float(text)
        return value if value > 0.0 else None

    def _append_segment_row(
        self,
        start: float,
        end: float,
        element_count: int,
        top_length: float | None,
        bottom_length: float | None,
    ):
        row = self.custom_table.rowCount()
        self.custom_table.insertRow(row)
        self.custom_table.setItem(row, 0, QTableWidgetItem(f"{start:.4f}"))
        self.custom_table.setItem(row, 1, QTableWidgetItem(f"{end:.4f}"))
        self.custom_table.setItem(row, 2, QTableWidgetItem(str(max(int(element_count), 1))))
        self.custom_table.setItem(row, 3, QTableWidgetItem("" if top_length is None else f"{float(top_length):.4f}"))
        self.custom_table.setItem(row, 4, QTableWidgetItem("" if bottom_length is None else f"{float(bottom_length):.4f}"))

    def _default_new_segment(self) -> Dict:
        total_length = self._current_total_length()
        if self.custom_table.rowCount() == 0:
            end = total_length if total_length > 0.0 else 1.0
            return {"start_m": 0.0, "end_m": end, "element_count": 20, "top_length_m": None, "bottom_length_m": None}

        last_end_item = self.custom_table.item(self.custom_table.rowCount() - 1, 1)
        try:
            start = float(last_end_item.text()) if last_end_item and last_end_item.text() else 0.0
        except ValueError:
            start = 0.0
        end = total_length if total_length > start else start + 1.0
        return {"start_m": start, "end_m": end, "element_count": 10, "top_length_m": None, "bottom_length_m": None}

    def _add_segment_row(self):
        new_seg = self._default_new_segment()
        self._append_segment_row(
            new_seg["start_m"],
            new_seg["end_m"],
            new_seg["element_count"],
            new_seg["top_length_m"],
            new_seg["bottom_length_m"],
        )
        self._emit_changed()

    def _delete_segment_row(self):
        row = self.custom_table.currentRow()
        if row < 0:
            row = self.custom_table.rowCount() - 1
        if row >= 0:
            self.custom_table.removeRow(row)
            self._emit_changed()

    def _current_total_length(self) -> float:
        if callable(self._total_length_provider):
            try:
                return max(float(self._total_length_provider()), 0.0)
            except Exception:
                return 0.0
        return 0.0

    def _refresh_ui(self):
        advanced = self.advanced_enabled.isChecked()
        self.advanced_box.setVisible(advanced)
        mesh_type = self._current_mesh_type()
        self.uniform_widget.setVisible(mesh_type in {"element_number", "element_length"})

        count_visible = mesh_type == "element_number"
        count_label = self.uniform_widget.layout().labelForField(self.uniform_count)
        self.uniform_count.setVisible(count_visible)
        if count_label is not None:
            count_label.setVisible(count_visible)

        length_visible = mesh_type == "element_length"
        length_label = self.uniform_widget.layout().labelForField(self.uniform_length)
        self.uniform_length.setVisible(length_visible)
        if length_label is not None:
            length_label.setVisible(length_visible)

        self.custom_widget.setVisible(mesh_type == "user_define")

        total_length = self._current_total_length()
        if total_length > 0.0:
            self.custom_note.setText(translate_text(
                "For user-defined mesh, the first start must be 0.0 m and the final end must equal "
                f"the pile length {total_length:.4f} m. Top/bottom lengths are optional and define linear grading."
            ))
        else:
            self.custom_note.setText(translate_text(
                "For user-defined mesh, fill start/end and element number. Top/bottom lengths are optional and control linear grading."
            ))

    def _on_controls_changed(self):
        if self._loading:
            return
        self._refresh_ui()
        self._emit_changed()

    def _emit_changed(self):
        if self._loading:
            return
        if callable(self._change_callback):
            try:
                self._change_callback()
            except Exception:
                pass
