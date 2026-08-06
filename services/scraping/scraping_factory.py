from database.db_manager import DBManager
from repositories.scraping.scraped_product_repository import (
    ScrapedProductRepository,
)
from scrapers.browser import Browser
from scrapers.collectors.category_scraper import (
    CategoryScraper,
)
from scrapers.collectors.product_collection_scraper import (
    ProductCollectionScraper,
)
from scrapers.extractors.category_product_extractor import (
    CategoryProductExtractor,
)
from scrapers.extractors.product_card_extractor import (
    ProductCardExtractor,
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
from services.scraping.scraping_runner import (
    ScrapingRunner,
)


class ScrapingFactory:
    """
    Construye pipeline completo de scraping.
    """

    @staticmethod
    def create_runner():

        db = DBManager()

        repository = ScrapedProductRepository(
            db,
        )

        persistence_service = ScrapedProductPersistenceService(
            repository,
        )

        browser = Browser()

        category_scraper = CategoryScraper(
            browser=browser,
        )

        collection_scraper = ProductCollectionScraper(
            category_scraper,
            ProductCardExtractor(),
            CategoryProductExtractor(),
        )

        scraping_service = CategoryProductScrapingService(
            collection_scraper,
        )

        sync_service = CategoryProductSyncService(
            scraping_service,
            persistence_service,
        )

        return ScrapingRunner(
            sync_service,
        )
