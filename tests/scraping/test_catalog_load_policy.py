from datetime import datetime, timedelta, timezone

from database.db_manager import DBManager
from models.product import Product
from repositories.scraping.catalog_load_repository import CatalogLoadRepository


def _repository() -> tuple[DBManager, CatalogLoadRepository]:
    db = DBManager(":memory:")
    return db, CatalogLoadRepository(db)


def _create_load(repository: CatalogLoadRepository, code: str) -> int:
    return repository.create_from_products(
        [
            Product(
                code=code,
                name=f"Producto {code}",
                category="Prueba",
                description="Detalle",
            ),
        ],
    )


def test_catalog_starts_from_latest_applied_version():
    db, repository = _repository()
    first = _create_load(repository, "TEST-001")
    second = _create_load(repository, "TEST-002")

    assert repository.apply(first) is True
    latest = repository.get_latest_applied()
    assert latest is not None
    assert int(latest["id"]) == first
    assert repository.get_catalog_action(second) == ("APLICAR", None)
    db.close()


def test_history_matches_applied_superseded_and_pending_states():
    db, repository = _repository()
    load_1 = _create_load(repository, "TEST-001")
    load_2 = _create_load(repository, "TEST-002")
    load_3 = _create_load(repository, "TEST-003")
    load_4 = _create_load(repository, "TEST-004")

    assert repository.apply(load_1) is True
    first = repository.get_by_id(load_1)
    assert first is not None
    first_applied_at = first["applied_at"]
    assert first_applied_at is not None

    assert repository.get_catalog_action(load_2) == ("APLICAR", None)
    assert repository.apply(load_3) is True

    assert repository.get_catalog_action(load_1) == (
        "APLICADO",
        first_applied_at,
    )
    assert repository.get_catalog_action(load_2) == ("NO_APLICADO", None)
    assert repository.get_catalog_action(load_3)[0] == "APLICADO"
    assert repository.get_catalog_action(load_4) == ("APLICAR", None)
    assert repository.apply(load_2) is False
    db.close()


def test_each_applied_download_keeps_its_own_timestamp():
    db, repository = _repository()
    first = _create_load(repository, "TEST-001")
    second = _create_load(repository, "TEST-002")

    assert repository.apply(first) is True
    first_record = repository.get_by_id(first)
    assert first_record is not None
    first_timestamp = first_record["applied_at"]
    assert first_timestamp is not None

    assert repository.apply(second) is True
    first_after = repository.get_by_id(first)
    second_after = repository.get_by_id(second)
    assert first_after is not None
    assert second_after is not None
    assert first_after["applied_at"] == first_timestamp
    assert second_after["applied_at"] is not None
    assert second_after["applied_at"] != first_timestamp
    assert datetime.fromisoformat(first_timestamp).tzinfo is not None
    db.close()


def test_load_details_report_new_and_updated_variations():
    db, repository = _repository()
    first = repository.create_from_products(
        [
            Product(
                code="TEST-001",
                name="Producto 1",
                category="Prueba",
                description="Detalle original",
                stock=10,
                price_sample=5.0,
            ),
        ],
    )
    second = repository.create_from_products(
        [
            Product(
                code="TEST-001",
                name="Producto 1",
                category="Prueba",
                description="Detalle modificado",
                stock=25,
                price_sample=6.5,
            ),
            Product(
                code="TEST-002",
                name="Producto nuevo",
                category="Nueva",
                description="Nuevo artículo",
            ),
        ],
    )

    assert first < second
    changes = repository.get_load_changes(second)
    assert [item["type"] for item in changes] == ["UPDATED", "NEW"]

    updated = changes[0]
    assert updated["code"] == "TEST-001"
    changed_fields = {
        change["field"]: (change["old"], change["new"])
        for change in updated["changes"]
    }
    assert changed_fields["description"] == (
        "Detalle original",
        "Detalle modificado",
    )
    assert changed_fields["stock"] == (10, 25)
    assert changed_fields["price_sample"] == (5.0, 6.5)

    new_product = changes[1]
    assert new_product["type"] == "NEW"
    assert new_product["code"] == "TEST-002"
    assert new_product["name"] == "Producto nuevo"
    assert new_product["changes"] == []
    db.close()


def test_history_is_preserved_without_explicit_cleanup():
    db, repository = _repository()
    load_id = _create_load(repository, "TEST-001")
    old_date = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    db.execute_query(
        "UPDATE catalog_loads SET created_at = ? WHERE id = ?",
        (old_date, load_id),
    )

    assert repository.cleanup_expired_history() == 0
    assert repository.get_by_id(load_id) is not None
    db.close()
