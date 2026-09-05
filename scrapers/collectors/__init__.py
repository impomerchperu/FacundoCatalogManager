"""Collectors package initialization."""

# Apply compatibility layers whenever the collectors package is imported.
# They preserve the existing architecture while overriding only the defective
# category pagination, WooCommerce code-discovery, page-audit, coverage
# recovery, price-detail, and JetSmartFilters concurrency behaviors.
from . import category_pagination_patch as _category_pagination_patch
from . import jsf_concurrency_patch as _jsf_concurrency_patch
from . import missing_code_recovery_patch as _missing_code_recovery_patch
from . import page_coverage_recovery_patch as _page_coverage_recovery_patch
from . import page_metrics_patch as _page_metrics_patch
from . import price_detail_recovery_patch as _price_detail_recovery_patch
from . import product_code_patch as _product_code_patch
from . import scraping_compat as _scraping_compat
from . import jsf_first_page_recovery_patch as _jsf_first_page_recovery_patch

__all__ = [
    "_category_pagination_patch",
    "_jsf_concurrency_patch",
    "_missing_code_recovery_patch",
    "_page_coverage_recovery_patch",
    "_page_metrics_patch",
    "_price_detail_recovery_patch",
    "_product_code_patch",
    "_scraping_compat",
    "_jsf_first_page_recovery_patch",
]
