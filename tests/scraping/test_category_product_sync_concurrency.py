import threading
import time
from types import SimpleNamespace

from models.scraping.category import Category
from models.scraping.sync_result import SyncResult
from services.scraping.category_product_sync_service import CategoryProductSyncService


class Product:
    def __init__(self, category):
        self.code = f"{category}-1"
        self.name = category
        self.category = category


class FakeBrowser:
    def __init__(self):
        self.thread_sessions_enabled = False

    def enable_thread_sessions(self):
        self.thread_sessions_enabled = True


class ConcurrentCollector:
    def __init__(self):
        self.browser = FakeBrowser()
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def collect_category(self, category):
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            time.sleep(0.05)
            return [(None, category.url, Product(category.name))]
        finally:
            with self.lock:
                self.active -= 1

    def enrich_category_products(self, products, category_name):
        return [item[2] if isinstance(item, tuple) else item for item in products]

    def reset_detail_metrics(self):
        return None

    def get_detail_metrics(self):
        return {}


def test_category_collection_is_parallel_and_keeps_input_order(monkeypatch):
    collector = ConcurrentCollector()
    service = CategoryProductSyncService(
        SimpleNamespace(scraper=collector),
        persistence_service=SimpleNamespace(),
        mapper=None,
        catalog_sync_service=None,
    )
    service.sync_products = lambda products, **kwargs: products
    service._attach_category_coverage = lambda *args: None
    service._full_sync_prune_guard = lambda *args, **kwargs: (False, "directed_mode")
    service._propagate_synced_fields = lambda *args: None
    service._write_final_result_artifact = lambda *args: None
    service._log_detail_metrics = lambda: None
    service._log_http_metrics = lambda: None
    service.last_sync_result = SyncResult()

    categories = [
        Category("A", "https://example.com/a/", expected_count=1),
        Category("B", "https://example.com/b/", expected_count=1),
        Category("C", "https://example.com/c/", expected_count=1),
    ]

    products = service.sync_categories(categories)

    assert collector.browser.thread_sessions_enabled is True
    assert collector.max_active >= 2
    assert [product.category for product in products] == ["A", "B", "C"]
    assert service.last_sync_result.expected_category_occurrences == 3


def test_category_collection_fails_without_hiding_worker_exception():
    class FailingCollector:
        browser = FakeBrowser()

        def collect_category(self, category):
            if category.name == "B":
                raise RuntimeError("B failed")
            return []

    service = CategoryProductSyncService(
        SimpleNamespace(scraper=FailingCollector()),
        persistence_service=SimpleNamespace(),
    )

    categories = [
        Category("A", "https://example.com/a/", expected_count=0),
        Category("B", "https://example.com/b/", expected_count=0),
    ]

    try:
        service.sync_categories(categories)
    except RuntimeError as error:
        assert str(error) == "B failed"
    else:
        raise AssertionError("Expected the category worker exception to propagate")
