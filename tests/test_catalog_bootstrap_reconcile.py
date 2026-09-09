import sqlite3

from services.catalog_bootstrap_service import CatalogBootstrapService


class SQLiteDBAdapter:
    """Adapta sqlite3.Connection a la interfaz mínima esperada por el servicio."""

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


def _create_schema(db):
    db.executescript(
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
        CREATE TABLE scraping_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            processed INTEGER DEFAULT 0,
            created INTEGER DEFAULT 0,
            updated INTEGER DEFAULT 0,
            unchanged INTEGER DEFAULT 0,
            deleted INTEGER DEFAULT 0,
            generated INTEGER DEFAULT 0,
            categories_processed INTEGER DEFAULT 0,
            products_expected INTEGER DEFAULT 0,
            products_found INTEGER DEFAULT 0,
            products_unique INTEGER DEFAULT 0,
            products_multiple_categories INTEGER DEFAULT 0,
            duplicate_occurrences INTEGER DEFAULT 0,
            category_summary TEXT DEFAULT '[]',
            multiple_category_products TEXT DEFAULT '[]',
            errors INTEGER DEFAULT 0,
            status TEXT DEFAULT 'SUCCESS',
            message TEXT DEFAULT ''
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
            FOREIGN KEY (history_id) REFERENCES scraping_history(id) ON DELETE CASCADE
        );
        CREATE TABLE catalog_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """
    )


def _new_connection():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    _create_schema(connection)
    return connection


def test_reconcile_latest_successful_run_prunes_and_rebuilds_relations():
    connection = _new_connection()
    db = SQLiteDBAdapter(connection)

    connection.execute(
        "INSERT INTO scraping_runs (mode, status, coverage_complete) VALUES ('full', 'SUCCESS', 1)"
    )
    run_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    connection.executemany(
        "INSERT INTO categories (name, canonical_url) VALUES (?, ?)",
        [("Cat A", "a"), ("Cat B", "b")],
    )
    category_ids = [
        row[0]
        for row in connection.execute("SELECT id FROM categories ORDER BY id")
    ]
    connection.executemany(
        "INSERT INTO products (code, name) VALUES (?, ?)",
        [("A", "Producto A"), ("B", "Producto B"), ("STALE", "Fuera")],
    )
    connection.executemany(
        """
        INSERT INTO scraping_product_occurrences
            (run_id, category_id, code, product_url, discovered_at)
        VALUES (?, ?, ?, '', 'now')
        """,
        [
            (run_id, category_ids[0], "A"),
            (run_id, category_ids[0], "B"),
            (run_id, category_ids[1], "B"),
        ],
    )
    connection.commit()

    service = CatalogBootstrapService(db=db)
    assert service.reconcile_latest_successful_run() == 2

    assert connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 2
    assert connection.execute(
        "SELECT COUNT(*) FROM product_categories"
    ).fetchone()[0] == 3
    assert connection.execute(
        """
        SELECT COUNT(*)
        FROM scraping_product_occurrences
        WHERE run_id=? AND product_id IS NOT NULL
        """,
        (run_id,),
    ).fetchone()[0] == 3
    assert [
        row["code"]
        for row in connection.execute("SELECT code FROM products ORDER BY code")
    ] == ["A", "B"]


def test_bootstrap_restores_latest_state_from_change_history_when_full_run_is_unusable():
    connection = _new_connection()
    db = SQLiteDBAdapter(connection)

    connection.execute("INSERT INTO products (code, name, stock) VALUES ('STALE', 'Viejo', 1)")
    connection.execute(
        """
        INSERT INTO scraping_history (
            started_at, finished_at, processed, created, updated, unchanged,
            deleted, generated, status, message
        ) VALUES ('2026-09-09T01:00:00+00:00', '2026-09-09T01:01:00+00:00',
                  2, 1, 1, 0, 1, 0, 'ERROR', 'Cobertura incompleta')
        """
    )
    history_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    connection.executemany(
        """
        INSERT INTO download_changes (
            history_id, change_type, code, product_name,
            field_name, field_label, old_value, new_value
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (history_id, "NEW", "A", "Producto A", "name", "Nombre", None, "Producto A"),
            (history_id, "NEW", "A", "Producto A", "stock", "Stock", None, "7"),
            (history_id, "UPDATED", "B", "Producto B", "name", "Nombre", "Anterior", "Producto B"),
            (history_id, "UPDATED", "B", "Producto B", "stock", "Stock", "2", "9"),
            (history_id, "DELETED", "STALE", "Viejo", None, "Producto eliminado", "Presente", "Ausente"),
        ],
    )
    connection.commit()

    service = CatalogBootstrapService(db=db)
    assert service.bootstrap() == 2

    rows = connection.execute(
        "SELECT code, name, stock FROM products ORDER BY code"
    ).fetchall()
    assert [(row["code"], row["name"], row["stock"]) for row in rows] == [
        ("A", "Producto A", 7),
        ("B", "Producto B", 9),
    ]


def test_restore_from_change_history_preserves_latest_update_after_multiple_runs():
    connection = _new_connection()
    db = SQLiteDBAdapter(connection)

    connection.executemany(
        """
        INSERT INTO scraping_history (
            started_at, finished_at, status
        ) VALUES (?, ?, 'SUCCESS')
        """,
        [
            ("2026-09-08T01:00:00+00:00", "2026-09-08T01:01:00+00:00"),
            ("2026-09-09T01:00:00+00:00", "2026-09-09T01:01:00+00:00"),
        ],
    )
    first_run, second_run = [
        row["id"]
        for row in connection.execute("SELECT id FROM scraping_history ORDER BY id")
    ]
    connection.executemany(
        """
        INSERT INTO download_changes (
            history_id, change_type, code, product_name,
            field_name, field_label, old_value, new_value
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (first_run, "NEW", "A", "Producto A", "name", "Nombre", None, "Producto A"),
            (first_run, "NEW", "A", "Producto A", "stock", "Stock", None, "3"),
            (second_run, "UPDATED", "A", "Producto A", "stock", "Stock", "3", "11"),
        ],
    )
    connection.commit()

    service = CatalogBootstrapService(db=db)
    assert service.restore_from_change_history() == 1
    row = connection.execute(
        "SELECT code, name, stock FROM products"
    ).fetchone()
    assert (row["code"], row["name"], row["stock"]) == ("A", "Producto A", 11)
