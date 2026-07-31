from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QTableWidget,
    QTableWidgetItem,
)

from controllers.product_controller import ProductController


class ProductTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.controller = ProductController()

        self.setColumnCount(6)

        self.setHorizontalHeaderLabels(
            [
                "Imagen",
                "Código",
                "Nombre",
                "Categoría",
                "Precio",
                "Stock",
            ]
        )

        self.load_products()

    def load_products(self, productos=None):

        if productos is None:
            productos = self.controller.get_products()

        self.setRowCount(len(productos))

        for fila, producto in enumerate(productos):
            # -------------------
            # Imagen
            # -------------------

            image = QLabel()

            image.setAlignment(Qt.AlignCenter)

            if producto.image_path:
                pixmap = QPixmap(producto.image_path)

                if not pixmap.isNull():
                    pixmap = pixmap.scaled(
                        60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )

                    image.setPixmap(pixmap)

            self.setCellWidget(fila, 0, image)

            # -------------------
            # Código
            # -------------------

            item_code = QTableWidgetItem(producto.code)

            item_code.setData(Qt.UserRole, producto.product_id)

            self.setItem(fila, 1, item_code)

            # -------------------
            # Nombre
            # -------------------

            self.setItem(fila, 2, QTableWidgetItem(producto.name))

            # -------------------
            # Categoría
            # -------------------

            self.setItem(fila, 3, QTableWidgetItem(producto.category))

            # -------------------
            # Precio
            # -------------------

            self.setItem(fila, 4, QTableWidgetItem(str(producto.price)))

            # -------------------
            # Stock
            # -------------------

            self.setItem(fila, 5, QTableWidgetItem(str(producto.stock)))

        for fila in range(self.rowCount()):
            self.setRowHeight(fila, 70)

        self.resizeColumnsToContents()
