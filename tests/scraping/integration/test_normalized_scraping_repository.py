from database.db_manager import DBManager
from models.product import Product
from models.scraping.category import Category
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
