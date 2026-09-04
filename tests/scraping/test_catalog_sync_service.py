from repositories.scraping.sync_repository import SyncRepository
from services.scraping.catalog_sync_service import CatalogSyncService
from services.scraping.product_diff_service import ProductDiffService


class Product:
    def __init__(
        self,
        code,
        name,
        price,
        category="",
        colors=None,
        color_stock=None,
        url="",
    ):
        self.code = code
        self.name = name
        self.price = price
        self.category = category
        self.colors = list(colors or [])
        self.color_stock = dict(color_stock or {})
        self.url = url


def test_catalog_sync_creates_new_product():
    repository = SyncRepository()
    service = CatalogSyncService(repository, ProductDiffService())

    result = service.synchronize([Product("P001", "Producto A", 10)])

    assert result.created == 1
    assert result.processed == 1
    assert result.classified_total == 1
    assert result.counts_are_consistent


def test_catalog_sync_updates_product():
    repository = SyncRepository()
    repository.save(Product("P001", "Producto A", 10))

    service = CatalogSyncService(repository, ProductDiffService())
    result = service.synchronize([Product("P001", "Producto A", 20)])

    assert result.updated == 1
    assert result.processed == 1
    assert result.counts_are_consistent


def test_catalog_sync_consolidates_product_in_multiple_categories():
    repository = SyncRepository()
    service = CatalogSyncService(repository, ProductDiffService())

    products = [
        Product(
            "P002",
            "Producto compartido",
            10,
            category="Jarros Mug",
            colors=["Rojo"],
            color_stock={"Rojo": 5},
        ),
        Product(
            "P002",
            "Producto compartido",
            10,
            category="Promocionales",
            colors=["Azul"],
            color_stock={"Azul": 7},
        ),
    ]

    result = service.synchronize(products)
    stored = repository.get("P002")

    assert result.created == 1
    assert result.processed == 2
    assert result.classified_total == 1
    assert result.counts_are_consistent
    assert result.products_found == 2
    assert result.products_unique == 1
    assert result.duplicate_occurrences == 1
    assert result.products_multiple_categories == 1
    assert stored.category == "Jarros Mug, Promocionales"
    assert stored.colors == ["Rojo", "Azul"]
    assert stored.color_stock == {"Rojo": 5, "Azul": 7}


def test_catalog_sync_preserves_richer_duplicate_product_fields():
    sparse = Product("P007", "", 0)
    sparse.description = ""
    sparse.price_sample = 0
    sparse.price_hundred = 0
    sparse.price_thousand = 0
    sparse.image_url = ""
    sparse.image_path = ""
    sparse.image_hash = ""

    rich = Product("P007", "Producto completo", 8)
    rich.description = "Detalle completo"
    rich.price_sample = 8
    rich.price_hundred = 70
    rich.price_thousand = 600
    rich.image_url = "https://example.com/p007.jpg"
    rich.image_path = "images/P007.jpg"
    rich.image_hash = "hash-p007"

    consolidated = CatalogSyncService.consolidate_products([sparse, rich])

    assert len(consolidated) == 1
    stored = consolidated[0]
    assert stored.name == "Producto completo"
    assert stored.description == "Detalle completo"
    assert stored.price == 8
    assert stored.price_sample == 8
    assert stored.price_hundred == 70
    assert stored.price_thousand == 600
    assert stored.image_url == "https://example.com/p007.jpg"
    assert stored.image_path == "images/P007.jpg"
    assert stored.image_hash == "hash-p007"


def test_catalog_sync_does_not_overwrite_richer_duplicate_product_fields():
    rich = Product("P008", "Producto completo", 8)
    rich.description = "Detalle completo"
    rich.price_sample = 8
    rich.price_hundred = 70
    rich.price_thousand = 600
    rich.image_url = "https://example.com/p008.jpg"

    sparse = Product("P008", "", 0)
    sparse.description = ""
    sparse.price_sample = 0
    sparse.price_hundred = 0
    sparse.price_thousand = 0
    sparse.image_url = ""

    consolidated = CatalogSyncService.consolidate_products([rich, sparse])

    stored = consolidated[0]
    assert stored.name == "Producto completo"
    assert stored.description == "Detalle completo"
    assert stored.price == 8
    assert stored.price_sample == 8
    assert stored.price_hundred == 70
    assert stored.price_thousand == 600
    assert stored.image_url == "https://example.com/p008.jpg"


