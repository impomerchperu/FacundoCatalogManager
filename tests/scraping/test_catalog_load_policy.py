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

    assert repository.get_catalog_action(first)[0] == "APLICADO"
    assert repository.get_catalog_action(second)[0] == "APLICAR"

    repository.apply(second)

    assert repository.get_catalog_action(first)[0] == "NO_APLICADO"
    assert repository.get_catalog_action(second)[0] == "APLICADO"

    db.close()


def test_cleanup_preserves_latest_applied_load_and_removes_old_history():
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

    repository.cleanup_expired_history()

    assert repository.get_by_id(old) is None
    assert repository.get_by_id(current) is not None

    db.close()
