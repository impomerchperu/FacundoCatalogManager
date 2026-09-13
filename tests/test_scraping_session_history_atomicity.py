import sqlite3

from models.product import Product
from models.scraping.scraping_history import ScrapingHistory
from models.scraping.sync_result import SyncResult
from services.scraping.scraping_session import ScrapingSession


class SQLiteAdapter:
    def __init__(self, connection):
        self.connection = connection

    def begin(self):
        self.connection.execute("BEGIN")

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def execute_query(self, query, params=()):
        return self.connection.execute(query, params)


class FailOnceHistoryRepository:
    def __init__(self, db):
        self.db = db
        self.calls = 0

    def save(self, history: ScrapingHistory, changes, products):
        del history, changes, products
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("fallo simulado al guardar historial")
        self.db.execute_query("INSERT INTO history_marker DEFAULT VALUES")
        return 1


class ScrapingService:
    def __init__(self, result):
        self.last_sync_result = result
        self.catalog_sync_service = None
        self.scraper_service = None


class Runner:
    def __init__(self, db, result, product):
        self.scraping_service = ScrapingService(result)
        self.db = db
        self.product = product

    def run(self, categories, progress_callback):
        del categories, progress_callback
        self.db.execute_query(
            "UPDATE products SET stock=? WHERE code=?",
            (self.product.stock, self.product.code),
        )
        return [self.product]


def _db():
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE products (code TEXT PRIMARY KEY, stock INTEGER NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE history_marker (id INTEGER PRIMARY KEY AUTOINCREMENT)"
    )
    connection.execute("INSERT INTO products (code, stock) VALUES ('FB-001', 10)")
    connection.commit()
    return SQLiteAdapter(connection), connection


def test_successful_catalog_change_rolls_back_when_history_save_fails():
    db, connection = _db()
    result = SyncResult(
        processed=1,
        created=1,
        expected_category_occurrences=1,
        products_found=1,
        products_unique=1,
    )
    result.category_summary = [
        {
            "category": "Categoría A",
            "expected": 1,
            "products": 1,
            "unique_products": 1,
            "gap": 0,
        }
    ]
    product = Product(code="FB-001", name="Producto", stock=99)
    runner = Runner(db, result, product)
    history = FailOnceHistoryRepository(db)

    session = ScrapingSession(runner, history_repository=history)
    returned = session.execute([])

    assert returned.success() is False
    assert connection.execute(
        "SELECT stock FROM products WHERE code='FB-001'"
    ).fetchone()[0] == 10
    assert connection.execute("SELECT COUNT(*) FROM history_marker").fetchone()[0] == 1
    assert history.calls == 2
