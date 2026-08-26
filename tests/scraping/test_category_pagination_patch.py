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


def test_jsf_payload_uses_requested_page_for_all_pagination_fields():
    payload = dict(CategoryScraper._jet_smart_filters_payload(127, 3))

    assert payload["defaults[paged]"] == "3"
    assert payload["props[page]"] == "3"
    assert payload["paged"] == "3"


def test_jsf_pagination_uses_each_category_count_not_global_total():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    responses = {
        category_url: '<body class="tax-product_cat term-127"></body>',
        "ajax:1": (
            '{"pagination":{"found_posts":25,"max_num_pages":1},'
            '"rendered_content":"<div>page1</div>"}'
        ),
        "ajax:2": (
            '{"pagination":{"found_posts":25,"max_num_pages":1},'
            '"rendered_content":"<div>page2</div>"}'
        ),
        "ajax:3": (
            '{"pagination":{"found_posts":25,"max_num_pages":1},'
            '"rendered_content":"<div>page3</div>"}'
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
    assert [
        next(value for key, value in data if key == "paged")
        for _, data in browser.post_calls
    ] == ["1", "2", "3"]
