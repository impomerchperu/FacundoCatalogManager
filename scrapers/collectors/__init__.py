"""Collectors package initialization."""

# Apply compatibility layers whenever the collectors package is imported.
# They preserve the existing architecture while overriding only the defective
# category pagination and WooCommerce code-discovery behaviors.
from . import category_pagination_patch as _category_pagination_patch
from . import product_code_patch as _product_code_patch
from . import scraping_compat as _scraping_compat

__all__ = [
    "_category_pagination_patch",
    "_product_code_patch",
    "_scraping_compat",
]
