import sqlite3

from models.product import Product
from models.scraping.scraping_history import ScrapingHistory
from services.scraping.scraping_session import ScrapingSession


class FakeDB:
    def __init__(self):
        self.operations = []

    def begin(self):
        self.operations.append("begin")

    def commit(self):
        self.operations.append("commit")

    def rollback(self):
        self.operations.append("rollback")

    def execute_query(self, query, params=()):
        del query, params
        return None


class FakeHistoryRepository:
    def __init__(self, db):
        self.db = db
        self.saved = []

    def save(self, history, changes, products):
        self.saved.append((history, changes, products))
        return 17


class FakeCatalogRepository:
    def __init__(self):
        self.saved = []

    def save(self, product):
        self.saved.append(product)


class IncompleteRunner:
    def __init__(self, products):
        self.products = products

        class Service:
            def __init__(self, result):
                self.last_sync_result = result
                self.catalog_sync_service = None
                self.scraper_service = None

        from models.scraping.sync_result import SyncResult

        result = SyncResult(
            processed=1,
            unchanged=1,
            expected_category_occurrences=2,
            products_found=1,
            products_unique=1,
        )
        result.category_summary = [
            {
                "category": "Categoría A",
                "expected": 2,
                "products": 1,
                "unique_products": 1,
                "gap": 1,
            }
        ]
        self.scraping_service = Service(result)

    def run(self, categories, progress_callback):
        del categories, progress_callback
        return self.products


class FailingRunner:
    def __init__(self):
        from models.scraping.sync_result import SyncResult

        self.scraping_service = type(
            "Service",
            (),
            {
                "last_sync_result": SyncResult(errors=["fallo controlado"]),
                "catalog_sync_service": None,
                "scraper_service": None,
            },
        )()

    def run(self, categories, progress_callback):
        del categories, progress_callback
        raise RuntimeError("fallo controlado")


def test_failure_rolls_back_catalog_transaction_and_keeps_history():
    db = FakeDB()
    history_repository = FakeHistoryRepository(db)
    session = ScrapingSession(
        FailingRunner(),
        history_repository=history_repository,
    )

    result = session.execute(categories=[])

    assert result.status() == "ERROR"
    assert result.errors == ["fallo controlado"]
    assert result.history_id == 17
    assert len(history_repository.saved) == 1
    assert db.operations == ["begin", "rollback", "begin", "commit"]


def test_incomplete_coverage_never_persists_products_to_catalog_repository():
    db = FakeDB()
    history_repository = FakeHistoryRepository(db)
    catalog_repository = FakeCatalogRepository()
    session = ScrapingSession(
        IncompleteRunner([Product()]),
        history_repository=history_repository,
        catalog_repository=catalog_repository,
    )

    result = session.execute(categories=[])

    assert result.status() == "ERROR"
    assert result.success() is False
    assert catalog_repository.saved == []
    assert result.history_id == 17
    assert history_repository.saved[0][1] == []
    assert history_repository.saved[0][0].message == (
        "Descarga finalizada con cobertura incompleta; "
        "cambios del catálogo no aplicados."
    )
    assert db.operations == ["begin", "rollback", "begin", "commit"]
