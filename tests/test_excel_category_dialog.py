from PySide6.QtCore import Qt

from gui.excel_category_dialog import ExcelCategorySelectionDialog
from models.product import Product


def test_filter_products_by_selected_excel_categories():
    products = [
        Product(
            code="A-001",
            name="Oficina",
            category="Artículos de Oficina",
        ),
        Product(
            code="A-002",
            name="Hogar",
            category="Cocina, Mesa y Hogar",
        ),
        Product(
            code="A-003",
            name="Mixto",
            category="Artículos de Oficina, Jarros Mug",
        ),
    ]

    result = ExcelCategorySelectionDialog.filter_products(
        products,
        {"Jarros Mug"},
    )

    assert [product.code for product in result] == ["A-003"]


def test_filter_products_respects_stock_only_filter():
    products = [
        Product(
            code="A-010",
            name="Con stock",
            category="Antiestres",
            stock=4,
        ),
        Product(
            code="A-011",
            name="Sin stock",
            category="Antiestres",
            stock=0,
        ),
        Product(
            code="A-012",
            name="Otra categoría",
            category="Escritorios",
            stock=8,
        ),
    ]

    result = ExcelCategorySelectionDialog.filter_products(
        products,
        {"Antiestres"},
        stock_only=True,
    )

    assert [product.code for product in result] == ["A-010"]


def test_filter_products_returns_empty_when_no_category_is_selected():
    product = Product(
        code="A-004",
        name="Producto",
        category="Jarros Mug",
    )

    assert ExcelCategorySelectionDialog.filter_products(
        [product],
        set(),
    ) == []


def test_filter_products_accepts_any_selected_category():
    products = [
        Product(
            code="A-005",
            name="Oficina",
            category="Artículos de Oficina",
        ),
        Product(
            code="A-006",
            name="Jarros",
            category="Jarros Mug",
        ),
    ]

    result = ExcelCategorySelectionDialog.filter_products(
        products,
        {"Artículos de Oficina", "Jarros Mug"},
    )

    assert [product.code for product in result] == ["A-005", "A-006"]


def test_dialog_initial_checks_match_filtered_categories():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    products = [
        Product(code="A-020", name="Antiestres", category="Antiestres", stock=5),
        Product(code="A-021", name="Escritorio", category="Escritorios", stock=7),
        Product(code="A-022", name="Sin stock", category="Bolsas / Mochilas", stock=0),
    ]
    dialog = ExcelCategorySelectionDialog(
        {"Antiestres", "Escritorios", "Bolsas / Mochilas"},
        products,
        initial_selected_categories={"Antiestres", "Escritorios"},
        stock_only=True,
    )

    checked = {
        dialog.category_list.item(index).text()
        for index in range(dialog.category_list.count())
        if dialog.category_list.item(index).checkState()
        == Qt.CheckState.Checked
    }

    assert checked == {"Antiestres", "Escritorios"}
    assert "Solo Stock Disponible: ACTIVADO" in (
        dialog.layout().itemAt(1).widget().text()
    )
    dialog.deleteLater()
    app.processEvents()
