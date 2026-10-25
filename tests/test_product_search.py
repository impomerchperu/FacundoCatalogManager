from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QToolButton

from gui.main_window import MainWindow, SearchLineEdit
from models.product import Product
from services.product_search import (
    normalize_search_text,
    product_matches_search,
    product_search_priority,
)


def _qapp():
    return QApplication.instance() or QApplication([])


def test_normalize_search_text_ignores_accents_case_and_punctuation():
    assert normalize_search_text("BÁSket, anti-estrés / rojo!") == (
        "basket antiestres rojo"
    )


def test_product_search_matches_partial_text_across_product_fields():
    product = Product(
        code="FB-100",
        name="Básket infantil",
        description="Cesta anti-estrés",
        category="Artículos / Recreación",
    )

    assert product_matches_search(product, "basket")
    assert product_matches_search(product, "antiestres")
    assert product_matches_search(product, "articulos recreacion")
    assert product_matches_search(product, "BÁSKET!")
    assert product_matches_search(product, "FB-100")
    assert product_matches_search(product, "basket antiestres")
    assert not product_matches_search(product, "basket verde")


def test_product_search_supports_synonyms_without_guessing_spelling():
    mochila = Product(code="FB-101", name="Mochila promocional")
    abridor = Product(
        code="FB-102",
        name="Abridor de botellas",
        description="Abridores para cocina",
    )

    assert product_matches_search(mochila, "mochila")
    assert not product_matches_search(mochila, "mochlia")
    assert not product_matches_search(mochila, "promocionla")
    assert product_matches_search(mochila, "morral")
    assert product_matches_search(abridor, "abridor")
    assert product_matches_search(abridor, "destapadores")

    destapador = Product(code="FB-103", name="Destapador profesional")
    assert product_matches_search(destapador, "abridor")

    bottle = Product(
        code="FB-104",
        name="Botella deportiva",
        color_stock={"Rojo": 3},
    )
    assert product_matches_search(bottle, "tomatodo")
    assert product_matches_search(bottle, "toma todo")
    assert product_matches_search(bottle, "toma todo rojo")


def test_product_search_includes_stock_colors_and_quantities():
    product = Product(
        code="FB-987",
        name="Producto",
        stock=15,
        color_stock={"Rojo": 10, "Azul": 5},
    )

    assert product_matches_search(product, "rojo")
    assert product_matches_search(product, "azul")
    assert product_matches_search(product, "10")
    assert not product_matches_search(product, "verde")


def test_product_search_includes_price_values():
    product = Product(
        code="FB-1600",
        name="Bolso promocional",
        category="Personales",
        stock=12,
        price_sample=7.5,
        price_hundred=70.0,
        color_stock={"Rojo": 12},
    )

    assert product_matches_search(product, "FB-1600")
    assert product_matches_search(product, "12")
    assert product_matches_search(product, "7.5")
    assert product_matches_search(product, "70")
    assert not product_matches_search(product, "99")


def test_search_with_symbols_filters_by_literal_symbol_instead_of_showing_all():
    hyphenated = Product(code="FB-200", name="Bolso")
    plain = Product(code="FB200", name="Bolso")

    assert product_matches_search(hyphenated, "-")
    assert not product_matches_search(plain, "-")
    assert product_matches_search(Product(code="FB-201", name="Bolso #1"), "#")
    assert not product_matches_search(Product(code="FB-202", name="Bolso"), "#")


def test_main_window_uses_search_with_synonyms_and_no_typo_correction():
    product = Product(
        code="FB-105",
        name="Mochila",
        description="Destapadores y abridores",
    )

    assert MainWindow.product_matches_search(product, "mochila")
    assert not MainWindow.product_matches_search(product, "mochlia")
    assert MainWindow.product_matches_search(product, "destapadores")
    assert MainWindow.product_matches_search(product, "morral")


class _VisibleProductsTable:
    def __init__(self):
        self.visible_products = []
        self.search_text = ""

    def show_only_products(self, products):
        self.visible_products = list(products)

    def set_search_text(self, text):
        self.search_text = text


def test_search_box_highlights_broom_button_only_when_text_exists():
    _qapp()
    field = SearchLineEdit()
    field.resize(320, 38)
    field.show()
    QApplication.processEvents()

    button = field.findChild(QToolButton, "search_clear_button")
    assert button is field.clear_button
    assert button.isVisible()
    assert button.width() >= 26
    assert not button.icon().isNull()
    assert button.toolTip() == "Limpiar búsqueda"
    assert button.property("hasText") is False

    field.setText("mochila")
    QApplication.processEvents()
    assert button.isVisible()
    assert button.property("hasText") is True

    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    assert field.text() == ""
    QApplication.processEvents()
    assert button.isVisible()
    assert not button.icon().isNull()
    assert button.property("hasText") is False
    field.deleteLater()


def test_search_box_filters_immediately_and_clearing_restores_products():
    _qapp()
    app = MainWindow.__new__(MainWindow)
    app.search_box = QLineEdit()
    app.all_products = [
        Product(code="FB-100", name="Mochila"),
        Product(code="XY200", name="Bolso"),
        Product(code="PP#300", name="Otro producto"),
    ]
    app.selected_categories = set()
    app.stock_only = False
    app.table = _VisibleProductsTable()
    app.product_counter = QLabel()

    app.search_box.textChanged.connect(app.search_products)

    app.search_box.setText("F")
    assert [product.code for product in app.table.visible_products] == ["FB-100"]
    app.search_box.setText("FB-")
    assert [product.code for product in app.table.visible_products] == ["FB-100"]
    app.search_box.setText("1")
    assert [product.code for product in app.table.visible_products] == ["FB-100"]
    app.search_box.setText("#")
    assert [product.code for product in app.table.visible_products] == ["PP#300"]

    app.search_box.clear()
    assert [product.code for product in app.table.visible_products] == [
        "FB-100",
        "XY200",
        "PP#300",
    ]
    assert app.table.search_text == ""

    app.search_box.deleteLater()
    app.product_counter.deleteLater()

def test_product_search_priority_matches_requested_field_order():
    products = [
        Product(code="PRICE", name="Artículo", price_sample=75.0),
        Product(code="STOCK", name="Artículo", stock=75),
        Product(code="DETAIL", name="Artículo", description="75 unidades"),
        Product(code="SKU-75", name="Artículo"),
        Product(code="CATEGORY", name="Artículo", category="Promociones 75"),
        Product(code="NAME", name="Artículo 75"),
    ]

    assert [product_search_priority(product, "75") for product in products] == [
        4,
        3,
        2,
        1,
        0,
        0,
    ]


def test_main_window_orders_search_results_by_priority_and_keeps_ties_stable():
    _qapp()
    app = MainWindow.__new__(MainWindow)
    app.search_box = QLineEdit()
    app.search_box.setText("75")
    app.all_products = [
        Product(code="PRICE", name="Artículo", price_sample=75.0),
        Product(code="STOCK", name="Artículo", stock=75),
        Product(code="DETAIL", name="Artículo", description="75 unidades"),
        Product(code="SKU-75", name="Artículo"),
        Product(code="CATEGORY", name="Artículo", category="Promociones 75"),
        Product(code="NAME", name="Artículo 75"),
    ]
    app.selected_categories = set()
    app.stock_only = False

    assert [product.code for product in app._filtered_products()] == [
        "CATEGORY",
        "NAME",
        "SKU-75",
        "DETAIL",
        "STOCK",
        "PRICE",
    ]
    app.search_box.deleteLater()
