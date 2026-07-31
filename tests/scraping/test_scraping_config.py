from config.scraping_config import (
    BASE_URL,
    STORE_URL,
    DEFAULT_HEADERS,
    REQUEST_TIMEOUT,
    MAX_RETRIES
)


def test_scraping_configuration():

    assert BASE_URL.startswith(
        "https://"
    )

    assert STORE_URL.endswith(
        "/tienda/"
    )

    assert "User-Agent" in DEFAULT_HEADERS

    assert REQUEST_TIMEOUT > 0

    assert MAX_RETRIES > 0