from time import perf_counter

import pytest

from config.scraping_config import STORE_URL
from database.db_manager import DBManager
from repositories.product_repository import ProductRepository
from repositories.scraping.normalized_scraping_repository import (
    NormalizedScrapingRepository,
)
from repositories.scraping.scraped_product_repository import (
    ScrapedProductRepository,
)
from repositories.scraping.scraping_history_repository import (
    ScrapingHistoryRepository,
)
from scrapers.browser import Browser
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.collectors.resilient_category_scraper import ResilientCategoryScraper
from scrapers.extractors.category_extractor import CategoryExtractor
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.product_card_extractor import ProductCardExtractor
from scrapers.extractors.product_extractor import ProductExtractor
from services.scraping.catalog_sync_service import CatalogSyncService
from services.scraping.category_product_scraping_service import (
    CategoryProductScrapingService,
)
from services.scraping.category_service import CategoryService
from services.scraping.normalized_category_product_sync_service import (
    NormalizedCategoryProductSyncService,
)
from services.scraping.product_diff_service import ProductDiffService
from services.scraping.scraped_product_mapper import ScrapedProductMapper
from services.scraping.scraped_product_persistence_service import (
    ScrapedProductPersistenceService,
)
from services.scraping.scraping_config import ScrapingConfig
from services.scraping.scraping_result_writer import ScrapingResultWriter
from services.scraping.scraping_runner import ScrapingRunner
from services.scraping.scraping_session import ScrapingSession

EXPECTED_CATEGORIES = 24
EXPECTED_CATEGORY_OCCURRENCES = 534
EXPECTED_UNIQUE_PRODUCTS = 530
EXPECTED_MULTI_CATEGORY_PRODUCTS = 4


