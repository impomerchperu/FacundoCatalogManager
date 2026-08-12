from datetime import datetime, timezone

from database.db_manager import DBManager
from models.product import Product
from repositories.product_repository import ProductRepository
from repositories.scraping.scraping_history_repository import ScrapingHistoryRepository
from services.scraping.catalog_sync_service import CatalogSyncService
from services.scraping.product_diff_service import ProductDiffService


def _setup():
    db = DBManager(":memory:")
    products = ProductRepository(db)
    history = ScrapingHistoryRepository(db)
    sync = CatalogSyncService(products, ProductDiffService())
    return db, products, history, sync


def test_catalog_uses_current_products_directly():
    db, products, _, sync = _setup()
    sync.sync([Product(code="TEST-001", name="Producto actual")])
    assert products.get_by_code("TEST-001") is not None
    assert products.get_by_code("TEST-001").name == "Producto actual"
    db.close()


def test_history_stores_new_products_and_field_variations():
    db, _, history, sync = _setup()
    sync.sync([
        Product(
            code="TEST-001",
            name="Producto 1",
            description="Detalle original",
            stock=10,
            price_sample=5.0,
        )
    ])

    result = sync.sync([
        Product(
            code="TEST-001",
            name="Producto 1",
            description="Detalle modificado",
            stock=25,
            price_sample=6.5,
        ),
        Product(code="TEST-002", name="Producto nuevo"),
    ])

    now = datetime.now(timezone.utc)
    from models.scraping.scraping_history import ScrapingHistory

    record = ScrapingHistory(
        started_at=now,
        finished_at=now,
        processed=2,
        created=result.created,
        updated=result.updated,
        unchanged=result.unchanged,
        status="SUCCESS",
    )
    history_id = history.save(record, result.changes)
    changes = history.get_changes(history_id)

    assert result.created == 1
    assert result.updated == 1
    assert {item["type"] for item in changes} == {"NEW", "UPDATED"}

    updated = [item for item in changes if item["type"] == "UPDATED"]
    fields = {item["field"]: (item["old"], item["new"]) for item in updated}
    assert fields["description"] == ("Detalle original", "Detalle modificado")
    assert fields["stock"] == ("10", "25")
    assert fields["price_sample"] == ("5.0", "6.5")

    new_items = [item for item in changes if item["type"] == "NEW"]
    assert len(new_items) == 1
    assert new_items[0]["code"] == "TEST-002"
    db.close()


def test_unchanged_products_are_not_written_to_history():
    db, _, _, sync = _setup()
    sync.sync([Product(code="TEST-001", name="Producto")])
    result = sync.sync([Product(code="TEST-001", name="Producto")])
    assert result.created == 0
    assert result.updated == 0
    assert result.unchanged == 1
    assert result.changes == []
    db.close()
