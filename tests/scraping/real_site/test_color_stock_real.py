import re

import pytest

from scrapers.browser import Browser
from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.product_card_extractor import ProductCardExtractor
from scrapers.extractors.product_extractor import ProductExtractor

pytestmark = pytest.mark.real_site

CATEGORY_URL = (
    "https://stock.importacionesfacundo.com/"
    "categoria-producto/bolsas-mochilas/"
)

EXPECTED_COLOR_ORDER = {
    "FB-6005": ("Azul", "Negro", "Rojo"),
    "FB-6002": ("Azul", "Negro", "Rojo", "Gris"),
}


class Category:
    name = "Bolsas / Mochilas"
    url = CATEGORY_URL
    expected_count = 0


def _base_code(value: object) -> str:
    code = str(value or "").strip().upper()
    return re.sub(r"-A$", "", code)


@pytest.mark.parametrize("expected_code", sorted(EXPECTED_COLOR_ORDER))
def test_real_site_color_stock_preserves_site_variant_order(expected_code):
    browser = Browser()
    category_scraper = CategoryScraper(browser)
    collection = ProductCollectionScraper(
        category_scraper,
        ProductCardExtractor(),
        CategoryProductExtractor(),
        ProductExtractor(),
    )

    try:
        collected = collection.collect_category(Category())
        matching = [
            item
            for item in collected
            if _base_code(getattr(item[2], "code", "")) == expected_code
        ]

        assert len(matching) == 1, [
            getattr(item[2], "code", "")
            for item in collected
        ]

        products = collection.enrich_category_products(
            matching,
            Category.name,
        )
        product = products[0]
    finally:
        collection.close()

    color_stock = dict(getattr(product, "color_stock", {}) or {})
    assert tuple(color_stock) == EXPECTED_COLOR_ORDER[expected_code]
    assert tuple(color_stock.values())
    assert all(int(value) >= 0 for value in color_stock.values())
    assert product.stock == sum(color_stock.values())

    print(
        f"{expected_code}: "
        f"{color_stock} total={product.stock}"
    )
