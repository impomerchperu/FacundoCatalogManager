from database.db_manager import DBManager
from services.catalog_bootstrap_service import CatalogBootstrapService


def test_restore_from_change_history_populates_empty_catalog(tmp_path):
    db = DBManager(str(tmp_path / "catalog.db"))
    db.execute_query(
        """
        INSERT INTO scraping_history (
            started_at, finished_at, processed, created, status, message
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("2026-08-14 10:00:00", "2026-08-14 10:01:00", 1, 1, "SUCCESS", "ok"),
    )
    history_id = db.fetch_one("SELECT id FROM scraping_history ORDER BY id DESC LIMIT 1")[
        "id"
    ]
    changes = [
        (history_id, "NEW", "BOOT001", "Producto inicial", "category", "General"),
        (history_id, "NEW", "BOOT001", "Producto inicial", "stock", "12"),
        (history_id, "NEW", "BOOT001", "Producto inicial", "price_sample", "4.50"),
        (
            history_id,
            "NEW",
            "BOOT001",
            "Producto inicial",
            "color_stock",
            '{"Rojo": 12}',
        ),
    ]
    db.connection.executemany(
        """
        INSERT INTO download_changes (
            history_id, change_type, code, product_name, field_name,
            field_label, new_value
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [row + (row[4],) for row in changes],
    )
    db.commit()

    service = CatalogBootstrapService(db=db)
    assert service.product_count() == 0

    restored = service.restore_from_change_history()

    assert restored == 1
    product = db.fetch_one("SELECT * FROM products WHERE code=?", ("BOOT001",))
    assert product["name"] == "Producto inicial"
    assert product["category"] == "General"
    assert product["stock"] == 12
    assert product["price_sample"] == 4.5
    assert product["color_stock"] == '{"Rojo": 12}'
    assert service.is_initialized() is True

    db.close()


def test_restore_from_change_history_does_not_overwrite_existing_catalog(tmp_path):
    db = DBManager(str(tmp_path / "catalog.db"))
    db.execute_query(
        "INSERT INTO products (code, name) VALUES (?, ?)",
        ("EXIST001", "Producto existente"),
    )

    service = CatalogBootstrapService(db=db)

    assert service.restore_from_change_history() == 0
    assert service.product_count() == 1
    assert service.is_initialized() is False

    db.close()


def test_bootstrap_never_starts_web_scraping(tmp_path):
    db = DBManager(str(tmp_path / "catalog.db"))
    service = CatalogBootstrapService(db=db)

    assert service.bootstrap() is None
    assert service.product_count() == 0

    db.close()
