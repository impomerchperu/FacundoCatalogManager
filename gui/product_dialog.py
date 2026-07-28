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
from utils.image_manager import ImageManager


class ProductDialog(QDialog):

    def __init__(self, parent=None, product=None):
        super().__init__(parent)

        self.product = product
        self.service = ProductService()

        if product:
            self.setWindowTitle("Editar Producto")
        else:
            self.setWindowTitle("Nuevo Producto")


        # Campos
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


        # Imagen
        self.image_path = QLineEdit()
        self.image_path.setReadOnly(True)

        self.image_preview = QLabel()
        self.image_preview.setFixedSize(180, 180)
        self.image_preview.setAlignment(Qt.AlignCenter)

        self.image_preview.setStyleSheet("""
            border: 1px solid gray;
            background: white;
        """)


        btn_image = QPushButton("Seleccionar imagen")
        btn_image.clicked.connect(self.select_image)


        # Cargar datos si es edición
        if self.product:

            self.code.setText(product.code)
            self.name.setText(product.name)
            self.category.setText(product.category)

            self.description.setText(product.description)

            self.price.setValue(product.price)
            self.stock.setValue(product.stock)

            self.image_path.setText(product.image_path)

            self.load_preview(product.image_path)


        # Formulario
        form = QFormLayout()

        form.addRow("Código:", self.code)
        form.addRow("Nombre:", self.name)
        form.addRow("Categoría:", self.category)
        form.addRow("Descripción:", self.description)
        form.addRow("Precio:", self.price)
        form.addRow("Stock:", self.stock)

        form.addRow("Imagen:", self.image_path)
        form.addRow("", btn_image)
        form.addRow("Vista previa:", self.image_preview)


        # Botones
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



    def select_image(self):

        file, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar imagen",
            "",
            "Imágenes (*.png *.jpg *.jpeg)"
        )

        if file:

            self.image_path.setText(file)

            self.load_preview(file)



    def load_preview(self, path):

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
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.image_preview.setPixmap(pixmap)



    def save_product(self):

        if not self.code.text().strip() or not self.name.text().strip():

            QMessageBox.warning(
                self,
                "Datos incompletos",
                "El código y el nombre son obligatorios"
            )

            return



        image_path = self.image_path.text()


        if image_path:

            image_path = ImageManager.save_image(
                image_path,
                self.code.text()
            )



        product = Product(

            code=self.code.text().strip(),

            name=self.name.text().strip(),

            category=self.category.text().strip(),

            description=self.description.toPlainText(),

            price=self.price.value(),

            stock=self.stock.value(),

            image_path=image_path,

            product_id=self.product.id if self.product else None
        )



        try:

            if self.product:

                self.service.update_product(product)

            else:

                self.service.create_product(product)



        except Exception as e:

            QMessageBox.critical(
                self,
                "Error",
                str(e)
            )

            return



        QMessageBox.information(
            self,
            "Correcto",
            "Producto guardado correctamente"
        )


        self.accept()