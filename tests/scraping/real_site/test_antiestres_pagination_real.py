import json
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


def _rendered_content(payload: str) -> str:
    try:
        data = json.loads(payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    data_section = data.get("data")
    if not isinstance(data_section, dict):
        return ""
    rendered = data_section.get("rendered_content")
    return rendered if isinstance(rendered, str) else ""


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

    captured_requests: list[dict[str, object]] = []
    original_post_jsf = category_scraper._post_jsf

    def capture_jsf(payload):
        values = dict(payload)
        result = original_post_jsf(payload)
        page = values.get("paged", "")
        rendered = _rendered_content(result)
        captured_requests.append(
            {
                "paged": page,
                "props_page": values.get("props[page]", ""),
                "defaults_paged": values.get("defaults[paged]", ""),
                "category_id": values.get("query[_tax_query_product_cat]", ""),
                "orderby_menu_order": values.get(
                    "defaults[orderby][menu_order]", ""
                ),
                "has_indexing_filters": "indexing_filters[]" in values,
                "rendered_html_len": len(rendered),
                "rendered_product_urls": sorted(
                    _direct_product_urls(rendered, STORE_URL)
                ),
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
    print("REQUESTS JSF:", captured_requests)
    for index, urls in enumerate(page_url_sets, start=1):
        print(
            f"PÁGINA FALLBACK {index}: URLS={len(urls)} "
            f"MUESTRA={sorted(urls)[:5]}"
        )
    jsf_page_groups = {
        str(request["paged"]): set(request["rendered_product_urls"])
        for request in captured_requests
        if request.get("paged") in {"1", "2"}
        and request.get("rendered_product_urls")
    }
    if "1" in jsf_page_groups and "2" in jsf_page_groups:
        print(
            "URLS JSF COMUNES P1/P2:",
            len(jsf_page_groups["1"] & jsf_page_groups["2"]),
        )
        print(
            "URLS JSF NUEVAS P2:",
            len(jsf_page_groups["2"] - jsf_page_groups["1"]),
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
