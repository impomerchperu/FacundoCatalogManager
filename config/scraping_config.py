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

# Allow a slightly wider HTTP pipeline than the category executor. This is
# intentionally independent so detail requests can use spare network capacity
# without increasing category scheduling contention.
SCRAPING_HTTP_WORKERS = 20

# Trusted unique-product target for a complete catalog run. Category counts are
# occurrence counts and may include the same product in multiple categories,
# so they must not be used as the unique-product target.
EXPECTED_CATALOG_PRODUCTS = 525
