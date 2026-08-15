import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from config.scraping_config import SCRAPING_CATEGORY_WORKERS
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
        category_workers: int = SCRAPING_CATEGORY_WORKERS,
    ):
        self.scraper_service = scraper_service
        self.persistence_service = persistence_service
        self.mapper = mapper
        self.catalog_sync_service = catalog_sync_service
        self.image_sync_adapter = image_sync_adapter
        self.category_workers = max(1, category_workers)
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

        Las categorías se extraen en paralelo con un límite conservador.
        La consolidación sigue ocurriendo después de completar todas las
        categorías para preservar correctamente las categorías múltiples.
        """
        started = time.perf_counter()
        categories = list(categories)
        total = len(categories)

        self._reset_detail_metrics()

        if not categories:
            _log_timing(
                "SCRAPING TIMING | stage=category_extraction | categories=0 "
                "| products=0 | seconds=0.000",
            )
            return self.sync_products([])

        worker_count = min(self.category_workers, total)
        results: list[list] = [[] for _ in categories]
        completed = 0

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_to_index = {
                executor.submit(
                    self._scrape_category,
                    index,
                    category,
                ): index
                for index, category in enumerate(categories)
            }

            for future in as_completed(future_to_index):
                index = future_to_index[future]
                results[index] = future.result()
                completed += 1

                if progress_callback:
                    progress_callback(completed, total)

        products = [
            product
            for category_products in results
            for product in category_products
        ]

        scraping_elapsed = time.perf_counter() - started
        _log_timing(
            "SCRAPING TIMING | stage=category_extraction | categories=%d "
            "| products=%d | seconds=%.3f",
            total,
            len(products),
            scraping_elapsed,
        )
        self._log_detail_metrics()

        return self.sync_products(products)

    def _scrape_category(self, index, category):
        """Extrae una categoría en un worker independiente."""
        category_started = time.perf_counter()
        products = self.scraper_service.scrape_category(
            category.url,
            category.name,
        )
        category_elapsed = time.perf_counter() - category_started
        _log_timing(
            "SCRAPING TIMING | category=%s | products=%d | seconds=%.3f",
            category.name,
            len(products),
            category_elapsed,
        )
        return products

    def _reset_detail_metrics(self):
        """Reinicia métricas del scraper antes de una ejecución completa."""
        scraper = getattr(self.scraper_service, "scraper", None)
        reset = getattr(scraper, "reset_detail_metrics", None)
        if callable(reset):
            reset()

    def _log_detail_metrics(self):
        """Registra métricas de peticiones y reutilización de páginas de detalle."""
        scraper = getattr(self.scraper_service, "scraper", None)
        get_metrics = getattr(scraper, "get_detail_metrics", None)
        if not callable(get_metrics):
            return

        metrics = get_metrics()
        _log_timing(
            "SCRAPING TIMING | stage=detail_cache | requests=%d "
            "| cache_hits=%d | cache_size=%d",
            metrics.get("detail_requests", 0),
            metrics.get("detail_cache_hits", 0),
            metrics.get("detail_cache_size", 0),
        )

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
