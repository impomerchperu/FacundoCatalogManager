from services.scraping.scraping_config import ScrapingConfig


def test_scraping_config_rejects_non_positive_http_settings():
    try:
        ScrapingConfig(request_timeout=0)
    except ValueError:
        pass
    else:
        raise AssertionError("request_timeout debe ser mayor que cero")

    try:
        ScrapingConfig(max_retries=0)
    except ValueError:
        pass
    else:
        raise AssertionError("max_retries debe ser mayor que cero")


def test_scraping_config_accepts_custom_http_settings():
    config = ScrapingConfig(request_timeout=7, max_retries=4)

    assert config.request_timeout == 7
    assert config.max_retries == 4
