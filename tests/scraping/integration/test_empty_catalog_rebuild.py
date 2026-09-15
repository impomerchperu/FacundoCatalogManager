from types import SimpleNamespace

from database.db_manager import DBManager
from models.product import Product
from models.scraping.category import Category
from repositories.product_repository import ProductRepository
from repositories.scraping.normalized_scraping_repository import (
    NormalizedScrapingRepository,
)
from services.scraping.catalog_sync_service import CatalogSyncService
from services.scraping.normalized_category_product_sync_service import (
    NormalizedCategoryProductSyncService,
)
from services.scraping.product_diff_service import ProductDiffService


class FakeScraper:
    def __init__(self, products_by_category):
        self.products_by_category = products_by_category

    def collect_category(self, category):
        return self.products_by_category[category.name]

    def enrich_category_products(self, products, category_name):
        del category_name
        return products


class IdentityMapper:
    def map(self, product):
        return product


def test_empty_catalog_rebuild_persists_master_products_before_occurrences(tmp_path):
    db = DBManager(str(tmp_path / "catalog.db"))
    product_repository = ProductRepository(db)
    catalog_sync_service = CatalogSyncService(
        product_repository,
        ProductDiffService(),
    )
    normalized_repository = NormalizedScrapingRepository(db)

    products_by_category = {
        "Categoria A": [
            Product(
                code="FB-001",
                name="Producto 1",
                category="Categoria A",
            ),
            Product(
                code="FB-002",
                name="Producto 2",
                category="Categoria A, Categoria B",
            ),
        ],
        "Categoria B": [
            Product(
                code="FB-002",
                name="Producto 2",
                category="Categoria A, Categoria B",
            ),
            Product(
                code="FB-003",
                name="Producto 3",
                category="Categoria B",
            ),
        ],
    }
    service = NormalizedCategoryProductSyncService(
        scraper_service=SimpleNamespace(
            scraper=FakeScraper(products_by_category)
        ),
        persistence_service=SimpleNamespace(),
        mapper=IdentityMapper(),
        catalog_sync_service=catalog_sync_service,
        normalized_repository=normalized_repository,
    )
    service._scraping_mode = "full"

    categories = [
        Category("Categoria A", "https://example.com/a/", expected_count=2),
        Category("Categoria B", "https://example.com/b/", expected_count=2),
    ]

    products = service.sync_categories(categories)
    result = service.last_sync_result

    master_rows = db.fetch_all(
        "SELECT id, code FROM products ORDER BY code"
    )
    occurrence_rows = db.fetch_all(
        """
        SELECT run_id, category_id, product_id, code
        FROM scraping_product_occurrences
        ORDER BY category_id, code
        """
    )
    product_category_rows = db.fetch_all(
        """
        SELECT product_id, category_id
        FROM product_categories
        ORDER BY product_id, category_id
        """
    )

    assert len(products) == 4
    assert len(master_rows) == 3
    assert [row["code"] for row in master_rows] == [
        "FB-001",
        "FB-002",
        "FB-003",
    ]
    assert len(occurrence_rows) == 4
    assert all(row["product_id"] is not None for row in occurrence_rows)
    assert {row["code"] for row in occurrence_rows} == {
        "FB-001",
        "FB-002",
        "FB-003",
    }
    assert len(product_category_rows) == 4
    assert result.expected_category_occurrences == 4
    assert result.products_found == 4
    assert result.products_unique == 3
    assert result.products_multiple_categories == 1
    assert result.duplicate_occurrences == 1
    assert result.coverage_complete is True
    assert result.success is True
