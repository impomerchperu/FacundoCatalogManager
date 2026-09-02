from threading import RLock

from bs4 import BeautifulSoup

from scrapers.collectors import (
    category_pagination_patch,
    product_code_patch,
    scraping_compat,
)
from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.extractors.product_extractor import ProductExtractor
from services.scraping.category_product_sync_service import (
    CategoryProductSyncService,
)


def _product_html(start: int, count: int) -> str:
    links = "".join(
        f'<a href="/producto/producto-{index:03d}/">Producto {index}</a>'
        for index in range(start, start + count)
    )
    return f"<html><body>{links}</body></html>"


def test_facundo_pagination_public_helper_counts_all_public_pages():
    scraper = object.__new__(CategoryScraper)
    scraper._category_html_cache = {}
    scraper._category_html_cache_lock = RLock()
    scraper.MAX_HIDDEN_PAGE_PROBES = 100
    category_url = "https://stock.importacionesfacundo.com/categoria-producto/demo/"
    first_html = _product_html(1, 25)
    second_url = f"{category_url}page/2/"
    second_html = _product_html(26, 6)
    scraper.get_html = lambda url: first_html
    scraper._fallback_category_pages = lambda url, html, expected: [
        category_url,
        second_url,
    ]
    scraper._category_html_cache[category_url] = first_html
    scraper._category_html_cache[second_url] = second_html

    pages, count = category_pagination_patch._facundo_direct_pages(
        scraper,
        category_url,
        first_html,
        31,
    )

    assert len(pages) == 2
    assert count == 31


def test_facundo_get_category_pages_prefers_jsf_pagination():
    scraper = object.__new__(CategoryScraper)
    scraper._category_html_cache = {}
    scraper._category_html_cache_lock = RLock()
    category_url = "https://stock.importacionesfacundo.com/categoria-producto/demo/"
    first_html = _product_html(1, 25)
    scraper.get_html = lambda url: first_html
    scraper._is_facundo_url = lambda url: True
    scraper._category_id = lambda html: 123
    scraper._original_get_category_pages = lambda url, expected_count=0: [
        category_url,
        f"{category_url}?product-page=2",
    ]

    def unexpected_public_fallback(*_args, **_kwargs):
        raise AssertionError("La paginación pública no debe ser la ruta primaria de Facundo")

    scraper._fallback_category_pages = unexpected_public_fallback

    pages = category_pagination_patch._get_category_pages(
        scraper,
        category_url,
        expected_count=31,
    )

    assert pages == [
        category_url,
        f"{category_url}?product-page=2",
    ]


def test_facundo_get_category_pages_uses_public_fallback_when_jsf_is_incomplete():
    scraper = object.__new__(CategoryScraper)
    scraper._category_html_cache = {}
    scraper._category_html_cache_lock = RLock()
    category_url = "https://stock.importacionesfacundo.com/categoria-producto/demo/"
    first_html = _product_html(1, 25)
    second_url = f"{category_url}page/2/"
    second_html = _product_html(26, 25)
    scraper.get_html = lambda url: first_html
    scraper._is_facundo_url = lambda url: True
    scraper._category_id = lambda html: 123
    scraper._original_get_category_pages = lambda url, expected_count=0: [category_url]
    scraper._fallback_category_pages = lambda url, html, expected: [
        category_url,
        second_url,
    ]
    scraper._category_html_cache[second_url] = second_html

    pages = category_pagination_patch._get_category_pages(
        scraper,
        category_url,
        expected_count=50,
    )

    assert pages == [category_url, second_url]


def test_product_code_patch_reads_json_ld_sku_without_fb_prefix():
    soup = BeautifulSoup(
        """
        <html><head>
          <script type="application/ld+json">
            {"@context":"https://schema.org","@type":"Product","sku":"PHOTO-2026"}
          </script>
        </head><body><h1>Software</h1></body></html>
        """,
        "html.parser",
    )

    extractor = ProductExtractor()
    code = product_code_patch._extract_code(extractor, soup)

    assert code == "PHOTO-2026"


def test_category_coverage_preserves_comma_in_real_category_name():
    service = object.__new__(CategoryProductSyncService)

    assert service._split_categories("Cocina, Mesa y Hogar") == [
        "Cocina, Mesa y Hogar"
    ]


def test_compatibility_layers_are_active():
    assert CategoryScraper.get_category_pages is category_pagination_patch._get_category_pages
    assert ProductExtractor.extract_code is product_code_patch._extract_code
    assert CategoryProductSyncService._split_categories.__name__ == "_split_categories"
    assert hasattr(scraping_compat, "activate")
