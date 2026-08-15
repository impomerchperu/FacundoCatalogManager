BASE_URL = "https://stock.importacionesfacundo.com"

STORE_URL = f"{BASE_URL}/tienda/"


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120 Safari/537.36"
    )
}


REQUEST_TIMEOUT = 15

MAX_RETRIES = 3

# Number of concurrent HTTP workers used when enriching product detail pages.
# Keep this conservative to avoid overloading the source site.
SCRAPING_MAX_WORKERS = 8

# Number of categories scraped concurrently. This is intentionally lower than
# the per-category detail worker count to keep total HTTP concurrency bounded.
SCRAPING_CATEGORY_WORKERS = 3