@pytest.mark.real_site
def test_full_catalog_production_e2e_real_site(tmp_path):
    """Valida FULL real contra el flujo productivo completo y una SQLite aislada."""
    started = perf_counter()
    db = DBManager(str(tmp_path / "catalog.db"))

    product_repository = ProductRepository(db)
    catalog_sync_service = CatalogSyncService(
        product_repository,
        ProductDiffService(),
    )
    catalog_sync_service.result_writer = ScrapingResultWriter()

    scraped_repository = ScrapedProductRepository(db)
    scraped_persistence = ScrapedProductPersistenceService(scraped_repository)
    normalized_repository = NormalizedScrapingRepository(db)
    history_repository = ScrapingHistoryRepository(db)

    config = ScrapingConfig(
        catalog_url=STORE_URL,
        download_images=False,
        category_workers=8,
        detail_workers=24,
        http_workers=28,
    )
    browser = Browser(
        request_timeout=config.request_timeout,
        max_retries=config.max_retries,
        http_workers=config.http_workers,
    )
    category_scraper = ResilientCategoryScraper(
        browser=browser,
        category_extractor=CategoryExtractor(),
    )
    category_service = CategoryService(category_scraper, config.catalog_url)
    collection_scraper = ProductCollectionScraper(
        category_scraper,
        ProductCardExtractor(),
        CategoryProductExtractor(),
        ProductExtractor(),
        max_workers=config.detail_workers,
    )
    product_scraping_service = CategoryProductScrapingService(product_collection_scraper)
    sync_service = NormalizedCategoryProductSyncService(
        product_scraping_service,
        scraped_persistence,
        ScrapedProductMapper(),
        catalog_sync_service,
        None,
        normalized_repository=normalized_repository,
        category_workers=config.category_workers,
    )
    runner = ScrapingRunner(
        sync_service,
        config=config,
        category_service=category_service,
        history_repository=history_repository,
        catalog_repository=product_repository,
    )
    session = ScrapingSession(
        runner,
        history_repository,
        product_repository,
    )

    try:
        result = session.execute_all()
        http_metrics = browser.get_http_metrics()

        assert result.success(), result.errors
        assert result.categories_processed == EXPECTED_CATEGORIES
        assert result.expected_category_occurrences == EXPECTED_CATEGORY_OCCURRENCES
        assert result.products_found == EXPECTED_CATEGORY_OCCURRENCES
        assert result.products_unique == EXPECTED_UNIQUE_PRODUCTS
        assert (
            result.products_multiple_categories == EXPECTED_MULTI_CATEGORY_PRODUCTS
        )
        assert result.category_occurrence_gap == 0
        assert result.history_id is not None

        product_count = db.fetch_one("SELECT COUNT(*) AS count FROM products")
        category_count = db.fetch_one("SELECT COUNT(*) AS count FROM categories")
        relation_count = db.fetch_one(
            "SELECT COUNT(*) AS count FROM product_categories"
        )
        occurrence_count = db.fetch_one(
            """
            SELECT COUNT(*) AS count
            FROM scraping_product_occurrences
            WHERE run_id = (
                SELECT id
                FROM scraping_runs
                ORDER BY id DESC
                LIMIT 1
            )
            """
        )
        run_row = db.fetch_one(
            """
            SELECT status, expected_category_occurrences,
                   actual_category_occurrences, products_found, products_unique,
                   products_multiple_categories, duplicate_occurrences,
                   coverage_complete, coverage_gap, error_count
            FROM scraping_runs
            ORDER BY id DESC
            LIMIT 1
            """
        )
        history_row = db.fetch_one(
            """
            SELECT status, applied_at, categories_processed,
                   products_expected, products_found, products_unique,
                   products_multiple_categories, created, updated, unchanged,
                   deleted, errors
            FROM scraping_history
            ORDER BY id DESC
            LIMIT 1
            """
        )
        change_summary = db.fetch_one(
            """
            SELECT COUNT(*) AS total,
                   COUNT(DISTINCT code) AS codes,
                   SUM(CASE WHEN change_type = 'NEW' THEN 1 ELSE 0 END) AS new_rows,
                   SUM(CASE WHEN change_type != 'NEW' THEN 1 ELSE 0 END) AS other_rows
            FROM download_changes
            WHERE history_id = ?
            """,
            (result.history_id,),
        )

        assert product_count["count"] == EXPECTED_UNIQUE_PRODUCTS
        assert category_count["count"] == EXPECTED_CATEGORIES
        assert relation_count["count"] == EXPECTED_CATEGORY_OCCURRENCES
        assert occurrence_count["count"] == EXPECTED_CATEGORY_OCCURRENCES

        assert run_row["status"] == "SUCCESS"
        assert run_row["expected_category_occurrences"] == EXPECTED_CATEGORY_OCCURRENCES
        assert run_row["actual_category_occurrences"] == EXPECTED_CATEGORY_OCCURRENCES
        assert run_row["products_found"] == EXPECTED_CATEGORY_OCCURRENCES
        assert run_row["products_unique"] == EXPECTED_UNIQUE_PRODUCTS
        assert run_row["products_multiple_categories"] == EXPECTED_MULTI_CATEGORY_PRODUCTS
        assert run_row["coverage_complete"] == 1
        assert run_row["coverage_gap"] == 0
        assert run_row["error_count"] == 0

        assert history_row["status"] == "SUCCESS"
        assert history_row["applied_at"]
        assert history_row["categories_processed"] == EXPECTED_CATEGORIES
        assert history_row["products_expected"] in {0, EXPECTED_UNIQUE_PRODUCTS}
        assert history_row["products_found"] == EXPECTED_CATEGORY_OCCURRENCES
        assert history_row["products_unique"] == EXPECTED_UNIQUE_PRODUCTS
        assert (
            history_row["products_multiple_categories"]
            == EXPECTED_MULTI_CATEGORY_PRODUCTS
        )
        assert history_row["created"] == EXPECTED_UNIQUE_PRODUCTS
        assert history_row["updated"] == 0
        assert history_row["unchanged"] == 0
        assert history_row["deleted"] == 0
        assert history_row["errors"] == 0

        assert change_summary["codes"] == EXPECTED_UNIQUE_PRODUCTS
        assert change_summary["new_rows"] > 0
        assert change_summary["other_rows"] == 0

        assert http_metrics["http_terminal_errors"] == 0
        assert http_metrics["http_retries"] == 0

        print("=" * 80)
        print("FULL PRODUCCIÓN - E2E SCRAPING -> SQLITE -> HISTORIAL")
        print("CATEGORÍAS:", result.categories_processed)
        print("APARICIONES:", result.products_found)
        print("PRODUCTOS ÚNICOS:", result.products_unique)
        print("MULTI-CATEGORÍA:", result.products_multiple_categories)
        print("PRODUCTOS DB:", product_count["count"])
        print("RELACIONES DB:", relation_count["count"])
        print("OCURRENCIAS RUN:", occurrence_count["count"])
        print("HISTORY ID:", result.history_id)
        print("HISTORY APPLIED:", bool(history_row["applied_at"]))
        print("CATEGORY WORKERS:", config.category_workers)
        print("DETAIL WORKERS:", config.detail_workers)
        print("HTTP WORKERS:", config.http_workers)
        print("HTTP REQUESTS:", http_metrics["http_requests"])
        print("HTTP MAX IN FLIGHT:", http_metrics["http_max_in_flight"])
        print("HTTP RETRIES:", http_metrics["http_retries"])
        print("TOTAL E2E:", f"{perf_counter() - started:.2f}s")
        print("=" * 80)
    finally:
        session.close()
        db.close()
