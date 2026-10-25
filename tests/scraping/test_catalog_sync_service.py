import hashlib
from pathlib import Path

import services.scraping.catalog_sync_service as catalog_sync_module
from services.scraping.catalog_sync_service import CatalogSyncService
from services.scraping.product_diff_service import ProductDiffService
from tests.scraping.catalog_sync_test_doubles import InMemoryCatalogRepository
from tests.scraping.image_test_utils import image_bytes


class Product:
    def __init__(
        self,
        code: str,
        name: str,
        price: float,
        category: str = "",
        colors: list[str] | None = None,
        color_stock: dict[str, int] | None = None,
        url: str = "",
    ) -> None:
        self.code = code
        self.name = name
        self.price = price
        self.category = category
        self.colors = list(colors or [])
        self.color_stock = dict(color_stock or {})
        self.url = url

        self.description = ""
        self.price_sample = 0.0
        self.price_hundred = 0.0
        self.price_thousand = 0.0
        self.image_url = ""
        self.image_path = ""
        self.image_hash = ""
        self.image_etag = ""
        self.image_last_modified = ""
        self.image_checked_at = ""
        self.gallery_images = []
        self.content_hash = ""


def test_catalog_sync_creates_new_product():
    repository = InMemoryCatalogRepository()
    service = CatalogSyncService(repository, ProductDiffService())

    result = service.synchronize([Product("P001", "Producto A", 10)])

    assert result.created == 1
    assert result.processed == 1
    assert result.classified_total == 1
    assert result.counts_are_consistent


def test_catalog_sync_updates_product():
    repository = InMemoryCatalogRepository()
    repository.save(Product("P001", "Producto A", 10))

    service = CatalogSyncService(repository, ProductDiffService())
    result = service.synchronize([Product("P001", "Producto A", 20)])

    assert result.updated == 1
    assert result.processed == 1
    assert result.counts_are_consistent


def test_catalog_sync_preserves_existing_prices_on_partial_update():
    repository = InMemoryCatalogRepository()
    existing = Product("P010", "Producto A", 8.5)
    existing.price_sample = 8.5
    existing.price_hundred = 770.0
    existing.price_thousand = 7500.0
    repository.save(existing)

    incoming = Product("P010", "Producto A actualizado", 0)
    incoming.price_sample = 0
    incoming.price_hundred = 0
    incoming.price_thousand = 0

    service = CatalogSyncService(repository, ProductDiffService())
    result = service.synchronize([incoming])
    stored = repository.get("P010")
    assert stored is not None

    assert result.updated == 1
    assert stored.price == 8.5
    assert stored.price_sample == 8.5
    assert stored.price_hundred == 770.0
    assert stored.price_thousand == 7500.0
    assert stored.name == "Producto A actualizado"


def test_catalog_sync_preserves_existing_prices_independently():
    repository = InMemoryCatalogRepository()
    existing = Product("P011", "Producto B", 8.5)
    existing.price_sample = 8.5
    existing.price_hundred = 770.0
    existing.price_thousand = 7500.0
    repository.save(existing)

    incoming = Product("P011", "Producto B", 9.0)
    incoming.price_sample = 9.0
    incoming.price_hundred = 0
    incoming.price_thousand = 8000.0

    service = CatalogSyncService(repository, ProductDiffService())
    service.synchronize([incoming])
    stored = repository.get("P011")
    assert stored is not None

    assert stored.price == 9.0
    assert stored.price_sample == 9.0
    assert stored.price_hundred == 770.0
    assert stored.price_thousand == 8000.0


def test_catalog_sync_consolidates_product_in_multiple_categories():
    repository = InMemoryCatalogRepository()
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
    assert stored is not None

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
    rich.description = "Material: Poliuretano. Peso unitario: 23.5 g."
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
    assert stored.description == "Material: Poliuretano. Peso unitario: 23.5 g."
    assert stored.price == 8
    assert stored.price_sample == 8
    assert stored.price_hundred == 70
    assert stored.price_thousand == 600
    assert stored.image_url == "https://example.com/p007.jpg"
    assert stored.image_path == "images/P007.jpg"
    assert stored.image_hash == "hash-p007"


def test_catalog_sync_does_not_overwrite_richer_duplicate_product_fields():
    rich = Product("P008", "Producto completo", 8)
    rich.description = "Material: Poliuretano. Peso unitario: 23.5 g."
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
    assert stored.description == "Material: Poliuretano. Peso unitario: 23.5 g."
    assert stored.price == 8
    assert stored.price_sample == 8
    assert stored.price_hundred == 70
    assert stored.price_thousand == 600
    assert stored.image_url == "https://example.com/p008.jpg"


def test_catalog_sync_reports_duplicate_occurrences_across_multiple_categories():
    repository = InMemoryCatalogRepository()
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


