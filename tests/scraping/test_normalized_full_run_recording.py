from types import SimpleNamespace

from models.scraping.sync_result import SyncResult
from services.scraping.normalized_category_product_sync_service import (
    NormalizedCategoryProductSyncService,
)


class RecordingNormalizedRepository:
    def __init__(self):
        self.started = []
        self.finished = []
        self.persisted = False

    def start_run(self, **kwargs):
        self.started.append(kwargs)
        return 41

    def finish_run(self, run_id, **kwargs):
        self.finished.append((run_id, kwargs))

    def persist_occurrences(self, *args, **kwargs):
        self.persisted = True
        raise AssertionError("No deben persistirse ocurrencias de un FULL incompleto.")


class RecordingProductRepository:
    def __init__(self):
        self.get_calls = []
        self.saved = False

    def get(self, code):
        self.get_calls.append(code)

    def save(self, _product):
        self.saved = True


class CatalogSync:
    def __init__(self):
        self.repository = RecordingProductRepository()


def _service(repository, catalog_sync):
    service = NormalizedCategoryProductSyncService.__new__(
        NormalizedCategoryProductSyncService
    )
    service.scraper_service = SimpleNamespace(scraper=None)
    service.normalized_repository = repository
    service.catalog_sync_service = catalog_sync
    service.last_sync_result = SyncResult(
        expected_category_occurrences=534,
        products_found=529,
        products_unique=525,
    )
    service.last_sync_result.errors = ["category timeout"]
    service.last_sync_result.category_summary = [
        {
            "category": "Categoria",
            "expected": 534,
            "products": 529,
            "unique_products": 529,
            "gap": 5,
        }
    ]
    service._scraping_mode = "full"
    service._full_sync_coverage_reason = "category_gap:5"
    return service


def test_incomplete_full_creates_error_run_without_persisting_catalog_data():
    repository = RecordingNormalizedRepository()
    catalog_sync = CatalogSync()
    service = _service(repository, catalog_sync)

    service._persist_normalized(
        [type("Category", (), {"name": "Categoria"})()],
        [type("Product", (), {"code": "FB-001"})()],
        mode="full",
    )

    assert repository.started == [
        {
            "mode": "full",
            "categories_requested": 1,
            "expected_category_occurrences": 534,
        }
    ]
    assert repository.persisted is False
    assert catalog_sync.repository.get_calls == []
    assert catalog_sync.repository.saved is False
    assert len(repository.finished) == 1
    run_id, values = repository.finished[0]
    assert run_id == 41
    assert values["actual_category_occurrences"] == 0
    assert values["message"] == "FULL incompleto: category_gap:5"


def test_complete_full_still_persists_after_run_is_started():
    repository = RecordingNormalizedRepository()
    catalog_sync = CatalogSync()
    service = _service(repository, catalog_sync)
    service.last_sync_result = SyncResult(
        expected_category_occurrences=1,
        products_found=1,
        products_unique=1,
    )
    service.last_sync_result.category_summary = [
        {
            "category": "Categoria",
            "expected": 1,
            "products": 1,
            "unique_products": 1,
            "gap": 0,
        }
    ]
    service.last_sync_result.errors = []

    def persist_occurrences(*_args, **_kwargs):
        repository.persisted = True
        return 1

    repository.persist_occurrences = persist_occurrences

    service._persist_normalized(
        [
            type(
                "Category",
                (),
                {
                    "name": "Categoria",
                    "url": "https://example.test/categoria/",
                    "expected_count": 1,
                },
            )()
        ],
        [
            type(
                "Product",
                (),
                {"code": "FB-001", "category": "Categoria"},
            )()
        ],
        mode="full",
    )

    assert repository.started[0]["mode"] == "full"
    assert catalog_sync.repository.get_calls == ["FB-001"]
    assert catalog_sync.repository.saved is True
    assert repository.persisted is True
    assert repository.finished[0][0] == 41
