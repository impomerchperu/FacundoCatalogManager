from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from models.product import Product
from services.scraping.category_name_normalizer import split_category_names


class ExcelCategorySelectionDialog(QDialog):
    """Permite elegir las categorías que se incluirán en el Excel."""

    def __init__(
        self,
        categories: Iterable[str],
        products: Iterable[Product],
        parent: QWidget | None = None,
        *,
        initial_selected_categories: Iterable[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Seleccionar categorías para Excel")
        self.setMinimumWidth(420)
        self.resize(480, 520)

        self._products = list(products)
        self._categories = self._normalize_categories(categories)
        initial = {
            str(value).strip().casefold()
            for value in (initial_selected_categories or [])
            if str(value).strip()
        }

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Seleccione las categorías que desea descargar en Excel.")
        title.setWordWrap(True)
        layout.addWidget(title)

        self.category_list = QListWidget()
        self.category_list.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection,
        )
        self.category_list.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        for category in self._categories:
            item = QListWidgetItem(category)
            item.setFlags(
                item.flags() | Qt.ItemFlag.ItemIsUserCheckable,
            )
            is_checked = not initial or category.casefold() in initial
            item.setCheckState(
                Qt.CheckState.Checked
                if is_checked
                else Qt.CheckState.Unchecked,
            )
            self.category_list.addItem(item)

        self.category_list.itemChanged.connect(self._update_summary)
        layout.addWidget(self.category_list, 1)

        selection_actions = QHBoxLayout()
        selection_actions.setContentsMargins(0, 0, 0, 0)
        selection_actions.setSpacing(6)

        select_all_button = QPushButton("Seleccionar todas")
        select_all_button.clicked.connect(self.select_all_categories)
        selection_actions.addWidget(select_all_button)

        clear_button = QPushButton("Ninguna")
        clear_button.clicked.connect(self.clear_categories)
        selection_actions.addWidget(clear_button)
        selection_actions.addStretch()
        layout.addLayout(selection_actions)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        dialog_actions = QHBoxLayout()
        dialog_actions.setContentsMargins(0, 0, 0, 0)
        dialog_actions.addStretch()

        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(self.reject)
        dialog_actions.addWidget(cancel_button)

        self.export_button = QPushButton("Exportar")
        self.export_button.setDefault(True)
        self.export_button.clicked.connect(self.accept)
        dialog_actions.addWidget(self.export_button)

        layout.addLayout(dialog_actions)
        self._update_summary()

    def selected_categories(self) -> set[str]:
        """Devuelve exactamente las categorías marcadas por el usuario."""
        selected: set[str] = set()
        for index in range(self.category_list.count()):
            item = self.category_list.item(index)
            if item is None:
                continue
            if item.checkState() == Qt.CheckState.Checked:
                selected.add(item.text())
        return selected

    @classmethod
    def filter_products(
        cls,
        products: Iterable[Product],
        categories: Iterable[str],
    ) -> list[Product]:
        """Devuelve productos pertenecientes a cualquiera de las categorías."""
        selected = {
            str(category).strip().casefold()
            for category in categories
            if str(category).strip()
        }
        if not selected:
            return []

        result: list[Product] = []
        for product in products:
            product_categories = {
                category.casefold()
                for category in split_category_names(
                    getattr(product, "category", ""),
                )
                if category
            }
            if selected.intersection(product_categories):
                result.append(product)
        return result

    def select_all_categories(self) -> None:
        for index in range(self.category_list.count()):
            item = self.category_list.item(index)
            if item is not None:
                item.setCheckState(Qt.CheckState.Checked)

    def clear_categories(self) -> None:
        for index in range(self.category_list.count()):
            item = self.category_list.item(index)
            if item is not None:
                item.setCheckState(Qt.CheckState.Unchecked)

    def _update_summary(
        self,
        _item: QListWidgetItem | None = None,
        _column: int = 0,
    ) -> None:
        selected = self.selected_categories()
        selected_products = self.filter_products(
            self._products,
            selected,
        )
        self.summary_label.setText(
            f"Categorías seleccionadas: {len(selected)} de "
            f"{len(self._categories)} · Productos a exportar: "
            f"{len(selected_products)}"
        )
        self.export_button.setEnabled(bool(selected))
        self.export_button.setToolTip(
            ""
            if selected
            else "Seleccione al menos una categoría.",
        )

    @staticmethod
    def _normalize_categories(categories: Iterable[str]) -> list[str]:
        unique: dict[str, str] = {}
        for value in categories:
            category = str(value).strip()
            if not category:
                continue
            unique.setdefault(category.casefold(), category)
        return sorted(unique.values(), key=str.casefold)
