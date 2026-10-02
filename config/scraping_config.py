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


REQUEST_TIMEOUT = 20

MAX_RETRIES = 3

# Use lxml for the large number of HTML parses performed during catalog
# extraction. category_scraper.py keeps a html.parser fallback for portability.
SCRAPING_HTML_PARSER = "lxml"

# Detail enrichment is I/O-bound. Controlled live benchmarks with crossed
# 16/24-worker runs repeatedly preserved complete coverage and zero errors;
# 24 workers reduced end-to-end wall time in both final comparison pairs.
# Production uses the validated 24-worker setting.
SCRAPING_MAX_WORKERS = 24

# Controlled live FULL image benchmarks with balanced run order completed all
# eight 8/12-worker runs with complete coverage and zero retries/errors.
# 12 workers was faster than 8 in all four paired comparisons, with a
# four-run average pipeline reduction of 12.1%. Use 12 as the current
# validated production candidate while main remains unchanged.
SCRAPING_CATEGORY_WORKERS = 12

# Category pages are fetched sequentially by default. This remains the
# production-safe value until an isolated live benchmark justifies overlap.
SCRAPING_CATEGORY_PAGE_WORKERS = 1

# Keep the shared HTTP budget at the validated live FULL baseline:
# 24 categories, 523 occurrences, 519 unique products, 4 multi-category
# products, 523 product-category relationships, complete coverage, and
# zero invalidating errors. Increasing this budget did not improve wall time.
SCRAPING_HTTP_WORKERS = 28

# JetSmartFilters/Bricks Query Loop request metadata observed on the live catalog.
# Keep these values centralized so the scraper can reproduce the provider query
# without hard-coding them inside the pagination implementation.
JETSMARTFILTERS_AJAX_URL = f"{BASE_URL}/wp-admin/admin-ajax.php"
JETSMARTFILTERS_ELEMENT_ID = "95dc8a"
JETSMARTFILTERS_SIGNATURE = "83bc155b208a7b2c473d90a84cf5fe01"
JETSMARTFILTERS_INDEXING_FILTERS = "434"

# The canonical pagination engine uses bounded page parallelism. Keep the JSF
# HTTP semaphore independently capped so pagination cannot consume the entire
# shared HTTP worker budget.
SCRAPING_JSF_HTTP_CONCURRENCY = 8

# JSF page requests per category worker. Controlled live repetitions with
# JSF HTTP concurrency fixed at 8 did not show a reproducible wall-clock
# benefit from increasing this value; keep the validated production default.
SCRAPING_JSF_PAGE_WORKERS = 2

# Image synchronization is I/O-bound; keep its worker pool separate from
# the shared catalog HTTP budget.
SCRAPING_IMAGE_WORKERS = 8
