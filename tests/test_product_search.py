from PySide6.QtWidgets import QLabel, QLineEdit

from gui.main_window import MainWindow
from models.product import Product
from services.product_search import normalize_search_text, product_matches_search


def test_normalize_search_text_ignores_accents_case_and_punctuation():
    assert normalize_search_text("BÁSket, anti-estrés / rojo!") == (
        "basket anti estres rojo"
    )


def test_product_search_matches_accents_and_punctuation():
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


def test_product_search_matches_spelling_errors_including_transposed_letters():
    product = Product(
        code="FB-101",
        name="Mochila promocional",
    )

    assert product_matches_search(product, "mochlia")
    assert product_matches_search(product, "mochila")
    assert product_matches_search(product, "promocionla")


def test_product_search_matches_synonyms_both_directions():
    product = Product(
        code="FB-102",
        name="Abridor de botellas",
        description="Abridores para cocina",
    )

    assert product_matches_search(product, "destapadores")
    assert product_matches_search(product, "destapador")

    destapador = Product(
        code="FB-103",
        name="Destapadores profesionales",
    )

    assert product_matches_search(destapador, "abridores")
    assert product_matches_search(destapador, "abridor")


def test_product_search_includes_stock_colors_and_quantities():
    product = Product(
        code="FB-104",
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


def test_main_window_uses_tolerant_product_search():
    product = Product(
        code="FB-105",
        name="Mochila",
        description="Destapadores y abridores",
    )

    assert MainWindow.product_matches_search(product, "mochlia")
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


def test_search_box_filters_immediately_for_letters_numbers_and_symbols():
    app = MainWindow.__new__(MainWindow)
    app.search_box = QLineEdit()
    app.all_products = [
        Product(code="FB-100", name="Mochila"),
        Product(code="FB200", name="Bolso"),
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

    app.search_box.deleteLater()
    app.product_counter.deleteLater()
