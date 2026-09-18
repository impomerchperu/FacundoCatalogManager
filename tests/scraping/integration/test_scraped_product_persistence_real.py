import pytest

from database.db_manager import DBManager
from repositories.scraping.scraped_product_repository import (
    ScrapedProductRepository,
)
from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.collectors.product_collection_scraper import (
    ProductCollectionScraper,
)
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.product_card_extractor import ProductCardExtractor
from scrapers.extractors.product_extractor import ProductExtractor

pytestmark = pytest.mark.integration


CATEGORY_URL = (
    "https://stock.importacionesfacundo.com/"
    "categoria-producto/jarros-mug/"
)


@pytest.mark.real_site
def test_scraped_product_persistence_real():
    db = DBManager()
    repository = ScrapedProductRepository(db)

    category_scraper = CategoryScraper(CATEGORY_URL)
    collection_scraper = ProductCollectionScraper(
        category_scraper,
        ProductCardExtractor(),
        CategoryProductExtractor(),
        ProductExtractor(),
    )

    category = type(
        "Category",
        (),
        {
            "name": "Jarros Mug",
            "url": CATEGORY_URL,
        },
    )()

    products = collection_scraper.scrape_category(category)

    assert products

    for product in products[:3]:
        repository.save(product)

    saved = repository.get_all()

    assert saved
