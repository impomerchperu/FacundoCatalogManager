import pytest
from bs4 import BeautifulSoup

from scrapers.browser import Browser
from scrapers.extractors.product_extractor import ProductExtractor

URL = (
    "https://stock.importacionesfacundo.com/"
    "producto/jarro-mug-ecologico-con-tapa-600-ml/"
)


@pytest.mark.real_site
def test_product_extractor_real_site():
    """Validación manual contra el sitio real; excluida de la suite normal."""
    browser = Browser()
    html = browser.fetch(URL)
    soup = BeautifulSoup(html, "lxml")

    product = ProductExtractor().extract(
        soup,
        url=URL,
        category="Jarros Mug",
    )

    assert product is not None
    print(product)

FB4008_URL = (
    "https://stock.importacionesfacundo.com/"
    "producto/antiestres-cerebro-largo/"
)


@pytest.mark.real_site
def test_product_extractor_real_site_fb4008_technical_detail():
    """Confirma que Detalle sale del resumen técnico real, no de las pestañas."""
    browser = Browser()
    try:
        html = browser.fetch(FB4008_URL)
    finally:
        browser.close()

    product = ProductExtractor().extract(
        BeautifulSoup(html, "lxml"),
        url=FB4008_URL,
        category="Artículos Antiestrés",
    )

    detail = product["description"]
    assert product["code"] == "FB-4008"
    assert detail.startswith("Material: Poliuretano.")
    assert "Dimensiones: 75*63*48mm." in detail
    assert "Peso Unitario: 23.5 G." in detail
    assert "Peso neto por caja: 5.5 Kg." in detail
    assert "Peso bruto por caja: 6.25 Kg." in detail
    assert "Color: Blanco" not in detail
    assert "Información adicional" not in detail
    assert "Valoraciones" not in detail

