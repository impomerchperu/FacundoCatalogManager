import threading
import time
from concurrent.futures import ThreadPoolExecutor

from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.collectors.jsf_concurrency_patch import JSF_HTTP_CONCURRENCY


class SlowBrowser:
    def __init__(self):
        self.in_flight = 0
        self.max_in_flight = 0
        self.lock = threading.Lock()

    def post(self, url, data=None):
        del url, data
        with self.lock:
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            time.sleep(0.03)
            return "{}"
        finally:
            with self.lock:
                self.in_flight -= 1


def test_jsf_requests_are_throttled_without_reducing_category_workers():
    browser = SlowBrowser()
    scraper = CategoryScraper(browser)

    with ThreadPoolExecutor(max_workers=12) as executor:
        list(executor.map(scraper._post_jsf, [[] for _ in range(12)]))

    assert browser.max_in_flight <= JSF_HTTP_CONCURRENCY
    assert browser.max_in_flight == JSF_HTTP_CONCURRENCY
