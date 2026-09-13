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
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finished_at TEXT,
            mode TEXT NOT NULL,
            status TEXT NOT NULL,
            categories_requested INTEGER DEFAULT 0,
            expected_category_occurrences INTEGER DEFAULT 0,
            actual_category_occurrences INTEGER DEFAULT 0,
            products_found INTEGER DEFAULT 0,
            products_unique INTEGER DEFAULT 0,
            products_multiple_categories INTEGER DEFAULT 0,
            duplicate_occurrences INTEGER DEFAULT 0,
            coverage_complete INTEGER DEFAULT 0,
            coverage_gap INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            message TEXT DEFAULT ''
        );
        CREATE TABLE scraping_product_occurrences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            product_id INTEGER,
            code TEXT NOT NULL,
            product_url TEXT NOT NULL DEFAULT '',
            page_number INTEGER DEFAULT 0,
            position INTEGER DEFAULT 0,
            name TEXT DEFAULT '',
            discovered_at TEXT,
            UNIQUE (run_id, category_id, code),
            FOREIGN KEY (run_id) REFERENCES scraping_runs(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
        );
        """
    )
    return connection


def test_reconcile_exact_full_coverage_preserves_530_masters_and_534_relations():
    connection = _db()
    db = SQLiteDBAdapter(connection)

    category_rows = [("Categoría A", "category-a"), ("Categoría B", "category-b")]
    connection.executemany(
        "INSERT INTO categories (name, canonical_url) VALUES (?, ?)",
        category_rows,
    )
    category_ids = [
        row["id"]
        for row in connection.execute("SELECT id FROM categories ORDER BY id")
    ]
    category_a, category_b = category_ids

    connection.execute(
        """
        INSERT INTO scraping_runs (
            mode, status, categories_requested,
            expected_category_occurrences, actual_category_occurrences,
            products_found, products_unique, products_multiple_categories,
            duplicate_occurrences, coverage_complete, coverage_gap, error_count
        ) VALUES ('full', 'SUCCESS', 24, 534, 534, 534, 530, 4, 0, 1, 0, 0)
        """
    )
    run_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]

    products = [
        (f"FB-{index:04d}", f"Producto {index:04d}")
        for index in range(1, 531)
    ]
    connection.executemany(
        "INSERT INTO products (code, name) VALUES (?, ?)",
        products,
    )
    product_ids = {
        row["code"]: row["id"]
        for row in connection.execute("SELECT id, code FROM products")
    }
    connection.execute("INSERT INTO products (code, name) VALUES (?, ?)", ("STALE", "Obsoleto"))
    connection.execute(
        "INSERT INTO scraping_product_occurrences
            (run_id, category_id, product_id, code, product_url, discovered_at)
         VALUES (?, ?, ?, ?, '', 'now')".replace("\n", " "),
        (run_id, category_a, product_ids["FB-0001"], "FB-0001"),
    )
    connection.execute(
        "DELETE FROM scraping_product_occurrences WHERE run_id=?", (run_id,)
    )

    occurrences = [
        (run_id, category_a, product_ids[code], code)
        for code, _ in products
    ] + [
        (run_id, category_b, product_ids[f"FB-{index:04d}"], f"FB-{index:04d}")
        for index in range(1, 5)
    ]
    connection.executemany(
        """
        INSERT INTO scraping_product_occurrences
            (run_id, category_id, product_id, code, product_url, discovered_at)
        VALUES (?, ?, ?, ?, '', 'now')
        """,
        occurrences,
    )
    connection.commit()

    service = CatalogBootstrapService(db=db)
    assert service.reconcile_latest_successful_run() == 530

    assert connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 530
    assert connection.execute(
        "SELECT COUNT(*) FROM scraping_product_occurrences WHERE run_id=?",
        (run_id,),
    ).fetchone()[0] == 534
    assert connection.execute(
        """
        SELECT COUNT(*)
        FROM scraping_product_occurrences
        WHERE run_id=? AND product_id IS NOT NULL
        """,
        (run_id,),
    ).fetchone()[0] == 534
    assert connection.execute("SELECT COUNT(*) FROM product_categories").fetchone()[0] == 534
    assert connection.execute(
        "SELECT COUNT(*) FROM products WHERE code='STALE'"
    ).fetchone()[0] == 0
    assert connection.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT product_id
            FROM scraping_product_occurrences
            WHERE run_id=?
            GROUP BY product_id
            HAVING COUNT(DISTINCT category_id)=2
        )
        """,
        (run_id,),
    ).fetchone()[0] == 4
