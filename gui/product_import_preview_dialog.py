from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config.runtime_paths import resolve_data_path
from models.product import Product


class ProductImportPreviewDialog(QDialog):
    """Previsualización editable con resolución de duplicados."""

    HEADERS = (
        "Imagen",
        "Código",
        "Producto",
        "Detalle",
        "Categoría",
        "Stock",
        "Stock por color",
        "Precio",
        "Precio muestra",
        "Precio ciento",
        "Precio millar",
        "Validación / catálogo actual",
    )
    DUPLICATE_ROLE = int(Qt.ItemDataRole.UserRole) + 60
    ACTION_ROLE = int(Qt.ItemDataRole.UserRole) + 61

    def __init__(
        self,
        products: list[Product],
        current_products: list[Product] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.accepted_products: list[Product] = []
        self.current_by_code = {
            str(product.code).strip().casefold(): product
            for product in list(current_products or [])
            if str(product.code).strip()
        }

        self.setWindowTitle("Previsualizar carga masiva")
        self.resize(1380, 680)

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection,
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked,
        )
        self.table.itemChanged.connect(self._preview_item_changed)
        self.table.verticalHeader().setDefaultSectionSize(156)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.summary = QLabel()
        self.summary.setWordWrap(True)

        edit_button = QPushButton("Editar seleccionado")
        edit_button.clicked.connect(self.edit_selected)
        delete_button = QPushButton("Eliminar seleccionado")
        delete_button.clicked.connect(self.delete_selected)
        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(self.reject)
        accept_button = QPushButton("Aceptar e importar")
        accept_button.clicked.connect(self.accept_import)

        actions = QHBoxLayout()
        actions.addWidget(edit_button)
        actions.addWidget(delete_button)
        actions.addStretch()
        actions.addWidget(cancel_button)
        actions.addWidget(accept_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary)
        layout.addWidget(self.table, 1)
        layout.addLayout(actions)

        self._load_rows(products)

    def _load_rows(self, products: list[Product]) -> None:
        self.table.setRowCount(0)
        for product in products:
            self._append_product(product)
        self._update_summary()

    def _append_product(self, product: Product) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        image_path = str(product.image_path or "").strip()
        image_item = QTableWidgetItem(Path(image_path).name if image_path else "—")
        image_item.setData(Qt.ItemDataRole.UserRole, image_path)
        image_item.setToolTip(image_path)
        image_item.setFlags(image_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 0, image_item)

        for column, value in (
            (1, product.code),
            (2, product.name),
            (3, product.description),
            (4, product.category),
            (5, str(product.stock)),
            (
                6,
                "\n".join(
                    f"{color}: {stock}"
                    for color, stock in product.color_stock.items()
                ),
            ),
            (7, f"{product.price:.2f}"),
            (8, f"{product.price_sample:.2f}"),
            (9, f"{product.price_hundred:.2f}"),
            (10, f"{product.price_thousand:.2f}"),
        ):
            self._set_text_item(row, column, str(value))

        self._set_image_preview(row, image_path)
        self._set_validation(row, product)

    def _set_image_preview(self, row: int, image_path: str) -> None:
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedSize(144, 144)
        label.setToolTip(image_path)

        path = resolve_data_path(image_path)
        if image_path and path.is_file():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                label.setPixmap(
                    pixmap.scaled(
                        144,
                        144,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        if label.pixmap() is None:
            label.setText("Sin vista previa")
        self.table.setCellWidget(row, 0, label)

    def _set_text_item(self, row: int, column: int, value: str) -> None:
        item = QTableWidgetItem(value)
        item.setToolTip(value)
        self.table.setItem(row, column, item)

    def _preview_item_changed(self, item: QTableWidgetItem | None) -> None:
        if item is None or item.column() != 1:
            return
        row = item.row()
        code = item.text().strip()
        self._set_validation(
            row,
            Product(code=code, name=""),
        )
        self._update_summary()

    def _set_validation(self, row: int, product: Product) -> None:
        current = self.current_by_code.get(
            str(product.code).strip().casefold()
        )
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        if current is None:
            label = QLabel("✓ NUEVO")
            label.setStyleSheet("font-weight: bold; color: #2e7d32;")
            layout.addWidget(label)
            item = self.table.item(row, 11)
            if item is None:
                item = QTableWidgetItem("NUEVO")
                self.table.setItem(row, 11, item)
            item.setData(self.DUPLICATE_ROLE, False)
            return

        label = QLabel(
            "⚠ CÓDIGO DUPLICADO\n"
            f"Actual: {current.code}\n"
            f"Producto: {current.name}\n"
            f"Categoría: {current.category or '—'}\n"
            f"Stock: {current.stock:,}\n"
            f"Precio muestra: S/ {current.price_sample:,.2f}\n"
            f"Precio ciento: S/ {current.price_hundred:,.2f}\n"
            f"Precio millar: S/ {current.price_thousand:,.2f}\n"
            f"Detalle: {current.description or '—'}"
        )
        label.setWordWrap(True)
        label.setStyleSheet(
            "font-weight: bold; color: #8a5a00; background: #fff7d6;"
            " padding: 4px;"
        )
        layout.addWidget(label)

        combo = QComboBox()
        combo.addItem("Desestimar", "dismiss")
        combo.addItem("Reemplazar", "replace")
        combo.setCurrentIndex(0)
        combo.currentIndexChanged.connect(
            lambda _index, widget=combo: self._update_duplicate_row_style(
                widget
            )
        )
        layout.addWidget(combo)

        self.table.setCellWidget(row, 11, container)
        self.table.item(row, 1).setData(self.DUPLICATE_ROLE, True)
        self._update_duplicate_row_style(combo)

    @staticmethod
    def _update_duplicate_row_style(combo: QComboBox) -> None:
        container = combo.parentWidget()
        if container is None:
            return
        replacing = combo.currentData() == "replace"
        container.setStyleSheet(
            "QWidget { background: #e7f6ea; }"
            if replacing
            else "QWidget { background: #fff7d6; }"
        )

    def _duplicate_action(self, row: int) -> str:
        widget = self.table.cellWidget(row, 11)
        if isinstance(widget, QWidget):
            combo = widget.findChild(QComboBox)
            if combo is not None:
                return str(combo.currentData() or "dismiss")
        return "new"

    def edit_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(
                self,
                "Editar",
                "Seleccione una fila para editarla. Los campos de la tabla son editables.",
            )
            return
        item = self.table.item(row, 2)
        if item is not None:
            self.table.editItem(item)

    def delete_selected(self) -> None:
        rows = sorted(
            {
                index.row()
                for index in self.table.selectionModel().selectedRows()
            },
            reverse=True,
        )
        if not rows:
            QMessageBox.information(
                self,
                "Eliminar",
                "Seleccione una o más filas para eliminarlas.",
            )
            return
        for row in rows:
            self.table.removeRow(row)
        self._update_summary()

    def _products_from_table(self) -> list[Product]:
        products: list[Product] = []
        for row in range(self.table.rowCount()):
            image_item = self.table.item(row, 0)
            code = self._text(row, 1)
            name = self._text(row, 2)
            if not name:
                continue

            if self._duplicate_action(row) == "dismiss":
                continue

            image_path = (
                str(image_item.data(Qt.ItemDataRole.UserRole) or "").strip()
                if image_item is not None
                else ""
            )
            stock = self._parse_int(self._text(row, 5))
            color_stock = self._parse_color_stock(self._text(row, 6))
            price = self._parse_float(self._text(row, 7))
            price_sample = self._parse_float(self._text(row, 8))
            price_hundred = self._parse_float(self._text(row, 9))
            price_thousand = self._parse_float(self._text(row, 10))

            gallery_images = (
                [
                    {
                        "url": "",
                        "image_path": image_path,
                        "image_hash": "",
                        "position": 1,
                        "source": "import",
                    }
                ]
                if image_path
                else []
            )

            products.append(
                Product(
                    code=code,
                    name=name,
                    description=self._text(row, 3),
                    category=self._text(row, 4),
                    price=price,
                    price_sample=price_sample,
                    price_hundred=price_hundred,
                    price_thousand=price_thousand,
                    stock=stock,
                    color_stock=color_stock,
                    image_path=image_path,
                    gallery_images=gallery_images,
                )
            )
        return products

    def _text(self, row: int, column: int) -> str:
        item = self.table.item(row, column)
        return item.text().strip() if item is not None else ""

    @staticmethod
    def _parse_float(value: str) -> float:
        text = value.strip().replace("S/", "").replace(" ", "")
        if "," in text and "." in text:
            text = text.replace(",", "")
        elif "," in text:
            text = text.replace(",", ".")
        try:
            return max(float(text), 0)
        except ValueError:
            return 0

    @classmethod
    def _parse_int(cls, value: str) -> int:
        return max(round(cls._parse_float(value)), 0)

    @classmethod
    def _parse_color_stock(cls, value: str) -> dict[str, int]:
        result: dict[str, int] = {}
        for line in value.splitlines():
            try:
                color, stock = line.rsplit(":", 1)
            except ValueError:
                continue
            color = color.strip()
            if color:
                result[color] = cls._parse_int(stock)
        return result

    def _update_summary(self) -> None:
        duplicate_count = sum(
            1
            for row in range(self.table.rowCount())
            if self.table.item(row, 1) is not None
            and bool(self.table.item(row, 1).data(self.DUPLICATE_ROLE))
        )
        count = self.table.rowCount()
        self.summary.setText(
            f"Registros: {count}. Duplicados detectados: {duplicate_count}. "
            "Los duplicados muestran el producto actual para comparar; "
            "elija Reemplazar o Desestimar antes de importar."
        )

    def accept_import(self) -> None:
        products = self._products_from_table()
        if not products:
            QMessageBox.warning(
                self,
                "Carga masiva",
                "No hay registros nuevos o marcados para reemplazo.",
            )
            return
        self.accepted_products = products
        self.accept()
