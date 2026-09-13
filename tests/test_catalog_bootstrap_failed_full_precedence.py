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
            name TEXT NOT NULL
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
            FOREIGN KEY (run_id) REFERENCES scraping_runs(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
        );
        """
    )
    return connection


def test_newer_failed_full_run_does_not_replace_older_successful_run():
    connection = _db()
    db = SQLiteDBAdapter(connection)

    connection.executemany(
        "INSERT INTO categories (name, canonical_url) VALUES (?, ?)",
        [("Categoría válida", "valid"), ("Categoría fallida", "failed")],
    )
    category_valid, category_failed = [
        row["id"]
        for row in connection.execute("SELECT id FROM categories ORDER BY id")
    ]

    connection.execute(
        "INSERT INTO scraping_runs (mode, status, coverage_complete) VALUES ('full', 'SUCCESS', 1)"
    )
    successful_run = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    connection.execute(
        "INSERT INTO products (code, name) VALUES ('VALID', 'Producto válido')"
    )
    valid_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    connection.execute(
        """
        INSERT INTO scraping_product_occurrences
            (run_id, category_id, product_id, code, discovered_at)
        VALUES (?, ?, ?, 'VALID', 'now')
        """,
        (successful_run, category_valid, valid_id),
    )

    connection.execute(
        "INSERT INTO scraping_runs (mode, status, coverage_complete) VALUES ('full', 'ERROR', 0)"
    )
    failed_run = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    connection.execute(
        "INSERT INTO products (code, name) VALUES ('FAILED', 'No aplicar')"
    )
    failed_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    connection.execute(
        """
        INSERT INTO scraping_product_occurrences
            (run_id, category_id, product_id, code, discovered_at)
        VALUES (?, ?, ?, 'FAILED', 'now')
        """,
        (failed_run, category_failed, failed_id),
    )

    connection.commit()
    connection.execute("DELETE FROM products")
    connection.execute(
        "UPDATE scraping_product_occurrences SET product_id=NULL WHERE run_id IN (?, ?)",
        (successful_run, failed_run),
    )
    connection.commit()

    service = CatalogBootstrapService(db=db)
    assert service.reconcile_latest_successful_run() == 1
    assert [
        row["code"]
        for row in connection.execute("SELECT code FROM products ORDER BY code")
    ] == ["VALID"]
