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
    assert len(dialog.thumbnail_labels) == 2
    assert all(
        thumbnail.height() == dialog.THUMBNAIL_HEIGHT
        for thumbnail in dialog.thumbnail_labels
    )
    assert all(
        thumbnail.width() == dialog.THUMBNAIL_WIDTH
        for thumbnail in dialog.thumbnail_labels
    )
    assert dialog.thumbnail_labels[0].property("active") is True
    assert dialog.thumbnail_labels[1].property("active") is False
    assert "border: 1px solid #1675e8" in (
        dialog.thumbnail_labels[0].styleSheet()
    )
    assert "border: 1px solid #cbd5e1" in (
        dialog.thumbnail_labels[1].styleSheet()
    )
    assert dialog.main_image.objectName() == "gallery_main_image"
    assert dialog.width() >= dialog.CONTENT_WIDTH + 24
    assert not dialog.findChildren(QPushButton, "gallery_next")
    dialog.close()


def test_selecting_thumbnail_preserves_fixed_positions_and_highlights_primary(tmp_path):
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
    ] == original_gallery
    assert [label.property("active") for label in dialog.thumbnail_labels] == [
        True,
        False,
    ]

    QTest.mouseClick(dialog.thumbnail_labels[1], Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert dialog.active_index == 1
    assert [image["image_path"] for image in dialog.images] == original_gallery
    assert [
        label.property("image_path") for label in dialog.thumbnail_labels
    ] == original_gallery
    assert [label.property("active") for label in dialog.thumbnail_labels] == [
        False,
        True,
    ]
    assert "border: 1px solid #1675e8" in (
        dialog.thumbnail_labels[1].styleSheet()
    )
    assert "border: 1px solid #cbd5e1" in (
        dialog.thumbnail_labels[0].styleSheet()
    )
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
    ] == original_gallery
    assert [label.property("active") for label in dialog.thumbnail_labels] == [
        True,
        False,
    ]
    assert [image["image_path"] for image in product.gallery_images] == (
        original_gallery
    )
    dialog.close()


def test_popup_arrow_keys_select_adjacent_thumbnails(tmp_path):
    _qapp()
    paths = [tmp_path / f"arrows-{index}.png" for index in range(4)]
    for index, path in enumerate(paths):
        _write_test_image(path, width=100 + index * 10, height=80)
    dialog = ProductImageGalleryDialog(_visual_product(paths))

    QTest.keyClick(dialog, Qt.Key.Key_Right)
    assert dialog.active_index == 1
    assert [label.property("active") for label in dialog.thumbnail_labels] == [
        False,
        True,
        False,
        False,
    ]

    QTest.keyClick(dialog, Qt.Key.Key_Left)
    assert dialog.active_index == 0
    QTest.keyClick(dialog, Qt.Key.Key_Left)
    assert dialog.active_index == 0

    QTest.keyClick(dialog, Qt.Key.Key_Right)
    QTest.keyClick(dialog, Qt.Key.Key_Right)
    QTest.keyClick(dialog, Qt.Key.Key_Right)
    assert dialog.active_index == 3
    QTest.keyClick(dialog, Qt.Key.Key_Right)
    assert dialog.active_index == 3

    QTest.keyClick(dialog, Qt.Key.Key_Left)
    assert dialog.active_index == 2
    assert [label.property("active") for label in dialog.thumbnail_labels] == [
        False,
        False,
        True,
        False,
    ]
    dialog.close()


