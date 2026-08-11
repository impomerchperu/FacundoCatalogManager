from datetime import datetime, timedelta, timezone

from database.db_manager import DBManager
from models.product import Product
from repositories.scraping.catalog_load_repository import CatalogLoadRepository


def _create_load(repository: CatalogLoadRepository, code: str, name: str) -> int:
    product = Product(
        code=code,
        name=name,
        category="Prueba",
        description="Detalle",
    )
    return repository.create_from_products([product])


def test_only_loads_after_latest_applied_can_be_applied():
    db = DBManager(":memory:")
    repository = CatalogLoadRepository(db)

    first = _create_load(repository, "TEST-001", "Producto 1")
    second = _create_load(repository, "TEST-002", "Producto 2")

    assert repository.apply(first) is True
    assert repository.apply(first) is True
    assert repository.apply(second) is True
    assert repository.apply(first) is False

    latest = repository.get_latest_applied()
    assert latest is not None
    assert int(latest["id"]) == second
    assert latest["applied_at"] is not None

    db.close()


def test_catalog_action_states_follow_latest_applied():
    db = DBManager(":memory:")
    repository = CatalogLoadRepository(db)

    first = _create_load(repository, "TEST-001", "Producto 1")
    second = _create_load(repository, "TEST-002", "Producto 2")

    assert repository.get_catalog_action(first)[0] == "APLICAR"
    assert repository.get_catalog_action(second)[0] == "APLICAR"

    repository.apply(first)

    action, applied_at = repository.get_catalog_action(first)
    assert action == "APLICADO"
    assert applied_at is not None
    assert repository.get_catalog_action(second)[0] == "APLICAR"

    repository.apply(second)

    # La primera carga fue aplicada anteriormente y conserva su auditoría.
    action, applied_at = repository.get_catalog_action(first)
    assert action == "APLICADO"
    assert applied_at is not None

    assert repository.get_catalog_action(second)[0] == "APLICADO"

    db.close()


def test_pending_load_before_latest_applied_becomes_not_applied():
    db = DBManager(":memory:")
    repository = CatalogLoadRepository(db)

    first = _create_load(repository, "TEST-001", "Producto 1")
    pending = _create_load(repository, "TEST-002", "Producto 2")
    latest = _create_load(repository, "TEST-003", "Producto 3")

    repository.apply(first)
    repository.apply(latest)

    assert repository.get_catalog_action(pending) == ("NO_APLICADO", None)
    assert repository.get_catalog_action(latest)[0] == "APLICADO"

    db.close()


def test_applied_load_keeps_application_timestamp():
    db = DBManager(":memory:")
    repository = CatalogLoadRepository(db)

    load_id = _create_load(repository, "TEST-001", "Producto 1")
    assert repository.apply(load_id) is True

    load = repository.get_by_id(load_id)
    assert load is not None
    assert int(load["applied"]) == 1
    assert load["applied_at"] is not None

    parsed = datetime.fromisoformat(load["applied_at"])
    assert parsed.tzinfo is not None

    db.close()


def test_load_details_report_new_and_updated_fields():
    db = DBManager(":memory:")
    repository = CatalogLoadRepository(db)

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
    assert updated["name"] == "Producto 1"

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


def test_cleanup_is_opt_in_and_preserves_history_by_default():
    db = DBManager(":memory:")
    repository = CatalogLoadRepository(db)

    load_id = _create_load(repository, "TEST-001", "Producto antiguo")
    old_date = (
        datetime.now(timezone.utc) - timedelta(days=8)
    ).isoformat()
    db.execute_query(
        "UPDATE catalog_loads SET created_at = ? WHERE id = ?",
        (old_date, load_id),
    )

    assert repository.cleanup_expired_history() == 0
    assert repository.get_by_id(load_id) is not None

    db.close()


def test_explicit_cleanup_removes_old_history():
    db = DBManager(":memory:")
    repository = CatalogLoadRepository(db)

    old = _create_load(repository, "TEST-001", "Producto antiguo")
    current = _create_load(repository, "TEST-002", "Producto actual")
    repository.apply(current)

    old_date = (
        datetime.now(timezone.utc) - timedelta(days=8)
    ).isoformat()
    db.execute_query(
        "UPDATE catalog_loads SET created_at = ? WHERE id = ?",
        (old_date, old),
    )
    db.execute_query(
        "UPDATE scraping_history SET started_at = ? WHERE load_id = ?",
        (old_date, old),
    )

    repository.cleanup_expired_history(retention_days=7)

    assert repository.get_by_id(old) is None
    assert repository.get_by_id(current) is not None

    db.close()
