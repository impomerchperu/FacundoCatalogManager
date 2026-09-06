from database.db_manager import DBManager
from models.product import Product
from models.scraping.category import Category
from models.scraping.sync_result import SyncResult
from repositories.product_repository import ProductRepository
from repositories.scraping.normalized_scraping_repository import (
    NormalizedScrapingRepository,
)


def test_normalized_repository_preserves_category_occurrences_for_one_product(tmp_path):
    db = DBManager(str(tmp_path / "catalog.db"))
    product_repository = ProductRepository(db)
    normalized_repository = NormalizedScrapingRepository(db)

    product = product_repository.create(
        Product(
            code="FB-001",
            name="Producto compartido",
            category="Categoria A, Categoria B",
        )
    )
    categories = [
        Category("Categoria A", "https://example.com/a/", expected_count=1),
        Category("Categoria B", "https://example.com/b/", expected_count=1),
    ]

    run_id = normalized_repository.start_run(
        mode="directed",
        categories_requested=2,
        expected_category_occurrences=2,
    )
    occurrences = normalized_repository.persist_occurrences(
        run_id,
        categories,
        [product],
        product_repository,
    )

    rows = db.fetch_all(
        """
        SELECT run_id, category_id, product_id, code
        FROM scraping_product_occurrences
        WHERE run_id = ?
        ORDER BY category_id
        """,
        (run_id,),
    )
    product_category_rows = db.fetch_all(
        """
        SELECT product_id, category_id
        FROM product_categories
        WHERE product_id = ?
        ORDER BY category_id
        """,
        (product.product_id,),
    )

    assert occurrences == 2
    assert len(rows) == 2
    assert {row["code"] for row in rows} == {"FB-001"}
    assert {row["product_id"] for row in rows} == {product.product_id}
    assert len(product_category_rows) == 2


def test_normalized_repository_finish_run_matches_sync_result_summary(tmp_path):
    db = DBManager(str(tmp_path / "catalog.db"))
    repository = NormalizedScrapingRepository(db)
    result = SyncResult(
        products_expected=2,
        expected_category_occurrences=2,
        products_found=2,
        products_unique=1,
        products_multiple_categories=1,
        duplicate_occurrences=1,
        errors=[],
    )
    run_id = repository.start_run(
        mode="directed",
        categories_requested=2,
        expected_category_occurrences=2,
    )

    repository.finish_run(
        run_id,
        result=result,
        actual_category_occurrences=2,
    )

    row = db.fetch_one(
        """
        SELECT status, categories_requested, expected_category_occurrences,
               actual_category_occurrences, products_found, products_unique,
               products_multiple_categories, duplicate_occurrences,
               coverage_complete, coverage_gap, error_count
        FROM scraping_runs
        WHERE id = ?
        """,
        (run_id,),
    )

    assert row["status"] == "SUCCESS"
    assert row["categories_requested"] == 2
    assert row["expected_category_occurrences"] == 2
    assert row["actual_category_occurrences"] == 2
    assert row["products_found"] == 2
    assert row["products_unique"] == 1
    assert row["products_multiple_categories"] == 1
    assert row["duplicate_occurrences"] == 1
    assert row["coverage_complete"] == 1
    assert row["coverage_gap"] == 0
    assert row["error_count"] == 0


def test_normalized_repository_marks_message_as_error(tmp_path):
    db = DBManager(str(tmp_path / "catalog.db"))
    repository = NormalizedScrapingRepository(db)
    result = SyncResult(
        expected_category_occurrences=1,
        products_found=1,
        products_unique=1,
        created=1,
        errors=[],
    )
    run_id = repository.start_run(
        mode="directed",
        categories_requested=1,
        expected_category_occurrences=1,
    )

    repository.finish_run(
        run_id,
        result=result,
        actual_category_occurrences=0,
        message="normalized persistence error: fallo controlado",
    )

    row = db.fetch_one(
        """
        SELECT status, finished_at, actual_category_occurrences,
               coverage_complete, coverage_gap, error_count, message
        FROM scraping_runs
        WHERE id = ?
        """,
        (run_id,),
    )

    assert row["status"] == "ERROR"
    assert row["finished_at"]
    assert row["actual_category_occurrences"] == 0
    assert row["coverage_complete"] == 0
    assert row["coverage_gap"] == 1
    assert row["error_count"] == 0
    assert row["message"] == "normalized persistence error: fallo controlado"
