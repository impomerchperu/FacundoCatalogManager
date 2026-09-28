from datetime import datetime, timezone

from database.db_manager import DBManager
from models.product import Product
from models.scraping.scraping_history import ScrapingHistory
from repositories.scraping.scraping_history_repository import ScrapingHistoryRepository
from services.scraping.catalog_sync_service import CatalogSyncService
from services.scraping.product_diff_service import ProductDiffService


class LookupAwareRepository:
    def __init__(self):
        self.records = {}
        self.get_calls = 0
        self.save_calls = 0
        self.save_with_existing_calls = 0

    def get(self, code):
        self.get_calls += 1
        return self.records.get(str(code).strip().upper())

    def save(self, product):
        self.save_calls += 1
        self.records[str(product.code).strip().upper()] = product
        return product

    def save_with_existing(self, product, existing=None):
        self.save_with_existing_calls += 1
        if existing is not None:
            product.product_id = existing.product_id
        self.records[str(product.code).strip().upper()] = product
        return product

    def get_all(self):
        return list(self.records.values())

    def delete_by_code(self, code):
        self.records.pop(str(code).strip().upper(), None)


def test_catalog_sync_reuses_existing_lookup_when_repository_supports_it():
    repository = LookupAwareRepository()
    service = CatalogSyncService(repository, ProductDiffService())

    first = service.synchronize(
        [Product(code="EFF-001", name="Producto", price=10)]
    )
    second = service.synchronize(
        [Product(code="EFF-001", name="Producto actualizado", price=12)]
    )

    assert first.created == 1
    assert second.updated == 1
    assert repository.get_calls == 2
    assert repository.save_with_existing_calls == 2
    assert repository.save_calls == 0


def test_history_change_persistence_batches_rows():
    db = DBManager(":memory:")
    repository = ScrapingHistoryRepository(db)
    calls = []
    original_execute_many = db.execute_many

    def execute_many(query, params_seq=()):
        params = list(params_seq)
        calls.append(len(params))
        return original_execute_many(query, params)

    db.execute_many = execute_many

    finished_at = datetime(2026, 9, 27, 21, 0, tzinfo=timezone.utc)
    history = ScrapingHistory(
        started_at=datetime(2026, 9, 27, 20, 59, tzinfo=timezone.utc),
        finished_at=finished_at,
        processed=2,
        created=1,
        updated=1,
        status="SUCCESS",
        errors=0,
    )
    products = [
        Product(
            code="EFF-001",
            name="Producto nuevo",
            price=10,
            description="Detalle",
            stock=5,
        )
    ]
    changes = [
        {
            "type": "UPDATED",
            "code": "EFF-002",
            "name": "Producto actualizado",
            "changes": [
                {"field": "stock", "label": "Stock", "old": 1, "new": 2},
                {"field": "price", "label": "Precio", "old": 5, "new": 6},
            ],
        },
        {
            "type": "NEW",
            "code": "EFF-001",
            "name": "Producto nuevo",
            "changes": [],
        },
    ]

    history_id = repository.save(history, changes, products)
    stored = repository.get_changes(history_id)

    assert calls == [2 + len(ScrapingHistoryRepository.PRODUCT_FIELDS)]
    assert len(stored) == calls[0]
    db.close()
