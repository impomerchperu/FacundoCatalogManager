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
# Empirical measurements on the source site show better throughput at 14
# workers than at 8, without increasing the request count or retry rate.
SCRAPING_MAX_WORKERS = 14

# Category listing requests can use the same concurrency budget as detail
# enrichment. Keeping both limits aligned avoids leaving HTTP capacity idle
# during the initial listing phase, which otherwise makes the UI appear stuck.
SCRAPING_CATEGORY_WORKERS = 14
