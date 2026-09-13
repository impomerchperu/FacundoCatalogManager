from config.scraping_config import (
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    SCRAPING_CATEGORY_WORKERS,
    SCRAPING_HTTP_WORKERS,
)


def test_scraping_configuration():
    assert REQUEST_TIMEOUT > 0
    assert MAX_RETRIES > 0
    assert SCRAPING_CATEGORY_WORKERS == 16
    assert SCRAPING_HTTP_WORKERS == 28
    assert SCRAPING_HTTP_WORKERS >= SCRAPING_CATEGORY_WORKERS