def test_four_image_gallery_keeps_order_and_highlights_primary_in_place(tmp_path):
    _qapp()
    paths = [tmp_path / f"selection-{index}.png" for index in range(4)]
    for index, path in enumerate(paths):
        _write_test_image(path, width=120 + index * 10, height=80)
    product = _visual_product(paths)
    dialog = ProductImageGalleryDialog(product)
    original_paths = [str(path) for path in paths]

    assert [
        label.property("image_path") for label in dialog.thumbnail_labels
    ] == original_paths

    QTest.mouseClick(dialog.thumbnail_labels[2], Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    assert dialog.active_index == 2
    assert [image["image_path"] for image in dialog.images] == original_paths
    assert [
        label.property("image_path") for label in dialog.thumbnail_labels
    ] == original_paths
    assert [label.property("active") for label in dialog.thumbnail_labels] == [
        False,
        False,
        True,
        False,
    ]

    # Selecting the first thumbnail changes only the main preview and border.
    QTest.mouseClick(dialog.thumbnail_labels[0], Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    assert dialog.active_index == 0
    assert [
        label.property("image_path") for label in dialog.thumbnail_labels
    ] == original_paths
    assert [label.property("active") for label in dialog.thumbnail_labels] == [
        True,
        False,
        False,
        False,
    ]
    dialog.close()


def test_dialog_expands_to_show_all_thumbnails_without_navigation_buttons(tmp_path):
    _qapp()
    paths = [tmp_path / f"image-{index}.png" for index in range(6)]
    for path in paths:
        _write_test_image(path)
    dialog = ProductImageGalleryDialog(_visual_product(paths))
    dialog.show()
    QApplication.processEvents()

    assert len(dialog.thumbnail_labels) == len(paths)
    assert [
        label.property("image_path") for label in dialog.thumbnail_labels
    ] == [str(path) for path in paths]
    assert not dialog.findChildren(QPushButton, "gallery_next")
    assert not dialog.findChildren(QPushButton, "gallery_previous")

    expected_row_width = (
        len(paths) * dialog.THUMBNAIL_WIDTH
        + (len(paths) - 1) * dialog.THUMBNAIL_GAP
    )
    assert dialog.thumbnail_area.width() == expected_row_width
    assert dialog.main_image_area.width() == expected_row_width
    assert dialog.width() >= expected_row_width + 24
    assert all(
        label.width() == dialog.THUMBNAIL_WIDTH
        and label.height() == dialog.THUMBNAIL_HEIGHT
        for label in dialog.thumbnail_labels
    )
    fixed_slot_geometry = [
        (label.x(), label.width(), label.height())
        for label in dialog.thumbnail_labels
    ]

    QTest.mouseClick(dialog.thumbnail_labels[4], Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    assert dialog.active_index == 4
    assert [
        label.property("image_path") for label in dialog.thumbnail_labels
    ] == [str(path) for path in paths]
    assert [label.property("active") for label in dialog.thumbnail_labels] == [
        False,
        False,
        False,
        False,
        True,
        False,
    ]
    assert [
        (label.x(), label.width(), label.height())
        for label in dialog.thumbnail_labels
    ] == fixed_slot_geometry
    dialog.close()


def test_gallery_dialog_opens_with_the_selected_table_primary(tmp_path):
    _qapp()
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    _write_test_image(first, width=100, height=400)
    _write_test_image(second, width=400, height=100)
    product = _visual_product([first, second])
    original_paths = [str(first), str(second)]

    dialog = ProductImageGalleryDialog(product, active_index=1)

    assert [image["image_path"] for image in dialog.images] == original_paths
    assert dialog.active_index == 1
    assert [
        label.property("image_path") for label in dialog.thumbnail_labels
    ] == original_paths
    assert [label.property("active") for label in dialog.thumbnail_labels] == [
        False,
        True,
    ]
    assert "border: 1px solid #1675e8" in (
        dialog.thumbnail_labels[1].styleSheet()
    )
    assert "border: 1px solid #cbd5e1" in (
        dialog.thumbnail_labels[0].styleSheet()
    )
    preview = dialog.main_image.pixmap()
    assert preview is not None
    assert preview.width() > preview.height()
    dialog.close()


def test_single_image_gallery_keeps_primary_thumbnail_visible(tmp_path):
    _qapp()
    image = tmp_path / "only.png"
    _write_test_image(image, width=200, height=100)
    dialog = ProductImageGalleryDialog(_visual_product([image]))
    QApplication.processEvents()

    assert len(dialog.thumbnail_labels) == 1
    assert not dialog.thumbnail_area.isHidden()
    assert dialog.thumbnail_labels[0].property("image_path") == str(image)
    assert dialog.thumbnail_labels[0].property("active") is True
    preview = dialog.main_image.pixmap()
    assert preview is not None
    assert preview.width() == ProductImageGalleryDialog.MAIN_IMAGE_WIDTH
    dialog.close()
