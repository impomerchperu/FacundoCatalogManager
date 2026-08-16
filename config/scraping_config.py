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

# Number of categories scraped concurrently. Eight workers better utilize
# the existing HTTP concurrency while keeping category pressure bounded.
SCRAPING_CATEGORY_WORKERS = 8
