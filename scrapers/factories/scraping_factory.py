from database.db_manager import DBManager
from repositories.scraping.scraped_product_repository import (
    ScrapedProductRepository,
)
from scrapers.browser import Browser
from scrapers.collectors import product_code_patch as _product_code_patch
from scrapers.collectors.category_scraper import (
    CategoryScraper,
)
from scrapers.extractors.category_product_extractor import (
    CategoryProductExtractor,
)
from services.scraping.category_product_scraping_service import (
    CategoryProductScrapingService,
)
from services.scraping.category_product_sync_service import (
    CategoryProductSyncService,
)
from services.scraping.scraped_product_persistence_service import (
    ScrapedProductPersistenceService,
)
from services.scraping.scraping_runner import ScrapingRunner


class ScrapingFactory:
    """
    Construye dependencias del pipeline de scraping.
    """

    @staticmethod
    def create():

        db = DBManager()

        repository = ScrapedProductRepository(
            db,
        )

        persistence_service = (
            ScrapedProductPersistenceService(
                repository,
            )
        )

        browser = Browser()

        product_block_extractor = (
            CategoryProductExtractor()
        )

        scraper = CategoryScraper(
            browser=browser,
            product_block_extractor=product_block_extractor,
        )

        scraping_service = (
            CategoryProductScrapingService(
                scraper,
            )
        )

        sync_service = (
            CategoryProductSyncService(
                scraping_service,
                persistence_service,
            )
        )

        return ScrapingRunner(
            sync_service,
        )
