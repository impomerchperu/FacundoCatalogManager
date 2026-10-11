from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

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


def test_dialog_images_use_130_percent_of_the_previous_scale(tmp_path):
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
    assert preview.width() == dialog.MAIN_IMAGE_WIDTH
    assert preview.width() == round(
        ProductImageDelegate.MAIN_IMAGE_WIDTH * 2 * 1.3
    )
    assert preview.height() == round(preview.width() / 2)
    assert round(
        ProductImageGalleryDialog.SCALE_FACTOR
        * ProductImageDelegate.MAIN_IMAGE_WIDTH
    ) == dialog.MAIN_IMAGE_WIDTH
    assert round(
        ProductImageDelegate.THUMBNAIL_HEIGHT * 2 * 1.3
    ) == dialog.THUMBNAIL_HEIGHT
    assert len(dialog.thumbnail_labels) == 1
    assert all(
        thumbnail.height() == dialog.THUMBNAIL_HEIGHT
        for thumbnail in dialog.thumbnail_labels
    )
    assert dialog.main_image.objectName() == "gallery_main_image"
    assert dialog.width() >= dialog.CONTENT_WIDTH + 24
    assert not dialog.findChildren(QPushButton, "gallery_next")
    dialog.close()


def test_selecting_thumbnail_moves_old_primary_first_and_restores_order(tmp_path):
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

    assert [
        label.property("image_path") for label in dialog.thumbnail_labels
    ] == [str(portrait)]

    QTest.mouseClick(dialog.thumbnail_labels[0], Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert dialog.active_index == 1
    assert [image["image_path"] for image in dialog.images] == original_gallery
    assert [
        label.property("image_path") for label in dialog.thumbnail_labels
    ] == [str(landscape)]
    preview = dialog.main_image.pixmap()
    assert preview is not None
    assert preview.height() > preview.width()
    assert dialog.thumbnail_start == 0

    QTest.mouseClick(dialog.thumbnail_labels[0], Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert dialog.active_index == 0
    assert [image["image_path"] for image in dialog.images] == original_gallery
    assert [
        label.property("image_path") for label in dialog.thumbnail_labels
    ] == [str(portrait)]
    assert [image["image_path"] for image in product.gallery_images] == (
        original_gallery
    )
    dialog.close()


def test_four_image_gallery_restores_thumbnail_order_after_switching_primary(tmp_path):
    _qapp()
    paths = [tmp_path / f"selection-{index}.png" for index in range(4)]
    for index, path in enumerate(paths):
        _write_test_image(path, width=120 + index * 10, height=80)
    product = _visual_product(paths)
    dialog = ProductImageGalleryDialog(product)
    original_paths = [str(path) for path in paths]

    assert [
        label.property("image_path") for label in dialog.thumbnail_labels
    ] == original_paths[1:]

    # Select the original third image. The original primary becomes first,
    # while the remaining alternatives keep their relative order.
    QTest.mouseClick(dialog.thumbnail_labels[1], Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    assert dialog.active_index == 2
    assert [image["image_path"] for image in dialog.images] == original_paths
    assert [
        label.property("image_path") for label in dialog.thumbnail_labels
    ] == [original_paths[0], original_paths[1], original_paths[3]]

    # Selecting the former primary restores the original thumbnail sequence.
    QTest.mouseClick(dialog.thumbnail_labels[0], Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    assert dialog.active_index == 0
    assert [
        label.property("image_path") for label in dialog.thumbnail_labels
    ] == original_paths[1:]
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
        str(path) for path in paths[1:5]
    ]

    QTest.mouseClick(next_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert dialog.thumbnail_start == 1
    assert [label.property("image_path") for label in dialog.thumbnail_labels] == [
        str(path) for path in paths[2:6]
    ]
    assert dialog.images[0]["image_path"] == str(paths[0])
    assert dialog.active_index == 0

    previous_button = dialog.findChild(QPushButton, "gallery_previous")
    assert previous_button is not None
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
    assert dialog.thumbnail_area.isHidden()
    preview = dialog.main_image.pixmap()
    assert preview is not None
    assert preview.width() == ProductImageGalleryDialog.MAIN_IMAGE_WIDTH
    dialog.close()
