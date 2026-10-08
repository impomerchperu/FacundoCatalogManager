from PySide6.QtWidgets import QApplication, QFileDialog, QPushButton

from gui.product_image_gallery_dialog import ProductImageGalleryDialog
from models.product import Product


def _qapp():
    return QApplication.instance() or QApplication([])


class _Service:
    def __init__(self) -> None:
        self.saved_product = None

    def update_product(self, product) -> None:
        self.saved_product = product


def _product() -> Product:
    return Product(
        code="FB-401",
        name="Galería",
        image_url="https://example.test/one.jpg",
        image_path="images/one.jpg",
        image_hash="hash-one",
        gallery_images=[
            {
                "url": "https://example.test/one.jpg",
                "image_path": "images/one.jpg",
                "image_hash": "hash-one",
                "position": 1,
                "source": "primary",
            },
            {
                "url": "https://example.test/two.jpg",
                "image_path": "images/two.jpg",
                "image_hash": "hash-two",
                "position": 2,
                "source": "gallery",
            },
        ],
        product_id=401,
    )


def test_product_image_gallery_dialog_uses_product_table_image_size():
    _qapp()
    dialog = ProductImageGalleryDialog(_product(), service=_Service())

    assert dialog.IMAGE_SIZE == 144
    assert dialog.selected_index == 0
    assert len(dialog.images) == 2
    assert dialog.layout().count() == 2
    assert dialog.save_button.text() == "Guardar"
    assert [
        button.text()
        for button in dialog.findChildren(QPushButton)
        if button.text()
    ] == ["Guardar"]

    dialog.close()


def test_clicking_current_image_replaces_it_and_moves_old_primary_to_alternatives(
    monkeypatch,
    tmp_path,
):
    _qapp()
    service = _Service()
    dialog = ProductImageGalleryDialog(_product(), service=service)
    replacement = tmp_path / "replacement.jpg"
    replacement.write_bytes(b"placeholder")

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args: (str(replacement), "Imágenes"),
    )
    current_button = dialog.canvas.findChildren(QPushButton)[0]
    current_button.click()

    assert [image["image_path"] for image in dialog.images] == [
        str(replacement),
        "images/one.jpg",
        "images/two.jpg",
    ]
    assert dialog.images[0]["source"] == "manual"
    assert dialog.images[1]["image_path"] == "images/one.jpg"

    dialog.close()


def test_clicking_alternative_swaps_it_with_current_image():
    _qapp()
    dialog = ProductImageGalleryDialog(_product(), service=_Service())

    dialog.exchange_with_primary(1)

    assert [image["image_path"] for image in dialog.images] == [
        "images/two.jpg",
        "images/one.jpg",
    ]
    assert dialog.images[0]["position"] == 1
    assert dialog.images[1]["position"] == 2

    dialog.close()


def test_guardar_persists_the_current_ordered_gallery():
    _qapp()
    service = _Service()
    product = _product()
    dialog = ProductImageGalleryDialog(product, service=service)
    dialog.exchange_with_primary(1)

    dialog.save()

    assert service.saved_product is not None
    assert service.saved_product.image_path == "images/two.jpg"
    assert [
        image["image_path"]
        for image in service.saved_product.gallery_images
    ] == ["images/two.jpg", "images/one.jpg"]
    assert dialog.result() == dialog.DialogCode.Accepted

    dialog.close()
