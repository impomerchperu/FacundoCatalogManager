from config.scraping_config import (
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    SCRAPING_CATEGORY_WORKERS,
    SCRAPING_HTTP_WORKERS,
    STORE_URL,
)
from services.scraping.scraping_config import ScrapingConfig


def test_scraping_configuration():
    assert REQUEST_TIMEOUT > 0
    assert MAX_RETRIES > 0
    assert SCRAPING_CATEGORY_WORKERS == 16
    assert SCRAPING_HTTP_WORKERS == 28
    assert SCRAPING_HTTP_WORKERS >= SCRAPING_CATEGORY_WORKERS


def test_high_level_config_uses_canonical_transport_defaults():
    config = ScrapingConfig()

    assert config.catalog_url == STORE_URL
    assert config.request_timeout == REQUEST_TIMEOUT
    assert config.max_retries == MAX_RETRIES
