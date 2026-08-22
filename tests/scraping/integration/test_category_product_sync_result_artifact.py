import json
from types import SimpleNamespace

import services.scraping.scraping_result_writer as scraping_result_writer
from models.scraping.category import Category
from repositories.scraping.sync_repository import SyncRepository
from services.scraping.catalog_sync_service import CatalogSyncService
from services.scraping.category_product_sync_service import CategoryProductSyncService
from services.scraping.product_diff_service import ProductDiffService


class Product:
    def __init__(self, category):
        self.code = "P001"
        self.name = "Producto 1"
        self.category = category
        self.description = ""
        self.stock = 0
        self.price = 10
        self.price_sample = 10
        self.price_hundred = 0
        self.price_thousand = 0
        self.colors = []
        self.color_stock = {}
        self.image_url = ""
        self.image_path = ""
        self.image_hash = ""
        self.content_hash = ""
        self.url = "https://example.com/product/p001/"


class FakeScraper:
    def __init__(self):
        self.products = {
            "Categoria A": [Product("Categoria A")],
            "Categoria B": [Product("Categoria B")],
        }

    def collect_category(self, category):
        return self.products[category.name]

    def enrich_category_products(self, products, category_name):
        return products


class IdentityMapper:
    def map(self, product):
        return product


def test_category_sync_rewrites_result_artifact_with_final_coverage(tmp_path, monkeypatch):
    result_path = tmp_path / "scraping_result.json"
    monkeypatch.setattr(scraping_result_writer, "RESULT_PATH", result_path)
    categories = [
        Category("Categoria A", "https://example.com/a/", expected_count=1),
        Category("Categoria B", "https://example.com/b/", expected_count=1),
    ]
    service = CategoryProductSyncService(
        SimpleNamespace(scraper=FakeScraper()),
        persistence_service=SimpleNamespace(),
        mapper=IdentityMapper(),
        catalog_sync_service=CatalogSyncService(
            SyncRepository(), ProductDiffService()
        ),
        category_workers=1,
    )

    service.sync_categories(categories, expected_products=1)

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["products_found"] == 2
    assert payload["scraped_unique_products"] == 1
    assert payload["products_unique"] == 1
    assert payload["reference_category_occurrences"] == 2
    assert payload["actual_category_occurrences"] == 2
    assert payload["unique_products"] == 1
    assert payload["multi_category_products"] == 1
    assert payload["coverage_complete"] is True
