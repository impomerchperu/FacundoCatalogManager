"""Compatibility facade for the native page metrics audit."""

from __future__ import annotations

from services.scraping.page_metrics_audit import TIMING_LOG, record_page_metrics

_PATCHED = False


def activate() -> None:
    """Preserve the historical activation API without monkey-patching runtime code."""
    return None


__all__ = ["TIMING_LOG", "activate", "record_page_metrics"]
