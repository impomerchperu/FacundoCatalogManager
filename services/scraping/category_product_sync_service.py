import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, cast

from config.scraping_config import EXPECTED_CATALOG_PRODUCTS, SCRAPING_CATEGORY_WORKERS
from models.scraping.sync_result import SyncResult
from services.scraping.category_name_normalizer import normalize_category_name

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
        scraper_service,
        persistence_service,
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
        _log_timing(
            "SCRAPING TIMING | category=%s | products=%d | seconds=%.3f",
            category,
            len(products),
            time.perf_counter() - started,
        )
        return self.sync_products(products)

    def sync_categories(
        self, categories, progress_callback=None, expected_products=None
    ):
        """Scrapea todas las categorías y sincroniza el conjunto completo."""
        started = time.perf_counter()
        categories = list(categories)
        total = len(categories)
        expected_category_occurrences = sum(
            max(int(getattr(category, "expected_count", 0) or 0), 0)
            for category in categories
        )
        trusted_expected_products = (
            EXPECTED_CATALOG_PRODUCTS
            if expected_products is None
            else max(int(expected_products or 0), 0)
        )
        self._reset_scraping_metrics()
        self.reset_sync_result()
        if progress_callback:
            progress_callback(0, 100)
        if not categories:
            return self.sync_products([], full_sync=False, expected_products=0)

        worker_count = min(self.category_workers, total)
        collected = [[] for _ in categories]
        results = [[] for _ in categories]
        listing_started = time.perf_counter()
        enrichment_started = None
        listing_completed = 0
        enrichment_completed = 0
        with (
            ThreadPoolExecutor(max_workers=worker_count) as listing_executor,
            ThreadPoolExecutor(max_workers=worker_count) as enrichment_executor,
        ):
            listing_futures = {
                listing_executor.submit(self._collect_category, index, category): index
                for index, category in enumerate(categories)
            }
            enrichment_futures = {}
            for future in as_completed(listing_futures):
                index = listing_futures[future]
                collected[index] = cast(list[Any], future.result())
                listing_completed += 1
                if enrichment_started is None:
                    enrichment_started = time.perf_counter()
                enrichment_futures[
                    enrichment_executor.submit(
                        self._enrich_category,
                        index,
                        categories[index],
                        collected[index],
                    )
                ] = index
                if progress_callback:
                    progress_callback(
                        min(40, 5 + int(listing_completed * 35 / total)), 100
                    )
            listing_elapsed = time.perf_counter() - listing_started
            for future in as_completed(enrichment_futures):
                index = enrichment_futures[future]
                results[index] = cast(list[Any], future.result())
                enrichment_completed += 1
                if progress_callback:
                    progress_callback(
                        min(90, 40 + int(enrichment_completed * 50 / total)), 100
                    )

        products = [product for items in results for product in items]
        occurrence_gap = max(expected_category_occurrences - len(products), 0)
        _log_timing(
            "SCRAPING TIMING | stage=category_listing | categories=%d | products=%d "
            "| expected_category_occurrences=%d | occurrence_gap=%d | seconds=%.3f",
            total,
            sum(map(len, collected)),
            expected_category_occurrences,
            max(expected_category_occurrences - sum(map(len, collected)), 0),
            listing_elapsed,
        )
        _log_timing(
            "SCRAPING TIMING | stage=category_extraction | categories=%d | products=%d "
            "| expected_category_occurrences=%d | occurrence_gap=%d "
            "| expected_unique_products=%d | seconds=%.3f",
            total,
            len(products),
            expected_category_occurrences,
            occurrence_gap,
            trusted_expected_products,
            time.perf_counter() - started,
        )
        self._log_detail_metrics()
        self._log_http_metrics()

        allow_prune, reason = self._full_sync_prune_guard(
            products,
            total,
            expected_category_occurrences,
            trusted_expected_products,
        )
        _log_timing(
            "SCRAPING TIMING | stage=coverage_incomplete | "
            "reason=%s | products=%d | categories=%d | "
            "expected_unique_products=%d | expected_category_occurrences=%d",
            reason,
            len(products),
            total,
            trusted_expected_products,
            expected_category_occurrences,
        )
        if progress_callback:
            progress_callback(95, 100)

        synced_products = self.sync_products(
            products,
            full_sync=True,
            allow_prune=allow_prune,
            expected_products=trusted_expected_products if allow_prune else 0,
            expected_category_occurrences=expected_category_occurrences,
        )
        self.last_sync_result.expected_category_occurrences = (
            expected_category_occurrences
        )
        self.last_sync_result.products_expected = trusted_expected_products
        self.last_sync_result.categories_processed = total
        self._attach_category_coverage(synced_products, categories)
        if progress_callback:
            progress_callback(100, 100)
        return synced_products

    @staticmethod
    def _split_categories(value: Any) -> list[str]:
        if not isinstance(value, str):
            return []
        return sorted(
            {part.strip() for part in value.split(",") if part.strip()},
            key=str.casefold,
        )

    def _attach_category_coverage(self, products, categories):
        """Construye métricas auditables por categoría y por código."""
        category_counts: dict[str, int] = {}
        category_products: dict[str, set[str]] = {}
        product_categories: dict[str, set[str]] = {}
        product_names: dict[str, str] = {}
        for product in products:
            code = str(getattr(product, "code", "")).strip()
            if not code:
                continue
            name = str(getattr(product, "name", "")).strip()
            product_names[code] = name
            values = self._split_categories(getattr(product, "category", ""))
            for category in values:
                key = normalize_category_name(category)
                if not key:
                    continue
                category_counts.setdefault(key, 0)
                category_products.setdefault(key, set())
                category_counts[key] += 1
                category_products[key].add(code)
                product_categories.setdefault(code, set()).add(category)

        expected_names = {
            normalize_category_name(getattr(category, "name", ""))
            for category in categories
            if normalize_category_name(getattr(category, "name", ""))
        }
        all_keys = expected_names | set(category_counts)
        display_names = {
            normalize_category_name(getattr(category, "name", "")): str(
                getattr(category, "name", "")
            ).strip()
            for category in categories
            if normalize_category_name(getattr(category, "name", ""))
        }
        display_names.update(
            {
                key: key
                for key in category_counts
                if key not in display_names
            }
        )
        self.last_sync_result.category_summary = [
            {
                "category": display_names[name],
                "comparison_key": name,
                "products": category_counts.get(name, 0),
                "unique_products": len(category_products.get(name, set())),
            }
            for name in sorted(all_keys)
        ]
        multiple = []
        for code, names in sorted(
            product_categories.items(), key=lambda item: item[0].casefold()
        ):
            if len(names) < 2:
                continue
            multiple.append(
                {
                    "code": code,
                    "name": product_names.get(code, ""),
                    "categories": sorted(names, key=str.casefold),
                }
            )
        self.last_sync_result.multiple_category_products = multiple
        self.last_sync_result.products_multiple_categories = len(multiple)
        self.last_sync_result.products_found = len(products)
        self.last_sync_result.products_unique = len(
            {
                str(getattr(product, "code", "")).strip()
                for product in products
                if str(getattr(product, "code", "")).strip()
            }
        )
        self.last_sync_result.duplicate_occurrences = max(
            self.last_sync_result.products_found
            - self.last_sync_result.products_unique,
            0,
        )
        for row in self.last_sync_result.category_summary:
            _log_timing(
                "SCRAPING TIMING | stage=category_coverage | "
                "category=%s | products=%d | unique=%d",
                row["category"],
                row["products"],
                row["unique_products"],
            )
        _log_timing(
            "SCRAPING TIMING | stage=multi_category_coverage | "
            "products=%d | categories=%d",
            len(multiple),
            len(self.last_sync_result.category_summary),
        )

    def _consolidate_for_coverage(self, products) -> list[Any]:
        if self.catalog_sync_service:
            consolidate = getattr(
                self.catalog_sync_service, "consolidate_products", None
            )
            if callable(consolidate):
                return cast(list[Any], consolidate(products))
        return list(products)

    def _collect_category(self, index, category):
        del index
        scraper = getattr(self.scraper_service, "scraper", None)
        collect = getattr(scraper, "collect_category", None)
        if callable(collect):
            return collect(category)
        return self.scraper_service.scrape_category(
            category.url,
            category.name,
            expected_count=max(int(getattr(category, "expected_count", 0) or 0), 0),
        )

    def _enrich_category(self, index, category, collected):
        del index
        scraper = getattr(self.scraper_service, "scraper", None)
        enrich = getattr(scraper, "enrich_category_products", None)
        if callable(enrich):
            return enrich(collected, category.name)
        return self.scraper_service.scrape_category(
            category.url,
            category.name,
            expected_count=max(int(getattr(category, "expected_count", 0) or 0), 0),
        )

    def _get_browser(self):
        scraper = getattr(self.scraper_service, "scraper", None)
        if scraper is None:
            return None
        category_scraper = getattr(scraper, "category_scraper", None)
        browser = getattr(category_scraper, "browser", None)
        if browser is not None:
            return browser
        return getattr(scraper, "browser", None)

    def _reset_scraping_metrics(self):
        scraper = getattr(self.scraper_service, "scraper", None)
        reset = getattr(scraper, "reset_detail_metrics", None)
        if callable(reset):
            reset()
        browser = self._get_browser()
        reset_http = getattr(browser, "reset_http_metrics", None)
        if callable(reset_http):
            reset_http()

    def _log_detail_metrics(self):
        scraper = getattr(self.scraper_service, "scraper", None)
        getter = getattr(scraper, "get_detail_metrics", None)
        if not callable(getter):
            return
        metrics = cast(dict[str, Any], getter())
        reasons = metrics.get("detail_reason_counts", {})
        _log_timing(
            "SCRAPING TIMING | stage=detail_cache | "
            "requests=%d | cache_hits=%d | skipped=%d | "
            "cache_size=%d | reasons=%s",
            metrics.get("detail_requests", 0),
            metrics.get("detail_cache_hits", 0),
            metrics.get("detail_skipped", 0),
            metrics.get("detail_cache_size", 0),
            ",".join(f"{k}:{v}" for k, v in sorted(reasons.items())) or "none",
        )

    def _log_http_metrics(self):
        browser = self._get_browser()
        getter = getattr(browser, "get_http_metrics", None)
        if not callable(getter):
            return
        metrics = cast(dict[str, Any], getter())
        _log_timing(
            "SCRAPING TIMING | stage=http | requests=%d | successes=%d | "
            "errors=%d | terminal_errors=%d | retries=%d | "
            "detail_requests=%d | category_requests=%d | other_requests=%d | "
            "max_concurrency=%d | http_seconds=%.3f | slowest_request=%.3f",
            metrics.get("http_requests", 0),
            metrics.get("http_successes", 0),
            metrics.get("http_errors", 0),
            metrics.get("http_terminal_errors", 0),
            metrics.get("http_retries", 0),
            metrics.get("detail_http_requests", 0),
            metrics.get("category_http_requests", 0),
            metrics.get("other_requests", 0),
            metrics.get("max_concurrency", 0),
            metrics.get("http_total_seconds", 0.0),
            metrics.get("http_max_seconds", 0.0),
        )

    def _log_missing_code_diagnostics(self, products):
        for product in products:
            if str(getattr(product, "code", "")).strip():
                continue
            _log_timing(
                "SCRAPING TIMING | stage=missing_code | name=%s | url=%s",
                str(getattr(product, "name", "")).strip() or "(sin nombre)",
                str(getattr(product, "url", "")).strip() or "(sin url)",
            )

    def _full_sync_prune_guard(
        self,
        products,
        category_count,
        expected_category_occurrences=0,
        expected_products=None,
    ):
        if category_count <= 0:
            return False, "no_categories"
        missing = sum(
            1 for product in products if not str(getattr(product, "code", "")).strip()
        )
        if missing:
            self._log_missing_code_diagnostics(products)
            return False, f"missing_codes:{missing}"
        browser = self._get_browser()
        getter = getattr(browser, "get_http_metrics", None)
        if callable(getter):
            metrics = cast(dict[str, Any], getter())
            errors = int(metrics.get("http_terminal_errors", 0))
            if errors:
                return False, f"terminal_http_errors:{errors}"
        if (
            expected_category_occurrences > 0
            and len(products) < expected_category_occurrences
        ):
            return False, (
                f"category_coverage_gap:{expected_category_occurrences - len(products)}"
            )
        if expected_products is not None and expected_products > 0:
            unique_products = self._consolidate_for_coverage(products)
            unique_count = len(unique_products)
            if unique_count < expected_products:
                return False, f"unique_coverage_gap:{expected_products - unique_count}"
        return True, "complete"

    def sync_products(
        self,
        products,
        full_sync=False,
        allow_prune=False,
        expected_products=0,
        expected_category_occurrences=0,
    ):
        total_started = time.perf_counter()
        if self.mapper and self.catalog_sync_service:
            started = time.perf_counter()
            consolidate = getattr(
                self.catalog_sync_service, "consolidate_products", None
            )
            if callable(consolidate):
                products = cast(list[Any], consolidate(products))
            _log_timing(
                "SCRAPING TIMING | stage=consolidation | products=%d | seconds=%.3f",
                len(products),
                time.perf_counter() - started,
            )
            if self.image_sync_adapter:
                started = time.perf_counter()
                products = cast(
                    list[Any], self.image_sync_adapter.sync_products(products)
                )
                _log_timing(
                    "SCRAPING TIMING | stage=images | products=%d | seconds=%.3f",
                    len(products),
                    time.perf_counter() - started,
                )
            started = time.perf_counter()
            mapped_products = [self.mapper.map(product) for product in products]
            _log_timing(
                "SCRAPING TIMING | stage=mapping | products=%d | seconds=%.3f",
                len(mapped_products),
                time.perf_counter() - started,
            )
            started = time.perf_counter()
            use_prune = bool(full_sync and allow_prune and expected_products)
            sync_full = getattr(self.catalog_sync_service, "sync_full_catalog", None)
            if use_prune and callable(sync_full):
                result = cast(
                    SyncResult,
                    sync_full(
                        mapped_products,
                        expected_products=expected_products,
                        expected_category_occurrences=expected_category_occurrences,
                    ),
                )
            else:
                result = cast(
                    SyncResult,
                    self.catalog_sync_service.sync(
                        mapped_products,
                        expected_products=expected_products,
                        expected_category_occurrences=expected_category_occurrences,
                    ),
                )
            _log_timing(
                "SCRAPING TIMING | stage=catalog_sync | products=%d | seconds=%.3f | "
                "prune=%s | expected_unique=%s | expected_category_occurrences=%s | "
                "unique=%d | gap=%d",
                len(mapped_products),
                time.perf_counter() - started,
                str(use_prune).lower(),
                expected_products if expected_products else "unknown",
                expected_category_occurrences
                if expected_category_occurrences
                else "unknown",
                result.products_unique,
                result.coverage_gap,
            )
            _log_timing(
                "SCRAPING TIMING | stage=sync_total | products=%d | seconds=%.3f",
                len(mapped_products),
                time.perf_counter() - total_started,
            )
            self._accumulate_sync_result(result)
            return mapped_products

        started = time.perf_counter()
        result = self.persistence_service.save_products(products)
        _log_timing(
            "SCRAPING TIMING | stage=persistence | products=%d | seconds=%.3f",
            len(products),
            time.perf_counter() - started,
        )
        _log_timing(
            "SCRAPING TIMING | stage=sync_total | products=%d | seconds=%.3f",
            len(products),
            time.perf_counter() - total_started,
        )
        return result

    def _accumulate_sync_result(self, result):
        for field in (
            "processed",
            "created",
            "updated",
            "unchanged",
            "deleted",
            "generated",
            "products_expected",
            "expected_category_occurrences",
            "products_found",
            "products_unique",
            "products_multiple_categories",
            "duplicate_occurrences",
        ):
            setattr(
                self.last_sync_result,
                field,
                getattr(self.last_sync_result, field, 0)
                + getattr(result, field, 0),
            )
        self.last_sync_result.errors.extend(result.errors)
        self.last_sync_result.failures.extend(result.failures)
        self.last_sync_result.changes.extend(result.changes)

    def reset_sync_result(self):
        self.last_sync_result = SyncResult()
