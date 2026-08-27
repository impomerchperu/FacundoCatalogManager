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
    html = "".join(_product(code) for code in ("FB-1001", "FB-1002", "FB-1003"))
    browser = FakeBrowser({category_url: html})
    scraper = CategoryScraper(
        browser,
        product_block_extractor=FakeProductBlockExtractor(),
    )

    pages = scraper.get_category_pages(category_url, expected_count=3)

    assert pages == [category_url]
    assert browser.post_calls == []


def test_public_woocommerce_page_is_preferred_to_jsf():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    page_two = f"{category_url.rstrip('/')}/page/2/"
    page_three = f"{category_url.rstrip('/')}/page/3/"
    responses = {
        category_url: _product("FB-1001"),
        page_two: _product("FB-1002"),
        page_three: _product("FB-1003"),
    }
    browser = FakeBrowser(responses)
    scraper = CategoryScraper(
        browser,
        product_block_extractor=FakeProductBlockExtractor(),
    )

    pages = scraper.get_category_pages(category_url, expected_count=51)

    assert pages == [category_url, page_two, page_three]
    assert browser.post_calls == []


def test_jsf_is_used_when_public_archive_page_is_unavailable():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    responses = {
        category_url: _product("FB-1001"),
        "ajax:2": (
            '{"pagination":{"found_posts":51,"max_num_pages":2},'
            f'"rendered_content":"{_product("FB-1002")}"}}'
        ),
        "ajax:3": (
            '{"pagination":{"found_posts":51,"max_num_pages":2},'
            f'"rendered_content":"{_product("FB-1003")}"}}'
        ),
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
    ] == ["2", "3"]


def test_repeated_jsf_page_is_rejected_when_no_new_products_exist():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    responses = {
        category_url: _product("FB-1001"),
        "ajax:2": (
            '{"pagination":{"found_posts":51,"max_num_pages":2},'
            f'"rendered_content":"{_product("FB-1001")}"}}'
        ),
        "ajax:3": (
            '{"pagination":{"found_posts":51,"max_num_pages":2},'
            f'"rendered_content":"{_product("FB-1001")}"}}'
        ),
    }
    browser = FakeBrowser(responses)
    scraper = CategoryScraper(
        browser,
        product_block_extractor=FakeProductBlockExtractor(),
    )

    try:
        scraper.get_category_pages(category_url, expected_count=51)
    except RuntimeError as exc:
        assert "página nueva" in str(exc)
    else:
        raise AssertionError("Expected repeated pagination to fail")
