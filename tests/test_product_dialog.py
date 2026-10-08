from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractSpinBox, QApplication, QPushButton

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

    assert "Importar carga masiva..." not in buttons
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


def test_product_dialog_new_generates_code_categories_and_hides_spin_buttons():
    _qapp()

    dialog = ProductDialog()

    assert dialog.code.text().startswith("FB-")
    assert dialog.code.text() != ""
    assert dialog.category.count() >= 24
    assert dialog.price.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons
    assert dialog.price_sample.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons
    assert dialog.price_hundred.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons
    assert dialog.price_thousand.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons
    assert dialog.stock.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons

    dialog.category.set_selected_categories(["Cocina, Mesa y Hogar"])
    assert dialog.category.selected_text() == "Cocina, Mesa y Hogar"

    dialog.close()


def test_product_dialog_edit_loads_and_allows_gallery_alternatives():
    _qapp()
    product = Product(
        code="FB-101",
        name="Producto",
        image_url="https://example.test/primary.jpg",
        image_path="images/primary.jpg",
        gallery_images=[
            {
                "url": "https://example.test/primary.jpg",
                "image_path": "images/primary.jpg",
                "image_hash": "primary",
                "position": 1,
                "source": "primary",
            },
            {
                "url": "https://example.test/alternative.jpg",
                "image_path": "images/alternative.jpg",
                "image_hash": "alternative",
                "position": 2,
                "source": "gallery",
            },
        ],
        product_id=101,
    )

    dialog = ProductDialog(product=product)

    assert len(dialog.gallery_images) == 2
    assert dialog.gallery_list.count() == 2
    assert dialog.image_path.text() == "images/primary.jpg"

    dialog.gallery_images[1]["source"] = "manual"
    dialog.gallery_list.setCurrentRow(1)
    dialog.set_primary_image()

    assert dialog.gallery_images[0]["image_path"] == "images/alternative.jpg"
    assert dialog.image_path.text() == "images/alternative.jpg"

    dialog.close()

def test_product_dialog_layout_matches_product_table_image_size():
    _qapp()
    from gui.product_table import ProductTable

    dialog = ProductDialog()
    assert dialog.image_preview.width() == ProductTable.IMAGE_SIZE
    assert dialog.image_preview.height() == ProductTable.IMAGE_SIZE
    assert dialog.gallery_list.iconSize().width() == ProductTable.IMAGE_SIZE
    assert dialog.gallery_list.iconSize().height() == ProductTable.IMAGE_SIZE
    assert dialog.stock.isReadOnly() is False

    dialog.close()

def test_product_dialog_auto_sums_stock_from_colors():
    _qapp()
    dialog = ProductDialog()
    dialog.color_stock.setPlainText("Rojo: 10\nAzul: 5")
    assert dialog.stock.value() == 15
    assert dialog.stock.isReadOnly() is True
    dialog.color_stock.clear()
    assert dialog.stock.isReadOnly() is False
    dialog.close()

def test_product_dialog_does_not_offer_bulk_import():
    _qapp()
    dialog = ProductDialog()
    buttons = [
        button.text()
        for button in dialog.findChildren(QPushButton)
    ]
    assert "Importar carga masiva..." not in buttons
    assert "+ Nueva categoría" in buttons
    assert "Subir imágenes..." in buttons
    dialog.close()
