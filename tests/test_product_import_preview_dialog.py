from PySide6.QtWidgets import QApplication, QComboBox, QLabel

from gui.product_import_preview_dialog import ProductImportPreviewDialog
from models.product import Product


def _qapp():
    return QApplication.instance() or QApplication([])


def test_bulk_import_preview_allows_edit_and_remove():
    _qapp()
    products = [
        Product(
            code="FB-201",
            name="Producto 1",
            category="Artículos de Oficina",
            price=6,
            price_sample=6,
            price_hundred=20,
            price_thousand=70,
            stock=4,
            color_stock={"Rojo": 4},
        ),
        Product(
            code="FB-202",
            name="Producto 2",
            category="Cocina, Mesa y Hogar",
            price=7,
            price_sample=7,
            price_hundred=21,
            price_thousand=72,
            stock=5,
        ),
    ]

    dialog = ProductImportPreviewDialog(products)
    assert dialog.table.rowCount() == 2

    dialog.table.item(0, 2).setText("Producto editado")
    assert dialog.table.item(0, 2).text() == "Producto editado"

    dialog.table.selectRow(1)
    dialog.delete_selected()
    assert dialog.table.rowCount() == 1

    dialog.accept_import()
    assert dialog.result() == dialog.DialogCode.Accepted
    assert len(dialog.accepted_products) == 1
    assert dialog.accepted_products[0].name == "Producto editado"

    dialog.close()

def test_bulk_import_preview_marks_existing_code_with_current_product():
    _qapp()
    imported = Product(
        code="FB-301",
        name="Importado",
        category="Artículos de Oficina",
        price=9,
        price_sample=9,
        price_hundred=30,
        price_thousand=90,
        stock=8,
    )
    current = Product(
        code="FB-301",
        name="Actual en catálogo",
        category="Cocina, Mesa y Hogar",
        price=5,
        price_sample=5,
        stock=4,
    )

    dialog = ProductImportPreviewDialog(
        [imported],
        current_products=[current],
    )

    assert dialog.table.rowCount() == 1
    widget = dialog.table.cellWidget(0, 11)
    assert widget is not None
    combo = widget.findChild(QComboBox)
    assert combo is not None
    assert combo.currentData() == "dismiss"
    label = widget.findChild(QLabel)
    assert label is not None
    assert "Actual en catálogo" in label.text()

    combo.setCurrentIndex(1)
    dialog.accept_import()

    assert len(dialog.accepted_products) == 1
    assert dialog.accepted_products[0].code == "FB-301"
    dialog.close()
