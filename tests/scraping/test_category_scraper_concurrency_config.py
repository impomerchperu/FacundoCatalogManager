import threading
import time

import pytest

from scrapers.collectors.category_scraper import CategoryScraper


class ConcurrentBrowser:
    def __init__(self, responses):
        self.responses = responses
        self.active = 0
        self.max_active = 0
        self._lock = threading.Lock()

    def get(self, url):
        return self.responses[url]

    def post(self, url, data=None):
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            time.sleep(0.02)
            page = next(value for key, value in data if key == "paged")
            response = self.responses[f"ajax:{page}"]
            if isinstance(response, Exception):
                raise response
            return response
        finally:
            with self._lock:
                self.active -= 1


def _responses(category_url):
    payloads = {
        1: '{"found_posts":75,"max_num_pages":3,"rendered_content":"<div>FB-001</div>"}',
        2: '{"found_posts":75,"max_num_pages":3,"rendered_content":"<div>FB-026</div>"}',
        3: '{"found_posts":75,"max_num_pages":3,"rendered_content":"<div>FB-051</div>"}',
        4: "",
    }
    return {
        category_url: '<body class="tax-product_cat term-127"></body>',
        **{f"ajax:{page}": payload for page, payload in payloads.items()},
    }


def test_category_scraper_configures_jsf_http_concurrency_per_instance():
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    browser = ConcurrentBrowser(_responses(category_url))
    scraper = CategoryScraper(browser, jsf_http_concurrency=1)

    pages = scraper.get_category_pages(category_url, expected_count=75)

    assert pages == [
        category_url,
        f"{category_url.rstrip('/')}?product-page=2",
        f"{category_url.rstrip('/')}?product-page=3",
    ]
    assert browser.max_active == 1


def test_category_scraper_rejects_non_positive_jsf_http_concurrency():
    with pytest.raises(ValueError, match="jsf_http_concurrency"):
        CategoryScraper(object(), jsf_http_concurrency=0)
