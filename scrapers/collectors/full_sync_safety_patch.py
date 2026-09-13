"""Compatibility layer for the retained FULL-sync safety policy."""

from __future__ import annotations

from services.scraping.category_product_sync_service import CategoryProductSyncService
from services.scraping.full_sync_coverage_policy import (
    demonstrates_complete_coverage,
    has_complete_category_coverage,
)

_PATCHED = False
_ORIGINAL_SYNC_CATEGORIES = CategoryProductSyncService.sync_categories
_ORIGINAL_COVERAGE_GUARD = CategoryProductSyncService._full_sync_prune_guard
_ORIGINAL_SYNC_PRODUCTS = CategoryProductSyncService.sync_products
_ORIGINAL_TERMINAL_HTTP_ERROR_REASON = CategoryProductSyncService._terminal_http_error_reason


def _sync_categories_with_safety(self, categories, progress_callback=None):
    self._full_sync_coverage_validated = None
    self._full_sync_coverage_reason = ""
    return _ORIGINAL_SYNC_CATEGORIES(self, categories, progress_callback)


def _has_complete_category_coverage(self: CategoryProductSyncService) -> bool:
    return has_complete_category_coverage(self.last_sync_result)


def _terminal_http_error_reason(self: CategoryProductSyncService):
    """Ignore transient terminal errors when final category coverage is complete."""
    if _has_complete_category_coverage(self):
        return None
    return _ORIGINAL_TERMINAL_HTTP_ERROR_REASON(self)


def _coverage_guard_with_state(
    self,
    products,
    category_count,
    *,
    expected_category_occurrences=0,
    expected_products=None,
):
    complete, reason = _ORIGINAL_COVERAGE_GUARD(
        self,
        products,
        category_count,
        expected_category_occurrences=expected_category_occurrences,
        expected_products=expected_products,
    )
    self._full_sync_coverage_validated = bool(complete)
    self._full_sync_coverage_reason = str(reason or "unknown")
    return complete, reason


def _demonstrates_complete_coverage(
    self,
    products,
    *,
    expected_products=0,
    expected_category_occurrences=0,
) -> bool:
    return demonstrates_complete_coverage(
        self.last_sync_result,
        products,
        expected_products=expected_products,
        expected_category_occurrences=expected_category_occurrences,
    )


def _sync_products_with_safety(
    self,
    products,
    full_sync=False,
    allow_prune=False,
    expected_products=0,
    expected_category_occurrences=0,
):
    coverage_validated = getattr(self, "_full_sync_coverage_validated", None)
    if full_sync and coverage_validated is False:
        recovered = _demonstrates_complete_coverage(
            self,
            products,
            expected_products=expected_products,
            expected_category_occurrences=expected_category_occurrences,
        )
        if not recovered:
            reason = str(
                getattr(self, "_full_sync_coverage_reason", "unknown") or "unknown"
            )
            self.last_sync_result.errors.append(
                "Cobertura del catálogo incompleta: "
                f"sincronización FULL omitida por seguridad ({reason})."
            )
            return list(products or [])
        allow_prune = True
        self._full_sync_coverage_validated = True
        self._full_sync_coverage_reason = "complete"

    return _ORIGINAL_SYNC_PRODUCTS(
        self,
        products,
        full_sync=full_sync,
        allow_prune=allow_prune,
        expected_products=expected_products,
        expected_category_occurrences=expected_category_occurrences,
    )


def activate() -> None:
    """Install the retained FULL-sync compatibility layer exactly once."""
    global _PATCHED
    if _PATCHED:
        return
    if CategoryProductSyncService.sync_categories is _sync_categories_with_safety:
        _PATCHED = True
        return
    CategoryProductSyncService.sync_categories = _sync_categories_with_safety
    CategoryProductSyncService._full_sync_prune_guard = _coverage_guard_with_state  # pyright: ignore[reportAttributeAccessIssue]
    CategoryProductSyncService._terminal_http_error_reason = _terminal_http_error_reason
    CategoryProductSyncService.sync_products = _sync_products_with_safety
    CategoryProductSyncService._has_complete_category_coverage = _has_complete_category_coverage  # pyright: ignore[reportAttributeAccessIssue]
    _PATCHED = True


activate()

__all__ = ["activate"]
