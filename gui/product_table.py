from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QTableWidget,
    QTableWidgetItem,
)

from controllers.product_controller import ProductController
from models.product import Product


class ProductTable(QTableWidget):
    def __init__(
        self,
        controller: ProductController,
    ) -> None:
        super().__init__()

        self.controller = controller

        self.setColumnCount(6)

        self.setHorizontalHeaderLabels(
            [
                "Imagen",
                "Código",
                "Nombre",
                "Categoría",
                "Precio",
                "Stock",
            ],
        )

        self.load_products()

    def load_products(
        self,
        productos: list[Product] | None = None,
    ) -> None:
        if productos is None:
            productos = self.controller.get_products()

        self.clearContents()
        self.setRowCount(
            len(productos),
        )

        for fila, producto in enumerate(productos):
            image = QLabel()

            image.setAlignment(
                Qt.AlignmentFlag.AlignCenter,
            )

            if producto.image_path:
                pixmap = QPixmap(
                    producto.image_path,
                )

                if not pixmap.isNull():
                    pixmap = pixmap.scaled(
                        60,
                        60,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )

                    image.setPixmap(
                        pixmap,
                    )

            self.setCellWidget(
                fila,
                0,
                image,
            )

            item_code = QTableWidgetItem(
                producto.code,
            )

            item_code.setData(
                Qt.ItemDataRole.UserRole,
                producto.id,
            )

            self.setItem(
                fila,
                1,
                item_code,
            )

            self.setItem(
                fila,
                2,
                QTableWidgetItem(
                    producto.name,
                ),
            )

            self.setItem(
                fila,
                3,
                QTableWidgetItem(
                    producto.category,
                ),
            )

            self.setItem(
                fila,
                4,
                QTableWidgetItem(
                    str(producto.price),
                ),
            )

            self.setItem(
                fila,
                5,
                QTableWidgetItem(
                    str(producto.stock),
                ),
            )

            self.setRowHeight(
                fila,
                70,
            )

        self.resizeColumnsToContents()
