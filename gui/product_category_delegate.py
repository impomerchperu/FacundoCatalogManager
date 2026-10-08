from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtWidgets import QStyledItemDelegate, QWidget

from gui.category_selector import CategorySelector
from services.scraping.category_name_normalizer import split_category_names


class ProductCategoryDelegate(QStyledItemDelegate):
    """Editor desplegable multi-categoría para una celda del catálogo."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.categories: list[str] = []

    def set_categories(self, categories: list[str]) -> None:
        self.categories = sorted(
            {str(value).strip() for value in categories if str(value).strip()},
            key=str.casefold,
        )

    def createEditor(
        self,
        parent: QWidget,
        option,
        index,
    ) -> CategorySelector:
        del option
        editor = CategorySelector(parent, editable_text=True)
        values = list(self.categories)
        current = str(
            index.data(Qt.ItemDataRole.UserRole + 50)
            or index.data(Qt.ItemDataRole.DisplayRole)
            or ""
        )
        values.extend(split_category_names(current))
        editor.set_categories(values)
        editor.set_selected_categories(split_category_names(current))
        return editor

    def setEditorData(self, editor: QWidget, index) -> None:
        if not isinstance(editor, CategorySelector):
            return
        current = str(
            index.data(Qt.ItemDataRole.UserRole + 50)
            or index.data(Qt.ItemDataRole.DisplayRole)
            or ""
        )
        editor.set_selected_categories(split_category_names(current))

    def setModelData(
        self,
        editor: QWidget,
        model,
        index,
    ) -> None:
        if not isinstance(editor, CategorySelector):
            return
        typed = editor.lineEdit().text().strip() if editor.lineEdit() else ""
        selected = editor.selected_text()
        if typed and typed.casefold() != selected.casefold():
            editor.add_category(typed, select=True)
            selected = editor.selected_text()
        model.setData(
            index,
            selected,
            Qt.ItemDataRole.EditRole,
        )

    def updateEditorGeometry(
        self,
        editor: QWidget,
        option,
        index,
    ) -> None:
        del index
        editor.setGeometry(
            QRect(
                option.rect.left(),
                option.rect.top(),
                max(option.rect.width(), 260),
                max(option.rect.height(), 32),
            )
        )
