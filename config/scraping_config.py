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

# Detail workers may prepare several categories concurrently, but Browser
# applies a shared HTTP semaphore so category and detail traffic never exceed
# the stable server-facing concurrency budget.
SCRAPING_MAX_WORKERS = 20

# Measurements show that 20 category workers add contention without improving
# end-to-end runtime. Keep the stable category budget at 16 workers; Browser
# also uses this value as the global HTTP concurrency ceiling.
SCRAPING_CATEGORY_WORKERS = 16
