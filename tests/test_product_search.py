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


def test_product_search_matches_simple_typo_variants():
    product = Product(
        code="FB-101",
        name="Básket infantil",
    )

    assert product_matches_search(product, "bascket")


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


def test_product_search_keeps_searching_colors_and_rejects_unrelated_terms():
    product = Product(
        code="FB-104",
        name="Producto",
        color_stock={"Rojo": 10, "Azul": 5},
    )

    assert product_matches_search(product, "rojo")
    assert product_matches_search(product, "azul")
    assert not product_matches_search(product, "verde")


def test_main_window_uses_tolerant_product_search():
    product = Product(
        code="FB-105",
        name="Básket",
        description="Destapadores y abridores",
    )

    assert MainWindow.product_matches_search(product, "bascket")
    assert MainWindow.product_matches_search(product, "destapadores")
