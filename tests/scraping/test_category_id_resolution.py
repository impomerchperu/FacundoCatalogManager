from scrapers.collectors.category_scraper import CategoryScraper


class FakeBrowser:
    def __init__(self, responses):
        self.responses = responses
        self.post_calls = []

    def get(self, url):
        return self.responses[url]

    def post(self, url, data=None):
        self.post_calls.append((url, data))
        page = next(value for key, value in data if key == "paged")
        return self.responses[f"ajax:{page}"]


def test_category_id_prefers_archive_body_over_sidebar_terms():
    html = """
    <html>
      <body class="archive tax-product_cat term-127">
        <a class="category-link term-999" href="/categoria-producto/otro/">Otro</a>
      </body>
    </html>
    """
    assert CategoryScraper._category_id(html) == 127


def test_jetsmartfilters_uses_resolved_archive_category_id():
    category_url = "https://stock.importacionesfacundo.com/categoria-producto/catalogo/"
    browser = FakeBrowser(
        {
            category_url: '<body class="archive tax-product_cat term-127"></body>',
            "ajax:1": (
                '{"pagination":{"found_posts":25,"max_num_pages":1},'
                '"rendered_content":"<table><tbody><tr><td>FB-001</td></tr></tbody></table>"}'
            ),
        }
    )
    scraper = CategoryScraper(browser)

    assert scraper.get_category_pages(category_url) == [category_url]
    payload = dict(browser.post_calls[0][1])
    assert payload["query[_tax_query_product_cat]"] == "127"
    assert payload["settings[filtered_post_id]"] == "127"
