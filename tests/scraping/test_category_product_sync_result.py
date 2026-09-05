from models.scraping.sync_result import SyncResult
from services.scraping.category_product_sync_service import CategoryProductSyncService


class FakeMapper:
    def map(self, product):
        return product


class FakeCatalogSyncService:
    def __init__(self):
        self.sync_calls = []
        self.full_sync_calls = []

    def consolidate_products(self, products):
        return products

    def sync(self, products, **kwargs):
        self.sync_calls.append(kwargs)
        result = SyncResult()
        result.products_unique = len(products)
        return result

    def sync_full_catalog(self, products, **kwargs):
        self.full_sync_calls.append(kwargs)
        result = SyncResult()
        result.products_unique = len(products)
        return result


def _build_sync_service(scraper_service=None):
    catalog_sync_service = FakeCatalogSyncService()
    service = CategoryProductSyncService(
        scraper_service or object(),
        persistence_service=None,
        mapper=FakeMapper(),
        catalog_sync_service=catalog_sync_service,
    )
    return service, catalog_sync_service


def test_accumulate_sync_result_does_not_double_count_expectations():
    service = CategoryProductSyncService.__new__(CategoryProductSyncService)
    service.last_sync_result = SyncResult()
    service.last_sync_result.expected_category_occurrences = 61

    result = SyncResult()
    result.expected_category_occurrences = 61
    result.products_found = 61
    result.products_unique = 61
    result.unchanged = 61

    service._accumulate_sync_result(result)

    assert service.last_sync_result.expected_category_occurrences == 61
    assert service.last_sync_result.products_found == 61
    assert service.last_sync_result.products_unique == 61
    assert service.last_sync_result.unchanged == 61
    assert service.last_sync_result.coverage_complete is True


def test_directed_category_sync_never_prunes_catalog():
    class FakeScraper:
        def scrape_category(self, url, category=""):
            return ["producto-1"]

    service, catalog_sync_service = _build_sync_service(FakeScraper())

    service.sync_category("https://example.test/categoria", "Categoría")

    assert catalog_sync_service.full_sync_calls == []
    assert len(catalog_sync_service.sync_calls) == 1
    assert catalog_sync_service.sync_calls[0]["prune_missing"] is False


def test_full_sync_with_incomplete_coverage_never_prunes_catalog():
    service, catalog_sync_service = _build_sync_service()
    service._scraping_mode = "full"

    service.sync_products(
        ["producto-1"],
        full_sync=True,
        allow_prune=False,
        expected_products=2,
        expected_category_occurrences=2,
    )

    assert catalog_sync_service.full_sync_calls == []
    assert len(catalog_sync_service.sync_calls) == 1
    assert catalog_sync_service.sync_calls[0]["prune_missing"] is False
    assert catalog_sync_service.sync_calls[0]["expected_products"] == 2


def test_full_sync_with_complete_coverage_uses_pruning_path():
    service, catalog_sync_service = _build_sync_service()
    service._scraping_mode = "full"

    service.sync_products(
        ["producto-1", "producto-2"],
        full_sync=True,
        allow_prune=True,
        expected_products=2,
        expected_category_occurrences=2,
    )

    assert catalog_sync_service.sync_calls == []
    assert len(catalog_sync_service.full_sync_calls) == 1
    assert catalog_sync_service.full_sync_calls[0]["expected_products"] == 2
    assert (
        catalog_sync_service.full_sync_calls[0]["expected_category_occurrences"]
        == 2
    )


def test_prune_guard_rejects_missing_expected_category_occurrences():
    service, _ = _build_sync_service()

    complete, reason = service._full_sync_prune_guard(
        ["producto-1"],
        category_count=1,
        expected_category_occurrences=0,
        expected_products=1,
    )

    assert complete is False
    assert reason == "no_expected_category_occurrences"


def test_prune_guard_rejects_category_undercoverage_even_when_total_matches():
    service, _ = _build_sync_service()
    service.last_sync_result.category_summary = [
        {
            "category": "Categoría A",
            "expected": 3,
            "products": 2,
            "unique_products": 2,
            "gap": 1,
        },
        {
            "category": "Categoría B",
            "expected": 2,
            "products": 3,
            "unique_products": 3,
            "gap": 0,
        },
    ]

    complete, reason = service._full_sync_prune_guard(
        ["producto-1", "producto-2", "producto-3", "producto-4", "producto-5"],
        category_count=2,
        expected_category_occurrences=5,
        expected_products=5,
    )

    assert complete is False
    assert reason == "category_coverage_gap:Categoría A"


def test_prune_guard_rejects_duplicate_category_occurrences():
    service, _ = _build_sync_service()
    service.last_sync_result.category_summary = [
        {
            "category": "Categoría",
            "expected": 2,
            "products": 3,
            "unique_products": 2,
            "gap": 0,
        }
    ]

    complete, reason = service._full_sync_prune_guard(
        ["producto-1", "producto-2", "producto-3"],
        category_count=1,
        expected_category_occurrences=2,
        expected_products=2,
    )

    assert complete is False
    assert reason == "category_coverage_gap:Categoría"
