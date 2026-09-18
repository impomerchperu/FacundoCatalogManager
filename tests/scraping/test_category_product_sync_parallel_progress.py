from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

from models.scraping.category import Category
from services.scraping.category_product_sync_service import CategoryProductSyncService


class Product:
    def __init__(self, category):
        self.code = f"P-{category}"
        self.name = category
        self.category = category
        self.url = f"https://example.com/product/{category}/"


def test_category_progress_tracks_completion_without_reordering_results():
    slow_started = Event()
    release_slow = Event()
    fast_completed = Event()
    progress = []
    first_progress = Event()

    class FakeScraper:
        def collect_category(self, category):
            if category.name == "Categoria Lenta":
                slow_started.set()
                assert release_slow.wait(timeout=2)
            else:
                fast_completed.set()
            return [(None, category.url, Product(category.name))]

        def enrich_category_products(self, products, category_name):
            del category_name
            return [item[2] for item in products]

    persistence = SimpleNamespace(save_products=lambda products: products)
    service = CategoryProductSyncService(
        SimpleNamespace(scraper=FakeScraper()),
        persistence_service=persistence,
        category_workers=2,
    )
    categories = [
        Category("Categoria Lenta", "https://example.com/lenta/", expected_count=1),
        Category("Categoria Rápida", "https://example.com/rapida/", expected_count=1),
    ]

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            run_future = executor.submit(
                service.sync_categories,
                categories,
                lambda current, total: (
                    progress.append((current, total)),
                    first_progress.set(),
                ),
            )
            assert slow_started.wait(timeout=2)
            assert fast_completed.wait(timeout=2)
            assert first_progress.wait(timeout=2)
            assert progress == [(1, 2)]
            release_slow.set()
            result = run_future.result(timeout=2)

        assert progress == [(1, 2), (2, 2), (3, 4), (4, 4)]
        assert [product.category for product in result] == [
            "Categoria Lenta",
            "Categoria Rápida",
        ]
    finally:
        release_slow.set()
