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

# Category listing requests use a separate budget. The source site became
# slower and started returning errors when category listing and detail
# enrichment both used 20 concurrent requests. Sixteen keeps a small safety
# margin while allowing one additional request batch slot over the previous
# fourteen-worker limit.
SCRAPING_CATEGORY_WORKERS = 16
