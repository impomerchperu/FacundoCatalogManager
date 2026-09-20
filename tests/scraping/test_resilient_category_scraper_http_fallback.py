from __future__ import annotations

import requests

from scrapers.collectors.resilient_category_scraper import ResilientCategoryScraper

CATEGORY_URL = "https://stock.importacionesfacundo.com/categoria-producto/enmicadoras-laminadoras/"
SHELL_HTML = """
<html>
  <body class="archive tax-product_cat term-123">
    <div id="products-shell"></div>
  </body>
</html>
"""
CATEGORY_HTML = """
<html>
  <body class="archive tax-product_cat term-123">
    <article>FB-1504</article>
    <article>FB-1503</article>
    <nav class="woocommerce-pagination">
      <a href="/categoria-producto/enmicadoras-laminadoras/page/2/">2</a>
    </nav>
  </body>
</html>
"""


class FailingJsfBrowser:
    def __init__(self) -> None:
        self.get_calls = 0
        self.post_calls = 0

    def get(self, url: str):
        del url
        self.get_calls += 1
        return SHELL_HTML if self.get_calls == 1 else CATEGORY_HTML

    def post(self, url: str, data=None):
        del url, data
        self.post_calls += 1
        response = requests.Response()
        response.status_code = 500
        response.url = "https://stock.importacionesfacundo.com/wp-admin/admin-ajax.php"
        raise requests.HTTPError(response=response)


def test_jsf_http_error_falls_back_to_fresh_category_html():
    browser = FailingJsfBrowser()
    scraper = ResilientCategoryScraper(browser=browser)

    pages = scraper.get_category_pages(CATEGORY_URL)

    assert pages == [
        CATEGORY_URL,
        f"{CATEGORY_URL}page/2/",
    ]
    assert browser.get_calls >= 3
    assert browser.post_calls >= 1
