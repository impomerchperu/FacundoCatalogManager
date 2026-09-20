from tools.profile_scraping_categories import _build_http_payload


def test_build_http_payload_preserves_semaphore_metrics_by_request_class():
    payload = _build_http_payload(
        {
            "category_http_requests": 2,
            "jsf_http_requests": 3,
            "detail_http_requests": 5,
            "other_http_requests": 0,
            "category_http_total_seconds": 4.0,
            "jsf_http_total_seconds": 6.0,
            "detail_http_total_seconds": 10.0,
            "other_http_total_seconds": 0.0,
            "category_http_max_seconds": 3.0,
            "jsf_http_max_seconds": 4.0,
            "detail_http_max_seconds": 5.0,
            "other_http_max_seconds": 0.0,
            "category_semaphore_wait_seconds": 1.25,
            "jsf_semaphore_wait_seconds": 2.5,
            "detail_semaphore_wait_seconds": 3.75,
            "other_semaphore_wait_seconds": 0.5,
            "category_semaphore_max_wait_seconds": 0.75,
            "jsf_semaphore_max_wait_seconds": 1.5,
            "detail_semaphore_max_wait_seconds": 2.25,
            "other_semaphore_max_wait_seconds": 0.25,
            "category_semaphore_wait_count": 2,
            "jsf_semaphore_wait_count": 3,
            "detail_semaphore_wait_count": 5,
            "other_semaphore_wait_count": 1,
        }
    )

    assert payload["semaphore_wait_seconds"] == 8.0
    assert payload["semaphore_max_wait_seconds"] == 2.25
    assert payload["semaphore_wait_count"] == 11
    assert payload["semaphore_wait_seconds_by_class"] == {
        "category": 1.25,
        "jsf": 2.5,
        "detail": 3.75,
        "other": 0.5,
    }
    assert payload["semaphore_max_wait_seconds_by_class"] == {
        "category": 0.75,
        "jsf": 1.5,
        "detail": 2.25,
        "other": 0.25,
    }
    assert payload["semaphore_wait_count_by_class"] == {
        "category": 2,
        "jsf": 3,
        "detail": 5,
        "other": 1,
    }
