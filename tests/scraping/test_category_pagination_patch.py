import json

from scrapers.collectors.category_pagination_patch import pages_required
from scrapers.collectors.category_scraper import CategoryScraper


class FakeBrowser:
    def __init__(self, responses):
        self.responses = responses
        self.post_calls = []
        self.get_calls = []

    def get(self, url):
        self.get_calls.append(url)
        return self.responses.get(url, "<html></html>")

    def post(self, url, data=None):
        self.post_calls.append((url, data))
        page = next(value for key, value in data if key == "paged")
        return self.responses[f"ajax:{page}"]


class FakeProductBlockExtractor:
    def extract(self, soup):
        return soup.select("article.product")


def _product(code):
    return f'<article class="product"><span class="sku">{code}</span></article>'


def _products(start, count):
    return "".join(
        _product(f"FB-{start + offset:04d}") for offset in range(count)
    )


def _facundo_products(start, count, category_id=127):
    return (
        f'<html><body class="product_cat-{category_id}">'
        f"{_products(start, count)}"
        "</body></html>"
    )


def _jsf_response(start, count, found_posts=51, max_num_pages=3):
    return json.dumps(
        {
            "pagination": {
                "found_posts": found_posts,
                "max_num_pages": max_num_pages,
            },
            "rendered_content": _products(start, count),
        }
    )


def test_pages_required_uses_only_the_category_published_count():
    assert pages_required(25) == 1
    assert pages_required(26) == 2
    assert pages_required(61) == 3
    assert pages_required(79) == 4
    assert pages_required(0) == 0


def test_jsf_payload_uses_requested_page_for_all_pagination_fields():
    payload = dict(CategoryScraper._jet_smart_filters_payload(127, 3))

    assert payload["defaults[paged]"] == "3"
    assert payload["props[page]"] == "3"
    assert payload["paged"] == "3"


def test_complete_category_html_is_used_before_pagination():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    html = "".join(
        _product(code) for code in ("FB-1001", "FB-1002", "FB-1003")
    )
    browser = FakeBrowser({category_url: html})
    scraper = CategoryScraper(
        browser,
        product_block_extractor=FakeProductBlockExtractor(),
    )

    pages = scraper.get_category_pages(category_url, expected_count=3)

    assert pages == [category_url]
    assert browser.post_calls == []


def test_public_archive_with_more_than_25_products_skips_jsf():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    browser = FakeBrowser({category_url: _products(1001, 51)})
    scraper = CategoryScraper(
        browser,
        product_block_extractor=FakeProductBlockExtractor(),
    )

    pages = scraper.get_category_pages(category_url, expected_count=51)

    assert pages == [category_url]
    assert browser.post_calls == []


def test_public_woocommerce_page_is_preferred_to_jsf():
    category_url = "https://example.com/categoria-producto/catalogo/"
    page_two = f"{category_url.rstrip('/')}/page/2/"
    page_three = f"{category_url.rstrip('/')}/page/3/"
    responses = {
        category_url: _products(1001, 25),
        page_two: _products(1026, 25),
        page_three: _products(1051, 1),
    }
    browser = FakeBrowser(responses)
    scraper = CategoryScraper(
        browser,
        product_block_extractor=FakeProductBlockExtractor(),
    )

    pages = scraper.get_category_pages(category_url, expected_count=51)

    assert pages == [category_url, page_two, page_three]
    assert browser.post_calls == []


def test_facundo_uses_native_jsf_before_public_woocommerce_variants():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    responses = {
        category_url: _facundo_products(1001, 25),
        "ajax:2": _jsf_response(1026, 25, found_posts=50, max_num_pages=2),
    }
    browser = FakeBrowser(responses)
    scraper = CategoryScraper(
        browser,
        product_block_extractor=FakeProductBlockExtractor(),
    )

    pages = scraper.get_category_pages(category_url, expected_count=50)

    assert pages == [
        category_url,
        f"{category_url.rstrip('/')}?product-page=2",
    ]
    assert browser.get_calls == [category_url]
    assert [
        next(value for key, value in data if key == "paged")
        for _, data in browser.post_calls
    ] == ["1", "2"]


def test_facundo_does_not_stop_at_expected_count_when_jsf_reports_more_pages():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    responses = {
        category_url: _facundo_products(1001, 25),
        "ajax:2": _jsf_response(1026, 25, found_posts=51, max_num_pages=3),
        "ajax:3": _jsf_response(1051, 1, found_posts=51, max_num_pages=3),
    }
    browser = FakeBrowser(responses)
    scraper = CategoryScraper(
        browser,
        product_block_extractor=FakeProductBlockExtractor(),
    )

    pages = scraper.get_category_pages(category_url, expected_count=25)

    assert pages == [
        category_url,
        f"{category_url.rstrip('/')}?product-page=2",
        f"{category_url.rstrip('/')}?product-page=3",
    ]
    assert [
        next(value for key, value in data if key == "paged")
        for _, data in browser.post_calls
    ] == ["1", "2", "3"]


def test_jsf_is_used_when_public_archive_page_is_unavailable():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    responses = {
        category_url: _facundo_products(1001, 25),
        "ajax:2": _jsf_response(1026, 25),
        "ajax:3": _jsf_response(1051, 1),
    }
    browser = FakeBrowser(responses)
    scraper = CategoryScraper(
        browser,
        product_block_extractor=FakeProductBlockExtractor(),
    )

    pages = scraper.get_category_pages(category_url, expected_count=51)

    assert pages == [
        category_url,
        f"{category_url.rstrip('/')}?product-page=2",
        f"{category_url.rstrip('/')}?product-page=3",
    ]
    assert [
        next(value for key, value in data if key == "paged")
        for _, data in browser.post_calls
    ] == ["1", "2", "3"]


def test_pagination_probes_beyond_nominal_page_count_when_pages_are_partial():
    category_url = "https://example.com/categoria-producto/catalogo/"
    page_two = f"{category_url.rstrip('/')}/page/2/"
    page_three = f"{category_url.rstrip('/')}/page/3/"
    responses = {
        category_url: _products(1001, 20),
        page_two: _products(1021, 20),
        page_three: _products(1041, 20),
    }
    browser = FakeBrowser(responses)
    scraper = CategoryScraper(
        browser,
        product_block_extractor=FakeProductBlockExtractor(),
    )

    pages = scraper.get_category_pages(category_url, expected_count=50)

    assert pages == [category_url, page_two, page_three]


def test_repeated_jsf_page_is_rejected_when_no_new_products_exist():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    responses = {
        category_url: _facundo_products(1001, 1),
        "ajax:2": _jsf_response(1001, 1),
    }
    browser = FakeBrowser(responses)
    scraper = CategoryScraper(
        browser,
        product_block_extractor=FakeProductBlockExtractor(),
    )

    try:
        scraper.get_category_pages(category_url, expected_count=51)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected repeated pagination to fail")
