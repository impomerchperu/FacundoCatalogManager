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
        CREATE TABLE product_categories (
            product_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            first_seen_at TEXT,
            last_seen_at TEXT,
            PRIMARY KEY (product_id, category_id),
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );
        CREATE TABLE scraping_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT NOT NULL,
            status TEXT NOT NULL,
            coverage_complete INTEGER DEFAULT 0,
            categories_requested INTEGER DEFAULT 0,
            expected_category_occurrences INTEGER DEFAULT 0,
            actual_category_occurrences INTEGER DEFAULT 0,
            products_found INTEGER DEFAULT 0,
            products_unique INTEGER DEFAULT 0,
            products_multiple_categories INTEGER DEFAULT 0,
            duplicate_occurrences INTEGER DEFAULT 0
        );
        CREATE TABLE scraping_product_occurrences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            product_id INTEGER,
            code TEXT NOT NULL,
            discovered_at TEXT,
            FOREIGN KEY (run_id) REFERENCES scraping_runs(id),
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL,
            UNIQUE (run_id, category_id, code)
        );
        CREATE TABLE catalog_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
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


def _insert_run(connection, *, products_found, products_unique, occurrences):
    connection.execute(
        """
        INSERT INTO scraping_runs
            (mode, status, coverage_complete, categories_requested,
             expected_category_occurrences, actual_category_occurrences,
             products_found, products_unique, products_multiple_categories,
             duplicate_occurrences)
        VALUES ('full', 'SUCCESS', 1, 24, ?, ?, ?, ?, 4, 4)
        """,
        (occurrences, occurrences, products_found, products_unique),
    )
    return connection.execute("SELECT last_insert_rowid()").fetchone()[0]


def test_reference_run_wins_over_a_later_529_525_successful_run():
    connection = _db()
    db = SQLiteDBAdapter(connection)

    old_run = _insert_run(
        connection,
        products_found=530,
        products_unique=526,
        occurrences=530,
    )
    later_run = _insert_run(
        connection,
        products_found=529,
        products_unique=525,
        occurrences=529,
    )

    connection.execute("INSERT INTO products (code, name) VALUES ('KEEP', 'Producto válido')")
    product_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    connection.execute(
        "INSERT INTO products (code, name) VALUES ('STALE', 'Producto fuera del run')"
    )
    for index in range(530):
        connection.execute(
            """
            INSERT INTO scraping_product_occurrences
                (run_id, category_id, product_id, code, discovered_at)
            VALUES (?, ?, ?, ?, 'now')
            """,
            (old_run, index + 1, product_id, f'C{index:03d}'),
        )
    # El segundo run es deliberadamente el más reciente, pero no coincide
    # con la referencia histórica 530/526/4.
    connection.execute(
        "INSERT INTO scraping_product_occurrences
            (run_id, category_id, product_id, code, discovered_at)
         VALUES (?, 1, ?, 'KEEP', 'now')",
        (later_run, product_id),
    )
    connection.commit()

    service = CatalogBootstrapService(db=db)
    assert service._find_reference_full_run()["id"] == old_run


def test_bootstrap_does_not_repeat_reference_recovery_after_version_is_marked():
    connection = _db()
    db = SQLiteDBAdapter(connection)
    connection.execute(
        "INSERT INTO catalog_metadata (key, value) VALUES (?, ?)",
        (CatalogBootstrapService.HISTORY_RECOVERY_KEY, "530-526-4-v1"),
    )
    connection.execute("INSERT INTO products (code, name) VALUES ('A', 'Persistente')")
    connection.commit()

    service = CatalogBootstrapService(db=db)
    assert service.bootstrap() == 1

    row = connection.execute("SELECT name FROM products WHERE code='A'").fetchone()
    assert row["name"] == "Persistente"
