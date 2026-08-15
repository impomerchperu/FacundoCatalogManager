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
from services.product_service import ProductService


class ProductDialog(QDialog):
    def __init__(
        self,
        parent=None,
        product: Product | None = None,
    ):
        super().__init__(parent)

        self.product = product
        self.service = ProductService()

        self.setWindowTitle("Editar Producto" if self.product else "Nuevo Producto")

        self.code = QLineEdit()
        self.name = QLineEdit()
        self.category = QLineEdit()

        self.description = QTextEdit()
        self.description.setFixedHeight(80)

        self.price = QDoubleSpinBox()
        self.price.setMaximum(999999)
        self.price.setDecimals(2)
        self.price.setPrefix("S/ ")

        self.stock = QSpinBox()
        self.stock.setMaximum(999999)

        self.image_path = QLineEdit()
        self.image_path.setReadOnly(True)

        self.image_preview = QLabel()
        self.image_preview.setFixedSize(
            180,
            180,
        )

        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.image_preview.setStyleSheet(
            """
            border: 1px solid gray;
            background: white;
            """
        )

        btn_image = QPushButton("Seleccionar imagen")

        btn_image.clicked.connect(self.select_image)

        self.load_product_data()

        form = QFormLayout()

        form.addRow(
            "Código:",
            self.code,
        )

        form.addRow(
            "Nombre:",
            self.name,
        )

        form.addRow(
            "Categoría:",
            self.category,
        )

        form.addRow(
            "Descripción:",
            self.description,
        )

        form.addRow(
            "Precio:",
            self.price,
        )

        form.addRow(
            "Stock:",
            self.stock,
        )

        form.addRow(
            "Imagen:",
            self.image_path,
        )

        form.addRow(
            "",
            btn_image,
        )

        form.addRow(
            "Vista previa:",
            self.image_preview,
        )

        btn_save = QPushButton("Guardar")

        btn_cancel = QPushButton("Cancelar")

        btn_save.clicked.connect(self.save_product)

        btn_cancel.clicked.connect(self.reject)

        buttons = QHBoxLayout()

        buttons.addWidget(btn_save)
        buttons.addWidget(btn_cancel)

        layout = QVBoxLayout()

        layout.addLayout(form)
        layout.addLayout(buttons)

        self.setLayout(layout)

    def load_product_data(self):

        if self.product is None:
            return

        self.code.setText(self.product.code)

        self.code.setReadOnly(True)

        self.name.setText(self.product.name)

        self.category.setText(self.product.category)

        self.description.setPlainText(self.product.description)

        self.price.setValue(self.product.price)

        self.stock.setValue(self.product.stock)

        self.image_path.setText(self.product.image_path)

        self.load_preview(self.product.image_path)

    def select_image(self):

        file, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar imagen",
            "",
            "Imágenes (*.png *.jpg *.jpeg)",
        )

        if file:
            self.image_path.setText(file)

            self.load_preview(file)

    def load_preview(
        self,
        path: str,
    ):

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

    def save_product(self):

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

        image_path = self.image_path.text().strip()

        if image_path:
            image_path = image_path.replace("\\", "/")

        product = Product(
            code=code,
            name=name,
            category=category,
            description=description,
            price=self.price.value(),
            stock=self.stock.value(),
            image_path=image_path,
            product_id=(self.product.id if self.product else None),
        )

        try:
            if self.product:
                self.service.update_product(product)

                mensaje = "Producto actualizado correctamente."

            else:
                self.service.create_product(product)

                mensaje = "Producto creado correctamente."

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

        QMessageBox.information(
            self,
            "Correcto",
            mensaje,
        )

        self.accept()
