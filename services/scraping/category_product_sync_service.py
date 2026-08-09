from models.scraping.sync_result import SyncResult
from services.scraping.category_product_scraping_service import (
    CategoryProductScrapingService,
)
from services.scraping.scraped_product_persistence_service import (
    ScrapedProductPersistenceService,
)


class CategoryProductSyncService:
    """
    Orquesta extracción y preparación de productos obtenidos
    desde categorías.

    La nueva versión del catálogo se persiste posteriormente
    mediante CatalogLoadRepository.
    """

    def __init__(
        self,
        scraper_service: CategoryProductScrapingService,
        persistence_service: ScrapedProductPersistenceService,
        mapper=None,
        catalog_sync_service=None,
        image_sync_adapter=None,
    ):
        self.scraper_service = scraper_service
        self.persistence_service = persistence_service

        self.mapper = mapper
        self.catalog_sync_service = catalog_sync_service
        self.image_sync_adapter = image_sync_adapter

        self.last_sync_result = SyncResult()

    def sync_category(
        self,
        category_url: str,
        category: str = "",
    ):
        products = self.scraper_service.scrape_category(
            category_url,
            category,
        )

        if (
            self.mapper
            and self.catalog_sync_service
        ):
            if self.image_sync_adapter:
                products = self.image_sync_adapter.sync_products(
                    products,
                )

            mapped_products = [
                self.mapper.map(product)
                for product in products
            ]

            result = self.catalog_sync_service.sync(
                mapped_products,
            )

            self._accumulate_sync_result(result)
            return mapped_products

        return self.persistence_service.save_products(products)

    def reset_sync_result(self):
        """Reinicia métricas antes de una ejecución completa."""
        self.last_sync_result = SyncResult()

    def _accumulate_sync_result(self, result: SyncResult):
        """Acumula resultados de todas las categorías."""
        self.last_sync_result.processed += result.processed
        self.last_sync_result.created += result.created
        self.last_sync_result.updated += result.updated
        self.last_sync_result.unchanged += result.unchanged
        self.last_sync_result.errors.extend(result.errors)
        self.last_sync_result.failures.extend(result.failures)
        self.last_sync_result.changes.extend(result.changes)
