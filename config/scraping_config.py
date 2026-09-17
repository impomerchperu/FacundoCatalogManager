BASE_URL = "https://stock.importacionesfacundo.com"

STORE_URL = f"{BASE_URL}/tienda/"


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "Chrome/120 Safari/537.36"
    )
}


REQUEST_TIMEOUT = 20

MAX_RETRIES = 3

# Use lxml for the large number of HTML parses performed during catalog
# extraction. category_scraper.py keeps a html.parser fallback for portability.
SCRAPING_HTML_PARSER = "lxml"

# Detail enrichment is an I/O-bound workload. The live FULL benchmark validated
# 24 detail workers as the best observed point with the current HTTP budget.
SCRAPING_MAX_WORKERS = 24

# The live production-concurrency benchmark repeatedly preserved complete
# coverage with 8 category workers while avoiding the retry pressure observed
# at higher category concurrency.
SCRAPING_CATEGORY_WORKERS = 8

# Keep the shared HTTP budget at the validated live FULL baseline:
# 24 categories, 534 occurrences, 530 unique products, 4 multi-category
# products, 534 product-category relationships, complete coverage, and
# zero invalidating errors. Increasing this budget did not improve wall time.
SCRAPING_HTTP_WORKERS = 28

# JetSmartFilters/Bricks Query Loop request metadata observed on the live catalog.
# Keep these values centralized so the scraper can reproduce the provider query
# without hard-coding them inside the pagination implementation.
JETSMARTFILTERS_AJAX_URL = f"{BASE_URL}/wp-admin/admin-ajax.php"
JETSMARTFILTERS_ELEMENT_ID = "95dc8a"
JETSMARTFILTERS_SIGNATURE = "83bc155b208a7b2c473d90a84cf5fe01"
JETSMARTFILTERS_INDEXING_FILTERS = "434"

# The canonical pagination engine still walks category pages sequentially, so
# this is intentionally isolated as the first network-only performance
# experiment. It remains below the shared HTTP worker budget.
SCRAPING_JSF_HTTP_CONCURRENCY = 8
