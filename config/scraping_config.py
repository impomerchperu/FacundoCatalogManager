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


REQUEST_TIMEOUT = 15

MAX_RETRIES = 3

# Detail workers may prepare several categories concurrently, while Browser
# applies a shared HTTP semaphore so category and detail traffic remain
# bounded independently.
SCRAPING_MAX_WORKERS = 20

# Measurements show that 20 category workers add contention without improving
# end-to-end runtime. Keep the stable category budget at 16 workers.
SCRAPING_CATEGORY_WORKERS = 16

# The detail pipeline is the dominant network workload. Keep its HTTP budget
# above the category executor so detail workers can overlap across categories
# without being serialized by the shared Browser semaphore.
SCRAPING_HTTP_WORKERS = 32

# Trusted unique-product target for a complete catalog run. Category counts are
# occurrence counts and may include the same product in multiple categories,
# so they must not be used as the unique-product target.
EXPECTED_CATALOG_PRODUCTS = 525

# JetSmartFilters/Bricks Query Loop request metadata observed on the live catalog.
# Keep these values centralized so the scraper can reproduce the provider query
# without hard-coding them inside the pagination implementation.
JETSMARTFILTERS_AJAX_URL = f"{BASE_URL}/wp-admin/admin-ajax.php"
JETSMARTFILTERS_ELEMENT_ID = "95dc8a"
JETSMARTFILTERS_SIGNATURE = "83bc155f208a7b2c473d90a84cf5fe01"
JETSMARTFILTERS_INDEXING_FILTERS = "434"
