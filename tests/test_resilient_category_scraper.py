import pytest

from scrapers.collectors.resilient_category_scraper import (
    ResilientCategoryScraper,
)


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


def test_resilient_scraper_falls_back_to_server_rendered_category():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/enmicadoras-laminadoras/"
    )
    responses = {
        category_url: (
            '<body class="archive tax-product_cat term-127">'
            "<div>FB-1504 FB-1503</div>"
            "</body>"
        ),
        "ajax:1": (
            '{"pagination":{"found_posts":9,"max_num_pages":1},'
            '"rendered_content":""}'
        ),
    }
    scraper = ResilientCategoryScraper(FakeBrowser(responses))

    assert scraper.get_category_pages(category_url) == [category_url]


def test_resilient_scraper_retries_empty_jsf_before_raising():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/enmicadoras-laminadoras/"
    )
    responses = {
        category_url: '<body class="archive tax-product_cat term-127"></body>',
        "ajax:1": (
            '{"pagination":{"found_posts":9,"max_num_pages":1},'
            '"rendered_content":""}'
        ),
    }
    browser = FakeBrowser(responses)
    scraper = ResilientCategoryScraper(browser)

    with pytest.raises(RuntimeError, match="no devolvió contenido"):
        scraper.get_category_pages(category_url)

    assert len(browser.post_calls) == 3
