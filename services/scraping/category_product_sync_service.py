import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, cast

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
    logger.info(message, *args)
    TIMING_LOG.parent.mkdir(parents=True, exist_ok=True)
    formatted = message % args if args else message
    with TIMING_LOG.open("a", encoding="utf-8") as file:
        file.write(f"{formatted}\n")


class CategoryProductSyncService:
    """Orquesta extracción, consolidación y sincronización del catálogo."""

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
        products = self.scraper_service.scrape_category(category_url, category)
        elapsed = time.perf_counter() - started
        _log_timing(
            "SCRAPING TIMING | category=%s | products=%d | seconds=%.3f",
            category,
            len(products),
            elapsed,
        )
        return self.sync_products(products)

    def sync_categories(self, categories, progress_callback=None):
        """Scrapea todas las categorías y sincroniza el conjunto completo."""
        started = time.perf_counter()
        categories = list(categories)
        total = len(categories)
        expected_products = sum(
            max(int(getattr(category, "expected_count", 0) or 0), 0)
            for category in categories
        )

        self._reset_scraping_metrics()
        if progress_callback:
            progress_callback(0, 100)

        if not categories:
            _log_timing(
                "SCRAPING TIMING | stage=category_listing | categories=0 "
                "| products=0 | seconds=0.000",
            )
            _log_timing(
                "SCRAPING TIMING | stage=category_extraction | categories=0 "
                "| products=0 | seconds=0.000",
            )
            if progress_callback:
                progress_callback(100, 100)
            return self.sync_products([], full_sync=False, expected_products=0)

        worker_count = min(self.category_workers, total)
        collected: list[list[Any]] = [[] for _ in categories]
        results: list[list[Any]] = [[] for _ in categories]
        listing_started = time.perf_counter()
        enrichment_started: float | None = None
        listing_completed = 0
        enrichment_completed = 0

        with (
            ThreadPoolExecutor(max_workers=worker_count) as listing_executor,
            ThreadPoolExecutor(max_workers=worker_count) as enrichment_executor,
        ):
            listing_future_to_index = {
                listing_executor.submit(
                    self._collect_category,
                    index,
                    category,
                ): index
                for index, category in enumerate(categories)
            }
            enrichment_futures: dict[Any, int] = {}

            for future in as_completed(listing_future_to_index):
                index = listing_future_to_index[future]
                collected[index] = cast(list[Any], future.result())
                listing_completed += 1
                if enrichment_started is None:
                    enrichment_started = time.perf_counter()

                enrichment_future = enrichment_executor.submit(
                    self._enrich_category,
                    index,
                    categories[index],
                    collected[index],
                )
                enrichment_futures[enrichment_future] = index

                if progress_callback:
                    progress = 5 + int(listing_completed * 35 / total) + int(
                        enrichment_completed * 50 / total
                    )
                    progress_callback(min(90, progress), 100)

            listing_elapsed = time.perf_counter() - listing_started

            for future in as_completed(enrichment_futures):
                index = enrichment_futures[future]
                results[index] = cast(list[Any], future.result())
                enrichment_completed += 1
                if progress_callback:
                    progress = 5 + int(listing_completed * 35 / total) + int(
                        enrichment_completed * 50 / total
                    )
                    progress_callback(min(90, progress), 100)

        collected_count = sum(len(items) for items in collected)
        _log_timing(
            "SCRAPING TIMING | stage=category_listing | categories=%d "
            "| products=%d | expected=%d | gap=%d | seconds=%.3f",
            total,
            collected_count,
            expected_products,
            max(expected_products - collected_count, 0),
            listing_elapsed,
        )

        enrichment_elapsed = (
            time.perf_counter() - enrichment_started
            if enrichment_started is not None
            else 0.0
        )
        products = [
            product
            for category_products in results
            for product in category_products
        ]
        _log_timing(
            "SCRAPING TIMING | stage=detail_enrichment | categories=%d "
            "| products=%d | seconds=%.3f",
            total,
            len(products),
            enrichment_elapsed,
        )

        scraping_elapsed = time.perf_counter() - started
        _log_timing(
            "SCRAPING TIMING | stage=category_extraction | categories=%d "
            "| products=%d | expected=%d | gap=%d | seconds=%.3f",
            total,
            len(products),
            expected_products,
            max(expected_products - len(products), 0),
            scraping_elapsed,
        )
        self._log_detail_metrics()
        self._log_http_metrics()

        allow_prune, guard_reason = self._full_sync_prune_guard(products, total)
        _log_timing(
            "SCRAPING TIMING | stage=prune_guard | enabled=%s | reason=%s "
            "| products=%d | categories=%d",
            str(allow_prune).lower(),
            guard_reason,
            len(products),
            total,
        )

        if progress_callback:
            progress_callback(95, 100)

        result = self.sync_products(
            products,
            full_sync=True,
            allow_prune=allow_prune,
            expected_products=expected_products,
        )

        if progress_callback:
            progress_callback(100, 100)
        return result

    def _collect_category(self, index, category):
        del index
        scraper = getattr(self.scraper_service, "scraper", None)
        collect_category = getattr(scraper, "collect_category", None)
        if callable(collect_category):
            return collect_category(category)
        return self.scraper_service.scrape_category(category.url, category.name)

    def _enrich_category(self, index, category, collected):
        del index
        scraper = getattr(self.scraper_service, "scraper", None)
        enrich_category_products = getattr(
            scraper,
            "enrich_category_products",
            None,
        )
        if callable(enrich_category_products):
            return enrich_category_products(collected, category.name)
        return self.scraper_service.scrape_category(category.url, category.name)

    def _reset_scraping_metrics(self):
        scraper = getattr(self.scraper_service, "scraper", None)
        reset_detail = getattr(scraper, "reset_detail_metrics", None)
        if callable(reset_detail):
            reset_detail()

        browser = getattr(self.scraper_service, "browser", None)
        if browser is None:
            category_scraper = getattr(scraper, "category_scraper", None)
            browser = getattr(category_scraper, "browser", None)
        reset_http = getattr(browser, "reset_http_metrics", None)
        if callable(reset_http):
            reset_http()

    def _log_detail_metrics(self):
        scraper = getattr(self.scraper_service, "scraper", None)
        get_metrics = getattr(scraper, "get_detail_metrics", None)
        if not callable(get_metrics):
            return
        metrics = cast(dict[str, Any], get_metrics())
        reason_counts = metrics.get("detail_reason_counts", {})
        reason_text = ",".join(
            f"{key}:{value}" for key, value in sorted(reason_counts.items())
        ) or "none"
        _log_timing(
            "SCRAPING TIMING | stage=detail_cache | requests=%d "
            "| cache_hits=%d | skipped=%d | cache_size=%d | reasons=%s",
            metrics.get("detail_requests", 0),
            metrics.get("detail_cache_hits", 0),
            metrics.get("detail_skipped", 0),
            metrics.get("detail_cache_size", 0),
            reason_text,
        )

    def _log_http_metrics(self):
        browser = self._get_browser()
        get_metrics = getattr(browser, "get_http_metrics", None)
        if not callable(get_metrics):
            return
        metrics = cast(dict[str, Any], get_metrics())
        _log_timing(
            "SCRAPING TIMING | stage=http | requests=%d | successes=%d "
            "| errors=%d | terminal_errors=%d | retries=%d "
            "| detail_requests=%d | category_requests=%d "
            "| other_requests=%d | max_concurrency=%d "
            "| http_seconds=%.3f | slowest_request=%.3f",
            metrics.get("http_requests", 0),
            metrics.get("http_successes", 0),
            metrics.get("http_errors", 0),
            metrics.get("http_terminal_errors", 0),
            metrics.get("http_retries", 0),
            metrics.get("detail_http_requests", 0),
            metrics.get("category_http_requests", 0),
            metrics.get("other_http_requests", 0),
            metrics.get("http_max_in_flight", 0),
            metrics.get("http_total_seconds", 0.0),
            metrics.get("http_max_seconds", 0.0),
        )

        buckets = metrics.get("latency_buckets", {})
        _log_timing(
            "SCRAPING TIMING | stage=http_latency | lt_0_5=%d "
            "| 0_5_1=%d | 1_2=%d | 2_5=%d | 5_10=%d | gte_10=%d",
            buckets.get("lt_0_5", 0),
            buckets.get("0_5_1", 0),
            buckets.get("1_2", 0),
            buckets.get("2_5", 0),
            buckets.get("5_10", 0),
            buckets.get("gte_10", 0),
        )

        for index, (elapsed, url) in enumerate(
            metrics.get("slowest_requests", []),
            start=1,
        ):
            _log_timing(
                "SCRAPING TIMING | stage=http_slowest | rank=%d "
                "| seconds=%.3f | url=%s",
                index,
                elapsed,
                url,
            )

    def _get_browser(self):
        scraper = getattr(self.scraper_service, "scraper", None)
        category_scraper = getattr(scraper, "category_scraper", None)
        browser = getattr(category_scraper, "browser", None)
        if browser is None:
            browser = getattr(self.scraper_service, "browser", None)
        return browser

    def _log_missing_code_diagnostics(self, products: list[Any]) -> None:
        for product in products:
            if str(getattr(product, "code", "")).strip():
                continue
            _log_timing(
                "SCRAPING TIMING | stage=missing_code | name=%s | url=%s",
                str(getattr(product, "name", "")).strip() or "(sin nombre)",
                str(getattr(product, "url", "")).strip() or "(sin url)",
            )

    def _full_sync_prune_guard(self, products: list[Any], category_count: int):
        """Permite pruning de códigos reales solo con extracción completa."""
        if category_count <= 0:
            return False, "no_categories"
        missing_codes = sum(
            1
            for product in products
            if not str(getattr(product, "code", "")).strip()
        )
        if missing_codes:
            self._log_missing_code_diagnostics(products)
            return False, f"missing_codes:{missing_codes}"

        browser = self._get_browser()
        get_metrics = getattr(browser, "get_http_metrics", None)
        if callable(get_metrics):
            metrics = cast(dict[str, Any], get_metrics())
            terminal_errors = int(metrics.get("http_terminal_errors", 0))
            if terminal_errors:
                return False, f"terminal_http_errors:{terminal_errors}"
        return True, "complete"

    def sync_products(
        self,
        products: list[Any],
        full_sync: bool = False,
        allow_prune: bool = False,
        expected_products: int = 0,
    ):
        total_started = time.perf_counter()
        if self.mapper and self.catalog_sync_service:
            consolidate_started = time.perf_counter()
            consolidate = getattr(
                self.catalog_sync_service,
                "consolidate_products",
                None,
            )
            if callable(consolidate):
                products = cast(list[Any], consolidate(products))
            _log_timing(
                "SCRAPING TIMING | stage=consolidation | products=%d | seconds=%.3f",
                len(products),
                time.perf_counter() - consolidate_started,
            )

            if self.image_sync_adapter:
                image_started = time.perf_counter()
                products = cast(
                    list[Any],
                    self.image_sync_adapter.sync_products(products),
                )
                _log_timing(
                    "SCRAPING TIMING | stage=images | products=%d | seconds=%.3f",
                    len(products),
                    time.perf_counter() - image_started,
                )

            mapping_started = time.perf_counter()
            mapped_products = [self.mapper.map(product) for product in products]
            _log_timing(
                "SCRAPING TIMING | stage=mapping | products=%d | seconds=%.3f",
                len(mapped_products),
                time.perf_counter() - mapping_started,
            )

            catalog_started = time.perf_counter()
            use_prune = bool(full_sync and allow_prune)
            sync_full_catalog = getattr(
                self.catalog_sync_service,
                "sync_full_catalog",
                None,
            )
            if use_prune and callable(sync_full_catalog):
                result = cast(
                    SyncResult,
                    sync_full_catalog(
                        mapped_products,
                        expected_products=expected_products,
                    ),
                )
            else:
                result = cast(
                    SyncResult,
                    self.catalog_sync_service.sync(
                        mapped_products,
                        expected_products=expected_products,
                    ),
                )
            _log_timing(
                "SCRAPING TIMING | stage=catalog_sync | products=%d "
                "| seconds=%.3f | prune=%s | expected=%d | gap=%d",
                len(mapped_products),
                time.perf_counter() - catalog_started,
                str(use_prune).lower(),
                result.products_expected,
                result.coverage_gap,
            )
            _log_timing(
                "SCRAPING TIMING | stage=sync_total | products=%d | seconds=%.3f",
                len(mapped_products),
                time.perf_counter() - total_started,
            )
            self._accumulate_sync_result(result)
            return mapped_products

        persistence_started = time.perf_counter()
        result = self.persistence_service.save_products(products)
        _log_timing(
            "SCRAPING TIMING | stage=persistence | products=%d | seconds=%.3f",
            len(products),
            time.perf_counter() - persistence_started,
        )
        _log_timing(
            "SCRAPING TIMING | stage=sync_total | products=%d | seconds=%.3f",
            len(products),
            time.perf_counter() - total_started,
        )
        return result

    def reset_sync_result(self):
        self.last_sync_result = SyncResult()

    def _accumulate_sync_result(self, result: SyncResult):
        self.last_sync_result.processed += result.processed
        self.last_sync_result.created += result.created
        self.last_sync_result.updated += result.updated
        self.last_sync_result.unchanged += result.unchanged
        self.last_sync_result.deleted += result.deleted
        self.last_sync_result.generated += result.generated
        self.last_sync_result.products_expected += result.products_expected
        self.last_sync_result.products_found += result.products_found
        self.last_sync_result.products_unique += result.products_unique
        self.last_sync_result.products_multiple_categories += (
            result.products_multiple_categories
        )
        self.last_sync_result.duplicate_occurrences += result.duplicate_occurrences
        self.last_sync_result.errors.extend(result.errors)
        self.last_sync_result.failures.extend(result.failures)
        self.last_sync_result.changes.extend(result.changes)
