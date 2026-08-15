from datetime import datetime, timezone

from database.db_manager import DBManager
from models.product import Product
from models.scraping.scraping_history import ScrapingHistory
from repositories.scraping.scraping_history_repository import ScrapingHistoryRepository


def _history() -> ScrapingHistory:
    now = datetime.now(timezone.utc)
    return ScrapingHistory(
        started_at=now,
        finished_at=now,
        processed=2,
        created=1,
        updated=1,
        unchanged=0,
        errors=0,
        status="SUCCESS",
        message="Descarga completada y cambios aplicados automáticamente.",
    )


def test_history_stores_only_detected_changes():
    db = DBManager(":memory:")
    repository = ScrapingHistoryRepository(db)
    products = [
        Product(
            code="TEST-001",
            name="Producto 1",
            description="Detalle modificado",
            stock=25,
            price_sample=6.5,
        ),
        Product(
            code="TEST-002",
            name="Producto nuevo",
            category="Nueva",
            description="Nuevo artículo",
            stock=10,
        ),
    ]
    changes = [
        {
            "type": "UPDATED",
            "code": "TEST-001",
            "name": "Producto 1",
            "changes": [
                {
                    "field": "description",
                    "label": "Detalle",
                    "old": "Detalle original",
                    "new": "Detalle modificado",
                },
                {"field": "stock", "label": "Stock", "old": 10, "new": 25},
                {
                    "field": "price_sample",
                    "label": "Precio muestra",
                    "old": 5.0,
                    "new": 6.5,
                },
            ],
        },
        {
            "type": "NEW",
            "code": "TEST-002",
            "name": "Producto nuevo",
            "changes": [],
        },
    ]

    history_id = repository.save(_history(), changes, products)
    stored = repository.get_changes(history_id)

    updated = [item for item in stored if item["type"] == "UPDATED"]
    assert {(item["field"], item["old"], item["new"]) for item in updated} == {
        ("description", "Detalle original", "Detalle modificado"),
        ("stock", 10, 25),
        ("price_sample", 5.0, 6.5),
    }

    new_fields = [item for item in stored if item["type"] == "NEW"]
    assert {item["field"] for item in new_fields} >= {
        "name",
        "category",
        "description",
        "stock",
    }
    assert all(item["old"] is None for item in new_fields)
    db.close()


def test_history_records_finished_time_as_application_time():
    db = DBManager(":memory:")
    repository = ScrapingHistoryRepository(db)
    history = _history()
    history_id = repository.save(history, [], [])

    stored = repository.get_by_id(history_id)
    assert stored is not None
    assert stored.finished_at == history.finished_at
    assert stored.status == "SUCCESS"
    db.close()
