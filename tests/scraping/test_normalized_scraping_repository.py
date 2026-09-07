from database.db_manager import DBManager
from models.product import Product
from models.scraping.category import Category
from models.scraping.sync_result import SyncResult
from repositories.product_repository import ProductRepository
from repositories.scraping.normalized_scraping_repository import (
    NormalizedScrapingRepository,
)


def test_normalized_repository_persists_run_relations_and_occurrences():
    db = DBManager(":memory:")
    product_repository = ProductRepository(db)
    product_repository.save(
        Product(
            code="FB-1000",
            name="Producto normalizado",
            category="Categoría A, Categoría B",
        )
    )

    repository = NormalizedScrapingRepository(db)
    categories = [
        Category(
            name="Categoría A",
            url="https://example.test/categoria-a/?page=1#fragment",
            expected_count=2,
        ),
        Category(
            name="Categoría B",
            url="https://example.test/categoria-b/",
            expected_count=1,
        ),
    ]
    products = [
        Product(
            code="FB-1000",
            name="Producto normalizado",
            category="Categoría A, Categoría B",
            image_url="https://example.test/producto/",
        )
    ]
    result = SyncResult()
    result.expected_category_occurrences = 3
    result.products_found = 1
    result.products_unique = 1
    result.products_multiple_categories = 1

    run_id = repository.start_run(
        mode="directed",
        categories_requested=2,
        expected_category_occurrences=3,
    )
    actual = repository.persist_occurrences(
        run_id,
        categories,
        products,
        product_repository,
    )
    repository.finish_run(
        run_id,
        result=result,
        actual_category_occurrences=actual,
    )

    assert actual == 2
    assert db.fetch_one("SELECT COUNT(*) AS n FROM categories")["n"] == 2
    assert db.fetch_one("SELECT COUNT(*) AS n FROM product_categories")["n"] == 2
    assert (
        db.fetch_one("SELECT COUNT(*) AS n FROM scraping_product_occurrences")["n"]
        == 2
    )

    run = db.fetch_one("SELECT * FROM scraping_runs WHERE id=?", (run_id,))
    assert run["mode"] == "directed"
    assert run["categories_requested"] == 2
    assert run["expected_category_occurrences"] == 3
    assert run["actual_category_occurrences"] == 2
    assert run["coverage_gap"] == 1
    assert run["coverage_complete"] == 0

    category = db.fetch_one(
        "SELECT canonical_url FROM categories WHERE name=?",
        ("Categoría A",),
    )
    assert category["canonical_url"] == "https://example.test/categoria-a"

    db.close()


def test_normalized_repository_matches_canonical_category_aliases():
    db = DBManager(":memory:")
    product_repository = ProductRepository(db)
    product_repository.save(
        Product(
            code="FB-2000",
            name="Producto cocina",
            category="Cocina, Mesa y Hogar",
        )
    )

    repository = NormalizedScrapingRepository(db)
    categories = [
        Category(
            name="Cocina",
            url="https://example.test/cocina/",
            expected_count=1,
        )
    ]
    products = [
        Product(
            code="FB-2000",
            name="Producto cocina",
            category="Cocina, Mesa y Hogar",
        )
    ]

    run_id = repository.start_run(
        mode="directed",
        categories_requested=1,
        expected_category_occurrences=1,
    )
    actual = repository.persist_occurrences(
        run_id,
        categories,
        products,
        product_repository,
    )

    assert actual == 1
    assert db.fetch_one("SELECT COUNT(*) AS n FROM product_categories")["n"] == 1
    assert (
        db.fetch_one("SELECT COUNT(*) AS n FROM scraping_product_occurrences")["n"]
        == 1
    )

    db.close()


def test_normalized_repository_does_not_hide_a_category_gap_with_global_overage():
    db = DBManager(":memory:")
    repository = NormalizedScrapingRepository(db)
    result = SyncResult(
        expected_category_occurrences=20,
        products_found=20,
        products_unique=20,
        unchanged=20,
        category_summary=[
            {"category": "Categoría A", "expected": 10, "products": 9, "gap": 1},
            {"category": "Categoría B", "expected": 10, "products": 11, "gap": 0},
        ],
    )

    run_id = repository.start_run(
        mode="full",
        categories_requested=2,
        expected_category_occurrences=20,
    )
    repository.finish_run(
        run_id,
        result=result,
        actual_category_occurrences=20,
    )

    run = db.fetch_one("SELECT * FROM scraping_runs WHERE id=?", (run_id,))

    assert run["actual_category_occurrences"] == 20
    assert run["coverage_gap"] == 0
    assert run["coverage_complete"] == 0
    assert run["status"] == "ERROR"

    db.close()
