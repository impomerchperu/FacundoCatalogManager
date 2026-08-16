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
# Detail requests can use a larger budget because they are numerous and the
# detail executor is shared across category enrichment tasks.
SCRAPING_MAX_WORKERS = 20

# Category listing requests run in a dedicated phase before detail enrichment.
# Measurements show that 20 workers add contention without improving the
# end-to-end runtime, so keep the category budget at the stable 16-worker level.
SCRAPING_CATEGORY_WORKERS = 16
