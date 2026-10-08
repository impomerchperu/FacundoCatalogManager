from PySide6.QtWidgets import QApplication, QPushButton

from gui.product_image_gallery_dialog import ProductImageGalleryDialog
from models.product import Product


def _qapp():
    return QApplication.instance() or QApplication([])


def test_product_image_gallery_dialog_uses_product_table_image_size():
    _qapp()
    product = Product(
        code="FB-401",
        name="Galería",
        image_path="images/one.jpg",
        gallery_images=[
            {
                "url": "",
                "image_path": "images/one.jpg",
                "position": 1,
                "source": "manual",
            },
            {
                "url": "",
                "image_path": "images/two.jpg",
                "position": 2,
                "source": "manual",
            },
        ],
        product_id=401,
    )

    dialog = ProductImageGalleryDialog(product)

    assert dialog.IMAGE_SIZE == 144
    assert dialog.selected_index == 0
    assert len(dialog.images) == 2
    buttons = [
        button.text()
        for button in dialog.findChildren(QPushButton)
    ]
    assert "Subir imágenes..." in buttons
    assert "Reemplazar seleccionada" in buttons
    assert "Hacer principal" in buttons

    dialog._select(1)
    assert dialog.selected_index == 1
    dialog.make_primary()
    assert dialog.selected_index == 0
    assert dialog.images[0]["image_path"] == "images/two.jpg"

    dialog.close()
