from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
    QLineEdit
)

from gui.product_table import ProductTable
from gui.product_dialog import ProductDialog
from models.product import Product


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Facundo Catalog Manager")

        self.resize(900, 600)

        central = QWidget()

        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        self.table = ProductTable()

        self.search_box = QLineEdit()

        self.search_box.setPlaceholderText(
            "Buscar producto..."
        )

        self.search_box.textChanged.connect(
            self.search_products
        )

        layout.addWidget(self.search_box)

        layout.addWidget(self.table)

        botones = QHBoxLayout()

        btn_new = QPushButton("Nuevo")
        btn_new.clicked.connect(self.new_product)

        btn_edit = QPushButton("Editar")
        btn_edit.clicked.connect(self.edit_product)

        btn_delete = QPushButton("Eliminar")
        btn_delete.clicked.connect(self.delete_product)

        botones.addWidget(btn_new)
        botones.addWidget(btn_edit)
        botones.addWidget(btn_delete)

        layout.addLayout(botones)


    def new_product(self):

        dialog = ProductDialog(self)

        if dialog.exec():

            self.table.load_products()


    def edit_product(self):

        row = self.table.currentRow()

        if row < 0:
            return


        product_id = self.table.item(row, 1).data(32)


        products = self.table.service.get_products()

        selected = None

        for p in products:

            if p[0] == product_id:
                selected = p
                break


        if selected:

            product = Product(
                code=selected[1],
                name=selected[2],
                category=selected[3],
                description=selected[4],
                price=selected[5],
                stock=selected[6],
                image_path=selected[7],
                product_id=selected[0]
            )


            dialog = ProductDialog(self, product)


            if dialog.exec():

                self.table.load_products()


    def delete_product(self):

        row = self.table.currentRow()

        if row < 0:
            return


        product_id = self.table.item(row, 1).data(32)


        respuesta = QMessageBox.question(
            self,
            "Confirmar eliminación",
            "¿Desea eliminar este producto?",
            QMessageBox.Yes | QMessageBox.No
        )


        if respuesta == QMessageBox.Yes:

            self.table.service.delete_product(product_id)

            self.table.load_products()


    def search_products(self, text):

        if text.strip() == "":

            self.table.load_products()

        else:

            productos = self.table.service.search_products(text)

            self.table.load_products(productos)        