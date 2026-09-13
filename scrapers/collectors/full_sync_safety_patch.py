"""Legacy compatibility facade for the FULL-sync safety policy.

The safety policy is now implemented by CategoryProductSyncService itself.
This module remains importable for historical callers but no longer patches
runtime classes at import time.
"""

from __future__ import annotations

from services.scraping.full_sync_coverage_policy import (
    demonstrates_complete_coverage,
    has_complete_category_coverage,
)


_PATCHED = False


def activate() -> None:
    """Preserve the historical activation API without monkey-patching runtime classes."""
    return None


__all__ = [
    "activate",
    "demonstrates_complete_coverage",
    "has_complete_category_coverage",
]
