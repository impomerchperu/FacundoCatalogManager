import sqlite3

from services.catalog_bootstrap_service import CatalogBootstrapService


class SQLiteDBAdapter:
    def __init__(self, connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row

    def fetch_one(self, query, params=()):
        return self.connection.execute(query, params).fetchone()

    def fetch_all(self, query, params=()):
        return self.connection.execute(query, params).fetchall()

    def execute_query(self, query, params=()):
        return self.connection.execute(query, params)

    def begin(self):
        self.connection.execute("BEGIN")

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()


def _db():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(
        """
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT,
            description TEXT,
            price REAL DEFAULT 0,
            price_sample REAL DEFAULT 0,
            price_hundred REAL DEFAULT 0,
            price_thousand REAL DEFAULT 0,
            stock INTEGER DEFAULT 0,
            color_stock TEXT DEFAULT '{}',
            image_url TEXT,
            image_path TEXT,
            image_hash TEXT DEFAULT '',
            content_hash TEXT DEFAULT ''
        );
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            canonical_url TEXT NOT NULL UNIQUE,
            expected_count INTEGER DEFAULT 0
        );
        CREATE TABLE product_categories (
            product_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            first_seen_at TEXT,
            last_seen_at TEXT,
            PRIMARY KEY (product_id, category_id),
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
        );
        CREATE TABLE scraping_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT NOT NULL,
            status TEXT NOT NULL,
            coverage_complete INTEGER DEFAULT 0
        );
        CREATE TABLE scraping_product_occurrences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            product_id INTEGER,
            code TEXT NOT NULL,
            product_url TEXT NOT NULL DEFAULT '',
            discovered_at TEXT,
            UNIQUE (run_id, category_id, code),
            FOREIGN KEY (run_id) REFERENCES scraping_runs(id),
            FOREIGN KEY (category_id) REFERENCES categories(id),
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
        );
        CREATE TABLE catalog_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE scraped_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            name TEXT,
            category TEXT,
            description TEXT,
            price REAL DEFAULT 0,
            price_sample REAL DEFAULT 0,
            price_hundred REAL DEFAULT 0,
            price_thousand REAL DEFAULT 0,
            stock INTEGER DEFAULT 0,
            color_stock TEXT DEFAULT '{}',
            image_url TEXT,
            image_path TEXT,
            image_hash TEXT DEFAULT '',
            content_hash TEXT DEFAULT ''
        );
        CREATE TABLE sync_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            name TEXT,
            category TEXT,
            description TEXT,
            price REAL DEFAULT 0,
            price_sample REAL DEFAULT 0,
            price_hundred REAL DEFAULT 0,
            price_thousand REAL DEFAULT 0,
            stock INTEGER DEFAULT 0,
            color_stock TEXT DEFAULT '{}',
            image_url TEXT,
            image_path TEXT,
            image_hash TEXT DEFAULT '',
            content_hash TEXT DEFAULT '',
            updated_at TEXT
        );
        CREATE TABLE scraping_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            status TEXT DEFAULT 'SUCCESS'
        );
        CREATE TABLE download_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            history_id INTEGER NOT NULL,
            change_type TEXT NOT NULL,
            code TEXT NOT NULL,
            product_name TEXT NOT NULL,
            field_name TEXT,
            field_label TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            FOREIGN KEY (history_id) REFERENCES scraping_history(id)
        );
        """
    )
    return connection


def _insert_successful_run(connection, code, category_id, name):
    connection.execute(
        "INSERT INTO scraping_runs (mode, status, coverage_complete) VALUES ('full', 'SUCCESS', 1)"
    )
    run_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    connection.execute(
        "INSERT INTO categories (id, name, canonical_url) VALUES (?, ?, ?)",
        (category_id, f"Categoría {category_id}", f"category-{category_id}"),
    )
    connection.execute(
        "INSERT INTO products (code, name) VALUES (?, ?)",
        (code, name),
    )
    product_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    connection.execute(
        "INSERT INTO scraped_products (code, name) VALUES (?, ?)",
        (code, name),
    )
    connection.execute(
        """
        INSERT INTO scraping_product_occurrences
            (run_id, category_id, product_id, code, discovered_at)
        VALUES (?, ?, ?, ?, 'now')
        """,
        (run_id, category_id, product_id, code),
    )
    return run_id


def test_recovery_uses_the_latest_successful_run_without_a_historical_count_floor():
    connection = _db()
    db = SQLiteDBAdapter(connection)

    older_run = _insert_successful_run(connection, "OLD", 1, "Producto antiguo")
    newer_run = _insert_successful_run(connection, "CURRENT", 2, "Producto actual")
    assert newer_run > older_run

    connection.execute("DELETE FROM products")
    connection.execute(
        "UPDATE scraping_product_occurrences SET product_id=NULL WHERE run_id IN (?, ?)",
        (older_run, newer_run),
    )
    connection.commit()

    service = CatalogBootstrapService(db=db)
    assert service.reconcile_latest_successful_run() == 1
    assert [
        row["code"]
        for row in connection.execute("SELECT code FROM products ORDER BY code")
    ] == ["CURRENT"]


def test_bootstrap_does_not_replace_initialized_catalog_with_another_successful_run():
    connection = _db()
    db = SQLiteDBAdapter(connection)
    connection.execute(
        "INSERT INTO scraping_runs (mode, status, coverage_complete) VALUES ('full', 'SUCCESS', 1)"
    )
    run_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    connection.execute(
        "INSERT INTO categories (name, canonical_url) VALUES ('Categoría 1', 'category-1')"
    )
    connection.execute(
        "INSERT INTO products (code, name, stock) VALUES ('CURRENT', 'Persistente', 99)"
    )
    product_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    connection.execute(
        "INSERT INTO scraping_product_occurrences (run_id, category_id, product_id, code, discovered_at) "
        "VALUES (?, 1, ?, 'CURRENT', 'now')",
        (run_id, product_id),
    )
    connection.execute(
        "INSERT INTO catalog_metadata (key, value) VALUES ('initialized', '1')"
    )
    connection.commit()

    service = CatalogBootstrapService(db=db)
    assert service.bootstrap() == 1
    row = connection.execute(
        "SELECT code, name, stock FROM products"
    ).fetchone()
    assert (row["code"], row["name"], row["stock"]) == (
        "CURRENT",
        "Persistente",
        99,
    )


def test_bootstrap_repairs_populated_uninitialized_catalog_from_latest_successful_run():
    connection = _db()
    db = SQLiteDBAdapter(connection)

    connection.execute(
        "INSERT INTO scraping_runs (mode, status, coverage_complete) VALUES ('full', 'SUCCESS', 1)"
    )
    run_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    connection.execute(
        "INSERT INTO categories (name, canonical_url) VALUES ('Categoría 1', 'category-1')"
    )
    connection.execute(
        "INSERT INTO products (code, name, stock) VALUES ('STALE', 'Obsoleto', 1)"
    )
    connection.execute(
        "INSERT INTO products (code, name, stock) VALUES ('CURRENT', 'Producto actual', 7)"
    )
    current_id = connection.execute("SELECT id FROM products WHERE code='CURRENT'").fetchone()[0]
    connection.execute(
        "INSERT INTO scraped_products (code, name, stock) VALUES ('CURRENT', 'Producto actual', 7)"
    )
    connection.execute(
        "INSERT INTO scraping_product_occurrences (run_id, category_id, product_id, code, discovered_at) "
        "VALUES (?, 1, ?, 'CURRENT', 'now')",
        (run_id, current_id),
    )
    connection.commit()

    service = CatalogBootstrapService(db=db)
    assert service.bootstrap() == 1
    rows = connection.execute(
        "SELECT code, name, stock FROM products ORDER BY code"
    ).fetchall()
    assert [(row["code"], row["name"], row["stock"]) for row in rows] == [
        ("CURRENT", "Producto actual", 7),
    ]

    assert connection.execute(
        "SELECT value FROM catalog_metadata WHERE key='initialized'"
    ).fetchone()[0] == "1"
