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
    assert result.processed == 1
    assert result.classified_total == 1
    assert result.counts_are_consistent
    assert result.products_found == 2
    assert result.products_unique == 1
    assert result.duplicate_occurrences == 1
    assert result.products_multiple_categories == 1
    assert stored.category == "Jarros Mug, Promocionales"
    assert stored.colors == ["Rojo", "Azul"]
    assert stored.color_stock == {"Rojo": 5, "Azul": 7}


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
    assert result.processed == 2
    assert result.classified_total == 2
    assert result.counts_are_consistent


def test_catalog_sync_preserves_categories_across_separate_category_syncs():
    repository = SyncRepository()
    service = CatalogSyncService(repository, ProductDiffService())

    first = service.synchronize([
        Product(
            "P003",
            "Producto compartido",
            10,
            category="Jarros",
        ),
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

    service.synchronize([
        Product("P004", "Producto", 10, category="Jarros"),
    ])

    result = service.synchronize([
        Product("P004", "Producto", 10, category="jarros"),
    ])

    stored = repository.get("P004")

    assert result.unchanged == 1
    assert result.updated == 0
    assert result.counts_are_consistent
    assert stored.category == "Jarros"


def test_catalog_sync_generates_stable_auditable_code_when_missing():
    repository = SyncRepository()
    service = CatalogSyncService(repository, ProductDiffService())

    product = Product(
        "",
        "Producto sin código",
        10,
        url="https://stock.importacionesfacundo.com/producto/producto-sin-codigo/",
    )

    result = service.synchronize([product])

    assert result.generated == 1
    assert result.created == 0
    assert result.processed == 0
    assert product.code.startswith("AUTO-PRODUCTO-SIN-CODIGO-")
    assert repository.get_all() == []
    assert result.changes[0]["type"] == "CODE_GENERATED"
    assert result.changes[0]["code"] == product.code


def test_catalog_sync_full_cleanup_removes_old_generated_code():
    repository = SyncRepository()
    repository.save(Product("AUTO-OLD-PRODUCT-12345678", "Producto provisional", 10))
    repository.save(Product("KEEP001", "Producto vigente", 20))

    service = CatalogSyncService(repository, ProductDiffService())
    result = service.sync(
        [Product("KEEP001", "Producto vigente", 20)],
        prune_missing=False,
        cleanup_generated=True,
    )

    assert result.deleted == 1
    assert repository.get("AUTO-OLD-PRODUCT-12345678") is None
    assert repository.get("KEEP001") is not None
    assert any(
        change["type"] == "DELETED"
        and change["code"] == "AUTO-OLD-PRODUCT-12345678"
        for change in result.changes
    )


def test_catalog_sync_prunes_codes_not_present_in_scraping():
    repository = SyncRepository()
    repository.save(Product("OLD001", "Producto antiguo", 10))
    repository.save(Product("KEEP001", "Producto vigente", 20))

    service = CatalogSyncService(repository, ProductDiffService())
    result = service.sync_full_catalog([
        Product("KEEP001", "Producto vigente", 20),
    ])

    assert result.deleted == 1
    assert repository.get("OLD001") is None
    assert repository.get("KEEP001") is not None
    assert any(
        change["type"] == "DELETED" and change["code"] == "OLD001"
        for change in result.changes
    )
