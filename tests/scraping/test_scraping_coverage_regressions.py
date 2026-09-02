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


def _new_jsf_test_scraper() -> CategoryScraper:
    scraper = object.__new__(CategoryScraper)
    scraper._category_html_cache = {}
    scraper._category_html_cache_lock = RLock()
    scraper._jsf_metadata_cache = {}
    scraper._jsf_page_cache = {}
    scraper._jsf_cache_lock = RLock()
    scraper.MAX_HIDDEN_PAGE_PROBES = 100
    return scraper


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
    scraper = _new_jsf_test_scraper()
    category_url = "https://stock.importacionesfacundo.com/categoria-producto/demo/"
    first_html = _product_html(1, 25)
    scraper.get_html = lambda url: first_html
    scraper._is_facundo_url = lambda url: True
    scraper._category_id = lambda html: 123

    def fetch(_url, _category_id, page):
        if page == 1:
            return 50, 2, first_html
        if page == 2:
            return 50, 2, _product_html(26, 6)
        return 50, 2, ""

    scraper._fetch_jsf_page = fetch
    scraper._fallback_category_pages = lambda *_args, **_kwargs: [
        category_url,
        f"{category_url}page/2/",
    ]

    pages = category_pagination_patch._get_category_pages(
        scraper,
        category_url,
        expected_count=31,
    )

    assert pages == [
        category_url,
        f"{category_url}?product-page=2",
    ]


def test_facundo_get_category_pages_does_not_replace_jsf_with_public_fallback():
    scraper = _new_jsf_test_scraper()
    category_url = "https://stock.importacionesfacundo.com/categoria-producto/demo/"
    first_html = _product_html(1, 25)
    second_html = _product_html(26, 6)
    scraper.get_html = lambda url: first_html
    scraper._is_facundo_url = lambda url: True
    scraper._category_id = lambda html: 123

    def fetch(_url, _category_id, page):
        if page == 1:
            return 25, 1, first_html
        return 25, 1, second_html

    scraper._fetch_jsf_page = fetch

    def unexpected_public_fallback(*_args, **_kwargs):
        raise AssertionError("La paginación pública no debe ser la ruta primaria de Facundo")

    scraper._fallback_category_pages = unexpected_public_fallback

    pages = category_pagination_patch._get_category_pages(
        scraper,
        category_url,
        expected_count=50,
    )

    assert pages == [
        category_url,
        f"{category_url}?product-page=2",
    ]


def test_facundo_jsf_page_retries_empty_response():
    scraper = _new_jsf_test_scraper()
    responses = [
        "",
        "",
        '{"found_posts":25,"max_num_pages":2,"rendered_content":"<div>FB-026</div>"}',
    ]
    calls = []

    def post(_payload):
        calls.append(1)
        return responses.pop(0)

    scraper._post_jsf = post
    original_state = dict(category_pagination_patch._JSF_QUERY_STATE)
    category_pagination_patch._JSF_QUERY_STATE.clear()
    try:
        result = category_pagination_patch._retry_jsf_page(
            scraper,
            "https://stock.importacionesfacundo.com/categoria-producto/demo/",
            123,
            2,
        )
    finally:
        category_pagination_patch._JSF_QUERY_STATE.clear()
        category_pagination_patch._JSF_QUERY_STATE.update(original_state)

    assert result[2] == "<div>FB-026</div>"
    assert len(calls) == 3


def test_facundo_jsf_retry_does_not_disable_retries_for_hidden_pages():
    scraper = _new_jsf_test_scraper()
    responses = [
        "",
        "",
        '{"rendered_content":"<div>FB-076</div>"}',
    ]
    calls = []

    def post(_payload):
        calls.append(1)
        return responses.pop(0)

    scraper._post_jsf = post
    original_state = dict(category_pagination_patch._JSF_QUERY_STATE)
    category_pagination_patch._JSF_QUERY_STATE.clear()
    try:
        result = category_pagination_patch._retry_jsf_page(
            scraper,
            "https://stock.importacionesfacundo.com/categoria-producto/demo/",
            123,
            4,
        )
    finally:
        category_pagination_patch._JSF_QUERY_STATE.clear()
        category_pagination_patch._JSF_QUERY_STATE.update(original_state)

    assert result[2] == "<div>FB-076</div>"
    assert len(calls) == 3


def test_facundo_jsf_payload_preserves_initial_query_state_for_next_page():
    scraper = _new_jsf_test_scraper()
    captured = []
    responses = [
        '{"found_posts":50,"max_num_pages":2,"rendered_content":"<div>FB-001</div>"}',
        '{"found_posts":50,"max_num_pages":2,"rendered_content":"<div>FB-026</div>"}',
    ]

    def post(payload):
        captured.append(dict(payload))
        return responses.pop(0)

    scraper._post_jsf = post
    original_state = dict(category_pagination_patch._JSF_QUERY_STATE)
    category_pagination_patch._JSF_QUERY_STATE.clear()
    try:
        category_pagination_patch._retry_jsf_page(
            scraper,
            "https://stock.importacionesfacundo.com/categoria-producto/demo/",
            127,
            1,
        )
        category_pagination_patch._retry_jsf_page(
            scraper,
            "https://stock.importacionesfacundo.com/categoria-producto/demo/",
            127,
            2,
        )
    finally:
        category_pagination_patch._JSF_QUERY_STATE.clear()
        category_pagination_patch._JSF_QUERY_STATE.update(original_state)

    assert captured[0]["defaults[paged]"] == "1"
    assert captured[0]["props[page]"] == "1"
    assert captured[0]["paged"] == "1"
    assert captured[1]["defaults[paged]"] == "1"
    assert captured[1]["props[page]"] == "1"
    assert captured[1]["props[found_posts]"] == "50"
    assert captured[1]["props[max_num_pages]"] == "2"
    assert captured[1]["paged"] == "2"


def test_facundo_jsf_pagination_does_not_treat_max_num_pages_as_hard_ceiling():
    scraper = _new_jsf_test_scraper()
    category_url = "https://stock.importacionesfacundo.com/categoria-producto/demo/"
    first_html = '<body class="archive tax-product_cat term-127"></body>'
    scraper.get_html = lambda _url: first_html
    scraper._is_facundo_url = lambda _url: True
    scraper._category_id = lambda _html: 127
    responses = {
        1: (25, 1, _product_html(1, 1)),
        2: (25, 1, _product_html(2, 1)),
        3: (25, 1, _product_html(3, 1)),
        4: (25, 1, ""),
    }
    scraper._fetch_jsf_page = lambda _url, _category_id, page: responses[page]

    pages = category_pagination_patch._get_category_pages(
        scraper,
        category_url,
        expected_count=0,
    )

    assert pages == [
        category_url,
        f"{category_url}?product-page=2",
        f"{category_url}?product-page=3",
    ]


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
    assert CategoryScraper._fetch_jsf_page is category_pagination_patch._retry_jsf_page
    assert ProductExtractor.extract_code is product_code_patch._extract_code
    assert CategoryProductSyncService._split_categories.__name__ == "_split_categories"
    assert hasattr(scraping_compat, "activate")
