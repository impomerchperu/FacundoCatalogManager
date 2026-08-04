import pytest

from models.scraping.category import Category
from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.collectors.product_collection_scraper import (
    ProductCollectionScraper,
)

pytestmark = pytest.mark.integration


BASE_URL = "https://stock.importacionesfacundo.com"


@pytest.mark.real_site
def test_product_collection_scraper_real():

    category_scraper = CategoryScraper(BASE_URL)

    collection = ProductCollectionScraper(
        category_scraper,
    )

    category = Category(
        name="Jarros Mug",
        url=(
            "https://stock.importacionesfacundo.com/"
            "categoria-producto/jarros-mug/"
        ),
    )

    products = collection.scrape_category(
        category,
    )

    assert products

    for product in products[:5]:
        print(
            product.code,
            "|",
            product.name,
            "|",
            product.category,
        )
