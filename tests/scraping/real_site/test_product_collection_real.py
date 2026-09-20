import pytest

from scrapers.browser import Browser
from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.collectors.product_collection_scraper import (
    ProductCollectionScraper,
)
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.product_card_extractor import ProductCardExtractor
from scrapers.extractors.product_extractor import ProductExtractor

pytestmark = pytest.mark.real_site


class Category:
    name = "Jarros Mug"

    url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/jarros-mug/"
    )


def test_product_collection_real():
    browser = Browser()

    category_scraper = CategoryScraper(
        browser,
    )

    collection = ProductCollectionScraper(
        category_scraper,
        ProductCardExtractor(),
        CategoryProductExtractor(),
        ProductExtractor(),
    )

    products = collection.scrape_category(
        Category(),
    )

    assert products

    print(
        "TOTAL PRODUCTOS:",
        len(products),
    )

    for product in products[:5]:
        print(product)
