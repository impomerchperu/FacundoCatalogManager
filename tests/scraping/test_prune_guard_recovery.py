from types import SimpleNamespace

from models.scraping.category import Category
from models.scraping.sync_result import SyncResult
from services.scraping.category_product_sync_service import CategoryProductSyncService
from services.scraping import prune_guard_recovery_patch


class Product:
    def __init__(self, code, category="Categoria A"):
        self.code = code
        self.name = code
        self.category = category


def make_service(terminal_errors):
    browser = SimpleNamespace(
        get_http_metrics=lambda: {"http_terminal_errors": terminal_errors},
    )
    scraper = SimpleNamespace(browser=browser)
    return CategoryProductSyncService(
        scraper_service=SimpleNamespace(scraper=scraper),
        persistence_service=SimpleNamespace(),
    )


def test_recovered_terminal_error_does_not_block_complete_pruning_guard():
    assert prune_guard_recovery_patch._PATCHED is True

    service = make_service(terminal_errors=1)
    service.last_sync_result = SyncResult(
        expected_category_occurrences=2,
        products_found=2,
        products_unique=2,
        category_summary=[
            {
                "category": "Categoria A",
                "expected": 2,
                "products": 2,
                "unique_products": 2,
                "gap": 0,
            },
        ],
    )

    allowed, reason = service._full_sync_prune_guard(
        [Product("P001"), Product("P002")],
        category_count=1,
        expected_category_occurrences=2,
        expected_products=2,
    )

    assert allowed is True
    assert reason == "complete"


def test_terminal_error_still_blocks_when_coverage_is_incomplete():
    service = make_service(terminal_errors=1)
    service.last_sync_result = SyncResult(
        expected_category_occurrences=2,
        products_found=1,
        products_unique=1,
        category_summary=[
            {
                "category": "Categoria A",
                "expected": 2,
                "products": 1,
                "unique_products": 1,
                "gap": 1,
            },
        ],
    )

    allowed, reason = service._full_sync_prune_guard(
        [Product("P001")],
        category_count=1,
        expected_category_occurrences=2,
        expected_products=2,
    )

    assert allowed is False
    assert reason == "category_coverage_gap:Categoria A"


def test_category_coverage_reports_processed_categories():
    categories = [
        Category("Categoria A", "https://example.com/a/", expected_count=1),
        Category("Categoria B", "https://example.com/b/", expected_count=1),
    ]
    service = CategoryProductSyncService(
        scraper_service=SimpleNamespace(),
        persistence_service=SimpleNamespace(),
    )

    service._attach_category_coverage([], [], categories)

    assert service.last_sync_result.categories_processed == 2
