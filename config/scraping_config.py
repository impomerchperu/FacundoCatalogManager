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
# The previous 14-worker baseline was stable, but the timing data shows that
# the source site still has enough parallel capacity to test a higher budget.
SCRAPING_MAX_WORKERS = 20

# Category listing requests use the same concurrency budget as detail
# enrichment so both HTTP phases can use the available worker capacity.
SCRAPING_CATEGORY_WORKERS = 20
