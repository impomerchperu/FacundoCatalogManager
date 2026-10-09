from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QPushButton

from gui.product_image_gallery_dialog import ProductImageGalleryDialog
from models.product import Product
from services.product_service import ProductService


def _qapp():
    return QApplication.instance() or QApplication([])


class _Service(ProductService):
    def __init__(self) -> None:
        self.saved_product: Product | None = None

    def update_product(self, product: Product) -> Product:
        self.saved_product = product
        return product


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
    assert dialog.layout().count() == 3
    assert dialog.save_button.text() == "Guardar"
    assert dialog.summary.text().splitlines() == [
        "Clic en imagen actual para elegir imagen local",
        "Clic en imagen alternativa para reemplazar actual",
    ]
    assert dialog.width() >= (
        dialog.summary.minimumWidth()
        + dialog.footer_layout.spacing()
        + dialog.save_button.sizeHint().width()
        + dialog.layout().contentsMargins().left()
        + dialog.layout().contentsMargins().right()
    )
    assert dialog.footer_layout.indexOf(dialog.save_button) > (
        dialog.footer_layout.indexOf(dialog.summary)
    )
    action_labels = {
        "Subir imágenes...",
        "Reemplazar seleccionada",
        "Hacer principal",
        "Quitar",
        "Cancelar",
    }
    assert "Guardar" in [
        button.text() for button in dialog.findChildren(QPushButton)
    ]
    assert not action_labels.intersection(
        button.text() for button in dialog.findChildren(QPushButton)
    )

    dialog.close()


def test_clicking_current_image_replaces_it_and_moves_old_primary_to_alternatives(
    monkeypatch,
    tmp_path,
):
    _qapp()
    service = _Service()
    dialog = ProductImageGalleryDialog(_product(), service=service)
    replacement = tmp_path / "replacement.jpg"
    _write_test_image(replacement)

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args: (str(replacement), "Imágenes"),
    )
    current_image = dialog.canvas.findChildren(
        QLabel,
        "gallery_image_choice",
    )[0]
    QTest.mouseClick(current_image, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert [image["image_path"] for image in dialog.images] == [
        str(replacement),
        "images/one.jpg",
        "images/two.jpg",
    ]
    assert dialog.images[0]["source"] == "manual"
    assert dialog.images[1]["image_path"] == "images/one.jpg"
    current_preview = dialog.canvas.findChildren(
        QLabel,
        "gallery_image_choice",
    )[0]
    assert current_preview.pixmap() is not None
    assert not current_preview.pixmap().isNull()

    dialog.close()


def test_clicking_alternative_swaps_it_with_current_image():
    _qapp()
    dialog = ProductImageGalleryDialog(_product(), service=_Service())

    alternatives = dialog.canvas.findChildren(
        QLabel,
        "gallery_image_choice",
    )
    QTest.mouseClick(alternatives[1], Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert [image["image_path"] for image in dialog.images] == [
        "images/two.jpg",
        "images/one.jpg",
    ]
    assert dialog.images[0]["position"] == 1
    assert dialog.images[1]["position"] == 2

    dialog.close()



def _visual_product(image_paths) -> Product:
    gallery = [
        {
            "url": f"https://example.test/{index}.png",
            "image_path": str(path),
            "image_hash": f"hash-{index}",
            "position": index,
            "source": "primary" if index == 1 else "gallery",
        }
        for index, path in enumerate(image_paths, start=1)
    ]
    return Product(
        code="FB-402",
        name="Galería visible",
        image_url=str(gallery[0]["url"]),
        image_path=str(image_paths[0]),
        gallery_images=gallery,
        product_id=402,
    )


def _write_test_image(path) -> None:
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.blue)
    assert pixmap.save(str(path))


def test_gallery_cards_keep_their_previews_after_local_replacement(tmp_path):
    _qapp()
    original_paths = [tmp_path / "one.png", tmp_path / "two.png"]
    for path in original_paths:
        _write_test_image(path)
    replacement = tmp_path / "replacement.png"
    _write_test_image(replacement)

    dialog = ProductImageGalleryDialog(
        _visual_product(original_paths),
        service=_Service(),
    )
    dialog._replace_primary_path(str(replacement))
    QApplication.processEvents()

    QApplication.processEvents()
    labels = dialog.canvas.findChildren(QLabel, "gallery_image_choice")
    assert len(labels) == 3
    assert all(
        label.pixmap() is not None and not label.pixmap().isNull()
        for label in labels
    )
    assert dialog.images[0]["image_path"] == str(replacement)

    dialog.close()


def test_gallery_cards_keep_their_previews_after_alternative_swap(tmp_path):
    _qapp()
    paths = [tmp_path / "one.png", tmp_path / "two.png"]
    for path in paths:
        _write_test_image(path)
    dialog = ProductImageGalleryDialog(
        _visual_product(paths),
        service=_Service(),
    )

    dialog.exchange_with_primary(1)
    QApplication.processEvents()

    QApplication.processEvents()
    labels = dialog.canvas.findChildren(QLabel, "gallery_image_choice")
    assert len(labels) == 2
    assert all(
        label.pixmap() is not None and not label.pixmap().isNull()
        for label in labels
    )
    assert Path(str(dialog.images[0]["image_path"])) == paths[1]

    dialog.close()


def test_gallery_with_more_than_five_images_scrolls_horizontally(tmp_path):
    _qapp()
    paths = [tmp_path / f"image-{index}.png" for index in range(6)]
    for path in paths:
        _write_test_image(path)
    dialog = ProductImageGalleryDialog(
        _visual_product(paths),
        service=_Service(),
    )
    dialog.show()
    QApplication.processEvents()

    scrollbar = dialog.gallery_scroll.horizontalScrollBar()
    assert scrollbar.maximum() > 0
    assert dialog.width() < 900
    assert dialog.canvas.width() > dialog.gallery_scroll.viewport().width()
    assert dialog.minimumWidth() >= (
        dialog.summary.minimumWidth()
        + dialog.footer_layout.spacing()
        + dialog.save_button.sizeHint().width()
        + dialog.layout().contentsMargins().left()
        + dialog.layout().contentsMargins().right()
    )

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
