from __future__ import annotations

import json
import os

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from config.scraping_config import BASE_URL, STORE_URL
from controllers.product_controller import ProductController
from database.db_manager import DBManager
from gui.product_table import ProductTable
from models.scraping.category import Category
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
from services.product_service import ProductService
from services.scraping.catalog_sync_service import CatalogSyncService
from services.scraping.category_product_scraping_service import (
    CategoryProductScrapingService,
)
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

CATEGORY_NAME = "Bolsas / Mochilas"
CATEGORY_URL = f"{BASE_URL}/categoria-producto/bolsas-mochilas/"


def _qapp() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _build_session(db: DBManager) -> ScrapingSession:
    config = ScrapingConfig(
        catalog_url=STORE_URL,
        download_images=False,
        category_workers=1,
        detail_workers=16,
        http_workers=28,
        jsf_http_concurrency=8,
        jsf_page_workers=2,
    )
    browser = Browser(
        request_timeout=config.request_timeout,
        max_retries=config.max_retries,
        http_workers=config.http_workers,
    )
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

    category_scraper = ResilientCategoryScraper(
        browser=browser,
        category_extractor=CategoryExtractor(),
        jsf_http_concurrency=config.jsf_http_concurrency,
        jsf_page_workers=config.jsf_page_workers,
    )
    category_service = None
    collection_scraper = ProductCollectionScraper(
        category_scraper,
        ProductCardExtractor(),
        CategoryProductExtractor(),
        ProductExtractor(),
        max_workers=config.detail_workers,
    )
    product_scraping_service = CategoryProductScrapingService(collection_scraper)
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
    return session


@pytest.mark.real_site
def test_real_category_color_stock_is_persisted_and_rendered_in_product_table(
    tmp_path,
) -> None:
    _qapp()
    db = DBManager(str(tmp_path / "catalog.db"))
    session = _build_session(db)

    try:
        result = session.execute(
            [
                Category(
                    name=CATEGORY_NAME,
                    url=CATEGORY_URL,
                )
            ]
        )

        assert result.success(), result.errors

        color_products = [
            product
            for product in result.products
            if str(product.category).strip() == CATEGORY_NAME
            and len(getattr(product, "color_stock", {}) or {}) >= 2
            and any(
                int(stock) > 0
                for stock in (getattr(product, "color_stock", {}) or {}).values()
            )
        ]

        assert color_products, (
            "La categoría real debe producir al menos un producto "
            "con stock explícito por color."
        )

        source_product = color_products[0]
        expected_color_stock = dict(source_product.color_stock)
        expected_total_stock = sum(expected_color_stock.values())

        db_row = db.fetch_one(
            """
            SELECT code, stock, color_stock, category
            FROM products
            WHERE code = ?
            """,
            (source_product.code,),
        )
        assert db_row is not None
        assert db_row["category"] == CATEGORY_NAME
        assert db_row["stock"] == expected_total_stock

        persisted_color_stock = json.loads(db_row["color_stock"] or "{}")
        assert persisted_color_stock == expected_color_stock

        repository_product = ProductRepository(db).get_by_code(source_product.code)
        assert repository_product is not None
        assert repository_product.stock == expected_total_stock
        assert repository_product.color_stock == expected_color_stock

        controller = ProductController(
            ProductService(ProductRepository(db)),
        )
        table = ProductTable(controller)
        table.load_products()

        matching_rows = [
            row
            for row in range(table.rowCount())
            if table.item(row, ProductTable.CODE_COLUMN)
            and table.item(row, ProductTable.CODE_COLUMN).text()
            == source_product.code
        ]
        assert len(matching_rows) == 1

        row = matching_rows[0]
        stock_widget = table.cellWidget(row, ProductTable.STOCK_COLUMN)
        assert isinstance(stock_widget, QLabel)

        rendered = stock_widget.text()
        tooltip = stock_widget.toolTip()

        for color, stock in expected_color_stock.items():
            assert str(color) in rendered
            assert f"{stock:,}" in rendered
            assert f"{color}: {stock}" in tooltip

        assert str(expected_total_stock) not in tooltip

        table.close()

        history_row = db.fetch_one(
            """
            SELECT status, applied_at, products_found
            FROM scraping_history
            ORDER BY id DESC
            LIMIT 1
            """
        )
        assert history_row is not None
        assert history_row["status"] == "SUCCESS"
        assert history_row["applied_at"]
        assert history_row["products_found"] == result.products_found
    finally:
        session.close()
        db.close()
