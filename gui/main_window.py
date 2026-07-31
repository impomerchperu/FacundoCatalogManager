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

        self.table = ProductTable()

        self.search_box = QLineEdit()

        self.search_box.setPlaceholderText("Buscar producto...")

        self.search_box.textChanged.connect(self.search_products)

        layout.addWidget(self.search_box)

        layout.addWidget(self.table)

        botones = QHBoxLayout()

        btn_new = QPushButton("Nuevo")

        btn_new.clicked.connect(self.new_product)

        btn_edit = QPushButton("Editar")

        btn_edit.clicked.connect(self.edit_product)

        btn_delete = QPushButton("Eliminar")

        btn_delete.clicked.connect(self.delete_product)

        btn_excel = QPushButton("Exportar Excel")

        btn_excel.clicked.connect(self.export_excel)

        btn_pdf = QPushButton("Exportar PDF")

        btn_pdf.clicked.connect(self.export_pdf)

        botones.addWidget(btn_new)

        botones.addWidget(btn_edit)

        botones.addWidget(btn_delete)

        botones.addWidget(btn_excel)

        botones.addWidget(btn_pdf)

        layout.addLayout(botones)

    def new_product(self):

        dialog = ProductDialog(self)

        if dialog.exec():
            self.table.load_products()

    def edit_product(self):

        row = self.table.currentRow()

        if row < 0:
            QMessageBox.warning(self, "Editar", "Seleccione un producto.")

            return

        item = self.table.item(row, 1)

        if item is None:
            return

        product_id = item.data(Qt.UserRole)

        product = self.controller.get_product_by_id(product_id)

        if product is None:
            QMessageBox.warning(self, "Error", "No se encontró el producto.")

            return

        dialog = ProductDialog(self, product)

        if dialog.exec():
            self.table.load_products()

    def delete_product(self):

        row = self.table.currentRow()

        if row < 0:
            QMessageBox.warning(self, "Eliminar", "Seleccione un producto.")

            return

        item = self.table.item(row, 1)

        if item is None:
            return

        product_id = item.data(Qt.UserRole)

        respuesta = QMessageBox.question(
            self,
            "Confirmar eliminación",
            "¿Desea eliminar este producto?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if respuesta == QMessageBox.Yes:
            self.controller.delete_product(product_id)

            self.table.load_products()

    def search_products(self, text):

        if text.strip() == "":
            self.table.load_products()

        else:
            productos = self.controller.search_products(text)

            self.table.load_products(productos)

    def export_excel(self):

        filename, _ = QFileDialog.getSaveFileName(
            self, "Guardar Excel", "catalogo.xlsx", "Excel (*.xlsx)"
        )

        if not filename:
            return

        productos = self.controller.get_products()

        ExcelExporter.export(productos, filename)

        QMessageBox.information(
            self, "Correcto", "Archivo Excel exportado correctamente."
        )

    def export_pdf(self):

        filename, _ = QFileDialog.getSaveFileName(
            self, "Guardar PDF", "catalogo.pdf", "PDF (*.pdf)"
        )

        if not filename:
            return

        productos = self.controller.get_products()

        PDFExporter.export(productos, filename)

        QMessageBox.information(
            self, "Correcto", "Catálogo PDF generado correctamente."
        )
