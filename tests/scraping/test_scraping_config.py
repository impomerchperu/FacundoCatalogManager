from config.scraping_config import (
    BASE_URL,
    DEFAULT_HEADERS,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    SCRAPING_CATEGORY_WORKERS,
    SCRAPING_HTTP_WORKERS,
    STORE_URL,
)


def test_scraping_configuration():
    assert BASE_URL.startswith("https://")
    assert STORE_URL.endswith("/tienda/")
    assert "User-Agent" in DEFAULT_HEADERS
    assert REQUEST_TIMEOUT > 0
    assert MAX_RETRIES > 0
    assert SCRAPING_CATEGORY_WORKERS == 16
    assert SCRAPING_HTTP_WORKERS == 20
    assert SCRAPING_HTTP_WORKERS >= SCRAPING_CATEGORY_WORKERS
