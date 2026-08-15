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

    La sincronización del catálogo se realiza una sola vez por
    ejecución completa para que los productos presentes en varias
    categorías puedan consolidarse correctamente.
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
        return self.sync_products(products)

    def sync_categories(
        self,
        categories,
        progress_callback=None,
    ):
        """
        Scrapea todas las categorías y sincroniza el conjunto completo.

        La sincronización conjunta es importante porque un mismo código
        puede aparecer en más de una categoría. La consolidación se hace
        antes de descargar imágenes, mapear y comparar contra el catálogo.
        """
        products = []
        total = len(categories)

        for index, category in enumerate(categories, start=1):
            products.extend(
                self.scraper_service.scrape_category(
                    category.url,
                    category.name,
                )
            )

            if progress_callback:
                progress_callback(index, total)

        return self.sync_products(products)

    def sync_products(self, products):
        """Procesa y sincroniza un conjunto consolidado de productos scrapeados."""
        if self.mapper and self.catalog_sync_service:
            consolidate = getattr(
                self.catalog_sync_service,
                "consolidate_products",
                None,
            )
            if callable(consolidate):
                products = consolidate(products)

            if self.image_sync_adapter:
                products = self.image_sync_adapter.sync_products(products)

            mapped_products = [
                self.mapper.map(product)
                for product in products
            ]

            result = self.catalog_sync_service.sync(mapped_products)
            self._accumulate_sync_result(result)
            return mapped_products

        return self.persistence_service.save_products(products)

    def reset_sync_result(self):
        """Reinicia métricas antes de una ejecución completa."""
        self.last_sync_result = SyncResult()

    def _accumulate_sync_result(self, result: SyncResult):
        """Acumula resultados de sincronizaciones realizadas en una sesión."""
        self.last_sync_result.processed += result.processed
        self.last_sync_result.created += result.created
        self.last_sync_result.updated += result.updated
        self.last_sync_result.unchanged += result.unchanged
        self.last_sync_result.errors.extend(result.errors)
        self.last_sync_result.failures.extend(result.failures)
        self.last_sync_result.changes.extend(result.changes)
