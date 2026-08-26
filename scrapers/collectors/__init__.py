"""Collectors package initialization."""

# Apply the JSF pagination correction before callers import CategoryScraper.
from . import category_pagination_patch as _category_pagination_patch  # noqa: F401
