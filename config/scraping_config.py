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

# Detail enrichment is an I/O-bound workload. Keep the detail worker pool
# larger than the shared HTTP budget so local task scheduling does not
# artificially serialize detail requests.
SCRAPING_MAX_WORKERS = 32

# Restore the previously validated category concurrency. The 8-worker tuning
# increased the category phase on the live catalog; 16 workers is the
# performance baseline that previously reached the correct FULL coverage.
SCRAPING_CATEGORY_WORKERS = 16

# Run 182 validated complete FULL coverage with 28 shared HTTP workers:
# 24 categories, 534 occurrences, 530 unique products, 4 multi-category
# products, 534 product-category relationships, complete coverage, and
# zero invalidating errors. Keep this as the production baseline until a
# new live FULL run establishes a different validated point.
SCRAPING_HTTP_WORKERS = 28

# JetSmartFilters/Bricks Query Loop request metadata observed on the live catalog.
# Keep these values centralized so the scraper can reproduce the provider query
# without hard-coding them inside the pagination implementation.
JETSMARTFILTERS_AJAX_URL = f"{BASE_URL}/wp-admin/admin-ajax.php"
JETSMARTFILTERS_ELEMENT_ID = "95dc8a"
JETSMARTFILTERS_SIGNATURE = "83bc155f208a7b2c473d90a84cf5fe01"
JETSMARTFILTERS_INDEXING_FILTERS = "434"