def test_incomplete_full_sync_preserves_existing_category_memberships():
    repository = InMemoryCatalogRepository()
    existing = Product(
        "FB-1908",
        "Tarjeta de PVC 5.4 x 8.6 cm - CR80",
        45,
        category=(
            "Artículos de Oficina, Papeles Fotográficos Koala Paper, "
            "Promocionales, Jarros Mug"
        ),
    )
    repository.save(existing)

    service = CatalogSyncService(repository, ProductDiffService())
    incoming = Product(
        "FB-1908",
        "Tarjeta de PVC 5.4 x 8.6 cm - CR80",
        45,
        category="Artículos de Oficina",
    )
    result = service.sync_full_catalog(
        [incoming],
        expected_products=2,
    )

    stored = repository.get("FB-1908")
    assert stored is not None
    assert stored.category == existing.category
    assert result.updated == 0
    assert result.unchanged == 1


def test_full_sync_blocks_prune_when_category_occurrences_are_missing():
    repository = InMemoryCatalogRepository()
    existing = Product(
        "KEEP001",
        "Producto vigente",
        20,
        category="Categoria A, Categoria B",
    )
    repository.save(existing)
    repository.save(Product("OLD001", "Producto anterior", 10))

    service = CatalogSyncService(repository, ProductDiffService())
    incoming = Product(
        "KEEP001",
        "Producto vigente",
        20,
        category="Categoria A",
    )
    result = service.sync_full_catalog(
        [incoming],
        expected_products=1,
        expected_category_occurrences=2,
    )

    stored = repository.get("KEEP001")
    assert result.coverage_complete is False
    assert result.success is False
    assert result.deleted == 0
    assert repository.get("OLD001") is not None
    assert stored is not None
    assert stored.category == existing.category
    assert result.updated == 0


def test_full_sync_removes_stale_categories_from_existing_product():
    repository = InMemoryCatalogRepository()
    existing = Product(
        "FB-1908",
        "Tarjeta de PVC 5.4 x 8.6 cm - CR80",
        45,
        category=(
            "Artículos de Oficina, Papeles Fotográficos Koala Paper, "
            "Promocionales, Jarros Mug"
        ),
    )
    repository.save(existing)

    service = CatalogSyncService(repository, ProductDiffService())
    incoming = Product(
        "FB-1908",
        "Tarjeta de PVC 5.4 x 8.6 cm - CR80",
        45,
        category="Artículos de Oficina",
    )
    result = service.sync_full_catalog(
        [incoming],
        expected_products=1,
    )

    stored = repository.get("FB-1908")
    assert stored is not None
    assert result.updated == 1
    assert stored.category == "Artículos de Oficina"


def test_catalog_sync_preserves_categories_across_separate_category_syncs():
    repository = InMemoryCatalogRepository()
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
    assert stored is not None

    assert first.created == 1
    assert first.counts_are_consistent
    assert second.updated == 1
    assert second.counts_are_consistent
    assert stored.category == "Jarros, Artículos de sublimación"


def test_catalog_sync_does_not_duplicate_existing_category():
    repository = InMemoryCatalogRepository()
    service = CatalogSyncService(repository, ProductDiffService())

    service.synchronize([Product("P004", "Producto", 10, category="Jarros")])
    result = service.synchronize([
        Product("P004", "Producto", 10, category="jarros"),
    ])

    stored = repository.get("P004")
    assert stored is not None

    assert result.unchanged == 1
    assert result.updated == 0
    assert result.counts_are_consistent
    assert stored.category == "Jarros"


def test_catalog_sync_does_not_create_local_code_when_missing():
    repository = InMemoryCatalogRepository()
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
    assert result.changes == []


