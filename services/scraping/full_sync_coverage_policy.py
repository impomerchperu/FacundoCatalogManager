"""Shared predicates for validating complete FULL catalog coverage."""

from __future__ import annotations

from typing import Any, Iterable


def has_complete_category_coverage(result: Any) -> bool:
    """Return whether the recorded category coverage is complete."""
    expected = max(
        int(getattr(result, "expected_category_occurrences", 0) or 0),
        0,
    )
    if expected <= 0:
        return False
    if int(getattr(result, "products_found", 0) or 0) < expected:
        return False

    summary = getattr(result, "category_summary", None) or []
    if not summary:
        return False

    for row in summary:
        row_expected = max(int(row.get("expected", 0) or 0), 0)
        if row_expected <= 0:
            continue
        if int(row.get("products", 0) or 0) != row_expected:
            return False
        if int(row.get("unique_products", 0) or 0) != row_expected:
            return False
    return True


def demonstrates_complete_coverage(
    result_or_products: Any,
    products: Iterable[Any] | None = None,
    *,
    expected_products: int = 0,
    expected_category_occurrences: int = 0,
    category_summary: Iterable[dict[str, Any]] | None = None,
) -> bool:
    """Verify final collected coverage independently of transient HTTP errors.

    The canonical form is ``(result, products, ...)``.  A compatibility form
    also accepts ``(products, category_summary=..., ...)`` so callers that
    already have the summary separated from the result object remain valid.
    """
    if products is None:
        raw_products = list(result_or_products or [])
        summary = list(category_summary or [])
    else:
        result = result_or_products
        raw_products = list(products or [])
        summary = list(
            category_summary
            if category_summary is not None
            else getattr(result, "category_summary", None) or []
        )

    if not raw_products:
        return False

    if any(
        not str(getattr(product, "code", "") or "").strip()
        for product in raw_products
    ):
        return False

    expected_occurrences = max(int(expected_category_occurrences or 0), 0)
    if expected_occurrences <= 0 or len(raw_products) < expected_occurrences:
        return False

    if summary:
        for row in summary:
            expected = max(int(row.get("expected", 0) or 0), 0)
            if expected <= 0:
                continue
            products_found = int(row.get("products", 0) or 0)
            unique_found = int(row.get("unique_products", 0) or 0)
            if products_found != expected or unique_found != expected:
                return False
    elif products is not None:
        actual_occurrences = int(
            getattr(result_or_products, "products_found", len(raw_products)) or 0
        )
        if actual_occurrences < expected_occurrences:
            return False

    if expected_products:
        unique_codes = {
            str(getattr(product, "code", "")).strip().casefold()
            for product in raw_products
            if str(getattr(product, "code", "")).strip()
        }
        if len(unique_codes) < max(int(expected_products), 0):
            return False

    return True


__all__ = [
    "demonstrates_complete_coverage",
    "has_complete_category_coverage",
]
