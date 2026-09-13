"""Compatibility facade for the canonical category pagination engine.

The pagination implementation lives in ``category_pagination_engine``.
This module remains import-compatible for older callers and tests while the
remaining runtime patch layer is retired.
"""

from __future__ import annotations

from .category_pagination_engine import (
    JSF_PAGE_RETRIES,
    _collect_direct_pages,
    _direct_product_urls,
    _jsf_category_pages_with_probe,
    _page_product_keys,
    get_category_pages,
    pages_required,
)

_PATCHED = False


def activate() -> None:
    """Keep the historical activation hook without installing a monkey patch."""
    global _PATCHED
    _PATCHED = True


activate()

__all__ = ["JSF_PAGE_RETRIES", "activate", "pages_required"]