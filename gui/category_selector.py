from __future__ import annotations

from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QComboBox

from services.product_search import normalize_search_text


class CategorySelector(QComboBox):
    """Selector multi-categoría editable con filtrado incremental."""

    CATEGORY_ROLE = int(Qt.ItemDataRole.UserRole) + 40
    NEW_CATEGORY_ROLE = int(Qt.ItemDataRole.UserRole) + 41

    category_created = Signal(str)

    def __init__(self, parent=None, *, editable_text: bool = True) -> None:
        super().__init__(parent)
        self._editable_text = editable_text
        self._model = QStandardItemModel(self)
        self.setModel(self._model)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._line_edit = self.lineEdit()
        if self._line_edit is not None:
            self._line_edit.setReadOnly(not editable_text)
            self._line_edit.textEdited.connect(self._filter_categories)
            self._line_edit.returnPressed.connect(self._accept_typed_category)
        self._model.itemChanged.connect(self._refresh_selected_text)
        self.view().pressed.connect(self._toggle_index)

    def set_categories(self, categories: list[str]) -> None:
        selected = set(self.selected_categories())
        self._model.clear()
        for category in sorted(
            {str(value).strip() for value in categories if str(value).strip()},
            key=str.casefold,
        ):
            item = QStandardItem(category)
            item.setData(category, self.CATEGORY_ROLE)
            item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(
                Qt.CheckState.Checked
                if category.casefold() in {value.casefold() for value in selected}
                else Qt.CheckState.Unchecked
            )
            self._model.appendRow(item)
        self._refresh_selected_text()

    def add_category(self, category: str, *, select: bool = True) -> bool:
        value = str(category or "").strip()
        if not value:
            return False
        existing = self._find_category(value)
        if existing is not None:
            if select:
                existing.setCheckState(Qt.CheckState.Checked)
            self._refresh_selected_text()
            return False

        item = QStandardItem(value)
        item.setData(value, self.CATEGORY_ROLE)
        item.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsUserCheckable
        )
        item.setCheckState(
            Qt.CheckState.Checked if select else Qt.CheckState.Unchecked
        )
        self._model.appendRow(item)
        self._refresh_selected_text()
        self.category_created.emit(value)
        return True

    def filter_popup_now(self) -> None:
        """Open the category dropdown for interactive filtering."""
        self._filter_categories(
            self._line_edit.text() if self._line_edit is not None else ""
        )
        self.showPopup()

    def add_typed_category(self) -> bool:
        """Add the current text only when it is not the current selection."""
        text = self._line_edit.text().strip() if self._line_edit else ""
        if not text or text.casefold() == self.selected_text().casefold():
            return False
        return self.add_category(text, select=True)

    def set_selected_categories(self, categories: list[str]) -> None:
        wanted = {str(value).casefold() for value in categories if str(value).strip()}
        self._model.blockSignals(True)
        try:
            for row in range(self._model.rowCount()):
                item = self._model.item(row)
                if item is None:
                    continue
                item.setCheckState(
                    Qt.CheckState.Checked
                    if item.text().casefold() in wanted
                    else Qt.CheckState.Unchecked
                )
        finally:
            self._model.blockSignals(False)
        self._refresh_selected_text()

    def selected_categories(self) -> list[str]:
        values: list[str] = []
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            if (
                item is not None
                and item.checkState() == Qt.CheckState.Checked
                and not bool(item.data(self.NEW_CATEGORY_ROLE))
            ):
                values.append(item.text())
        return values

    def selected_text(self) -> str:
        return ", ".join(self.selected_categories())

    def _find_category(self, category: str) -> QStandardItem | None:
        key = category.casefold()
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            if item is not None and item.text().casefold() == key:
                return item
        return None

    def _toggle_index(self, index: QModelIndex) -> None:
        item = self._model.itemFromIndex(index)
        if item is None:
            return
        if bool(item.data(self.NEW_CATEGORY_ROLE)):
            return
        item.setCheckState(
            Qt.CheckState.Unchecked
            if item.checkState() == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )
        self._refresh_selected_text()

    def _filter_categories(self, text: str) -> None:
        query = normalize_search_text(text)
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            if item is None:
                continue
            matches = not query or query in normalize_search_text(item.text())
            self.view().setRowHidden(row, not matches)

    def _accept_typed_category(self) -> None:
        if not self._editable_text:
            return
        text = self._line_edit.text().strip() if self._line_edit else ""
        if not text:
            self._refresh_selected_text()
            return
        matching = [
            item
            for row in range(self._model.rowCount())
            if (item := self._model.item(row)) is not None
            and normalize_search_text(text)
            in normalize_search_text(item.text())
        ]
        if not matching:
            self.add_category(text, select=True)
        else:
            exact = self._find_category(text)
            if exact is not None:
                exact.setCheckState(Qt.CheckState.Checked)
        self._refresh_selected_text()

    def _refresh_selected_text(self, _item: QStandardItem | None = None) -> None:
        if self._line_edit is not None:
            self._line_edit.blockSignals(True)
            self._line_edit.setText(self.selected_text())
            self._line_edit.blockSignals(False)
        for row in range(self._model.rowCount()):
            self.view().setRowHidden(row, False)

