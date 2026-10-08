from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from config.runtime_paths import resolve_data_path
from models.product import Product


class ProductImportPreviewDialog(QDialog):
    """Vista previa editable de una carga masiva antes de importarla."""

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
    )

    def __init__(
        self,
        products: list[Product],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.accepted_products: list[Product] = []

        self.setWindowTitle("Previsualizar carga masiva")
        self.resize(1120, 620)

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
        self.table.verticalHeader().setDefaultSectionSize(72)
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

        self._set_text_item(row, 1, product.code)
        self._set_text_item(row, 2, product.name)
        self._set_text_item(row, 3, product.description)
        self._set_text_item(row, 4, product.category)
        self._set_text_item(row, 5, str(product.stock))
        self._set_text_item(
            row,
            6,
            "\n".join(
                f"{color}: {stock}"
                for color, stock in product.color_stock.items()
            ),
        )
        self._set_text_item(row, 7, f"{product.price:.2f}")
        self._set_text_item(row, 8, f"{product.price_sample:.2f}")
        self._set_text_item(row, 9, f"{product.price_hundred:.2f}")
        self._set_text_item(row, 10, f"{product.price_thousand:.2f}")

        self._set_image_preview(row, image_path)

    def _set_image_preview(self, row: int, image_path: str) -> None:
        path = resolve_data_path(image_path)
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedSize(68, 68)
        label.setToolTip(image_path)
        if image_path and path.is_file():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                label.setPixmap(
                    pixmap.scaled(
                        64,
                        64,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            else:
                label.setText("Sin vista previa")
        else:
            label.setText("Sin vista previa")
        self.table.setCellWidget(row, 0, label)

        item = self.table.item(row, 0)
        if item is None:
            item = QTableWidgetItem(Path(image_path).name if image_path else "—")
            self.table.setItem(row, 0, item)
        item.setData(Qt.ItemDataRole.UserRole, image_path)
        item.setToolTip(image_path)

    def _set_text_item(self, row: int, column: int, value: str) -> None:
        item = QTableWidgetItem(value)
        item.setToolTip(value)
        self.table.setItem(row, column, item)

    def edit_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(
                self,
                "Editar",
                "Seleccione una fila para editarla. Los campos de la tabla son editables.",
            )
            return
        self.table.editItem(self.table.item(row, 2))

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
        count = self.table.rowCount()
        self.summary.setText(
            f"Registros en previsualización: {count}. "
            "Puede editar directamente las celdas, quitar filas o aceptar la carga."
        )

    def accept_import(self) -> None:
        products = self._products_from_table()
        if not products:
            QMessageBox.warning(
                self,
                "Carga masiva",
                "No hay registros válidos para importar.",
            )
            return
        self.accepted_products = products
        self.accept()

