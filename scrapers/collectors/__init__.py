"""Collectors package initialization."""

# Apply compatibility layers whenever the collectors package is imported.
# They preserve the existing architecture while overriding only the defective
# category pagination, WooCommerce code-discovery, page-audit, and coverage
# recovery behaviors.
from . import category_pagination_patch as _category_pagination_patch
from . import missing_code_recovery_patch as _missing_code_recovery_patch
from . import page_coverage_recovery_patch as _page_coverage_recovery_patch
from . import page_metrics_patch as _page_metrics_patch
from . import product_code_patch as _product_code_patch
from . import scraping_compat as _scraping_compat

__all__ = [
    "_category_pagination_patch",
    "_missing_code_recovery_patch",
    "_page_coverage_recovery_patch",
    "_page_metrics_patch",
    "_product_code_patch",
    "_scraping_compat",
]
