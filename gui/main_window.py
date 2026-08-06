from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from controllers.product_controller import ProductController
from exporters.excel_exporter import ExcelExporter
from exporters.pdf_exporter import PDFExporter
from gui.product_dialog import ProductDialog
from gui.product_table import ProductTable


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.controller = ProductController()

        self.setWindowTitle("Facundo Catalog Manager")
        self.resize(900, 600)

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        self.table = ProductTable(
            self.controller,
        )

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Buscar producto...")
        self.search_box.textChanged.connect(self.search_products)

        layout.addWidget(self.search_box)
        layout.addWidget(self.table)

        botones = QHBoxLayout()

        buttons = [
            ("Nuevo", self.new_product),
            ("Editar", self.edit_product),
            ("Eliminar", self.delete_product),
            ("Exportar Excel", self.export_excel),
            ("Exportar PDF", self.export_pdf),
        ]

        for text, callback in buttons:
            button = QPushButton(text)
            button.clicked.connect(callback)
            botones.addWidget(button)

        layout.addLayout(botones)

    def new_product(self):

        dialog = ProductDialog(self)

        if dialog.exec():
            self.table.load_products()

    def edit_product(self):

        row = self.table.currentRow()

        if row < 0:
            QMessageBox.warning(
                self,
                "Editar",
                "Seleccione un producto.",
            )
            return

        item = self.table.item(row, 1)

        if item is None:
            return

        product_id = item.data(Qt.ItemDataRole.UserRole)

        product = self.controller.get_product_by_id(product_id)

        if product is None:
            QMessageBox.warning(
                self,
                "Error",
                "No se encontró el producto.",
            )
            return

        dialog = ProductDialog(self, product)

        if dialog.exec():
            self.table.load_products()

    def delete_product(self):

        row = self.table.currentRow()

        if row < 0:
            QMessageBox.warning(
                self,
                "Eliminar",
                "Seleccione un producto.",
            )
            return

        item = self.table.item(row, 1)

        if item is None:
            return

        product_id = item.data(Qt.ItemDataRole.UserRole)

        respuesta = QMessageBox.question(
            self,
            "Confirmar eliminación",
            "¿Desea eliminar este producto?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if respuesta == QMessageBox.StandardButton.Yes:
            self.controller.delete_product(product_id)
            self.table.load_products()

    def search_products(self, text):

        if not text.strip():
            self.table.load_products()
            return

        productos = self.controller.search_products(text)

        self.table.load_products(productos)

    def export_excel(self):

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar Excel",
            "catalogo.xlsx",
            "Excel (*.xlsx)",
        )

        if not filename:
            return

        productos = self.controller.get_products()

        ExcelExporter.export(productos, filename)

        QMessageBox.information(
            self,
            "Correcto",
            "Archivo Excel exportado correctamente.",
        )

    def export_pdf(self):

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar PDF",
            "catalogo.pdf",
            "PDF (*.pdf)",
        )

        if not filename:
            return

        productos = self.controller.get_products()

        PDFExporter.export(productos, filename)

        QMessageBox.information(
            self,
            "Correcto",
            "Catálogo PDF generado correctamente.",
        )
