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