def test_catalog_sync_reports_duplicate_occurrences_across_multiple_categories():
    repository = SyncRepository()
    service = CatalogSyncService(repository, ProductDiffService())

    products = [
        Product("P005", "Compartido", 10, category="Jarros"),
        Product("P005", "Compartido", 10, category="Promocionales"),
        Product("P005", "Compartido", 10, category="Oficina"),
        Product("P006", "Único", 12, category="Oficina"),
    ]

    result = service.synchronize(products)

    assert result.products_found == 4
    assert result.products_unique == 2
    assert result.duplicate_occurrences == 2
    assert result.products_multiple_categories == 1
    assert result.processed == 4
    assert result.classified_total == 2
    assert result.counts_are_consistent


def test_catalog_sync_preserves_categories_across_separate_category_syncs():
    repository = SyncRepository()
    service = CatalogSyncService(repository, ProductDiffService())

    first = service.synchronize([
        Product("P003", "Producto compartido", 10, category="Jarros"),
    ])
    second = service.synchronize([
        Product(
            "P003",
            "Producto compartido",
            10,
            category="Artículos de sublimación",
        ),
    ])

    stored = repository.get("P003")

    assert first.created == 1
    assert first.counts_are_consistent
    assert second.updated == 1
    assert second.counts_are_consistent
    assert stored.category == "Jarros, Artículos de sublimación"


def test_catalog_sync_does_not_duplicate_existing_category():
    repository = SyncRepository()
    service = CatalogSyncService(repository, ProductDiffService())

    service.synchronize([Product("P004", "Producto", 10, category="Jarros")])
    result = service.synchronize([
        Product("P004", "Producto", 10, category="jarros"),
    ])

    stored = repository.get("P004")

    assert result.unchanged == 1
    assert result.updated == 0
    assert result.counts_are_consistent
    assert stored.category == "Jarros"


def test_catalog_sync_does_not_create_local_code_when_missing():
    repository = SyncRepository()
    service = CatalogSyncService(repository, ProductDiffService())
    product = Product(
        "",
        "Producto sin código",
        10,
        url="https://stock.importacionesfacundo.com/producto/producto-sin-codigo/",
    )

    result = service.synchronize([product])

    assert result.missing_code == 1
    assert result.created == 0
    assert result.processed == 1
    assert result.classified_total == 0
    assert result.products_unique == 0
    assert product.code == ""
    assert repository.get_all() == []
    assert result.changes[0]["type"] == "MISSING_CODE"


def test_catalog_sync_prunes_every_unmatched_local_code_after_complete_coverage():
    repository = SyncRepository()
    repository.save(Product("AUTO-OLD-12.50-35.00", "Producto provisional", 12.50))
    repository.save(Product("OLD-LEGACY-999", "Otro legado", 99))
    repository.save(Product("KEEP001", "Producto vigente", 20))

    service = CatalogSyncService(repository, ProductDiffService())
    result = service.sync(
        [Product("KEEP001", "Producto vigente", 20)],
        expected_products=1,
    )

    assert result.processed == 1
    assert result.classified_total == 1
    assert result.deleted == 2
    assert repository.get("AUTO-OLD-12.50-35.00") is None
    assert repository.get("OLD-LEGACY-999") is None
    assert repository.get("KEEP001") is not None
    deleted_codes = {
        change["code"]
        for change in result.changes
        if change["type"] == "DELETED"
    }
    assert deleted_codes == {"AUTO-OLD-12.50-35.00", "OLD-LEGACY-999"}


def test_catalog_sync_keeps_unmatched_local_codes_when_coverage_is_incomplete():
    repository = SyncRepository()
    repository.save(Product("OLD001", "Producto antiguo", 10))
    repository.save(Product("KEEP001", "Producto vigente", 20))

    service = CatalogSyncService(repository, ProductDiffService())
    result = service.sync_full_catalog(
        [Product("KEEP001", "Producto vigente", 20)],
        expected_products=2,
    )

    assert result.deleted == 0
    assert repository.get("OLD001") is not None
    assert repository.get("KEEP001") is not None
