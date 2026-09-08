import unicodedata
from time import perf_counter

import pytest

from config.scraping_config import STORE_URL
from scrapers.browser import Browser
from scrapers.collectors.category_pagination_patch import _direct_product_urls
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
    """Validate live JSF pagination and expose page/request identity."""
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

    captured_requests: list[dict[str, str]] = []
    original_post_jsf = category_scraper._post_jsf

    def capture_jsf(payload):
        values = dict(payload)
        result = original_post_jsf(payload)
        page = values.get("paged", "")
        props_page = values.get("props[page]", "")
        defaults_page = values.get("defaults[paged]", "")
        category_id = values.get("query[_tax_query_product_cat]", "")
        captured_requests.append(
            {
                "paged": page,
                "props_page": props_page,
                "defaults_paged": defaults_page,
                "category_id": category_id,
                "html_len": str(len(result)),
            }
        )
        return result

    category_scraper._post_jsf = capture_jsf

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

    pages = category_scraper.get_category_pages(
        category.url,
        expected_count=category.expected_count,
    )
    page_html = [category_scraper.get_html(page) for page in pages]
    page_url_sets = [
        _direct_product_urls(html, page_url)
        for html, page_url in zip(page_html, pages, strict=True)
    ]

    print("CATEGORÍA:", category.name)
    print("ESPERADOS:", EXPECTED_PRODUCTS)
    print("PÁGINAS DEVUELTAS:", len(pages), pages)
    print(
        "REQUESTS JSF:",
        captured_requests,
    )
    for index, urls in enumerate(page_url_sets, start=1):
        print(
            f"PÁGINA {index}: URLS={len(urls)} "
            f"MUESTRA={sorted(urls)[:5]}"
        )
    if len(page_url_sets) >= 2:
        print(
            "URLS COMUNES P1/P2:",
            len(page_url_sets[0] & page_url_sets[1]),
        )
        print(
            "URLS NUEVAS P2:",
            len(page_url_sets[1] - page_url_sets[0]),
        )

    products = collection.scrape_category(category)
    metrics = collection.get_page_metrics()[category.url]

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