def test_catalog_sync_prunes_every_unmatched_local_code_after_complete_coverage():
    repository = InMemoryCatalogRepository()
    repository.save(Product("AUTO-OLD-12.50-35.00", "Producto provisional", 12.50))
    repository.save(Product("OLD-LEGACY-999", "Otro legado", 99))
    repository.save(Product("KEEP001", "Producto vigente", 20))

    service = CatalogSyncService(repository, ProductDiffService())
    result = service.sync_full_catalog(
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
    repository = InMemoryCatalogRepository()
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


def test_catalog_sync_is_idempotent_after_initial_create():
    repository = InMemoryCatalogRepository()
    service = CatalogSyncService(repository, ProductDiffService())

    products = [
        Product(
            "P009",
            "Producto estable",
            12,
            category="Categoria A",
        ),
        Product(
            "P009",
            "Producto estable",
            12,
            category="Categoria B",
        ),
        Product(
            "P010",
            "Otro producto",
            18,
            category="Categoria A",
        ),
    ]

    first = service.synchronize(products)
    second = service.synchronize(
        [
            Product("P009", "Producto estable", 12, category="Categoria A"),
            Product("P009", "Producto estable", 12, category="Categoria B"),
            Product("P010", "Otro producto", 18, category="Categoria A"),
        ]
    )

    assert first.created == 2
    assert first.updated == 0
    assert first.unchanged == 0
    assert first.counts_are_consistent

    assert second.created == 0
    assert second.updated == 0
    assert second.unchanged == 2
    assert second.deleted == 0
    assert second.changes == []
    assert second.counts_are_consistent

    stored = repository.get("P009")
    assert stored is not None
    assert stored.content_hash


def test_catalog_sync_cleans_unused_images_only_after_allowed_prune():
    repository = InMemoryCatalogRepository()
    old_product = Product("OLD001", "Producto antiguo", 10)
    old_product.image_path = "data/images/products/OLD001/OLD001-01.webp"
    old_product.image_hash = "old-image-hash"
    old_product.gallery_images = [
        {
            "url": "https://site.test/old-gallery.webp",
            "image_path": "data/images/products/OLD001/OLD001-02.webp",
            "image_hash": "old-gallery-hash",
            "position": 1,
        }
    ]
    repository.save(old_product)
    cleanup_calls = []

    def cleanup():
        # Cleanup must run after the full-catalog prune has actually removed
        # the product from the persisted repository, not just after scrape end.
        assert repository.get("OLD001") is None
        cleanup_calls.append(True)
        return [
            {"path": "data/images/products/OLD001/OLD001-01.webp"},
            {"path": "data/images/products/OLD001/OLD001-02.webp"},
        ]

    service = CatalogSyncService(
        repository,
        ProductDiffService(),
        image_cleanup=cleanup,
    )

    result = service.sync_full_catalog(
        [Product("KEEP001", "Producto vigente", 20)],
        expected_products=1,
    )

    assert result.deleted == 1
    assert repository.get("OLD001") is None
    assert cleanup_calls == [True]


def test_catalog_sync_does_not_clean_images_for_generic_sync():
    repository = InMemoryCatalogRepository()
    repository.save(Product("OLD001", "Producto antiguo", 10))
    cleanup_calls = []

    def cleanup():
        cleanup_calls.append(True)
        return [{"path": "old.webp"}]

    service = CatalogSyncService(
        repository,
        ProductDiffService(),
        image_cleanup=cleanup,
    )

    result = service.sync(
        [Product("KEEP001", "Producto vigente", 20)],
        expected_products=1,
    )

    assert result.deleted == 1
    assert cleanup_calls == []


def test_catalog_sync_does_not_clean_images_when_full_prune_is_blocked():
    repository = InMemoryCatalogRepository()
    repository.save(Product("OLD001", "Producto antiguo", 10))
    repository.save(Product("KEEP001", "Producto vigente", 20))
    cleanup_calls = []

    def cleanup():
        cleanup_calls.append(True)
        return [{"path": "old.webp"}]

    service = CatalogSyncService(
        repository,
        ProductDiffService(),
        image_cleanup=cleanup,
    )

    result = service.sync_full_catalog(
        [Product("KEEP001", "Producto vigente", 20)],
        expected_products=2,
    )

    assert result.deleted == 0
    assert cleanup_calls == []


def test_catalog_sync_updates_color_stock_and_reports_the_changed_field():
    repository = InMemoryCatalogRepository()
    service = CatalogSyncService(repository, ProductDiffService())

    service.synchronize(
        [
            Product(
                "COLOR001",
                "Producto por color",
                10,
                category="Categoria A",
                color_stock={"Rojo": 4, "Azul": 6},
            )
        ]
    )

    incoming = Product(
        "COLOR001",
        "Producto por color",
        10,
        category="Categoria A",
        color_stock={"Rojo": 8, "Azul": 6},
    )
    incoming.stock = 14

    result = service.synchronize([incoming])
    stored = repository.get("COLOR001")

    assert stored is not None
    assert result.updated == 1
    assert result.counts_are_consistent
    assert stored.color_stock == {"Rojo": 8, "Azul": 6}
    assert stored.stock == 14
    assert result.changes[0]["type"] == "UPDATED"
    assert any(
        change["field"] == "color_stock"
        and change["label"] == "Stock por color"
        for change in result.changes[0]["changes"]
    )


def test_catalog_sync_is_idempotent_when_color_stock_is_unchanged():
    repository = InMemoryCatalogRepository()
    service = CatalogSyncService(repository, ProductDiffService())

    product = Product(
        "COLOR002",
        "Producto estable por color",
        12,
        category="Categoria A",
        color_stock={"Negro": 5, "Blanco": 7},
    )
    product.stock = 12

    first = service.synchronize([product])
    incoming = Product(
        "COLOR002",
        "Producto estable por color",
        12,
        category="Categoria A",
        color_stock={"Negro": 5, "Blanco": 7},
    )
    incoming.stock = 12
    second = service.synchronize([incoming])

    assert first.created == 1
    assert second.updated == 0
    assert second.unchanged == 1
    assert second.changes == []
    assert second.counts_are_consistent

class BulkLookupRepository:
    def __init__(self):
        self.products = {}
        self.bulk_calls = []
        self.get_calls = 0
        self.save_with_existing_calls = 0

    def get_by_codes(self, codes):
        self.bulk_calls.append(list(codes))
        return {
            code.casefold(): self.products[code.casefold()]
            for code in codes
            if code.casefold() in self.products
        }

    def get(self, code):
        self.get_calls += 1
        return self.products.get(code.casefold())

    def save_with_existing(self, product, existing=None):
        self.save_with_existing_calls += 1
        if existing is not None:
            product.product_id = getattr(existing, "product_id", None)
        self.products[product.code.casefold()] = product
        return product

    def get_all(self):
        return list(self.products.values())

    def delete_by_code(self, code):
        self.products.pop(code.casefold(), None)


def test_catalog_sync_uses_one_bulk_lookup_for_existing_products():
    repository = BulkLookupRepository()
    repository.save_with_existing(Product("P100", "Producto A", 10))
    repository.save_with_existing(Product("P101", "Producto B", 11))

    service = CatalogSyncService(repository, ProductDiffService())
    result = service.synchronize(
        [
            Product("P100", "Producto A actualizado", 12),
            Product("P101", "Producto B actualizado", 13),
        ]
    )

    assert result.updated == 2
    assert repository.bulk_calls == [["P100", "P101"]]
    assert repository.get_calls == 0
    assert repository.save_with_existing_calls == 4
    assert result.counts_are_consistent


def test_catalog_sync_bulk_lookup_preserves_case_insensitive_identity():
    repository = BulkLookupRepository()
    repository.save_with_existing(Product("p200", "Producto", 10))

    service = CatalogSyncService(repository, ProductDiffService())
    result = service.synchronize([Product("P200", "Producto actualizado", 11)])

    assert result.updated == 1
    assert repository.bulk_calls == [["P200"]]
    assert repository.get_calls == 0
    assert repository.products["p200".casefold()].name == "Producto actualizado"

class TransactionTracker:
    def __init__(self):
        self._transaction_active = False
        self.begins = 0
        self.commits = 0
        self.rollbacks = 0

    def begin(self):
        if self._transaction_active:
            raise RuntimeError("transaction already active")
        self._transaction_active = True
        self.begins += 1

    def commit(self):
        if not self._transaction_active:
            raise RuntimeError("no active transaction")
        self._transaction_active = False
        self.commits += 1

    def rollback(self):
        self._transaction_active = False
        self.rollbacks += 1


class TransactionAwareRepository(BulkLookupRepository):
    def __init__(self):
        super().__init__()
        self.db = TransactionTracker()


def test_catalog_sync_groups_canonical_repository_writes_in_one_transaction():
    repository = TransactionAwareRepository()
    service = CatalogSyncService(repository, ProductDiffService())

    result = service.synchronize(
        [
            Product("TX001", "Producto A", 10),
            Product("TX002", "Producto B", 20),
        ]
    )

    assert result.created == 2
    assert repository.db.begins == 1
    assert repository.db.commits == 1
    assert repository.db.rollbacks == 0


class FailingTransactionRepository(TransactionAwareRepository):
    def save_with_existing(self, product, existing=None):
        del product, existing
        raise RuntimeError("simulated persistence failure")


def test_catalog_sync_rolls_back_when_persistence_fails():
    repository = FailingTransactionRepository()
    service = CatalogSyncService(repository, ProductDiffService())

    try:
        service.synchronize([Product("TX004", "Producto", 10)])
    except RuntimeError as error:
        assert str(error) == "simulated persistence failure"
    else:
        raise AssertionError("se esperaba RuntimeError")

    assert repository.db.begins == 1
    assert repository.db.commits == 0
    assert repository.db.rollbacks == 1


def test_catalog_sync_does_not_start_a_nested_transaction():
    repository = TransactionAwareRepository()
    repository.db._transaction_active = True
    service = CatalogSyncService(repository, ProductDiffService())

    result = service.synchronize([Product("TX003", "Producto", 10)])

    assert result.created == 1
    assert repository.db.begins == 0
    assert repository.db.commits == 0
    assert repository.db.rollbacks == 0


def test_catalog_sync_preserves_existing_description_when_source_detail_is_incomplete():
    repository = InMemoryCatalogRepository()
    existing = Product("P099", "Producto vigente", 10)
    existing.description = (
        "Material: ABS. Peso neto por caja: 5.5 Kg. "
        "Peso bruto por caja: 6.25 Kg."
    )
    existing.price_sample = 10.0
    repository.save(existing)

    incoming = Product("P099", "Producto vigente", 10)
    incoming.description = ""
    incoming.price_sample = 10.0

    service = CatalogSyncService(repository, ProductDiffService())
    result = service.synchronize([incoming])

    stored = repository.get("P099")
    assert stored is not None
    assert stored.description == existing.description
    assert result.updated == 0
    assert result.unchanged == 1


def test_catalog_sync_replaces_existing_description_with_verified_complete_detail():
    repository = InMemoryCatalogRepository()
    existing = Product("P098", "Producto vigente", 10)
    existing.description = "Resumen antiguo de la tarjeta."
    existing.price_sample = 10.0
    repository.save(existing)

    incoming = Product("P098", "Producto vigente", 10)
    incoming.description = (
        "Material: Poliuretano. Peso neto por caja: 5.5 Kg. "
        "Peso bruto por caja: 6.25 Kg."
    )
    incoming.price_sample = 10.0

    service = CatalogSyncService(repository, ProductDiffService())
    result = service.synchronize([incoming])

    stored = repository.get("P098")
    assert stored is not None
    assert stored.description == (
        "Material: Poliuretano. Peso neto por caja: 5.5 Kg. "
        "Peso bruto por caja: 6.25 Kg."
    )
    assert result.updated == 1
    assert any(
        change["field"] == "description"
        for change in result.changes[0]["changes"]
    )


def test_catalog_sync_keeps_technical_detail_when_incoming_text_is_commercial_prose():
    repository = InMemoryCatalogRepository()
    existing = Product("P097", "Producto vigente", 10)
    existing.description = (
        "Color: Blanco. Material: Poliuretano. "
        "Peso neto por caja: 5.5 Kg. Peso bruto por caja: 6.25 Kg."
    )
    existing.price_sample = 10.0
    repository.save(existing)

    incoming = Product("P097", "Producto vigente", 10)
    incoming.description = "Descripción promocional general."
    incoming.price_sample = 10.0

    service = CatalogSyncService(repository, ProductDiffService())
    result = service.synchronize([incoming])

    stored = repository.get("P097")
    assert stored is not None
    assert stored.description == (
        "Material: Poliuretano. "
        "Peso neto por caja: 5.5 Kg. Peso bruto por caja: 6.25 Kg."
    )
    assert "Color:" not in stored.description
    # Cleaning the legacy color field is a single legitimate catalog update.
    assert result.updated == 1
    assert result.unchanged == 0


def test_catalog_sync_preserves_summary_description_with_technical_fields():
    repository = InMemoryCatalogRepository()
    incoming = Product("P092", "Producto nuevo", 10)
    incoming.description = (
        "Descripción: Elegante y funcional. Material: ABS. Dimensiones: 12 cm."
    )

    service = CatalogSyncService(repository, ProductDiffService())
    service.synchronize([incoming])

    stored = repository.get("P092")
    assert stored is not None
    assert stored.description == incoming.description


def test_catalog_sync_consolidation_does_not_select_commercial_prose_as_detail():
    first = Product("P093", "Producto vigente", 10)
    second = Product("P093", "Producto vigente", 10)
    second.description = "Descripción comercial: producto promocional."

    consolidated = CatalogSyncService.consolidate_products([first, second])

    assert len(consolidated) == 1
    assert consolidated[0].description == ""


def test_catalog_sync_does_not_save_commercial_prose_as_new_technical_detail():
    repository = InMemoryCatalogRepository()
    incoming = Product("P094", "Producto nuevo", 10)
    incoming.description = "Descripción promocional general."

    service = CatalogSyncService(repository, ProductDiffService())
    result = service.synchronize([incoming])

    stored = repository.get("P094")
    assert stored is not None
    assert stored.description == ""
    assert result.created == 1


def test_catalog_sync_uses_more_informative_description_across_duplicate_codes():
    repository = InMemoryCatalogRepository()
    service = CatalogSyncService(repository, ProductDiffService())

    first = Product("P096", "Producto vigente", 10)
    first.description = "Material: ABS. Peso bruto por..."
    second = Product("P096", "Producto vigente", 10)
    second.description = (
        "Color: Blanco. Material: Poliuretano. "
        "Peso neto por caja: 5.5 Kg. Peso bruto por caja: 6.25 Kg."
    )

    result = service.synchronize([first, second])

    stored = repository.get("P096")
    assert stored is not None
    assert stored.description == second.description
    assert result.created == 1


def test_catalog_sync_refreshes_complete_detail_across_duplicate_codes():
    first = Product("P094", "Producto vigente", 10)
    first.description = (
        "Material: ABS. Peso neto por caja: 5.5 Kg. "
        "Peso bruto por caja: 6.25 Kg."
    )

    refreshed = Product("P094", "Producto vigente", 10)
    refreshed.description = (
        "Material: Poliuretano. Peso neto por caja: 6.5 Kg. "
        "Peso bruto por caja: 7.25 Kg."
    )

    consolidated = CatalogSyncService.consolidate_products([first, refreshed])

    assert len(consolidated) == 1
    assert consolidated[0].description == refreshed.description


def test_catalog_sync_does_not_save_an_incomplete_description_for_new_product():
    repository = InMemoryCatalogRepository()
    incoming = Product("P095", "Producto nuevo", 10)
    incoming.description = "Material: ABS. Peso bruto por..."

    service = CatalogSyncService(repository, ProductDiffService())
    result = service.synchronize([incoming])

    stored = repository.get("P095")
    assert stored is not None
    assert stored.description == ""
    assert result.created == 1


def test_failed_image_download_clears_broken_local_reference(tmp_path):
    existing = Product("FB-9911", "Producto", 10)
    existing.image_url = "https://example.test/FB-9911-old.jpg"
    existing.image_path = str(tmp_path / "missing.jpg")
    existing.image_hash = "stale-hash"
    existing.image_etag = '"old-etag"'
    existing.image_last_modified = "Sun, 18 Oct 2026 00:00:00 GMT"
    existing.image_checked_at = "2026-10-18T00:00:00+00:00"

    incoming = Product("FB-9911", "Producto", 10)
    incoming.image_url = "https://example.test/FB-9911-new.jpg"

    CatalogSyncService._preserve_existing_image_state(existing, incoming)

    assert incoming.image_url == "https://example.test/FB-9911-new.jpg"
    assert incoming.image_path == ""
    assert incoming.image_hash == ""
    assert incoming.image_etag == ""
    assert incoming.image_last_modified == ""
    assert incoming.image_checked_at == ""


def test_failed_refresh_keeps_only_a_verified_current_image(tmp_path):
    current_file = tmp_path / "FB-9912.jpg"
    current_file.write_bytes(image_bytes("JPEG", (34, 56, 78)))

    existing = Product("FB-9912", "Producto", 10)
    existing.image_url = "https://example.test/FB-9912-old.jpg"
    existing.image_path = str(current_file)
    existing.image_hash = "historically-wrong-hash"
    existing.image_etag = '"old-etag"'

    incoming = Product("FB-9912", "Producto", 10)
    incoming.image_url = "https://example.test/FB-9912-new.jpg"

    CatalogSyncService._preserve_existing_image_state(existing, incoming)

    assert incoming.image_url == "https://example.test/FB-9912-old.jpg"
    assert incoming.image_path == str(current_file)
    assert incoming.image_hash != "historically-wrong-hash"
    assert incoming.image_etag == '"old-etag"'


def test_catalog_sync_runs_image_cleanup_after_gallery_reference_update(
    tmp_path,
    monkeypatch,
):
    import scrapers.images.product_image_storage as storage_module

    monkeypatch.setattr(
        catalog_sync_module,
        "resolve_data_path",
        lambda value: Path(value) if Path(value).is_absolute() else tmp_path / value,
    )
    products_root = tmp_path / "data" / "images" / "products"
    monkeypatch.setattr(catalog_sync_module, "IMAGE_PRODUCTS_DIR", products_root)
    monkeypatch.setattr(
        storage_module,
        "to_data_relative_path",
        lambda value: str(Path(value).resolve().relative_to(tmp_path)).replace("\\", "/"),
    )

    old_primary = products_root / "FB-1507.webp"
    legacy_gallery = tmp_path / "data" / "images" / "gallery" / "FB-1507"
    product_dir = products_root / "FB-1507"
    legacy_gallery.mkdir(parents=True)
    product_dir.mkdir(parents=True)
    primary_bytes = image_bytes("WEBP", (12, 34, 56))
    scaled_bytes = image_bytes("WEBP", (56, 67, 78))
    alternate_bytes = image_bytes("WEBP", (89, 90, 91))
    old_primary.write_bytes(primary_bytes)
    (legacy_gallery / "FB-1507-01.webp").write_bytes(scaled_bytes)
    (legacy_gallery / "FB-1507-02.webp").write_bytes(primary_bytes)
    (legacy_gallery / "FB-1507-03.webp").write_bytes(alternate_bytes)
    canonical_primary = product_dir / "FB-1507-01.webp"
    canonical_scaled = product_dir / "FB-1507-02.webp"
    canonical_alternate = product_dir / "FB-1507-03.webp"
    canonical_primary.write_bytes(primary_bytes)
    canonical_scaled.write_bytes(scaled_bytes)
    canonical_alternate.write_bytes(alternate_bytes)

    repository = InMemoryCatalogRepository()
    existing = Product("FB-1507", "Producto FB-1507", 10)
    existing.image_url = "https://site.test/uploads/FB-1507-2.webp"
    existing.image_path = "data/images/products/FB-1507.webp"
    existing.image_hash = hashlib.sha256(primary_bytes).hexdigest()
    existing.gallery_images = [
        {
            "url": "https://site.test/uploads/FB-1507-2-scaled.webp",
            "image_path": "data/images/gallery/FB-1507/FB-1507-01.webp",
            "image_hash": hashlib.sha256(scaled_bytes).hexdigest(),
            "position": 1,
        },
        {
            "url": "https://site.test/uploads/FB-1507-2.webp",
            "image_path": "data/images/gallery/FB-1507/FB-1507-02.webp",
            "image_hash": hashlib.sha256(primary_bytes).hexdigest(),
            "position": 2,
        },
        {
            "url": "https://site.test/uploads/FB-1507.webp",
            "image_path": "data/images/gallery/FB-1507/FB-1507-03.webp",
            "image_hash": hashlib.sha256(alternate_bytes).hexdigest(),
            "position": 3,
        },
    ]
    repository.save(existing)

    incoming = Product("FB-1507", "Producto FB-1507", 10)
    incoming.image_url = existing.image_url
    incoming.image_path = "data/images/products/FB-1507/FB-1507-01.webp"
    incoming.image_hash = hashlib.sha256(primary_bytes).hexdigest()
    incoming.gallery_images = [
        {
            "url": existing.image_url,
            "image_path": incoming.image_path,
            "image_hash": incoming.image_hash,
            "position": 1,
        },
        {
            "url": "https://site.test/uploads/FB-1507-2-scaled.webp",
            "image_path": "data/images/products/FB-1507/FB-1507-02.webp",
            "image_hash": hashlib.sha256(scaled_bytes).hexdigest(),
            "position": 2,
        },
        {
            "url": "https://site.test/uploads/FB-1507.webp",
            "image_path": "data/images/products/FB-1507/FB-1507-03.webp",
            "image_hash": hashlib.sha256(alternate_bytes).hexdigest(),
            "position": 3,
        },
    ]

    cleanup_snapshots = []

    def cleanup():
        stored = repository.get("FB-1507")
        assert stored is not None
        cleanup_snapshots.append(
            {
                "image_path": stored.image_path,
                "gallery_paths": [
                    image["image_path"] for image in stored.gallery_images
                ],
            }
        )
        return []

    service = CatalogSyncService(
        repository,
        ProductDiffService(),
        image_cleanup=cleanup,
    )
    result = service.sync([incoming], prune_missing=False)

    assert result.updated == 1
    assert any(
        change["field"] == "gallery_images"
        for change in result.changes[0]["changes"]
    )
    assert len(cleanup_snapshots) == 1
    assert cleanup_snapshots[0]["image_path"] == incoming.image_path
    assert "data/images/gallery/FB-1507/FB-1507-02.webp" not in (
        cleanup_snapshots[0]["gallery_paths"]
    )
    assert cleanup_snapshots[0]["gallery_paths"] == [
        incoming.image_path,
        "data/images/products/FB-1507/FB-1507-02.webp",
        "data/images/products/FB-1507/FB-1507-03.webp",
    ]


def test_catalog_sync_drops_unidentifiable_and_duplicate_legacy_gallery_entries(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        catalog_sync_module,
        "resolve_data_path",
        lambda value: (
            Path(value) if Path(value).is_absolute() else tmp_path / value
        ),
    )
    product_root = tmp_path / "data" / "images" / "products"
    gallery_root = tmp_path / "data" / "images" / "gallery" / "P099"
    product_root.mkdir(parents=True)
    gallery_root.mkdir(parents=True)

    invalid_primary = product_root / "P099.webp"
    invalid_primary.write_bytes(b"not an image")
    valid_duplicate = image_bytes("WEBP", (12, 34, 56))
    first_gallery = gallery_root / "P099-01.webp"
    duplicate_gallery = gallery_root / "P099-02.webp"
    invalid_gallery = gallery_root / "P099-03.webp"
    first_gallery.write_bytes(valid_duplicate)
    duplicate_gallery.write_bytes(valid_duplicate)
    invalid_gallery.write_bytes(b"not a raster")

    monkeypatch.setattr(
        catalog_sync_module,
        "IMAGE_PRODUCTS_DIR",
        product_root,
    )
    existing = Product("P099", "Legacy product", 10)
    existing.image_url = "https://site.test/P099.webp"
    existing.image_path = "data/images/products/P099.webp"
    existing.image_hash = "stale-hash"
    existing.gallery_images = [
        {
            "url": "https://site.test/P099-gallery-1.webp",
            "image_path": "data/images/gallery/P099/P099-01.webp",
            "image_hash": "old-1",
            "position": 1,
        },
        {
            "url": "https://site.test/P099-gallery-2.webp",
            "image_path": "data/images/gallery/P099/P099-02.webp",
            "image_hash": "old-2",
            "position": 2,
        },
        {
            "url": "https://site.test/P099-gallery-bad.webp",
            "image_path": "data/images/gallery/P099/P099-03.webp",
            "image_hash": "old-bad",
            "position": 3,
        },
    ]
    incoming = Product("P099", "Legacy product", 10)

    CatalogSyncService._preserve_existing_image_state(existing, incoming)
    CatalogSyncService._normalize_product_image_state(incoming)

    assert incoming.image_url == "https://site.test/P099-gallery-1.webp"
    assert incoming.image_path
    assert incoming.image_hash == hashlib.sha256(valid_duplicate).hexdigest()
    assert len(incoming.gallery_images) == 1
    assert incoming.gallery_images[0]["image_hash"] == hashlib.sha256(valid_duplicate).hexdigest()
    assert Path(
        catalog_sync_module.resolve_data_path(
            incoming.gallery_images[0]["image_path"]
        )
    ).is_file()
    assert "P099-02.webp" not in incoming.gallery_images[0]["image_path"]
    assert invalid_primary.is_file()
    assert duplicate_gallery.is_file()
    assert invalid_gallery.is_file()


def test_catalog_sync_cleans_unused_images_after_new_image_bearing_product(
    tmp_path,
    monkeypatch,
):
    import scrapers.images.product_image_storage as storage_module

    monkeypatch.setattr(
        catalog_sync_module,
        "resolve_data_path",
        lambda value: Path(value) if Path(value).is_absolute() else tmp_path / value,
    )
    products_root = tmp_path / "data" / "images" / "products"
    monkeypatch.setattr(catalog_sync_module, "IMAGE_PRODUCTS_DIR", products_root)
    monkeypatch.setattr(
        storage_module,
        "to_data_relative_path",
        lambda value: str(Path(value).resolve().relative_to(tmp_path)).replace("\\", "/"),
    )
    source = products_root / "P101" / "P101-01.png"
    source.parent.mkdir(parents=True)
    payload = image_bytes("PNG", (42, 53, 64))
    source.write_bytes(payload)

    repository = InMemoryCatalogRepository()
    cleanup_snapshots = []

    def cleanup():
        stored = repository.get("P101")
        assert stored is not None
        cleanup_snapshots.append(stored.image_path)
        return [{"path": "legacy/orphan.webp"}]

    incoming = Product("P101", "Nuevo producto", 10)
    incoming.image_path = "data/images/products/P101/P101-01.png"
    incoming.image_hash = hashlib.sha256(payload).hexdigest()
    incoming.gallery_images = [
        {
            "url": "https://site.test/P101.png",
            "image_path": incoming.image_path,
            "image_hash": incoming.image_hash,
            "position": 1,
            "source": "primary",
        }
    ]

    service = CatalogSyncService(
        repository,
        ProductDiffService(),
        image_cleanup=cleanup,
    )
    result = service.synchronize([incoming])

    assert result.created == 1
    assert cleanup_snapshots == ["data/images/products/P101/P101-01.png"]

def test_catalog_sync_clears_unidentifiable_image_refs_before_post_commit_cleanup(
    tmp_path,
    monkeypatch,
):
    import scrapers.images.product_image_storage as storage_module

    monkeypatch.setattr(
        catalog_sync_module,
        "resolve_data_path",
        lambda value: Path(value) if Path(value).is_absolute() else tmp_path / value,
    )
    products_root = tmp_path / "data" / "images" / "products"
    monkeypatch.setattr(catalog_sync_module, "IMAGE_PRODUCTS_DIR", products_root)
    monkeypatch.setattr(
        storage_module,
        "to_data_relative_path",
        lambda value: str(Path(value).resolve().relative_to(tmp_path)).replace("\\", "/"),
    )

    invalid_path = products_root / "P102" / "P102-01.webp"
    invalid_path.parent.mkdir(parents=True)
    invalid_path.write_bytes(b"html or arbitrary bytes, not a raster image")

    incoming = Product("P102", "Producto inválido", 10)
    incoming.image_url = "https://site.test/P102.webp"
    incoming.image_path = "data/images/products/P102/P102-01.webp"
    incoming.image_hash = "stale-hash"
    incoming.image_etag = '"stale-etag"'
    incoming.gallery_images = [
        {
            "url": incoming.image_url,
            "image_path": incoming.image_path,
            "image_hash": "stale-hash",
            "position": 1,
        }
    ]

    repository = InMemoryCatalogRepository()
    cleanup_observations = []

    def cleanup():
        stored = repository.get("P102")
        assert stored is not None
        cleanup_observations.append(
            (stored.image_path, stored.image_hash, list(stored.gallery_images))
        )
        invalid_path.unlink(missing_ok=True)
        return [{"path": str(invalid_path)}]

    service = CatalogSyncService(
        repository,
        ProductDiffService(),
        image_cleanup=cleanup,
    )
    result = service.synchronize([incoming])

    stored = repository.get("P102")
    assert result.created == 1
    assert stored is not None
    assert stored.image_url == "https://site.test/P102.webp"
    assert stored.image_path == ""
    assert stored.image_hash == ""
    assert stored.image_etag == ""
    assert stored.image_last_modified == ""
    assert stored.image_checked_at == ""
    assert stored.gallery_images == []
    assert cleanup_observations == [("", "", [])]
    assert not invalid_path.exists()

def test_catalog_sync_repairs_truncated_fb4008_detail_with_complete_technical_source():
    repository = InMemoryCatalogRepository()
    existing = Product("FB-4008", "Antiestrés Cerebro Largo", 4.0)
    existing.description = (
        "Color: Blanco. Material: Poliuretano. Dimensiones: 75*63*48mm. "
        "Peso Unitario: 23.5 G. Uso Recomendado: Antiestrés,"
    )
    existing.price_sample = 4.0
    repository.save(existing)

    incoming = Product("FB-4008", "Antiestrés Cerebro Largo", 4.0)
    incoming.description = (
        "Color: Blanco. Material: Poliuretano. Dimensiones: 75*63*48mm. "
        "Peso Unitario: 23.5 G. Uso Recomendado: Antiestrés, Promocional. "
        "Empaque Individual: Bolsa de polietileno. Cantidad Por Caja: 250 Pza. "
        "Dimensiones Caja: 50*42*42cm. Cubicaje por Caja: 0.0882 m³/CBM. "
        "Peso neto por caja: 5.5 Kg. Peso bruto por caja: 6.25 Kg."
    )
    incoming.price_sample = 4.0

    service = CatalogSyncService(repository, ProductDiffService())
    result = service.synchronize([incoming])

    stored = repository.get("FB-4008")
    assert stored is not None
    assert stored.description == (
        "Material: Poliuretano. Dimensiones: 75*63*48mm. "
        "Peso Unitario: 23.5 G. Uso Recomendado: Antiestrés, Promocional. "
        "Empaque Individual: Bolsa de polietileno. Cantidad Por Caja: 250 Pza. "
        "Dimensiones Caja: 50*42*42cm. Cubicaje por Caja: 0.0882 m³/CBM. "
        "Peso neto por caja: 5.5 Kg. Peso bruto por caja: 6.25 Kg."
    )
    assert result.updated == 1
    assert any(
        change["field"] == "description"
        for change in result.changes[0]["changes"]
    )
