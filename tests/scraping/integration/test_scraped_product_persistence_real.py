import pytest

from database.db_manager import DBManager
from models.scraping.scraped_product import ScrapedProduct
from repositories.scraping.scraped_product_repository import (
    ScrapedProductRepository,
)
from scrapers.collectors.product_collection_scraper import (
    ProductCollectionScraper,
)


pytestmark = pytest.mark.integration


CATEGORY_URL = (
    "https://stock.importacionesfacundo.com/"
    "categoria-producto/jarros-mug/"
)


@pytest.mark.real_site
def test_scraped_product_persistence_real():

    db = DBManager()

    repository = ScrapedProductRepository(db)

    collection_scraper = ProductCollectionScraper()

    category = type(
        "Category",
        (),
        {
            "name": "Jarros Mug",
            "url": CATEGORY_URL,
        },
    )()

    products = collection_scraper.scrape_category(
        category,
    )

    assert products

    for product in products[:3]:

        repository.save(product)

    saved = repository.get_all()

    assert saved