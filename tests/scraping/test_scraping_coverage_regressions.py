import json
from threading import RLock

from bs4 import BeautifulSoup

from scrapers.collectors import (
    category_pagination_patch,
    jsf_concurrency_patch,
    product_code_patch,
    scraping_compat,
)
from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.extractors.product_extractor import ProductExtractor
from services.scraping.category_product_sync_service import CategoryProductSyncService


def _product_html(start: int, count: int) -> str:
    links = "".join(
        f'<a href="/producto/producto-{index:03d}/">Producto {index}</a>'
        for index in range(start, start + count)
    )
    return f"<html><body>{links}</body></html>"


def _new_jsf_test_scraper() -> CategoryScraper:
    scraper = CategoryScraper(browser=object())
    scraper._category_html_cache = {}
    scraper._category_html_cache_lock = RLock()
    scraper._jsf_metadata_cache = {}
    scraper._jsf_page_cache = {}
    scraper._jsf_cache_lock = RLock()
    scraper.MAX_HIDDEN_PAGE_PROBES = 100
    return scraper


def test_product_code_patch_extracts_product_code_without_relationship_rules():
    extractor = object.__new__(ProductExtractor)
    soup = BeautifulSoup('<span class="sku">AB-7008-X</span>', "html.parser")

    code = product_code_patch._extract_code(extractor, soup)

    assert code == "AB-7008-X"


def test_category_coverage_preserves_comma_in_real_category_name():
    service = object.__new__(CategoryProductSyncService)

    assert service._split_categories("Cocina, Mesa y Hogar") == [
        "Cocina, Mesa y Hogar"
    ]


def test_compatibility_layers_are_explicit_not_implicitly_active():
    assert CategoryScraper.get_category_pages is not (
        category_pagination_patch._get_category_pages
    )
    assert not hasattr(jsf_concurrency_patch, "_post_jsf")
    assert CategoryScraper.JSF_HTTP_CONCURRENCY == jsf_concurrency_patch.JSF_HTTP_CONCURRENCY
    assert ProductExtractor.extract_code is product_code_patch._extract_code
    assert hasattr(scraping_compat, "activate")
