from services.scraping.category_product_scraping_service import (
    CategoryProductScrapingService,
)
from services.scraping.scraped_product_persistence_service import (
    ScrapedProductPersistenceService,
)


class CategoryProductSyncService:
    """
    Orquesta extracción y persistencia de productos
    obtenidos desde páginas categoría.
    """

    def __init__(
        self,
        scraper_service: CategoryProductScrapingService,
        persistence_service: ScrapedProductPersistenceService,
    ):
        self.scraper_service = scraper_service
        self.persistence_service = persistence_service

    def sync_category(
        self,
        category_url: str,
        category: str = "",
    ):
        products = self.scraper_service.scrape_category(
            category_url,
            category,
        )

        saved = self.persistence_service.save_products(
            products,
        )

        return saved
