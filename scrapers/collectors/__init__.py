"""Collectors package initialization."""

# Apply the Facundo-specific pagination and SKU compatibility layer whenever
# the collectors package is imported. The compatibility module preserves the
# existing scraper architecture and overrides only the two defective behaviors.
from . import category_pagination_patch as _category_pagination_patch
from . import scraping_compat as _scraping_compat

__all__ = ["_category_pagination_patch", "_scraping_compat"]
