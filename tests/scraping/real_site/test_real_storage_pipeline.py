import pytest

from models.scraping.category import Category
from scrapers.browser import Browser
from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.collectors.product_collection_scraper import (
    ProductCollectionScraper,
)
from scrapers.parser import Parser
from scrapers.storage.product_storage import ProductStorage


pytestmark = pytest.mark.real_site


CATEGORY_URL = (
    "https://stock.importacionesfacundo.com/"
    "categoria-producto/jarros-mug/"
)


def test_real_storage_pipeline():

    category = Category(
        name="Jarros Mug",
        url=CATEGORY_URL,
    )

    browser = Browser()

    parser = Parser()

    category_scraper = CategoryScraper(
        browser=browser,
        parser=parser,
    )

    collection = ProductCollectionScraper(
        category_scraper=category_scraper,
    )

    products = collection.scrape_category(
        category,
    )

    assert products

    storage = ProductStorage()

    storage.save(products)

    saved = storage.load()

    assert saved