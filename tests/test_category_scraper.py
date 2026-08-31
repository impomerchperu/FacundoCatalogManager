from scrapers.collectors.category_scraper import CategoryScraper


class FakeBrowser:
    def __init__(self, responses):
        self.responses = responses
        self.get_calls = []
        self.post_calls = []

    def get(self, url):
        self.get_calls.append(url)
        return self.responses.get(url, "<html></html>")

    def post(self, url, data=None):
        self.post_calls.append((url, data))
        page = next(value for key, value in data if key == "paged")
        return self.responses[f"ajax:{page}"]


def test_category_scraper_extracts_categories():
    class Parser:
        def extract_categories(self, html):
            return ["Herramientas", "Electricidad"]

    scraper = CategoryScraper(
        FakeBrowser({"https://example.test/categories": "<html></html>"}),
        Parser(),
    )
    assert scraper.scrape("https://example.test/categories") == [
        "Herramientas",
        "Electricidad",
    ]


def test_parse_jsf_response_reads_pagination_and_rendered_content():
    payload = (
        '{"pagination":{"found_posts":50,"max_num_pages":2},'
        '"rendered_content":"<div class=\\"product\\">FB-001</div>"}'
    )
    assert CategoryScraper._parse_jsf_response(payload) == (
        50,
        2,
        '<div class="product">FB-001</div>',
    )


def test_category_scraper_uses_jetsmartfilters_for_every_declared_page():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    category_html = '<body class="archive tax-product_cat term-127"></body>'
    responses = {
        category_url: category_html,
        "ajax:1": (
            '{"pagination":{"found_posts":50,"max_num_pages":2},'
            '"rendered_content":"<div>FB-001 FB-002</div>"}'
        ),
        "ajax:2": (
            '{"pagination":{"found_posts":50,"max_num_pages":2},'
            '"rendered_content":"<div>FB-026 FB-027</div>"}'
        ),
    }
    browser = FakeBrowser(responses)
    scraper = CategoryScraper(browser)

    pages = scraper.get_category_pages(category_url)

    page_2 = f"{category_url.rstrip('/')}?product-page=2"
    assert pages == [category_url, page_2]
    assert len(browser.get_calls) == 1
    assert [
        next(value for key, value in data if key == "paged")
        for _, data in browser.post_calls
    ] == ["1", "2"]
    first_payload = dict(browser.post_calls[0][1])
    assert first_payload["action"] == "jet_smart_filters"
    assert first_payload["provider"] == "bricks-query-loop/querydesk"
    assert first_payload["query[_tax_query_product_cat]"] == "127"
    assert first_payload["defaults[posts_per_page]"] == "25"
    assert first_payload["settings[filtered_post_id]"] == "127"
    assert first_payload["settings[element_id]"] == "95dc8a"
    assert first_payload["settings[jsf_signature]"] == (
        "83bc155f208a7b2c473d90a84cf5fe01"
    )
    assert first_payload["indexing_filters[]"] == "434"

    assert scraper.get_html(category_url) == "<div>FB-001 FB-002</div>"
    assert scraper.get_html(page_2) == "<div>FB-026 FB-027</div>"


def test_category_scraper_uses_found_posts_when_max_num_pages_missing():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    responses = {
        category_url: '<body class="tax-product_cat term-127"></body>',
        "ajax:1": '{"found_posts":51,"rendered_content":"<div>page1</div>"}',
        "ajax:2": '{"found_posts":51,"rendered_content":"<div>page2</div>"}',
        "ajax:3": '{"found_posts":51,"rendered_content":"<div>page3</div>"}',
    }
    browser = FakeBrowser(responses)
    scraper = CategoryScraper(browser)

    pages = scraper.get_category_pages(category_url)

    assert pages == [
        category_url,
        f"{category_url.rstrip('/')}?product-page=2",
        f"{category_url.rstrip('/')}?product-page=3",
    ]


def test_category_scraper_does_not_probe_wordpress_when_jsf_metadata_exists():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    responses = {
        category_url: '<body class="tax-product_cat term-127"></body>',
        "ajax:1": (
            '{"found_posts":25,"max_num_pages":1,'
            '"rendered_content":"<div>only</div>"}'
        ),
    }
    browser = FakeBrowser(responses)
    scraper = CategoryScraper(browser)

    assert scraper.get_category_pages(category_url) == [category_url]
    assert browser.get_calls == [category_url]
    assert len(browser.post_calls) == 1


def test_category_scraper_uses_expected_count_to_cover_all_pages():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    responses = {
        category_url: '<body class="tax-product_cat term-127"></body>',
        "ajax:1": (
            '{"found_posts":25,"max_num_pages":1,'
            '"rendered_content":"<div>page1</div>"}'
        ),
        "ajax:2": (
            '{"found_posts":25,"max_num_pages":1,'
            '"rendered_content":"<div>page2</div>"}'
        ),
        "ajax:3": (
            '{"found_posts":25,"max_num_pages":1,'
            '"rendered_content":"<div>page3</div>"}'
        ),
        "ajax:4": (
            '{"found_posts":25,"max_num_pages":1,'
            '"rendered_content":"<div>page4</div>"}'
        ),
    }
    browser = FakeBrowser(responses)
    scraper = CategoryScraper(browser)

    pages = scraper.get_category_pages(category_url, expected_count=82)

    assert pages == [
        category_url,
        f"{category_url.rstrip('/')}?product-page=2",
        f"{category_url.rstrip('/')}?product-page=3",
        f"{category_url.rstrip('/')}?product-page=4",
    ]
    assert [
        next(value for key, value in data if key == "paged")
        for _, data in browser.post_calls
    ] == ["1", "2", "3", "4"]


def test_category_scraper_continues_real_products_past_underreported_jsf_pages():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    responses = {
        category_url: '<body class="archive tax-product_cat term-127"></body>',
        "ajax:1": (
            '{"found_posts":75,"max_num_pages":2,'
            '"rendered_content":"'
            '<ul><li><a href="https://stock.importacionesfacundo.com/producto/fb-001/">'
            'FB-001</a></li></ul>"}'
        ),
        "ajax:2": (
            '{"found_posts":75,"max_num_pages":2,'
            '"rendered_content":"'
            '<ul><li><a href="https://stock.importacionesfacundo.com/producto/fb-026/">'
            'FB-026</a></li></ul>"}'
        ),
        "ajax:3": (
            '{"found_posts":75,"max_num_pages":2,'
            '"rendered_content":"'
            '<ul><li><a href="https://stock.importacionesfacundo.com/producto/fb-051/">'
            'FB-051</a></li></ul>"}'
        ),
        "ajax:4": "",
    }
    browser = FakeBrowser(responses)
    scraper = CategoryScraper(browser)

    pages = scraper.get_category_pages(category_url)

    assert pages == [
        category_url,
        f"{category_url.rstrip('/')}?product-page=2",
        f"{category_url.rstrip('/')}?product-page=3",
    ]
    assert [
        next(value for key, value in data if key == "paged")
        for _, data in browser.post_calls
    ] == ["1", "2", "3", "4"]
    assert scraper.get_html(
        f"{category_url.rstrip('/')}?product-page=3"
    ) == (
        '<ul><li><a href="https://stock.importacionesfacundo.com/producto/fb-051/">'
        "FB-051</a></li></ul>"
    )
