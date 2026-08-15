from database.db_manager import DBManager
from repositories.product_repository import ProductRepository
from repositories.scraping.scraped_product_repository import (
    ScrapedProductRepository,
)
from repositories.scraping.scraping_history_repository import (
    ScrapingHistoryRepository,
)
from scrapers.browser import Browser
from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.collectors.product_collection_scraper import (
    ProductCollectionScraper,
)
from scrapers.extractors.category_product_extractor import (
    CategoryProductExtractor,
)
from scrapers.extractors.product_card_extractor import ProductCardExtractor
from scrapers.extractors.product_extractor import ProductExtractor
from services.scraping.catalog_sync_service import CatalogSyncService
from services.scraping.category_product_scraping_service import (
    CategoryProductScrapingService,
)
from services.scraping.category_product_sync_service import (
    CategoryProductSyncService,
)
from services.scraping.category_service import CategoryService
from services.scraping.image_sync_adapter import ImageSyncAdapter
from services.scraping.product_diff_service import ProductDiffService
from services.scraping.scraped_product_mapper import ScrapedProductMapper
from services.scraping.scraped_product_persistence_service import (
    ScrapedProductPersistenceService,
)
from services.scraping.scraping_runner import ScrapingRunner


class ScrapingFactory:
    """Construye el pipeline completo de scraping y sincronización."""

    CATALOG_URL = "https://stock.importacionesfacundo.com/tienda/"

    @staticmethod
    def create_runner():
        db = DBManager()

        product_repository = ProductRepository(db)
        catalog_sync_service = CatalogSyncService(
            product_repository,
            ProductDiffService(),
        )
        mapper = ScrapedProductMapper()
        image_sync_adapter = ImageSyncAdapter()

        scraped_repository = ScrapedProductRepository(db)
        persistence_service = ScrapedProductPersistenceService(
            scraped_repository,
        )

        browser = Browser()

        category_scraper = CategoryScraper(
            browser=browser,
        )

        collection_scraper = ProductCollectionScraper(
            category_scraper,
            ProductCardExtractor(),
            CategoryProductExtractor(),
            detail_extractor=ProductExtractor(),
        )

        scraping_service = CategoryProductScrapingService(
            collection_scraper,
        )

        sync_service = CategoryProductSyncService(
            scraping_service,
            persistence_service,
            mapper=mapper,
            catalog_sync_service=catalog_sync_service,
            image_sync_adapter=image_sync_adapter,
        )

        category_service = CategoryService(
            category_scraper,
            ScrapingFactory.CATALOG_URL,
        )

        history_repository = ScrapingHistoryRepository(db)

        return ScrapingRunner(
            sync_service,
            category_service=category_service,
            history_repository=history_repository,
        )
