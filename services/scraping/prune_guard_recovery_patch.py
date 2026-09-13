"""Allow pruning after terminal HTTP errors are fully recovered.

A terminal HTTP error is only a pruning blocker while final category coverage
is still incomplete. The scraper can report a terminal HTTP error from an
intermediate request and still recover every expected product occurrence.
In that case the final coverage, not the transient request metric, decides
whether a FULL catalog sync may prune.
"""

from services.scraping.category_product_sync_service import CategoryProductSyncService

_PATCHED = False
_ORIGINAL_TERMINAL_HTTP_ERROR_REASON = (
    CategoryProductSyncService._terminal_http_error_reason
)


def _has_complete_category_coverage(self: CategoryProductSyncService) -> bool:
    result = self.last_sync_result
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


def _terminal_http_error_reason(self: CategoryProductSyncService):
    """Ignore terminal request errors when the final category coverage is complete."""
    if _has_complete_category_coverage(self):
        return None
    return _ORIGINAL_TERMINAL_HTTP_ERROR_REASON(self)


def activate() -> None:
    """Install the recovered-error pruning hook once."""
    global _PATCHED
    if _PATCHED:
        return
    CategoryProductSyncService._has_complete_category_coverage = _has_complete_category_coverage  # pyright: ignore[reportAttributeAccessIssue]
    CategoryProductSyncService._terminal_http_error_reason = _terminal_http_error_reason
    _PATCHED = True


activate()

__all__ = ["activate"]
