from types import SimpleNamespace

from models.scraping.category import Category
from models.scraping.sync_result import SyncResult
from services.scraping.category_product_sync_service import CategoryProductSyncService


class FakeScraper:
    def __init__(self, product):
        self.product = product

    def collect_category(self, category):
        return [self.product]

    def enrich_category_products(self, products, category_name):
        return products


class FakeImageSyncAdapter:
    def sync_products(self, products):
        for product in products:
            product.image_path = f"data/images/products/{product.code}.webp"
            product.image_hash = "image-hash"
        return products


class FakeCatalogSyncService:
    result_writer = None

    @staticmethod
    def consolidate_products(products):
        return products

    @staticmethod
    def sync(
        products,
        prune_missing=False,
        expected_products=0,
        expected_category_occurrences=0,
    ):
        del prune_missing
        result = SyncResult()
        result.processed = len(products)
        result.created = len(products)
        result.products_found = len(products)
        result.products_unique = len(products)
        result.products_expected = expected_products
        result.expected_category_occurrences = expected_category_occurrences
        return result


class FakeMapper:
    @staticmethod
    def map(product):
        return SimpleNamespace(
            code=product.code,
            image_path=product.image_path,
            image_hash=product.image_hash,
            content_hash="content-hash",
        )


def test_sync_categories_propagates_synced_image_fields_to_raw_products():
    product = SimpleNamespace(
        code="P001",
        name="Producto 1",
        category="Jarros Mug",
        description="",
        price=10.0,
        price_sample=10.0,
        price_hundred=100.0,
        price_thousand=1000.0,
        stock=5,
        color_stock={},
        image_url="https://example.com/p001.webp",
        image_path="",
        image_hash="",
        content_hash="",
        url="https://example.com/p001/",
    )

    service = CategoryProductSyncService(
        SimpleNamespace(scraper=FakeScraper(product)),
        persistence_service=SimpleNamespace(),
        mapper=FakeMapper(),
        catalog_sync_service=FakeCatalogSyncService(),
        image_sync_adapter=FakeImageSyncAdapter(),
    )

    result = service.sync_categories(
        [Category("Jarros Mug", "https://example.com/jarros-mug/", expected_count=1)]
    )

    assert result[0].image_path == "data/images/products/P001.webp"
    assert result[0].image_hash == "image-hash"
    assert result[0].content_hash == "content-hash"
