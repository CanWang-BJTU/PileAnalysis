# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Callable, List, Optional

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QPushButton,
    QStyledItemDelegate,
    QTableWidget,
    QWidget,
)


class EnterKeyDelegate(QStyledItemDelegate):
    """Navigate editable table cells on Enter / Return key.

    *editable_cols* defines the ordered list of column indices that
    should participate in navigation.  When the last column is reached
    the cursor moves to the first editable column of the next row.  If
    *add_row_fn* is provided it is called when Enter is pressed in the
    last cell of the last row to auto-append a new row.
    """

    def __init__(
        self,
        table: QTableWidget,
        editable_cols: List[int],
        add_row_fn: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._table = table
        self._editable_cols = editable_cols
        self._add_row_fn = add_row_fn

    # ---- intercept Enter inside editor widgets ----
    def eventFilter(self, editor, event):  # noqa: N802
        if event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.commitData.emit(editor)
                self.closeEditor.emit(editor)
                self._advance_cell()
                return True
        return super().eventFilter(editor, event)

    def _advance_cell(self):
        table = self._table
        row = table.currentRow()
        col = table.currentColumn()
        if row < 0 or col < 0:
            return
        try:
            cur_idx = self._editable_cols.index(col)
        except ValueError:
            cur_idx = -1

        if cur_idx < len(self._editable_cols) - 1:
            next_col = self._editable_cols[cur_idx + 1]
            table.setCurrentCell(row, next_col)
            table.editItem(table.item(row, next_col))
        else:
            next_row = row + 1
            if next_row >= table.rowCount():
                if self._add_row_fn is not None:
                    self._add_row_fn()
                else:
                    return
            next_row = min(next_row, table.rowCount() - 1)
            if next_row < table.rowCount():
                next_col = self._editable_cols[0]
                table.setCurrentCell(next_row, next_col)
                table.editItem(table.item(next_row, next_col))


def install_enter_navigation(
    table: QTableWidget,
    editable_cols: List[int],
    add_row_fn: Optional[Callable[[], None]] = None,
) -> EnterKeyDelegate:
    """Convenience: create, install, and return an *EnterKeyDelegate*."""
    delegate = EnterKeyDelegate(table, editable_cols, add_row_fn, parent=table)
    table.setItemDelegate(delegate)
    return delegate


def configure_table_interaction(table: QTableWidget, *, select_rows: bool):
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setSelectionBehavior(
        QAbstractItemView.SelectionBehavior.SelectRows
        if select_rows
        else QAbstractItemView.SelectionBehavior.SelectItems
    )
    table.setEditTriggers(
        QAbstractItemView.EditTrigger.DoubleClicked
        | QAbstractItemView.EditTrigger.EditKeyPressed
        | QAbstractItemView.EditTrigger.AnyKeyPressed
    )
    table.setTabKeyNavigation(False)
    table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)


def soften_button_focus(root: QWidget):
    for button in root.findChildren(QPushButton):
        button.setAutoDefault(False)
        button.setDefault(False)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
