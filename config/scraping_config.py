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


REQUEST_TIMEOUT = 10

MAX_RETRIES = 3

# Use lxml for the large number of HTML parses performed during catalog
# extraction. category_scraper.py keeps a html.parser fallback for portability.
SCRAPING_HTML_PARSER = "lxml"

# Detail enrichment is an I/O-bound workload. Match its worker pool to the
# shared Browser HTTP budget so detail requests can fully use the available
# 32 in-flight HTTP slots without creating a larger unbounded queue.
SCRAPING_MAX_WORKERS = 32

# Restore the previously validated category concurrency. The 8-worker tuning
# increased the category phase on the live catalog; 16 workers is the
# performance baseline that previously reached the correct FULL coverage.
SCRAPING_CATEGORY_WORKERS = 16

# The detail pipeline is the dominant network workload. Keep its HTTP budget
# aligned with the detail executor so detail workers can overlap across
# categories without being serialized by the shared Browser semaphore.
SCRAPING_HTTP_WORKERS = 32

# JetSmartFilters/Bricks Query Loop request metadata observed on the live catalog.
# Keep these values centralized so the scraper can reproduce the provider query
# without hard-coding them inside the pagination implementation.
JETSMARTFILTERS_AJAX_URL = f"{BASE_URL}/wp-admin/admin-ajax.php"
JETSMARTFILTERS_ELEMENT_ID = "95dc8a"
JETSMARTFILTERS_SIGNATURE = "83bc155f208a7b2c473d90a84cf5fe01"
JETSMARTFILTERS_INDEXING_FILTERS = "434"
