from gui.workers.catalog_load_worker import CatalogLoadWorker
from models.product import Product


def test_catalog_load_worker_emits_products_and_closes_database(monkeypatch):
    events = []

    class FakeCursor:
        def fetchall(self):
            return []

    class FakeConnection:
        def __init__(self):
            self.row_factory = None

        def execute(self, query):
            events.append(query)
            return FakeCursor()

        def close(self):
            events.append("closed")

    monkeypatch.setattr(
        "gui.workers.catalog_load_worker.sqlite3.connect",
        lambda *args, **kwargs: FakeConnection(),
    )

    worker = CatalogLoadWorker()
    worker.finished.connect(lambda products: events.append(("finished", products)))
    worker.run()

    assert events == [
        "SELECT * FROM products ORDER BY id DESC",
        ("finished", []),
        "closed",
    ]


def test_catalog_load_worker_maps_product_rows(monkeypatch):
    class FakeCursor:
        def fetchall(self):
            return [
                {
                    "id": 7,
                    "code": "FB-100",
                    "name": "Producto",
                    "price": 10.5,
                    "category": "Categoría",
                    "description": "Detalle",
                    "price_sample": 11.0,
                    "price_hundred": 9.0,
                    "price_thousand": 8.0,
                    "stock": 25,
                    "color_stock": "{}",
                    "image_url": "https://example.com/a.jpg",
                    "image_path": "images/a.jpg",
                    "image_hash": "hash-image",
                    "content_hash": "hash-content",
                }
            ]

    class FakeConnection:
        def __init__(self):
            self.row_factory = None

        def execute(self, query):
            del query
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr(
        "gui.workers.catalog_load_worker.sqlite3.connect",
        lambda *args, **kwargs: FakeConnection(),
    )

    worker = CatalogLoadWorker()
    received = []
    worker.finished.connect(received.append)
    worker.run()

    assert received == [
        [
            Product(
                product_id=7,
                code="FB-100",
                name="Producto",
                price=10.5,
                category="Categoría",
                description="Detalle",
                price_sample=11.0,
                price_hundred=9.0,
                price_thousand=8.0,
                stock=25,
                image_url="https://example.com/a.jpg",
                image_path="images/a.jpg",
                image_hash="hash-image",
                content_hash="hash-content",
            )
        ]
    ]
