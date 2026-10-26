from database.db_manager import DBManager
from models.product import Product
from repositories.product_repository import ProductRepository


def test_database_connection():

    db = DBManager(":memory:")

    db.initialize_database()

    db.execute_query("DELETE FROM products")

    db.execute_query(
        """
        INSERT INTO products
        (
            code,
            name,
            category,
            description,
            price,
            stock,
            image_path
        )

        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "TEST001",
            "Producto de prueba",
            "General",
            "Primer registro del catálogo",
            25.50,
            10,
            "",
        ),
    )

    products = db.fetch_all(
        """
        SELECT *
        FROM products
        WHERE code=?
        """,
        ("TEST001",),
    )

    assert len(products) == 1

    assert products[0]["code"] == "TEST001"

    db.close()


def test_normalized_scraping_schema():
    db = DBManager(":memory:")

    expected_tables = {
        "categories",
        "product_categories",
        "scraping_runs",
        "scraping_product_occurrences",
        "scraping_run_categories",
        "scraping_run_history",
    }
    rows = db.fetch_all(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        """
    )

    assert expected_tables <= {row["name"] for row in rows}

    db.execute_query(
        """
        INSERT INTO products (code, name)
        VALUES (?, ?)
        """,
        ("TEST-NORMALIZED", "Producto normalizado"),
    )
    product_id = db.fetch_one(
        "SELECT id FROM products WHERE code=?",
        ("TEST-NORMALIZED",),
    )["id"]

    db.execute_query(
        """
        INSERT INTO categories (name, canonical_url, expected_count)
        VALUES (?, ?, ?)
        """,
        (
            "Categoría de prueba",
            "https://stock.importacionesfacundo.com/categoria-producto/prueba/",
            25,
        ),
    )
    category_id = db.fetch_one(
        "SELECT id FROM categories WHERE canonical_url=?",
        ("https://stock.importacionesfacundo.com/categoria-producto/prueba/",),
    )["id"]

    db.execute_query(
        """
        INSERT INTO product_categories (product_id, category_id)
        VALUES (?, ?)
        """,
        (product_id, category_id),
    )

    db.execute_query(
        """
        INSERT INTO scraping_runs
        (started_at, mode, status, categories_requested)
        VALUES (?, ?, ?, ?)
        """,
        ("2026-09-05T00:00:00+00:00", "directed", "RUNNING", 1),
    )
    run_id = db.fetch_one(
        "SELECT id FROM scraping_runs ORDER BY id DESC LIMIT 1"
    )["id"]

    db.execute_query(
        """
        INSERT INTO scraping_product_occurrences
        (run_id, category_id, product_id, code, product_url, page_number, position)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            category_id,
            product_id,
            "TEST-NORMALIZED",
            "https://stock.importacionesfacundo.com/producto/test-normalized/",
            2,
            7,
        ),
    )

    relation = db.fetch_one(
        """
        SELECT p.code, c.name, o.page_number, o.position
        FROM scraping_product_occurrences o
        JOIN products p ON p.id = o.product_id
        JOIN categories c ON c.id = o.category_id
        WHERE o.run_id=?
        """,
        (run_id,),
    )

    assert relation["code"] == "TEST-NORMALIZED"
    assert relation["name"] == "Categoría de prueba"
    assert relation["page_number"] == 2
    assert relation["position"] == 7

    db.close()


def test_execute_many_persists_multiple_rows():
    db = DBManager(":memory:")

    db.execute_many(
        "INSERT INTO products (code, name) VALUES (?, ?)",
        [
            ("BATCH-001", "Producto 1"),
            ("BATCH-002", "Producto 2"),
        ],
    )

    rows = db.fetch_all(
        "SELECT code FROM products WHERE code LIKE 'BATCH-%' ORDER BY code"
    )

    assert [row["code"] for row in rows] == ["BATCH-001", "BATCH-002"]
    db.close()


def test_product_repository_round_trips_all_catalog_prices():
    db = DBManager(":memory:")
    db.initialize_database()
    repository = ProductRepository(db)

    product = Product(
        code="PRICE001",
        name="Producto con precios",
        price=8.50,
        price_sample=8.50,
        price_hundred=770.00,
        price_thousand=7500.00,
    )

    repository.create(product)
    stored = repository.get_by_code("PRICE001")

    assert stored is not None
    assert stored.price == 8.50
    assert stored.price_sample == 8.50
    assert stored.price_hundred == 770.00
    assert stored.price_thousand == 7500.00

    product.price = 9.25
    product.price_sample = 9.25
    product.price_hundred = 820.00
    product.price_thousand = 7900.00
    repository.update(product)

    updated = repository.get_by_code("PRICE001")
    assert updated is not None
    assert updated.price == 9.25
    assert updated.price_sample == 9.25
    assert updated.price_hundred == 820.00
    assert updated.price_thousand == 7900.00

    db.close()


def test_database_schema_migration_ledger_records_current_version():
    db = DBManager(":memory:")

    row = db.fetch_one(
        "SELECT version, description FROM schema_migrations ORDER BY version DESC LIMIT 1"
    )

    assert row is not None
    assert row["version"] == DBManager.SCHEMA_VERSION
    assert row["description"]

    db.close()


def test_database_rejects_newer_schema_version():
    db = DBManager(":memory:")
    db.execute_query(
        """
        INSERT INTO schema_migrations (version, applied_at, description)
        VALUES (?, CURRENT_TIMESTAMP, ?)
        """,
        (DBManager.SCHEMA_VERSION + 1, "future"),
    )

    try:
        db._run_migrations()
    except RuntimeError as error:
        assert "versión más nueva" in str(error)
    else:
        raise AssertionError("Se esperaba rechazo de una versión futura.")

    db.close()


def test_scraping_run_history_enforces_one_to_one_execution_link():
    db = DBManager(":memory:")

    db.execute_query(
        """
        INSERT INTO categories (name, canonical_url)
        VALUES ('Categoría vínculo', 'category-link')
        """
    )
    db.execute_query(
        """
        INSERT INTO scraping_runs (started_at, mode, status, categories_requested)
        VALUES (?, 'directed', 'SUCCESS', 1)
        """,
        ("2026-09-20T00:00:00+00:00",),
    )
    run_id = db.fetch_one(
        "SELECT id FROM scraping_runs ORDER BY id DESC LIMIT 1"
    )["id"]

    db.execute_query(
        """
        INSERT INTO scraping_history
            (started_at, finished_at, status, message)
        VALUES (?, ?, 'SUCCESS', 'Aplicado')
        """,
        (
            "2026-09-20T00:00:00+00:00",
            "2026-09-20T00:00:01+00:00",
        ),
    )
    history_id = db.fetch_one(
        "SELECT id FROM scraping_history ORDER BY id DESC LIMIT 1"
    )["id"]

    db.execute_query(
        """
        INSERT INTO scraping_run_history (run_id, history_id)
        VALUES (?, ?)
        """,
        (run_id, history_id),
    )

    relation = db.fetch_one(
        """
        SELECT run_id, history_id
        FROM scraping_run_history
        WHERE run_id=?
        """,
        (run_id,),
    )

    assert relation["run_id"] == run_id
    assert relation["history_id"] == history_id

    db.close()


def test_database_migrates_v2_run_history_relationship_from_v1():
    db = DBManager(":memory:")

    db.execute_query(
        "DROP TABLE scraping_run_history"
    )
    db.execute_query(
        "DELETE FROM schema_migrations WHERE version >= 2"
    )

    assert db.fetch_one(
        """
        SELECT COUNT(*) AS n
        FROM sqlite_master
        WHERE type='table' AND name='scraping_run_history'
        """
    )["n"] == 0

    db._run_migrations()

    assert db.fetch_one(
        """
        SELECT COUNT(*) AS n
        FROM sqlite_master
        WHERE type='table' AND name='scraping_run_history'
        """
    )["n"] == 1
    assert db.fetch_one(
        "SELECT MAX(version) AS version FROM schema_migrations"
    )["version"] == DBManager.SCHEMA_VERSION

    db.close()

def test_database_migrates_from_v2_to_v6_idempotently_and_preserves_product_data():
    db = DBManager(":memory:")
    db.execute_query(
        "INSERT INTO products (code, name, stock) VALUES (?, ?, ?)",
        ("MIGRATION-001", "Producto de migración", 17),
    )

    # Recreate the schema surface of a v2 database, then run the real v3-v5
    # migration path. The existing product row must survive every ALTER TABLE.
    for column in (
        "gallery_images",
        "image_etag",
        "image_last_modified",
        "image_checked_at",
    ):
        db.execute_query(f"ALTER TABLE products DROP COLUMN {column}")
    db.execute_query("DROP TABLE source_page_cache")
    db.execute_query("DELETE FROM schema_migrations WHERE version >= 3")

    db._run_migrations()

    columns = {
        row["name"] for row in db.fetch_all("PRAGMA table_info(products)")
    }
    assert {
        "gallery_images",
        "image_etag",
        "image_last_modified",
        "image_checked_at",
        "legacy_colors",
    } <= columns

    cache = db.fetch_one(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name = 'source_page_cache'"
    )
    assert cache is not None
    cache_index = db.fetch_one(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'index' AND name = 'idx_source_page_cache_checked_at'"
    )
    assert cache_index is not None

    stored = db.fetch_one(
        "SELECT code, name, stock, gallery_images, image_etag "
        "FROM products WHERE code = ?",
        ("MIGRATION-001",),
    )
    assert stored is not None
    assert stored["name"] == "Producto de migración"
    assert stored["stock"] == 17
    assert stored["gallery_images"] == "[]"
    assert stored["image_etag"] == ""

    # Re-running migrations must not duplicate ledger records or mutate data.
    db._run_migrations()
    versions = db.fetch_all(
        "SELECT version FROM schema_migrations ORDER BY version"
    )
    assert [row["version"] for row in versions] == [1, 2, 3, 4, 5, 6]
    db.close()

def test_database_migrates_legacy_download_changes_without_losing_history():
    db = DBManager(":memory:")
    db.execute_query(
        """
        INSERT INTO scraping_history (started_at, finished_at, status, message)
        VALUES (?, ?, 'SUCCESS', ?)
        """,
        ("2026-10-01T00:00:00", "2026-10-01T00:00:01", "Historial heredado"),
    )
    history_id = db.fetch_one(
        "SELECT id FROM scraping_history ORDER BY id DESC LIMIT 1"
    )["id"]

    # Emulate an older download_changes table without its required history FK.
    db.execute_query("DROP TABLE download_changes")
    db.execute_query(
        """
        CREATE TABLE download_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            history_id INTEGER NOT NULL,
            change_type TEXT NOT NULL,
            code TEXT NOT NULL,
            product_name TEXT NOT NULL,
            field_name TEXT,
            field_label TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT
        )
        """
    )
    db.execute_query(
        """
        INSERT INTO download_changes (
            history_id, change_type, code, product_name,
            field_name, field_label, old_value, new_value
        )
        VALUES (?, 'UPDATED', ?, ?, 'description', 'Detalle', ?, ?)
        """,
        (history_id, "MIGRATION-002", "Producto heredado", "old", "new"),
    )
    db.execute_query("DELETE FROM schema_migrations")

    db._run_migrations()

    restored = db.fetch_all(
        """
        SELECT history_id, change_type, code, field_name, old_value, new_value
        FROM download_changes
        WHERE history_id = ?
        """,
        (history_id,),
    )
    assert len(restored) == 1
    assert restored[0]["change_type"] == "UPDATED"
    assert restored[0]["code"] == "MIGRATION-002"
    assert restored[0]["field_name"] == "description"
    assert restored[0]["old_value"] == "old"
    assert restored[0]["new_value"] == "new"

    foreign_keys = db.fetch_all("PRAGMA foreign_key_list(download_changes)")
    assert any(
        row["table"] == "scraping_history"
        and row["from"] == "history_id"
        and row["to"] == "id"
        for row in foreign_keys
    )
    legacy_rows = db.fetch_one(
        "SELECT COUNT(*) AS total FROM download_changes_legacy"
    )
    assert legacy_rows is not None
    assert legacy_rows["total"] == 1
    db.close()

def test_database_migration_preserves_legacy_color_names_without_inventing_stock():
    import json

    db = DBManager(":memory:")
    db.execute_query(
        "ALTER TABLE products ADD COLUMN colors TEXT DEFAULT '[]'"
    )
    db.execute_query(
        "ALTER TABLE scraped_products ADD COLUMN colors TEXT DEFAULT '[]'"
    )

    product_colors = json.dumps(["Azul", "Verde"], ensure_ascii=False)
    scraped_colors = json.dumps(["Negro", "Blanco"], ensure_ascii=False)
    product_stock = json.dumps({"Rojo": 4}, ensure_ascii=False)

    db.execute_query(
        """
        INSERT INTO products (code, name, color_stock, colors)
        VALUES (?, ?, ?, ?)
        """,
        ("MIGRATION-COLORS", "Producto heredado", product_stock, product_colors),
    )
    db.execute_query(
        """
        INSERT INTO scraped_products (
            source, url, code, name, color_stock, colors
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "legacy",
            "https://example.invalid/producto/migration-colors/",
            "MIGRATION-COLORS",
            "Producto heredado",
            "{}",
            scraped_colors,
        ),
    )

    # Re-run the legacy migration path as if opening an unversioned older DB.
    db.execute_query("DELETE FROM schema_migrations")
    db._run_migrations()

    product = db.fetch_one(
        "SELECT color_stock, legacy_colors FROM products WHERE code=?",
        ("MIGRATION-COLORS",),
    )
    scraped = db.fetch_one(
        "SELECT color_stock, legacy_colors FROM scraped_products WHERE code=?",
        ("MIGRATION-COLORS",),
    )
    assert product is not None and scraped is not None
    assert product["legacy_colors"] == product_colors
    assert scraped["legacy_colors"] == scraped_colors
    # Preserve actual numeric counts only; the legacy color-name list must not
    # be converted into invented zero/positive stock values.
    assert json.loads(product["color_stock"]) == {"Rojo": 4}
    assert json.loads(scraped["color_stock"]) == {}

    product_columns = {
        row["name"] for row in db.fetch_all("PRAGMA table_info(products)")
    }
    scraped_columns = {
        row["name"] for row in db.fetch_all("PRAGMA table_info(scraped_products)")
    }
    assert "colors" not in product_columns
    assert "colors" not in scraped_columns
    assert "legacy_colors" in product_columns
    assert "legacy_colors" in scraped_columns
    db.close()
