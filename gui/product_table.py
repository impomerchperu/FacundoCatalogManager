from PySide6.QtWidgets import (
    QTableWidget,
    QTableWidgetItem
)

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt

from services.product_service import ProductService


class ProductTable(QTableWidget):

    def __init__(self):
        super().__init__()

        self.service = ProductService()

        self.setColumnCount(6)
        self.setHorizontalHeaderLabels([
            "Imagen",
            "Código",
            "Nombre",
            "Categoría",
            "Precio",
            "Stock"
        ])

        self.load_products()

    def load_products(self, productos=None):

        if productos is None:
            productos = self.service.get_products()

        self.setRowCount(len(productos))

        for fila, producto in enumerate(productos):

            image = QLabel()
            image.setAlignment(Qt.AlignCenter)

            if producto[7]:
                pixmap = QPixmap(producto[7])

                pixmap = pixmap.scaled(
                    60,
                    60,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )

                image.setPixmap(pixmap)


            self.setCellWidget(
                fila,
                0,
                image
            )


            item_code = QTableWidgetItem(producto[1])
            item_code.setData(32, producto[0])

            self.setItem(
                fila,
                1,
                item_code
            )


            self.setItem(
                fila,
                2,
                QTableWidgetItem(producto[2])
            )


            self.setItem(
                fila,
                3,
                QTableWidgetItem(producto[3])
            )


            self.setItem(
                fila,
                4,
                QTableWidgetItem(str(producto[5]))
            )


            self.setItem(
                fila,
                5,
                QTableWidgetItem(str(producto[6]))
            )

        for fila in range(self.rowCount()):
            self.setRowHeight(fila, 70)    

        self.resizeColumnsToContents()