from __future__ import annotations

from pathlib import Path

from database.db_manager import DBManager
from repositories.product_repository import ProductRepository
from repositories.scraped_product_repository import ScrapedProductRepository
from repositories.scraping.history_repository import ScrapingHistoryRepository
from repositories.scraping.normalized_scraping_repository import NormalizedScrapingRepository
from services.scraping.category_product_scraping_service import CategoryProductScrapingService
from services.scraping.category_product_sync_service import CategoryProductSyncService
from services.scraping.category_service import CategoryService
from services.scraping.image_sync_adapter import ImageSyncAdapter
from services.scraping.product_diff_service import ProductDiffService
from services.scraping.scraped_product_mapper import ScrapedProductMapper
from services.scraping.scraped_product_persistence_service import ScrapedProductPersistenceService
from services.scraping.scraping_config import ScrapingConfig
from services.scraping.scraping_runner import ScrapingRunner
from services.scraping.scraping_result_writer import ScrapingResultWriter
from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.product_extractor import ProductExtractor
from scrapers.extractors.stock_extractor import StockExtractor
from scrapers.extractors.price_extractor import PriceExtractor
from scrapers.browser import Browser
from scrapers.resilient_category_scraper import ResilientCategoryScraper


class ScrapingFactory:
    """Construye la cadena canónica de scraping."""

    @staticmethod
    def create_runner(config: ScrapingConfig | None = None) -> ScrapingRunner:
        config = config or ScrapingConfig()
        db = DBManager()

        scraped_repository = ScrapedProductRepository(db)
        scraped_persistence = ScrapedProductPersistenceService(
            scraped_repository,
        )

        product_repository = ProductRepository(db)
        catalog_sync_service = CategoryProductSyncService(
            product_repository,
            ProductDiffService(),
        )
        catalog_sync_service.result_writer = ScrapingResultWriter()
        normalized_repository = NormalizedScrapingRepository(db)
        mapper = ScrapedProductMapper()

        history_repository = ScrapingHistoryRepository(db)

        image_sync_adapter = None
        if config.download_images:
            image_output_dir = Path(config.images_folder)
            if image_output_dir.name.casefold() != "products":
                image_output_dir /= "products"
            image_sync_adapter = ImageSyncAdapter(image_output_dir)

        browser = Browser(
            request_timeout=config.request_timeout,
            max_retries=config.max_retries,
        )
        category_scraper = CategoryScraper(browser)
        resilient_category_scraper = ResilientCategoryScraper(category_scraper)
        category_extractor = CategoryProductExtractor()
        product_extractor = ProductExtractor()
        stock_extractor = StockExtractor()
        price_extractor = PriceExtractor()
        product_collection_scraper = ProductCollectionScraper(
            browser=browser,
            product_extractor=product_extractor,
            stock_extractor=stock_extractor,
            price_extractor=price_extractor,
        )
        category_service = CategoryService(
            resilient_category_scraper,
            category_extractor,
        )
        scraping_service = CategoryProductScrapingService(
            category_service=category_service,
            category_scraper=resilient_category_scraper,
            product_collection_scraper=product_collection_scraper,
            category_extractor=category_extractor,
        )
        normalized_sync_service = CategoryProductSyncService(
            product_repository=product_repository,
            product_diff_service=ProductDiffService(),
        )

        return ScrapingRunner(
            config=config,
            scraping_service=scraping_service,
            sync_service=normalized_sync_service,
            scraped_persistence=scraped_persistence,
            mapper=mapper,
            history_repository=history_repository,
            image_sync_adapter=image_sync_adapter,
            db=db,
        )
