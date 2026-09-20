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


def _normalize_coverage_inputs(
    result_or_products: Any,
    products: Iterable[Any] | None,
    category_summary: Iterable[dict[str, Any]] | None,
) -> tuple[list[Any], list[dict[str, Any]], Any | None]:
    if products is None:
        return list(result_or_products or []), list(category_summary or []), None

    result = result_or_products
    summary = list(
        category_summary
        if category_summary is not None
        else getattr(result, "category_summary", None) or []
    )
    return list(products or []), summary, result


def _products_have_codes(raw_products: list[Any]) -> bool:
    return all(str(getattr(product, "code", "") or "").strip() for product in raw_products)


def _category_summary_is_complete(summary: list[dict[str, Any]]) -> bool:
    for row in summary:
        expected = max(int(row.get("expected", 0) or 0), 0)
        if expected <= 0:
            continue
        products_found = int(row.get("products", 0) or 0)
        unique_found = int(row.get("unique_products", 0) or 0)
        if products_found != expected or unique_found != expected:
            return False
    return True


def _has_expected_occurrences(
    raw_products: list[Any],
    expected_occurrences: int,
    result: Any | None,
) -> bool:
    if expected_occurrences <= 0 or len(raw_products) < expected_occurrences:
        return False
    if result is None or getattr(result, "products_found", None) is None:
        return True
    actual_occurrences = int(getattr(result, "products_found", len(raw_products)) or 0)
    return actual_occurrences >= expected_occurrences


def _has_expected_unique_products(raw_products: list[Any], expected_products: int) -> bool:
    if not expected_products:
        return True
    unique_codes = {
        str(getattr(product, "code", "")).strip().casefold()
        for product in raw_products
        if str(getattr(product, "code", "")).strip()
    }
    return len(unique_codes) >= max(int(expected_products), 0)


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
    raw_products, summary, result = _normalize_coverage_inputs(
        result_or_products,
        products,
        category_summary,
    )
    expected_occurrences = max(int(expected_category_occurrences or 0), 0)

    if not raw_products or not _products_have_codes(raw_products):
        return False
    if not _has_expected_occurrences(raw_products, expected_occurrences, result):
        return False
    if summary and not _category_summary_is_complete(summary):
        return False
    return _has_expected_unique_products(raw_products, expected_products)


__all__ = [
    "demonstrates_complete_coverage",
    "has_complete_category_coverage",
]
