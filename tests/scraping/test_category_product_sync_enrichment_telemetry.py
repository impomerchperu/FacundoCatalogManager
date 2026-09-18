from types import SimpleNamespace

import services.scraping.category_product_sync_service as module
from models.scraping.category import Category
from services.scraping.category_product_sync_service import CategoryProductSyncService


def test_enrich_category_logs_metrics_per_category(monkeypatch):
    messages = []

    class FakeScraper:
        def enrich_category_products(self, products, category_name):
            return [*products, SimpleNamespace(code=category_name)]

        def get_enrichment_metrics(self, category_name):
            assert category_name == "Categoria A"
            return {
                "requested": 3,
                "skipped": 1,
                "total_seconds": 1.25,
                "submit_seconds": 0.10,
                "wait_seconds": 1.15,
            }

    monkeypatch.setattr(module, "_log_timing", lambda message, *args: messages.append((message, args)))

    service = CategoryProductSyncService(
        SimpleNamespace(scraper=FakeScraper()),
        persistence_service=SimpleNamespace(),
        category_workers=1,
    )
    category = Category("Categoria A", "https://example.com/categoria-a/", expected_count=1)
    original = [SimpleNamespace(code="P-1")]

    result = service._enrich_category(0, category, original)

    assert [item.code for item in result] == ["P-1", "Categoria A"]
    assert messages == [
        (
            "SCRAPING TIMING | stage=category_enrichment_summary | "
            "category=%s | requested=%d | skipped=%d | total_seconds=%.3f | "
            "submit_seconds=%.3f | wait_seconds=%.3f",
            ("Categoria A", 3, 1, 1.25, 0.1, 1.15),
        )
    ]
