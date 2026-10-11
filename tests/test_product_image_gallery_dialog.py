from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from gui.product_image_gallery_dialog import ProductImageGalleryDialog
from gui.product_table import ProductImageDelegate
from models.product import Product


def _qapp():
    return QApplication.instance() or QApplication([])


def _visual_product(image_paths: list[Path]) -> Product:
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
        image_url=str(gallery[0]["url"]) if gallery else "",
        image_path=str(image_paths[0]) if image_paths else "",
        gallery_images=gallery,
        product_id=402,
    )


def _write_test_image(
    path: Path,
    width: int = 100,
    height: int = 100,
) -> None:
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.blue)
    assert pixmap.save(str(path))


def test_dialog_renders_main_image_and_thumbnails_at_200_percent(tmp_path):
    _qapp()
    landscape = tmp_path / "landscape.png"
    portrait = tmp_path / "portrait.png"
    _write_test_image(landscape, width=400, height=200)
    _write_test_image(portrait, width=100, height=400)
    dialog = ProductImageGalleryDialog(
        _visual_product([landscape, portrait]),
    )
    QApplication.processEvents()

    preview = dialog.main_image.pixmap()
    assert preview is not None
    assert preview.width() == ProductImageDelegate.MAIN_IMAGE_WIDTH * 2
    assert preview.height() == 144
    assert dialog.MAIN_IMAGE_WIDTH == ProductImageGalleryDialog.SCALE_FACTOR * (
        ProductImageDelegate.MAIN_IMAGE_WIDTH
    )
    assert dialog.THUMBNAIL_HEIGHT == ProductImageDelegate.THUMBNAIL_HEIGHT * 2
    assert len(dialog.thumbnail_labels) == 2
    assert all(
        thumbnail.height() == ProductImageDelegate.THUMBNAIL_HEIGHT * 2
        for thumbnail in dialog.thumbnail_labels
    )
    assert dialog.main_image.objectName() == "gallery_main_image"
    assert dialog.width() >= dialog.CONTENT_WIDTH + 24
    assert not dialog.findChildren(QPushButton, "gallery_next")
    dialog.close()


def test_selecting_thumbnail_swaps_it_with_the_temporary_primary(tmp_path):
    _qapp()
    landscape = tmp_path / "landscape.png"
    portrait = tmp_path / "portrait.png"
    _write_test_image(landscape, width=400, height=200)
    _write_test_image(portrait, width=100, height=400)
    product = _visual_product([landscape, portrait])
    original_gallery = [
        str(image["image_path"]) for image in product.gallery_images
    ]
    dialog = ProductImageGalleryDialog(product)

    QTest.mouseClick(dialog.thumbnail_labels[1], Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert [image["image_path"] for image in dialog.images] == [
        str(portrait),
        str(landscape),
    ]
    assert [image["image_path"] for image in product.gallery_images] == (
        original_gallery
    )
    preview = dialog.main_image.pixmap()
    assert preview is not None
    assert preview.height() > preview.width()
    assert dialog.thumbnail_start == 0
    dialog.close()


def test_thumbnail_arrows_scroll_four_visible_images(tmp_path):
    _qapp()
    paths = [tmp_path / f"image-{index}.png" for index in range(6)]
    for path in paths:
        _write_test_image(path)
    dialog = ProductImageGalleryDialog(_visual_product(paths))
    dialog.show()
    QApplication.processEvents()

    next_button = dialog.findChild(QPushButton, "gallery_next")
    previous_button = dialog.findChild(QPushButton, "gallery_previous")
    assert next_button is not None
    assert previous_button is not None
    assert len(dialog.thumbnail_labels) == 4
    assert [label.property("image_path") for label in dialog.thumbnail_labels] == [
        str(path) for path in paths[:4]
    ]

    QTest.mouseClick(next_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert dialog.thumbnail_start == 1
    assert [label.property("image_path") for label in dialog.thumbnail_labels] == [
        str(path) for path in paths[1:5]
    ]
    assert dialog.images[0]["image_path"] == str(paths[0])

    QTest.mouseClick(previous_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    assert dialog.thumbnail_start == 0
    dialog.close()


def test_gallery_view_can_start_with_the_table_temporary_order(tmp_path):
    _qapp()
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    _write_test_image(first, width=100, height=400)
    _write_test_image(second, width=400, height=100)
    product = _visual_product([first, second])
    temporary_order = [
        dict(product.gallery_images[1]),
        dict(product.gallery_images[0]),
    ]

    dialog = ProductImageGalleryDialog(
        product,
        gallery_images=temporary_order,
    )

    assert dialog.images[0]["image_path"] == str(second)
    preview = dialog.main_image.pixmap()
    assert preview is not None
    assert preview.width() > preview.height()
    dialog.close()


def test_single_image_hides_thumbnail_strip(tmp_path):
    _qapp()
    image = tmp_path / "only.png"
    _write_test_image(image, width=200, height=100)
    dialog = ProductImageGalleryDialog(_visual_product([image]))
    QApplication.processEvents()

    assert len(dialog.thumbnail_labels) == 0
    assert not dialog.thumbnail_area.isVisible()
    preview = dialog.main_image.pixmap()
    assert preview is not None
    assert preview.width() == 288
    dialog.close()
