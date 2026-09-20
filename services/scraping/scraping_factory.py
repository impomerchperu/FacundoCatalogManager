from pathlib import Path

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
from scrapers.collectors.resilient_category_scraper import (
    ResilientCategoryScraper,
)
from scrapers.extractors.category_extractor import CategoryExtractor
from scrapers.extractors.category_product_extractor import (
    CategoryProductExtractor,
)
from scrapers.extractors.product_card_extractor import ProductCardExtractor
from scrapers.extractors.product_extractor import ProductExtractor
from scrapers.images.image_downloader import ImageDownloader
from scrapers.images.safe_image_manager import SafeImageManager
from scrapers.sync.image_sync import ImageSync
from services.scraping.catalog_sync_service import CatalogSyncService
from services.scraping.category_product_scraping_service import (
    CategoryProductScrapingService,
)
from services.scraping.category_service import CategoryService
from services.scraping.image_sync_adapter import ImageSyncAdapter
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
from tools.clean_unused_images import clean_unused_images


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ScrapingFactory:
    """Construye el pipeline completo de scraping."""

    @staticmethod
    def create_runner(
        config: ScrapingConfig | None = None,
    ) -> ScrapingRunner:
        config = config or ScrapingConfig()
        db = DBManager()

        scraped_repository = ScrapedProductRepository(db)
        scraped_persistence = ScrapedProductPersistenceService(
            scraped_repository,
        )

        sync_service = NormalizedCategoryProductSyncService(
            product_scraping_service,
            scraped_persistence,
            mapper,
            catalog_sync_service,
            image_sync_adapter,
            normalized_repository=normalized_repository,
            image_cleanup=cleanup_unused_images,
            category_workers=config.category_workers,
        )

        return ScrapingRunner(
            sync_service,
            config=config,
            category_service=category_service,
            history_repository=history_repository,
            catalog_repository=product_repository,
            owned_resources=(db,),
        )
