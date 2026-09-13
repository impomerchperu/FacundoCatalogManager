from scrapers.collectors.category_scraper import CategoryScraper


def test_category_scraper_probes_pages_when_pagination_is_hidden():
    category_url = "https://example.com/categoria-producto/jarros-mug/"
    page_2_url = f"{category_url}page/2/"
    page_3_url = f"{category_url}page/3/"

    html_by_url = {
        category_url: "<article>FB-1000-AZ producto 1</article>",
        page_2_url: "<article>FB-1001-AZ producto 2</article>",
        page_3_url: "<article>FB-1002-AZ producto 3</article>",
    }

    class FakeBrowser:
        def get(self, url):
            return html_by_url.get(url, "")

    pages = CategoryScraper(FakeBrowser()).get_category_pages(category_url)

    assert pages == [category_url, page_2_url, page_3_url]


def test_category_scraper_expands_declared_total_pages():
    category_url = "https://example.com/categoria-producto/jarros-mug/"
    page_2_url = f"{category_url}page/2/"
    page_3_url = f"{category_url}page/3/"

    class FakeBrowser:
        def get(self, url):
            if url == category_url:
                return '<script>const totalPages = 3;</script>'
            if url == page_2_url:
                return '<article>FB-1001-AZ producto 2</article>'
            if url == page_3_url:
                return '<article>FB-1002-AZ producto 3</article>'
            return ""

    pages = CategoryScraper(FakeBrowser()).get_category_pages(category_url)

    assert page_2_url in pages
    assert page_3_url in pages


def test_category_scraper_bounds_hidden_probes_by_expected_count():
    category_url = "https://example.com/categoria-producto/jarros-mug/"
    page_2_url = f"{category_url}page/2/"
    page_3_url = f"{category_url}page/3/"
    page_4_url = f"{category_url}page/4/"

    class FakeBrowser:
        def __init__(self):
            self.calls = []

        def get(self, url):
            self.calls.append(url)
            if url == category_url:
                return "<article>FB-1000-AZ producto 1</article>"
            return {
                page_2_url: "<article>FB-1001-AZ producto 2</article>",
                page_3_url: "<article>FB-1002-AZ producto 3</article>",
                page_4_url: "<article>FB-1003-AZ producto 4</article>",
            }.get(url, "")

    browser = FakeBrowser()
    pages = CategoryScraper(browser).get_category_pages(
        category_url,
        expected_count=75,
    )

    assert pages == [category_url, page_2_url, page_3_url]
    assert page_4_url not in browser.calls
