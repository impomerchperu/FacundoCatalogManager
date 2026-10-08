from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from models.product import Product
from services.product_import import ProductImportService
from services.product_service import ProductService


class ProductDialog(QDialog):
    """Editor y alta manual de productos."""

    def __init__(
        self,
        parent=None,
        product: Product | None = None,
    ):
        super().__init__(parent)
        self.product = product
        self.service = ProductService()

        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowCloseButtonHint,
        )
        self.setWindowTitle(
            "Editar Producto" if self.product else "Nuevo Producto",
        )
        self.resize(520, 620)

        self.code = QLineEdit()
        self.name = QLineEdit()
        self.category = QLineEdit()

        self.description = QTextEdit()
        self.description.setFixedHeight(80)

        self.price = self._create_price_spinbox()
        self.price_sample = self._create_price_spinbox()
        self.price_hundred = self._create_price_spinbox()
        self.price_thousand = self._create_price_spinbox()

        self.stock = QSpinBox()
        self.stock.setMaximum(9999999)

        self.color_stock = QTextEdit()
        self.color_stock.setFixedHeight(70)
        self.color_stock.setPlaceholderText("Rojo: 10\nAzul: 25")

        self.image_path = QLineEdit()
        self.image_path.setReadOnly(True)

        self.image_preview = QLabel()
        self.image_preview.setFixedSize(180, 180)
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setStyleSheet(
            "border: 1px solid gray; background: white;"
        )

        self.load_product_data()

        form = QFormLayout()
        form.addRow("Código:", self.code)
        form.addRow("Nombre:", self.name)
        form.addRow("Categoría:", self.category)
        form.addRow("Descripción:", self.description)
        form.addRow("Precio:", self.price)
        form.addRow("Precio muestra:", self.price_sample)
        form.addRow("Precio ciento:", self.price_hundred)
        form.addRow("Precio millar:", self.price_thousand)
        form.addRow("Stock:", self.stock)
        form.addRow("Stock por color:", self.color_stock)
        form.addRow("Imagen:", self.image_path)

        image_buttons = QHBoxLayout()
        btn_image = QPushButton("Seleccionar imagen")
        btn_image.clicked.connect(self.select_image)
        image_buttons.addWidget(btn_image)

        if self.product is None:
            btn_import = QPushButton("Importar CSV / Excel")
            btn_import.clicked.connect(self.import_product)
            image_buttons.addWidget(btn_import)

        form.addRow("", image_buttons)
        form.addRow("Vista previa:", self.image_preview)

        btn_save = QPushButton("Guardar")
        btn_save.clicked.connect(self.save_product)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(btn_save)
        buttons.addWidget(btn_cancel)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)

    @staticmethod
    def _create_price_spinbox() -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setMaximum(9999999)
        widget.setDecimals(2)
        widget.setPrefix("S/ ")
        return widget

    def load_product_data(self) -> None:
        if self.product is None:
            return

        self.code.setText(self.product.code)
        self.code.setReadOnly(True)
        self.name.setText(self.product.name)
        self.category.setText(self.product.category)
        self.description.setPlainText(self.product.description)
        self.price.setValue(self.product.price)
        self.price_sample.setValue(self.product.price_sample)
        self.price_hundred.setValue(self.product.price_hundred)
        self.price_thousand.setValue(self.product.price_thousand)
        self.stock.setValue(self.product.stock)
        self.color_stock.setPlainText(
            "\n".join(
                f"{color}: {stock}"
                for color, stock in self.product.color_stock.items()
            ),
        )
        self.image_path.setText(self.product.image_path)
        self.load_preview(self.product.image_path)

    def select_image(self) -> None:
        file, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar imagen",
            "",
            "Imágenes (*.png *.jpg *.jpeg *.webp)",
        )
        if file:
            self.image_path.setText(file)
            self.load_preview(file)

    def import_product(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Importar producto",
            "",
            "Archivos compatibles (*.csv *.xlsx);;CSV (*.csv);;Excel (*.xlsx)",
        )
        if not filename:
            return

        try:
            product = ProductImportService.import_first_product(filename)
        except (OSError, ValueError) as error:
            QMessageBox.warning(
                self,
                "Importar producto",
                str(error),
            )
            return

        self.code.setText(product.code)
        self.name.setText(product.name)
        self.category.setText(product.category)
        self.description.setPlainText(product.description)
        self.price.setValue(product.price)
        self.price_sample.setValue(product.price_sample)
        self.price_hundred.setValue(product.price_hundred)
        self.price_thousand.setValue(product.price_thousand)
        self.stock.setValue(product.stock)
        self.color_stock.setPlainText(
            "\n".join(
                f"{color}: {stock}"
                for color, stock in product.color_stock.items()
            ),
        )
        self.image_path.setText(product.image_path)
        self.load_preview(product.image_path)

    def load_preview(self, path: str) -> None:
        if not path:
            self.image_preview.clear()
            return

        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.image_preview.clear()
            return

        pixmap = pixmap.scaled(
            170,
            170,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_preview.setPixmap(pixmap)

    def _color_stock_values(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for line in self.color_stock.toPlainText().splitlines():
            try:
                color, stock = line.rsplit(":", 1)
            except ValueError:
                continue
            color = color.strip()
            if not color:
                continue
            try:
                result[color] = max(int(stock.strip().replace(",", "")), 0)
            except ValueError:
                continue
        return result

    def save_product(self) -> None:
        code = self.code.text().strip()
        name = self.name.text().strip()
        category = self.category.text().strip()
        description = self.description.toPlainText().strip()

        if not code or not name:
            QMessageBox.warning(
                self,
                "Datos incompletos",
                "El código y el nombre son obligatorios.",
            )
            return

        image_path = self.image_path.text().strip().replace("\\", "/")

        if self.product is None:
            product = Product(
                code=code,
                name=name,
                category=category,
                description=description,
                price=self.price.value(),
                price_sample=self.price_sample.value(),
                price_hundred=self.price_hundred.value(),
                price_thousand=self.price_thousand.value(),
                stock=self.stock.value(),
                color_stock=self._color_stock_values(),
                image_path=image_path,
            )
        else:
            product = Product(
                code=self.product.code,
                name=name,
                category=category,
                description=description,
                price=self.price.value(),
                price_sample=self.price_sample.value(),
                price_hundred=self.price_hundred.value(),
                price_thousand=self.price_thousand.value(),
                stock=self.stock.value(),
                color_stock=self._color_stock_values(),
                image_url=self.product.image_url,
                image_path=image_path,
                image_hash=self.product.image_hash,
                gallery_images=list(self.product.gallery_images),
                content_hash=self.product.content_hash,
                product_id=self.product.id,
            )

        try:
            if self.product:
                self.service.update_product(product)
                message = "Producto actualizado correctamente."
            else:
                self.service.create_product(product)
                message = "Producto creado correctamente."
        except sqlite3.IntegrityError:
            QMessageBox.critical(
                self,
                "Error",
                "Ya existe un producto con ese código.",
            )
            return
        except sqlite3.Error as error:
            QMessageBox.critical(
                self,
                "Error de base de datos",
                str(error),
            )
            return
        except ValueError as error:
            QMessageBox.critical(
                self,
                "Error de validación",
                str(error),
            )
            return

        QMessageBox.information(self, "Correcto", message)
        self.accept()
