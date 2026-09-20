from datetime import datetime, timezone

from database.db_manager import DBManager
from models.product import Product
from models.scraping.scraping_history import ScrapingHistory
from repositories.product_repository import ProductRepository
from repositories.scraping.scraping_history_repository import ScrapingHistoryRepository
from services.scraping.catalog_sync_service import CatalogSyncService
from services.scraping.product_diff_service import ProductDiffService


def _history_from_result(result, finished_at: datetime) -> ScrapingHistory:
    return ScrapingHistory(
        started_at=finished_at.replace(microsecond=0),
        finished_at=finished_at,
        processed=result.processed,
        created=result.created,
        updated=result.updated,
        unchanged=result.unchanged,
        deleted=result.deleted,
        generated=result.generated,
        categories_processed=2,
        products_expected=result.products_unique,
        products_found=result.products_found,
        products_unique=result.products_unique,
        products_multiple_categories=result.products_multiple_categories,
        duplicate_occurrences=result.duplicate_occurrences,
        errors=0,
        status="SUCCESS",
    )


def _products():
    return [
        Product(
            code="IDEMP-001",
            name="Producto estable",
            category="Categoria A",
            description="Detalle estable",
            price=12.5,
            price_sample=12.5,
            price_hundred=110.0,
            price_thousand=1000.0,
            stock=25,
            color_stock={"Rojo": 10},
        ),
        Product(
            code="IDEMP-002",
            name="Segundo producto",
            category="Categoria B",
            description="Otro detalle",
            price=18.0,
            price_sample=18.0,
            price_hundred=165.0,
            price_thousand=1500.0,
            stock=12,
        ),
    ]


def test_catalog_sync_is_idempotent_on_same_sqlite_and_history(tmp_path):
    db = DBManager(str(tmp_path / "catalog.db"))
    product_repository = ProductRepository(db)
    history_repository = ScrapingHistoryRepository(db)
    service = CatalogSyncService(
        product_repository,
        ProductDiffService(),
    )

    try:
        first_products = _products()
        first = service.sync(
            first_products,
            prune_missing=False,
            expected_products=2,
            expected_category_occurrences=2,
        )
        first_finished_at = datetime(2026, 9, 20, 4, 30, tzinfo=timezone.utc)
        first_history_id = history_repository.save(
            _history_from_result(first, first_finished_at),
            first.changes,
            first_products,
        )

        second_products = _products()
        second = service.sync(
            second_products,
            prune_missing=False,
            expected_products=2,
            expected_category_occurrences=2,
        )
        second_finished_at = datetime(2026, 9, 20, 4, 31, tzinfo=timezone.utc)
        second_history_id = history_repository.save(
            _history_from_result(second, second_finished_at),
            second.changes,
            _products(),
        )

        product_count = db.fetch_one(
            "SELECT COUNT(*) AS count FROM products"
        )
        change_count = db.fetch_one(
            """
            SELECT COUNT(*) AS count
            FROM download_changes
            WHERE history_id = ?
            """,
            (second_history_id,),
        )
        applied_rows = db.fetch_all(
            """
            SELECT id, applied_at
            FROM scraping_history
            WHERE applied_at IS NOT NULL
            ORDER BY id
            """
        )

        assert first.created == 2
        assert first.updated == 0
        assert first.unchanged == 0
        assert first.changes

        assert second.created == 0
        assert second.updated == 0
        assert second.unchanged == 2
        assert second.deleted == 0
        assert second.changes == []
        assert second.counts_are_consistent

        assert product_count["count"] == 2
        assert change_count["count"] == 0
        assert history_repository.get_by_id(first_history_id).applied_at is None
        assert history_repository.get_by_id(second_history_id).applied_at == second_finished_at
        assert len(applied_rows) == 1
        assert applied_rows[0]["id"] == second_history_id
        assert applied_rows[0]["applied_at"] == second_finished_at.isoformat()
    finally:
        db.close()
