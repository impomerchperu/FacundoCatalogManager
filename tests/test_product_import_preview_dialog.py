from PySide6.QtWidgets import QApplication

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
