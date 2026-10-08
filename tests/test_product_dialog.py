from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton

from gui.product_dialog import ProductDialog
from models.product import Product


def _qapp():
    return QApplication.instance() or QApplication([])


def test_product_dialog_new_has_import_action_and_no_resize_controls():
    _qapp()

    dialog = ProductDialog()
    buttons = [
        button.text()
        for button in dialog.findChildren(QPushButton)
    ]

    assert "Importar CSV / Excel" in buttons
    assert not dialog.windowFlags() & Qt.WindowType.WindowMinimizeButtonHint
    assert not dialog.windowFlags() & Qt.WindowType.WindowMaximizeButtonHint

    dialog.close()


def test_product_dialog_edit_preserves_advanced_product_fields():
    _qapp()
    product = Product(
        code="FB-100",
        name="Producto",
        price=6,
        price_sample=6,
        price_hundred=23.8,
        price_thousand=90,
        stock=15,
        color_stock={"Rojo": 10},
        image_url="https://example.test/image.jpg",
        image_path="images/fb100.jpg",
        image_hash="hash",
        gallery_images=[
            {
                "url": "https://example.test/image.jpg",
                "image_path": "images/fb100.jpg",
                "image_hash": "hash",
                "position": 1,
                "source": "primary",
            }
        ],
        content_hash="content",
        product_id=100,
    )

    dialog = ProductDialog(product=product)

    assert dialog.price.value() == 6
    assert dialog.price_sample.value() == 6
    assert dialog.price_hundred.value() == 23.8
    assert dialog.price_thousand.value() == 90
    assert dialog.stock.value() == 15
    assert dialog.color_stock.toPlainText() == "Rojo: 10"
    assert dialog.image_path.text() == "images/fb100.jpg"

    dialog.close()
