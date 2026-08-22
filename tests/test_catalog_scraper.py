import threading
import time

from models.scraping.category import Category
from scrapers.collectors.catalog_scraper import CatalogScraper


def test_catalog_scraper_discovers_categories_in_parallel_and_preserves_order():
    categories = [
        Category(name=f"Categoria {index}", url=f"https://example.com/cat/{index}")
        for index in range(3)
    ]
    lock = threading.Lock()
    active_workers = 0
    max_active_workers = 0
    thread_sessions_enabled = False

    class FakeBrowser:
        def enable_thread_sessions(self):
            nonlocal thread_sessions_enabled
            thread_sessions_enabled = True

    class FakeCategoryScraper:
        browser = FakeBrowser()

        def scrape(self, url):
            assert url == "https://example.com/tienda/"
            return categories

        def get_category_pages(self, url, expected_count=0):
            nonlocal active_workers, max_active_workers
            with lock:
                active_workers += 1
                max_active_workers = max(max_active_workers, active_workers)
            try:
                time.sleep(0.03)
                return [f"{url}?product-page=1", f"{url}?product-page=2"]
            finally:
                with lock:
                    active_workers -= 1

    scraper = CatalogScraper(FakeCategoryScraper())

    pages = scraper.scrape_catalog("https://example.com/tienda/")

    assert thread_sessions_enabled is True
    assert max_active_workers >= 2
    assert pages == [
        (categories[0], "https://example.com/cat/0?product-page=1"),
        (categories[0], "https://example.com/cat/0?product-page=2"),
        (categories[1], "https://example.com/cat/1?product-page=1"),
        (categories[1], "https://example.com/cat/1?product-page=2"),
        (categories[2], "https://example.com/cat/2?product-page=1"),
        (categories[2], "https://example.com/cat/2?product-page=2"),
    ]
