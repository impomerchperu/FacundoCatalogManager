import pytest

from database.db_manager import DBManager
from models.product import Product
from models.scraping.category import Category
from models.scraping.sync_result import SyncResult
from repositories.product_repository import ProductRepository
from repositories.scraping.normalized_scraping_repository import (
    NormalizedScrapingRepository,
)


def test_finish_run_rejects_incomplete_sync_when_expected_occurrences_are_zero():
    db = DBManager(":memory:")
    repository = NormalizedScrapingRepository(db)
    result = SyncResult(
        products_found=1,
        products_unique=1,
        created=1,
        missing_code=1,
    )

    run_id = repository.start_run(
        mode="directed",
        categories_requested=0,
        expected_category_occurrences=0,
    )
    repository.finish_run(
        run_id,
        result=result,
        actual_category_occurrences=1,
    )

    row = db.fetch_one(
        "SELECT status, coverage_complete, error_count FROM scraping_runs WHERE id=?",
        (run_id,),
    )

    assert row["status"] == "ERROR"
    assert row["coverage_complete"] == 0
    assert row["error_count"] == 0
    db.close()


def test_persist_occurrences_rejects_missing_master_product():
    db = DBManager(":memory:")
    repository = NormalizedScrapingRepository(db)
    product_repository = ProductRepository(db)
    categories = [
        Category(
            "Categoria A",
            "https://example.com/categoria-a/",
            expected_count=1,
        )
    ]
    products = [
        Product(
            code="MISSING-001",
            name="Producto sin maestro",
            category="Categoria A",
            image_url="https://example.com/producto/",
        )
    ]

    run_id = repository.start_run(
        mode="directed",
        categories_requested=1,
        expected_category_occurrences=1,
    )

    with pytest.raises(
        RuntimeError,
        match="No existe el producto maestro.*MISSING-001",
    ):
        repository.persist_occurrences(
            run_id,
            categories,
            products,
            product_repository,
        )

    assert db.fetch_one("SELECT COUNT(*) AS n FROM product_categories")["n"] == 0
    assert (
        db.fetch_one("SELECT COUNT(*) AS n FROM scraping_product_occurrences")["n"]
        == 0
    )
    db.close()
