import logging
import time
from pathlib import Path

from models.scraping.sync_result import SyncResult
from services.scraping.category_product_scraping_service import (
    CategoryProductScrapingService,
)
from services.scraping.scraped_product_persistence_service import (
    ScrapedProductPersistenceService,
)


logger = logging.getLogger("FCM")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
TIMING_LOG = PROJECT_ROOT / "data" / "scraping_timing.log"


def _log_timing(message, *args):
    """Registra diagnóstico en el logger y en un archivo del proyecto."""
    logger.info(message, *args)
    TIMING_LOG.parent.mkdir(parents=True, exist_ok=True)
    formatted = message % args if args else message
    with TIMING_LOG.open("a", encoding="utf-8") as file:
        file.write(f"{formatted}\n")


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

    def sync_category(self, category_url: str, category: str = ""):
        started = time.perf_counter()
        products = self.scraper_service.scrape_category(
            category_url,
            category,
        )
        elapsed = time.perf_counter() - started
        _log_timing(
            "SCRAPING TIMING | category=%s | products=%d | seconds=%.3f",
            category,
            len(products),
            elapsed,
        )
        return self.sync_products(products)

    def sync_categories(self, categories, progress_callback=None):
        """
        Scrapea todas las categorías y sincroniza el conjunto completo.

        La sincronización conjunta es importante porque un mismo código
        puede aparecer en más de una categoría. La consolidación se hace
        antes de descargar imágenes, mapear y comparar contra el catálogo.
        """
        started = time.perf_counter()
        products = []
        total = len(categories)

        for index, category in enumerate(categories, start=1):
            category_started = time.perf_counter()
            category_products = self.scraper_service.scrape_category(
                category.url,
                category.name,
            )
            category_elapsed = time.perf_counter() - category_started
            products.extend(category_products)

            _log_timing(
                "SCRAPING TIMING | category=%s | products=%d | seconds=%.3f",
                category.name,
                len(category_products),
                category_elapsed,
            )

            if progress_callback:
                progress_callback(index, total)

        scraping_elapsed = time.perf_counter() - started
        _log_timing(
            "SCRAPING TIMING | stage=category_extraction | categories=%d "
            "| products=%d | seconds=%.3f",
            total,
            len(products),
            scraping_elapsed,
        )

        return self.sync_products(products)

    def sync_products(self, products):
        """Procesa y sincroniza un conjunto consolidado de productos scrapeados."""
        total_started = time.perf_counter()

        if self.mapper and self.catalog_sync_service:
            consolidate_started = time.perf_counter()
            consolidate = getattr(
                self.catalog_sync_service,
                "consolidate_products",
                None,
            )
            if callable(consolidate):
                products = consolidate(products)
            consolidate_elapsed = time.perf_counter() - consolidate_started
            _log_timing(
                "SCRAPING TIMING | stage=consolidation | products=%d "
                "| seconds=%.3f",
                len(products),
                consolidate_elapsed,
            )

            if self.image_sync_adapter:
                image_started = time.perf_counter()
                products = self.image_sync_adapter.sync_products(products)
                image_elapsed = time.perf_counter() - image_started
                _log_timing(
                    "SCRAPING TIMING | stage=images | products=%d "
                    "| seconds=%.3f",
                    len(products),
                    image_elapsed,
                )

            mapping_started = time.perf_counter()
            mapped_products = [self.mapper.map(product) for product in products]
            mapping_elapsed = time.perf_counter() - mapping_started
            _log_timing(
                "SCRAPING TIMING | stage=mapping | products=%d "
                "| seconds=%.3f",
                len(mapped_products),
                mapping_elapsed,
            )

            catalog_started = time.perf_counter()
            result = self.catalog_sync_service.sync(mapped_products)
            catalog_elapsed = time.perf_counter() - catalog_started
            _log_timing(
                "SCRAPING TIMING | stage=catalog_sync | products=%d "
                "| seconds=%.3f",
                len(mapped_products),
                catalog_elapsed,
            )

            total_elapsed = time.perf_counter() - total_started
            _log_timing(
                "SCRAPING TIMING | stage=sync_total | products=%d "
                "| seconds=%.3f",
                len(mapped_products),
                total_elapsed,
            )

            self._accumulate_sync_result(result)
            return mapped_products

        persistence_started = time.perf_counter()
        result = self.persistence_service.save_products(products)
        persistence_elapsed = time.perf_counter() - persistence_started
        total_elapsed = time.perf_counter() - total_started
        _log_timing(
            "SCRAPING TIMING | stage=persistence | products=%d "
            "| seconds=%.3f",
            len(products),
            persistence_elapsed,
        )
        _log_timing(
            "SCRAPING TIMING | stage=sync_total | products=%d "
            "| seconds=%.3f",
            len(products),
            total_elapsed,
        )
        return result

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
