"""Compatibility patch for normalized category coverage behavior."""

from __future__ import annotations

from typing import Any

from services.scraping.category_name_normalizer import (
    normalize_category_name,
    split_category_names,
)
from services.scraping.category_product_sync_service import CategoryProductSyncService

_PATCHED = False


def _product_category_keys(product: Any) -> set[str]:
    return {
        normalize_category_name(category)
        for category in split_category_names(str(getattr(product, "category", "")))
        if normalize_category_name(category)
    }


def _attach_category_coverage(
    self: CategoryProductSyncService,
    raw_products: list[Any],
    products_or_categories: list[Any],
    categories: list[Any] | None = None,
) -> None:
    """Compare category coverage by normalized key while preserving display text."""
    legacy_call = categories is None
    categories = products_or_categories if legacy_call else categories

    category_summary = []
    multiple = []
    for category in categories or []:
        category_name = str(getattr(category, "name", "")).strip()
        comparison_key = normalize_category_name(category_name)
        category_products = [
            product
            for product in raw_products
            if comparison_key and comparison_key in _product_category_keys(product)
        ]
        unique = {
            str(getattr(product, "code", "")).strip().casefold()
            for product in category_products
            if str(getattr(product, "code", "")).strip()
        }
        if legacy_call:
            category_summary.append(
                {
                    "category": category_name,
                    "comparison_key": comparison_key,
                    "products": len(category_products),
                    "unique_products": len(unique),
                }
            )
        else:
            expected = max(int(getattr(category, "expected_count", 0) or 0), 0)
            category_summary.append(
                {
                    "category": category_name,
                    "comparison_key": comparison_key,
                    "expected": expected,
                    "products": len(category_products),
                    "unique_products": len(unique),
                    "gap": max(expected - len(category_products), 0),
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
    self.last_sync_result.products_found = len(raw_products)
    self.last_sync_result.products_unique = len(
        {
            str(getattr(product, "code", "")).strip()
            for product in raw_products
            if str(getattr(product, "code", "")).strip()
        }
    )
    self.last_sync_result.duplicate_occurrences = max(
        self.last_sync_result.products_found - self.last_sync_result.products_unique,
        0,
    )


def _split_categories(self: CategoryProductSyncService, value: object) -> list[str]:
    """Preserve canonical category names while supporting the legacy helper API."""
    del self
    return split_category_names(value)


def activate() -> None:
    """Install normalized category coverage compatibility hooks once."""
    global _PATCHED
    if _PATCHED:
        return
    CategoryProductSyncService._attach_category_coverage = _attach_category_coverage
    CategoryProductSyncService._split_categories = _split_categories
    _PATCHED = True


activate()

__all__ = ["activate"]
