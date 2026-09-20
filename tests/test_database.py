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
