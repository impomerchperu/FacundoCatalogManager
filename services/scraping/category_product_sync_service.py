from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import requests

from config.scraping_config import SCRAPING_CATEGORY_WORKERS
from models.scraping.sync_result import SyncResult
from services.scraping.category_name_normalizer import (
    canonical_category_name,
    normalize_category_name,
    split_category_names,
)

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
        self._occurrence_categories = []

    def reset_sync_result(self):
        self.last_sync_result = SyncResult()

    @staticmethod
    def _split_categories(value: object) -> list[str]:
        """Mantiene la API histórica delegando en el normalizador canónico."""
        return split_category_names(value)

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
        self._occurrence_categories = []
        expected_category_occurrences = sum(
            max(int(getattr(category, "expected_count", 0) or 0), 0)
            for category in categories
        )
        self.last_sync_result = SyncResult()
        self.last_sync_result.products_expected = 0
        self.last_sync_result.expected_category_occurrences = expected_category_occurrences

        collected_by_index: list[list[Any]] = [[] for _ in categories]
        failed_category_errors: dict[int, str] = {}
        started = time.perf_counter()
        self._enable_thread_sessions()
        if categories:
            worker_count = min(SCRAPING_CATEGORY_WORKERS, len(categories))
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = {
                    executor.submit(self._collect_category, index, category): index
                    for index, category in enumerate(categories)
                }
                for future, index in futures.items():
                    category = categories[index]
                    try:
                        collected_by_index[index] = cast(list[Any], future.result())
                    except requests.exceptions.RequestException as error:
                        collected_by_index[index] = []
                        category_name = str(
                            getattr(category, "name", "")
                        ).strip() or "(sin nombre)"
                        message = (
                            f"Error de red en categoría '{category_name}': "
                            f"{error}"
                        )
                        failed_category_errors[index] = message
                        self.last_sync_result.errors.append(message)
                        _log_timing(
                            "SCRAPING TIMING | stage=category_error | category=%s | "
                            "error_type=%s | error=%s",
                            category_name,
                            type(error).__name__,
                            str(error),
                        )
                    if progress_callback:
                        progress_callback(index + 1, len(categories))

        if failed_category_errors:
            recovery_started = time.perf_counter()
            recovered = 0
            for index, original_error in failed_category_errors.items():
                category = categories[index]
                category_name = str(getattr(category, "name", "")).strip() or "(sin nombre)"
                try:
                    collected_by_index[index] = cast(
                        list[Any],
                        self._collect_category(index, category),
                    )
                except requests.exceptions.RequestException as error:
                    _log_timing(
                        "SCRAPING TIMING | stage=category_recovery_error | category=%s | "
                        "error_type=%s | error=%s",
                        category_name,
                        type(error).__name__,
                        str(error),
                    )
                    self.last_sync_result.errors.append(
                        f"Reintento fallido en categoría '{category_name}': {error}"
                    )
                else:
                    recovered += 1
                    self.last_sync_result.errors = [
                        message
                        for message in self.last_sync_result.errors
                        if message != original_error
                    ]
                    _log_timing(
                        "SCRAPING TIMING | stage=category_recovered | category=%s | products=%d",
                        category_name,
                        len(collected_by_index[index]),
                    )
            _log_timing(
                "SCRAPING TIMING | stage=category_recovery | attempted=%d | recovered=%d | seconds=%.3f",
                len(failed_category_errors),
                recovered,
                time.perf_counter() - recovery_started,
            )

        _log_timing(
            "SCRAPING TIMING | stage=category_listing | categories=%d | products=%d | expected_category_occurrences=%d | seconds=%.3f",
            len(categories),
            sum(len(items) for items in collected_by_index),
            expected_category_occurrences,
            time.perf_counter() - started,
        )

        started = time.perf_counter()
        enriched_by_index: list[list[Any] | None] = [None] * len(categories)
        if categories:
            worker_count = min(SCRAPING_CATEGORY_WORKERS, len(categories))
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = {
                    executor.submit(
                        self._enrich_category,
                        index,
                        category,
                        collected_by_index[index],
                    ): index
                    for index, category in enumerate(categories)
                }
                for future, index in futures.items():
                    enriched_by_index[index] = cast(list[Any], future.result())

        products = []
        for index, category in enumerate(categories):
            enriched = enriched_by_index[index] or []
            for product in enriched:
                self._record_category_occurrence(product, category.name)
            products.extend(enriched)
        _log_timing(
            "SCRAPING TIMING | stage=category_extraction | categories=%d | products=%d | expected_category_occurrences=%d | seconds=%.3f",
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

        full_mode = getattr(self, "_scraping_mode", "directed") == "full"
        complete, reason = self._full_sync_prune_guard(
            raw_products,
            len(categories),
            expected_category_occurrences=expected_category_occurrences,
            expected_products=len(coverage_products) if full_mode else 0,
        )
        if not full_mode:
            reason = "directed_mode"
            complete = False
        _log_timing(
            "SCRAPING TIMING | stage=coverage_incomplete | reason=%s | products=%d | categories=%d | expected_category_occurrences=%d",
            reason,
            len(raw_products),
            len(categories),
            expected_category_occurrences,
        )

        synced_products = self.sync_products(
            raw_products,
            full_sync=full_mode,
            allow_prune=complete,
            expected_products=len(coverage_products) if full_mode else 0,
            expected_category_occurrences=expected_category_occurrences,
        )
        self._propagate_synced_fields(raw_products, synced_products)
        self._attach_category_coverage(
            raw_products,
            self._consolidate_for_coverage(raw_products),
            categories,
        )
        self.last_sync_result.errors = list(dict.fromkeys(self.last_sync_result.errors))
        self.last_sync_result.finish()
        self._write_final_result_artifact(raw_products)
        _log_timing(
            "SCRAPING TIMING | stage=sync_categories_total | categories=%d | products=%d | seconds=%.3f",
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
            consolidate = getattr(self.catalog_sync_service, "consolidate_products", None)
            if callable(consolidate):
                products = cast(list[Any], consolidate(deepcopy(products)))
            _log_timing(
                "SCRAPING TIMING | stage=consolidation | products=%d | seconds=%.3f",
                len(products),
                time.perf_counter() - started,
            )
            if self.image_sync_adapter:
                started = time.perf_counter()
                products = cast(list[Any], self.image_sync_adapter.sync_products(products))
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
                "SCRAPING TIMING | stage=catalog_sync | products=%d | seconds=%.3f | prune=%s | expected_unique=%s | expected_category_occurrences=%s | unique=%d | gap=%d",
                len(mapped_products),
                time.perf_counter() - started,
                str(use_prune).lower(),
                expected_products if expected_products else "unknown",
                expected_category_occurrences if expected_category_occurrences else "unknown",
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

    @staticmethod
    def _propagate_synced_fields(raw_products, synced_products):
        """Devuelve al objeto scrapeado los campos enriquecidos durante sync."""
        synced_by_code = {}
        for product in synced_products or []:
            code = str(getattr(product, "code", "")).strip()
            if code:
                synced_by_code[code.casefold()] = product
        for raw_product in raw_products or []:
            code = str(getattr(raw_product, "code", "")).strip()
            if not code:
                continue
            synced_product = synced_by_code.get(code.casefold())
            if synced_product is None:
                continue
            for field in ("image_path", "image_hash", "content_hash"):
                value = getattr(synced_product, field, "")
                if value:
                    setattr(raw_product, field, value)

    def _accumulate_sync_result(self, result):
        for field in (
            "processed", "created", "updated", "unchanged", "deleted", "generated",
            "products_found", "products_unique", "products_multiple_categories",
            "duplicate_occurrences",
        ):
            setattr(
                self.last_sync_result,
                field,
                getattr(self.last_sync_result, field, 0) + getattr(result, field, 0),
            )
        self.last_sync_result.products_expected = max(
            getattr(self.last_sync_result, "products_expected", 0),
            getattr(result, "products_expected", 0),
        )
        self.last_sync_result.expected_category_occurrences = max(
            getattr(self.last_sync_result, "expected_category_occurrences", 0),
            getattr(result, "expected_category_occurrences", 0),
        )
        self.last_sync_result.missing_code += getattr(result, "missing_code", 0)
        self.last_sync_result.errors.extend(getattr(result, "errors", []))
        self.last_sync_result.changes.extend(getattr(result, "changes", []))
        if getattr(result, "category_summary", None):
            self.last_sync_result.category_summary = list(result.category_summary)
        if getattr(result, "multiple_category_products", None):
            self.last_sync_result.multiple_category_products = list(result.multiple_category_products)

    def _record_category_occurrence(self, product, category_name):
        code = str(getattr(product, "code", "")).strip()
        if not code:
            return
        canonical_name = canonical_category_name(str(category_name or "").strip())
        normalized = normalize_category_name(canonical_name)
        if not normalized:
            return
        self._occurrence_categories.append(
            {
                "code": code,
                "code_key": code.casefold(),
                "category": canonical_name,
                "category_key": normalized,
            }
        )

    def _category_summary(self, raw_products, categories, legacy_call):
        has_occurrences = bool(self._occurrence_categories)
        return [
            self._build_category_summary_row(
                raw_products,
                category,
                legacy_call,
                has_occurrences,
            )
            for category in categories
        ]

    def _build_category_summary_row(
        self,
        raw_products,
        category,
        legacy_call,
        has_occurrences,
    ):
        category_name = canonical_category_name(str(getattr(category, "name", "")).strip())
        expected = max(int(getattr(category, "expected_count", 0) or 0), 0)
        category_key = normalize_category_name(category_name)
        if has_occurrences:
            occurrences = [
                occurrence
                for occurrence in self._occurrence_categories
                if occurrence["category_key"] == category_key
            ]
            products_found = len(occurrences)
            unique = {occurrence["code_key"] for occurrence in occurrences}
        else:
            category_products = [
                product
                for product in raw_products
                if category_key
                and category_key in {
                    normalize_category_name(value)
                    for value in split_category_names(getattr(product, "category", ""))
                }
            ]
            products_found = len(category_products)
            unique = {
                str(getattr(product, "code", "")).strip().casefold()
                for product in category_products
                if str(getattr(product, "code", "")).strip()
            }
        if legacy_call:
            return {
                "category": category_name,
                "comparison_key": category_key,
                "products": products_found,
                "unique_products": len(unique),
            }
        return {
            "category": category_name,
            "expected": expected,
            "products": products_found,
            "unique_products": len(unique),
            "gap": max(expected - products_found, 0),
        }

    def _multiple_category_products(self, raw_products, categories=None):
        by_code = {}
        for occurrence in self._occurrence_categories:
            by_code.setdefault(occurrence["code_key"], {}).setdefault(
                occurrence["category_key"], occurrence["category"]
            )
        if not by_code and categories:
            requested = {
                normalize_category_name(canonical_category_name(getattr(category, "name", "")))
                for category in categories
            }
            for product in raw_products or []:
                code_key = str(getattr(product, "code", "")).strip().casefold()
                if not code_key:
                    continue
                category_map = by_code.setdefault(code_key, {})
                for value in split_category_names(getattr(product, "category", "")):
                    category_name = canonical_category_name(value)
                    category_key = normalize_category_name(category_name)
                    if category_key in requested:
                        category_map.setdefault(category_key, category_name)
                if len(category_map) <= 1:
                    by_code.pop(code_key, None)
        product_by_code = {
            str(getattr(product, "code", "")).strip().casefold(): product
            for product in raw_products or []
            if str(getattr(product, "code", "")).strip()
        }
        multiple = []
        for code_key, categories_by_key in by_code.items():
            if len(categories_by_key) <= 1:
                continue
            product = product_by_code.get(code_key)
            if product is None:
                continue
            multiple.append(
                {
                    "code": str(getattr(product, "code", "")).strip(),
                    "name": str(getattr(product, "name", "")).strip(),
                    "categories": list(categories_by_key.values()),
                }
            )
        return multiple

    def _attach_category_coverage(self, raw_products, products_or_categories, categories=None):
        legacy_call = categories is None
        categories = (
            list(products_or_categories or [])
            if legacy_call
            else list(categories or [])
        )
        del products_or_categories

        category_summary = self._category_summary(raw_products, categories, legacy_call)
        multiple = self._multiple_category_products(
            raw_products,
            None if legacy_call else categories,
        )
        self.last_sync_result.category_summary = category_summary
        self.last_sync_result.multiple_category_products = multiple
        self.last_sync_result.products_multiple_categories = len(multiple)
        self.last_sync_result.products_found = len(raw_products or [])
        self.last_sync_result.products_unique = len({
            str(getattr(product, "code", "")).strip().casefold()
            for product in raw_products or []
            if str(getattr(product, "code", "")).strip()
        })
        self.last_sync_result.duplicate_occurrences = max(
            self.last_sync_result.products_found - self.last_sync_result.products_unique,
            0,
        )
        for row in self.last_sync_result.category_summary:
            _log_timing(
                "SCRAPING TIMING | stage=category_coverage | category=%s | products=%d | unique=%d",
                row["category"], row["products"], row["unique_products"],
            )
        _log_timing(
            "SCRAPING TIMING | stage=multi_category_coverage | products=%d | categories=%d",
            len(multiple), len(self.last_sync_result.category_summary),
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
            consolidate = getattr(self.catalog_sync_service, "consolidate_products", None)
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
            category.url, category.name,
            expected_count=max(int(getattr(category, "expected_count", 0) or 0), 0),
        )

    def _enrich_category(self, index, category, collected):
        del index
        scraper = getattr(self.scraper_service, "scraper", None)
        enrich = getattr(scraper, "enrich_category_products", None)
        if callable(enrich):
            return enrich(collected, category.name)
        return self.scraper_service.scrape_category(
            category.url, category.name,
            expected_count=max(int(getattr(category, "expected_count", 0) or 0), 0),
        )

    def _enable_thread_sessions(self):
        scraper = getattr(self.scraper_service, "scraper", None)
        if scraper is None:
            return
        browser = getattr(scraper, "browser", None)
        if browser is None:
            category_scraper = getattr(scraper, "category_scraper", None)
            browser = getattr(category_scraper, "browser", None)
        enable = getattr(browser, "enable_thread_sessions", None)
        if callable(enable):
            enable()

    def _reset_scraping_metrics(self):
        scraper = getattr(self.scraper_service, "scraper", None)
        reset = getattr(scraper, "reset_metrics", None)
        if callable(reset):
            reset()

    def _log_detail_metrics(self):
        scraper = getattr(self.scraper_service, "scraper", None)
        metrics = getattr(scraper, "get_detail_metrics", None)
        if not callable(metrics):
            return
        values = cast(dict[str, Any], metrics() or {})
        _log_timing(
            "SCRAPING TIMING | stage=detail_cache | requests=%d | cache_hits=%d | cache_size=%d | skipped=%d",
            int(values.get("detail_requests", 0) or 0),
            int(values.get("detail_cache_hits", 0) or 0),
            int(values.get("detail_cache_size", 0) or 0),
            int(values.get("detail_skipped", 0) or 0),
        )

    def _log_http_metrics(self):
        scraper = getattr(self.scraper_service, "scraper", None)
        metrics = getattr(scraper, "get_http_metrics", None)
        if not callable(metrics):
            return
        values = cast(dict[str, Any], metrics() or {})
        _log_timing(
            "SCRAPING TIMING | stage=http | requests=%d | category=%d | detail=%d | other=%d | retries=%d | errors=%d | terminal=%d | total_seconds=%.3f | max_seconds=%.3f | max_concurrency=%d",
            int(values.get("http_requests", 0) or 0),
            int(values.get("category_http_requests", 0) or 0),
            int(values.get("detail_http_requests", 0) or 0),
            int(values.get("other_http_requests", 0) or 0),
            int(values.get("http_retries", 0) or 0),
            int(values.get("http_errors", 0) or 0),
            int(values.get("http_terminal_errors", 0) or 0),
            float(values.get("http_total_seconds", 0.0) or 0.0),
            float(values.get("http_max_seconds", 0.0) or 0.0),
            int(values.get("http_max_in_flight", 0) or 0),
        )

    def _browser(self):
        scraper = getattr(self.scraper_service, "scraper", None)
        browser = getattr(scraper, "browser", None)
        if browser is not None:
            return browser
        category_scraper = getattr(scraper, "category_scraper", None)
        return getattr(category_scraper, "browser", None)

    def _terminal_http_error_reason(self):
        browser = self._browser()
        metrics_getter = getattr(browser, "get_http_metrics", None)
        if not callable(metrics_getter):
            return None
        metrics = cast(dict[str, Any], metrics_getter() or {})
        terminal_errors = int(metrics.get("http_terminal_errors", 0) or 0)
        if terminal_errors:
            return f"terminal_http_errors:{terminal_errors}"
        return None

    @staticmethod
    def _category_coverage_gap_reason(category_summary):
        for row in cast(list[dict[str, Any]], category_summary):
            expected = max(int(row.get("expected", 0) or 0), 0)
            if expected <= 0:
                continue
            products_found = int(row.get("products", 0) or 0)
            unique_found = int(row.get("unique_products", 0) or 0)
            if products_found != expected or unique_found != expected:
                return f"category_coverage_gap:{row.get('category', '')}"
        return None

    @staticmethod
    def _unique_coverage_gap_reason(products, expected_products):
        expected_unique = max(int(expected_products or 0), 0)
        if not expected_unique:
            return None
        unique_codes = {
            str(getattr(product, "code", "")).strip().casefold()
            for product in products
            if str(getattr(product, "code", "")).strip()
        }
        if len(unique_codes) < expected_unique:
            return f"unique_coverage_gap:{expected_unique - len(unique_codes)}"
        return None

    def _full_sync_prune_guard(
        self,
        products,
        category_count,
        *,
        expected_category_occurrences=0,
        expected_products=None,
    ):
        if not products:
            return False, "no_products"
        if category_count <= 0:
            return False, "no_categories"

        expected_occurrences = max(int(expected_category_occurrences or 0), 0)
        if expected_occurrences <= 0:
            return False, "no_expected_category_occurrences"

        missing = sum(
            1 for product in products
            if not str(getattr(product, "code", "") or "").strip()
        )
        if missing:
            return False, f"missing_codes:{missing}"

        terminal_reason = self._terminal_http_error_reason()
        if terminal_reason:
            return False, terminal_reason

        category_reason = self._category_coverage_gap_reason(
            getattr(self.last_sync_result, "category_summary", []) or []
        )
        if category_reason:
            return False, category_reason

        if len(products) < expected_occurrences:
            return False, f"category_coverage_gap:{expected_occurrences - len(products)}"

        unique_reason = self._unique_coverage_gap_reason(products, expected_products)
        if unique_reason:
            return False, unique_reason

        return True, "complete"
