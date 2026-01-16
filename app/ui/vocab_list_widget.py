# app/ui/vocab_list_widget.py
from __future__ import annotations

from typing import Optional

from PySide6 import QtWidgets, QtCore

from app.modules.vocab_store import get_user_vocab


class VocabListWidget(QtWidgets.QWidget):
    """
    Simple UI to show the current user's saved vocabulary.
    - Double-click a row to see the full definition in a popup.
    """

    def __init__(self, user_id: Optional[str], parent=None) -> None:
        super().__init__(parent)
        self.user_id = user_id

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.info_label = QtWidgets.QLabel()
        self.info_label.setStyleSheet("color:#34a0a4; font-size:12px;")

        self.table = QtWidgets.QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Word", "Definition"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeToContents
        )
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        # 👇 NEW: double-click to open full definition
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(self.refresh_btn)

        layout.addWidget(self.info_label)
        layout.addWidget(self.table, 1)
        layout.addLayout(btn_row)

        self.refresh()

    @QtCore.Slot()
    def refresh(self) -> None:
        if not self.user_id:
            self.info_label.setText("Not logged in — vocabulary will be stored as 'anonymous'.")
            data = get_user_vocab(None)
        else:
            self.info_label.setText("Your saved vocabulary words:")
            data = get_user_vocab(self.user_id)

        # data is { word: { "definition": str, "examples": [...] } }
        items = sorted(data.items(), key=lambda x: x[0])
        self.table.setRowCount(len(items))

        for row, (word, info) in enumerate(items):
            definition = info.get("definition", "")

            w_item = QtWidgets.QTableWidgetItem(word)
            d_item = QtWidgets.QTableWidgetItem(definition)

            # optional: make first column a little bolder
            font = w_item.font()
            font.setBold(True)
            w_item.setFont(font)

            self.table.setItem(row, 0, w_item)
            self.table.setItem(row, 1, d_item)

        if not items:
            self.info_label.setText(self.info_label.text() + " (no words saved yet)")

    @QtCore.Slot(int, int)
    def _on_cell_double_clicked(self, row: int, column: int) -> None:
        """
        When the user double-clicks a row, show the full definition in a dialog.
        """
        word_item = self.table.item(row, 0)
        def_item = self.table.item(row, 1)
        if not word_item or not def_item:
            return

        word = word_item.text()
        definition = def_item.text()

        dlg = QtWidgets.QMessageBox(self)
        dlg.setWindowTitle(f"Word: {word}")
        dlg.setText(word)
        dlg.setInformativeText(definition)
        dlg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        dlg.exec()