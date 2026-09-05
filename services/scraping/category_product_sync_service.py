from __future__ import annotations

import time
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

from models.scraping.sync_result import SyncResult

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TIMING_LOG = PROJECT_ROOT / "data" / "scraping_timing.log"


def _log_timing(message, *args):
    TIMING_LOG.parent.mkdir(parents=True, exist_ok=True)
    formatted = message % args if args else message
    with TIMING_LOG.open("a", encoding="utf-8") as file:
        file.write(f"{formatted}\n")


class CategoryProductSyncService:
    """Coordina extracción, enriquecimiento y sincronización de productos."""

    def __init__(
        self,
        scraper_service,
        persistence_service,
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

    def reset_sync_result(self):
        self.last_sync_result = SyncResult()

    def sync_category(self, category_url, category=""):
        started = time.perf_counter()
        result = self.scraper_service.scrape_category(category_url, category)
        _log_timing(
            "SCRAPING TIMING | stage=category_sync | category=%s | products=%d | seconds=%.3f",
            category,
            len(result),
            time.perf_counter() - started,
        )
        self.sync_products(result, full_sync=False, allow_prune=False)
        return result

    def sync_categories(self, categories, progress_callback=None):
        self._reset_scraping_metrics()
        total_started = time.perf_counter()
        categories = list(categories or [])
        expected_category_occurrences = sum(
            max(int(getattr(category, "expected_count", 0) or 0), 0)
            for category in categories
        )
        self.last_sync_result = SyncResult()
        self.last_sync_result.products_expected = 0
        self.last_sync_result.expected_category_occurrences = (
            expected_category_occurrences
        )

        collected_by_index = [None] * len(categories)
        started = time.perf_counter()
        for index, category in enumerate(categories):
            collected_by_index[index] = self._collect_category(index, category)
            if progress_callback:
                progress_callback(index + 1, len(categories))
        _log_timing(
            "SCRAPING TIMING | stage=category_listing | categories=%d | products=%d | "
            "expected_category_occurrences=%d | seconds=%.3f",
            len(categories),
            sum(len(items or []) for items in collected_by_index),
            expected_category_occurrences,
            time.perf_counter() - started,
        )

        started = time.perf_counter()
        products = []
        for index, category in enumerate(categories):
            collected = collected_by_index[index] or []
            products.extend(self._enrich_category(index, category, collected))
        _log_timing(
            "SCRAPING TIMING | stage=category_extraction | categories=%d | products=%d | "
            "expected_category_occurrences=%d | seconds=%.3f",
            len(categories),
            len(products),
            expected_category_occurrences,
            time.perf_counter() - started,
        )
        self._log_detail_metrics()
        self._log_http_metrics()

        raw_products = list(products)
        coverage_products = self._consolidate_for_coverage(raw_products)
        self._attach_category_coverage(raw_products, coverage_products, categories)

        complete, reason = self._full_sync_prune_guard(
            raw_products,
            len(categories),
            expected_category_occurrences=expected_category_occurrences,
            expected_products=0,
        )
        _log_timing(
            "SCRAPING TIMING | stage=coverage_incomplete | reason=%s | products=%d | "
            "categories=%d | expected_category_occurrences=%d",
            reason,
            len(raw_products),
            len(categories),
            expected_category_occurrences,
        )

        self.sync_products(
            raw_products,
            full_sync=bool(categories),
            allow_prune=complete,
            expected_products=0,
            expected_category_occurrences=expected_category_occurrences,
        )
        self._attach_category_coverage(
            raw_products,
            self._consolidate_for_coverage(raw_products),
            categories,
        )
        self.last_sync_result.errors = list(
            dict.fromkeys(self.last_sync_result.errors)
        )
        self.last_sync_result.finish()
        _log_timing(
            "SCRAPING TIMING | stage=sync_categories_total | categories=%d | "
            "products=%d | seconds=%.3f",
            len(categories),
            len(raw_products),
            time.perf_counter() - total_started,
        )
        return raw_products

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
                products = cast(list[Any], consolidate(list(products)))
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
                        prune_missing=False,
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
        self.last_sync_result.missing_code = (
            getattr(self.last_sync_result, "missing_code", 0)
            + getattr(result, "missing_code", 0)
        )
        self.last_sync_result.errors.extend(getattr(result, "errors", []))
        self.last_sync_result.changes.extend(getattr(result, "changes", []))
        if getattr(result, "category_summary", None):
            self.last_sync_result.category_summary = list(result.category_summary)
        if getattr(result, "multiple_category_products", None):
            self.last_sync_result.multiple_category_products = list(
                result.multiple_category_products
            )

    def _attach_category_coverage(self, raw_products, products, categories):
        category_summary = []
        multiple = []
        for category in categories:
            category_name = str(getattr(category, "name", "")).strip()
            category_products = [
                product
                for product in raw_products
                if category_name.casefold()
                in str(getattr(product, "category", "")).casefold()
            ]
            unique = {
                str(getattr(product, "code", "")).strip().casefold()
                for product in category_products
                if str(getattr(product, "code", "")).strip()
            }
            category_summary.append(
                {
                    "category": category_name,
                    "expected": max(
                        int(getattr(category, "expected_count", 0) or 0), 0
                    ),
                    "products": len(category_products),
                    "unique_products": len(unique),
                    "gap": max(
                        max(int(getattr(category, "expected_count", 0) or 0), 0)
                        - len(category_products),
                        0,
                    ),
                }
            )
        by_code = {}
        for product in raw_products:
            code = str(getattr(product, "code", "")).strip()
            if code:
                by_code.setdefault(code.casefold(), []).append(product)
        for code, occurrences in by_code.items():
            category_names = []
            for product in occurrences:
                name = str(getattr(product, "category", "")).strip()
                if name and name not in category_names:
                    category_names.append(name)
            if len(category_names) > 1:
                multiple.append(
                    {
                        "code": str(getattr(occurrences[0], "code", code)).strip(),
                        "name": str(getattr(occurrences[0], "name", "")).strip(),
                        "categories": category_names,
                    }
                )
        self.last_sync_result.category_summary = category_summary
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

    def _write_final_result_artifact(self, raw_products):
        writer = getattr(self.catalog_sync_service, "result_writer", None)
        if writer is None:
            return
        self.last_sync_result.finish()
        codes = {
            str(getattr(product, "code", "")).strip().upper().casefold()
            for product in raw_products
            if str(getattr(product, "code", "")).strip()
        }
        writer.write(self.last_sync_result, codes)

    def _consolidate_for_coverage(self, products) -> list[Any]:
        if self.catalog_sync_service:
            consolidate = getattr(
                self.catalog_sync_service, "consolidate_products", None
            )
            if callable(consolidate):
                return cast(list[Any], consolidate(deepcopy(products)))
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

        expected_unique = max(int(expected_products or 0), 0)
        if expected_unique > 0:
            unique_codes = {
                str(getattr(product, "code", "")).strip().casefold()
                for product in products
                if str(getattr(product, "code", "")).strip()
            }
            if len(unique_codes) < expected_unique:
                return False, f"unique_coverage_gap:{expected_unique - len(unique_codes)}"

        if expected_category_occurrences > 0:
            occurrence_gap = max(expected_category_occurrences - len(products), 0)
            if occurrence_gap:
                return False, f"category_coverage_gap:{occurrence_gap}"
        return True, "complete"
