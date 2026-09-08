from time import perf_counter
import unicodedata

import pytest

from config.scraping_config import STORE_URL
from scrapers.browser import Browser
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.collectors.resilient_category_scraper import ResilientCategoryScraper
from scrapers.extractors.category_extractor import CategoryExtractor
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.product_card_extractor import ProductCardExtractor
from scrapers.extractors.product_extractor import ProductExtractor
from services.scraping.category_service import CategoryService

EXPECTED_PRODUCTS = 50
EXPECTED_PAGES = 2


def _normalize(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(character)
    )


@pytest.mark.real_site
def test_antiestres_pagination_real_site():
    """Validate that the live Antiestrés category returns two distinct pages."""
    started = perf_counter()
    browser = Browser()
    category_scraper = ResilientCategoryScraper(
        browser=browser,
        category_extractor=CategoryExtractor(),
    )
    category_service = CategoryService(category_scraper, STORE_URL)
    collection = ProductCollectionScraper(
        category_scraper,
        ProductCardExtractor(),
        CategoryProductExtractor(),
        ProductExtractor(),
    )

    categories = category_service.scrape_all()
    category = next(
        (
            item
            for item in categories
            if _normalize(str(item.name)) == "articulos antiestres"
        ),
        None,
    )
    assert category is not None, [item.name for item in categories]

    products = collection.scrape_category(category)
    metrics = collection.get_page_metrics()[category.url]

    print("CATEGORÍA:", category.name)
    print("ESPERADOS:", EXPECTED_PRODUCTS)
    print("ENCONTRADOS:", len(products))
    print("PÁGINAS:", metrics["pages_requested"])
    print("PÁGINAS CARGADAS:", metrics["pages_loaded"])
    print("TARJETAS:", metrics["cards_found"])
    print("ÚNICOS:", metrics["unique_products"])
    print("DURACIÓN:", f"{perf_counter() - started:.2f}s")

    assert len(products) == EXPECTED_PRODUCTS
    assert metrics["pages_requested"] == EXPECTED_PAGES
    assert metrics["pages_loaded"] == EXPECTED_PAGES
    assert metrics["cards_found"] == EXPECTED_PRODUCTS
    assert metrics["unique_products"] == EXPECTED_PRODUCTS
