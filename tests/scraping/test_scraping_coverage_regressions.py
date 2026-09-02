from bs4 import BeautifulSoup

from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.collectors import category_pagination_patch
from scrapers.collectors import product_code_patch
from scrapers.extractors.product_extractor import ProductExtractor
from services.scraping.category_product_sync_service import CategoryProductSyncService


def _product_html(count: int) -> str:
    links = "".join(
        f'<a href="/producto/producto-{index:03d}/">Producto {index}</a>'
        for index in range(1, count + 1)
    )
    return f"<html><body>{links}</body></html>"


def test_facundo_pagination_prefers_public_archive_when_it_has_multiple_pages():
    scraper = object.__new__(CategoryScraper)
    scraper._category_html_cache = {}
    scraper.MAX_HIDDEN_PAGE_PROBES = 100
    category_url = "https://stock.importacionesfacundo.com/categoria-producto/demo/"
    first_html = _product_html(25)
    second_html = _product_html(6)
    scraper.get_html = lambda url: first_html
    scraper._is_facundo_url = lambda url: True
    scraper._fallback_category_pages = lambda url, html, expected: [
        category_url,
        f"{category_url}page/2/",
    ]
    scraper._category_html_cache[category_url] = first_html
    scraper._category_html_cache[f"{category_url}page/2/"] = second_html

    def unexpected_jsf(*_args, **_kwargs):
        raise AssertionError("JSF no debe ser la fuente primaria del archivo público")

    scraper._fetch_jsf_page = unexpected_jsf
    pages, count = category_pagination_patch._facundo_direct_pages(
        scraper,
        category_url,
        first_html,
        31,
    )

    assert len(pages) == 2
    assert count == 31


def test_facundo_get_category_pages_does_not_fallback_to_jsf_after_public_pages():
    scraper = object.__new__(CategoryScraper)
    scraper._category_html_cache = {}
    scraper.MAX_HIDDEN_PAGE_PROBES = 100
    category_url = "https://stock.importacionesfacundo.com/categoria-producto/demo/"
    first_html = _product_html(25)
    scraper.get_html = lambda url: first_html
    scraper._is_facundo_url = lambda url: True
    scraper._fallback_category_pages = lambda url, html, expected: [
        category_url,
        f"{category_url}page/2/",
    ]
    scraper._category_html_cache[category_url] = first_html
    scraper._category_html_cache[f"{category_url}page/2/"] = _product_html(6)

    def unexpected_jsf(*_args, **_kwargs):
        raise AssertionError("No debe invocarse JSF con un archivo público paginado")

    scraper._fetch_jsf_page = unexpected_jsf
    scraper._category_id = lambda html: 123

    pages = scraper.get_category_pages(category_url, expected_count=31)

    assert pages == [category_url, f"{category_url}page/2/"]


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
