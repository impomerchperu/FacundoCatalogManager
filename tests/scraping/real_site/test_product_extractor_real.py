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
