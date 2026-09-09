import sqlite3

from services.catalog_bootstrap_service import CatalogBootstrapService


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
        CREATE TABLE catalog_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """
    )


def test_reconcile_latest_successful_run_prunes_and_rebuilds_relations():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    _create_schema(db)

    db.execute(
        "INSERT INTO scraping_runs (mode, status, coverage_complete) VALUES ('full', 'SUCCESS', 1)"
    )
    run_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.executemany(
        "INSERT INTO categories (name, canonical_url) VALUES (?, ?)",
        [("Cat A", "a"), ("Cat B", "b")],
    )
    category_ids = [row[0] for row in db.execute("SELECT id FROM categories ORDER BY id")]
    db.executemany(
        "INSERT INTO products (code, name) VALUES (?, ?)",
        [("A", "Producto A"), ("B", "Producto B"), ("STALE", "Fuera")],
    )
    db.executemany(
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
    db.commit()

    service = CatalogBootstrapService(db=db)
    assert service.reconcile_latest_successful_run() == 2

    assert db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 2
    assert db.execute("SELECT COUNT(*) FROM product_categories").fetchone()[0] == 3
    assert db.execute(
        "SELECT COUNT(*) FROM scraping_product_occurrences WHERE run_id=? AND product_id IS NOT NULL",
        (run_id,),
    ).fetchone()[0] == 3
    assert db.execute(
        "SELECT code FROM products ORDER BY code"
    ).fetchall() == [
        ("A",),
        ("B",),
    ]
