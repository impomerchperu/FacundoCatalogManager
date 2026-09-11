import json

import requests

from scrapers.collectors import category_pagination_patch, jsf_request_recovery_patch
from scrapers.collectors.category_scraper import CategoryScraper


def test_jsf_page_request_timeout_is_retried():
    scraper = CategoryScraper(browser=object())
    calls = 0

    def post(_payload):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise requests.exceptions.ReadTimeout("timed out")
        return json.dumps(
            {
                "found_posts": 25,
                "max_num_pages": 1,
                "rendered_content": "<article>FB-1000-AZ</article>",
            }
        )

    scraper._post_jsf = post

    assert (
        category_pagination_patch._retry_jsf_page
        is jsf_request_recovery_patch._retry_jsf_page
    )

    result = category_pagination_patch._retry_jsf_page(
        scraper,
        "https://stock.importacionesfacundo.com/categoria-producto/test/",
        123,
        2,
    )

    assert calls == 2
    assert result == (
        25,
        1,
        "<article>FB-1000-AZ</article>",
    )


def test_jsf_page_request_timeout_is_raised_after_retries():
    scraper = CategoryScraper(browser=object())
    calls = 0

    def post(_payload):
        nonlocal calls
        calls += 1
        raise requests.exceptions.ReadTimeout("timed out")

    scraper._post_jsf = post

    try:
        category_pagination_patch._retry_jsf_page(
            scraper,
            "https://stock.importacionesfacundo.com/categoria-producto/test/",
            123,
            2,
        )
    except requests.exceptions.ReadTimeout:
        pass
    else:
        raise AssertionError("Expected the final JSF timeout to be raised")

    assert calls == category_pagination_patch.JSF_PAGE_RETRIES
