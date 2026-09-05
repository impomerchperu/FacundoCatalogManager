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
