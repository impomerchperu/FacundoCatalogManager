"""Allow pruning after terminal HTTP errors are fully recovered.

A terminal HTTP error is only a pruning blocker while final category coverage
is still incomplete. Once every expected category occurrence is present, the
error was recovered without a coverage loss and must not prevent full sync
cleanup.
"""

from services.scraping.category_product_sync_service import CategoryProductSyncService

_PATCHED = False
_ORIGINAL_TERMINAL_HTTP_ERROR_REASON = (
    CategoryProductSyncService._terminal_http_error_reason
)


def _terminal_http_error_reason(self: CategoryProductSyncService):
    """Ignore recovered terminal errors once the final coverage is complete."""
    if getattr(self.last_sync_result, "coverage_complete", False):
        return None
    return _ORIGINAL_TERMINAL_HTTP_ERROR_REASON(self)


def activate() -> None:
    """Install the recovered-error pruning hook once."""
    global _PATCHED
    if _PATCHED:
        return
    CategoryProductSyncService._terminal_http_error_reason = _terminal_http_error_reason
    _PATCHED = True


activate()

__all__ = ["activate"]
