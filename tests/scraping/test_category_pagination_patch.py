from scrapers.collectors.category_pagination_patch import pages_required
from scrapers.collectors.category_scraper import CategoryScraper


class FakeBrowser:
    def __init__(self, responses):
        self.responses = responses
        self.post_calls = []

    def get(self, url):
        return self.responses.get(url, "<html></html>")

    def post(self, url, data=None):
        self.post_calls.append((url, data))
        page = next(value for key, value in data if key == "paged")
        return self.responses[f"ajax:{page}"]


class FakeProductBlockExtractor:
    def extract(self, soup):
        return soup.select("article.product")


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


def test_complete_category_html_is_used_before_jsf_when_cards_are_complete():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    html = "".join(
        f'<article class="product"><span>FB-{code}</span></article>'
        for code in ("1001", "1002", "1003")
    )
    browser = FakeBrowser({category_url: html})
    scraper = CategoryScraper(
        browser,
        product_block_extractor=FakeProductBlockExtractor(),
    )

    pages = scraper.get_category_pages(category_url, expected_count=3)

    assert pages == [category_url]
    assert browser.post_calls == []


def test_category_count_forces_every_required_jsf_page():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    responses = {
        category_url: "<body class=\"tax-product_cat term-127\"></body>",
        "ajax:2": (
            '{"pagination":{"found_posts":51,"max_num_pages":2},'
            '"rendered_content":"<article class=\"product\">'
            "<span class=\"sku\">FB-1002</span></article>"}'
        ),
        "ajax:3": (
            '{"pagination":{"found_posts":51,"max_num_pages":2},'
            '"rendered_content":"<article class=\"product\">'
            "<span class=\"sku\">FB-1003</span></article>"}'
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


def test_jsf_pagination_uses_each_category_count_not_global_total():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    responses = {
        category_url: '<body class="tax-product_cat term-127"></body>',
        "ajax:2": (
            '{"pagination":{"found_posts":25,"max_num_pages":1},'
            '"rendered_content":"<article class=\"product\">'
            "<span class=\"sku\">FB-2002</span></article>"}'
        ),
        "ajax:3": (
            '{"pagination":{"found_posts":25,"max_num_pages":1},'
            '"rendered_content":"<article class=\"product\">'
            "<span class=\"sku\">FB-2003</span></article>"}'
        ),
    }
    browser = FakeBrowser(responses)
    scraper = CategoryScraper(browser)

    pages = scraper.get_category_pages(category_url, expected_count=51)

    assert pages == [
        category_url,
        f"{category_url.rstrip('/')}?product-page=2",
        f"{category_url.rstrip('/')}?product-page=3",
    ]
