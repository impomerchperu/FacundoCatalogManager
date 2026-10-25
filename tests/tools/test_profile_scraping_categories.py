from tools.profile_scraping_categories import (
    _build_coverage_payload,
    _build_http_payload,
    _build_source_page_cache_payload,
    _enable_thread_sessions,
    _profile_category_workers,
    _resolve_output_path,
)


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


class _FakeBrowser:
    def __init__(self) -> None:
        self.enabled = False

    def enable_thread_sessions(self) -> None:
        self.enabled = True


class _FakeBrowserWithoutThreadSessions:
    pass


def test_profile_enables_thread_sessions_when_available():
    browser = _FakeBrowser()

    assert _enable_thread_sessions(browser) is True
    assert browser.enabled is True


def test_profile_detects_missing_thread_sessions_support():
    browser = _FakeBrowserWithoutThreadSessions()

    assert _enable_thread_sessions(browser) is False


def test_profile_category_workers_reads_positive_override(monkeypatch):
    monkeypatch.setenv("FCM_PROFILE_CATEGORY_WORKERS", "12")

    assert _profile_category_workers() == 12


def test_profile_category_workers_defaults_to_none(monkeypatch):
    monkeypatch.delenv("FCM_PROFILE_CATEGORY_WORKERS", raising=False)

    assert _profile_category_workers() is None


def test_build_http_payload_preserves_latency_percentiles():
    payload = _build_http_payload(
        {
            "http_latency_percentiles": {
                "category": {"p50": 0.2, "p95": 1.5, "p99": 2.0},
                "detail": {"p50": 0.4, "p95": 2.5, "p99": 4.0},
            }
        }
    )

    assert payload["latency_percentiles"]["category"] == {
        "p50": 0.2,
        "p95": 1.5,
        "p99": 2.0,
    }
    assert payload["latency_percentiles"]["detail"] == {
        "p50": 0.4,
        "p95": 2.5,
        "p99": 4.0,
    }
    assert payload["latency_percentiles"]["jsf"] == {
        "p50": 0.0,
        "p95": 0.0,
        "p99": 0.0,
    }


def test_build_source_page_cache_payload_reports_fresh_hit_rate():
    payload = _build_source_page_cache_payload(
        {
            "fresh_hits": 3,
            "network_validations": 7,
            "not_modified_304": 4,
            "updated_200": 3,
            "stale_fallbacks": 1,
            "request_errors": 1,
        }
    )

    assert payload["fresh_hits"] == 3
    assert payload["network_validations"] == 7
    assert payload["not_modified_304"] == 4
    assert payload["updated_200"] == 3
    assert payload["stale_fallbacks"] == 1
    assert payload["request_errors"] == 1
    assert payload["fresh_hit_rate"] == 0.3


def test_build_source_page_cache_payload_has_no_rate_without_observations():
    payload = _build_source_page_cache_payload({})

    assert payload["fresh_hit_rate"] is None


def test_build_coverage_payload_reports_complete_current_category_counts():
    payload = _build_coverage_payload(
        [
            {"category": "A", "expected": 2, "collected": 2, "enriched": 2},
            {"category": "B", "expected": 3, "collected": 3, "enriched": 3},
        ]
    )

    assert payload == {
        "expected_category_occurrences": 5,
        "collected_category_occurrences": 5,
        "enriched_category_occurrences": 5,
        "collected_minus_expected": 0,
        "enriched_minus_collected": 0,
        "matches_current_category_counts": True,
        "mismatched_categories": [],
    }


def test_build_coverage_payload_identifies_category_level_mismatch():
    payload = _build_coverage_payload(
        [
            {"category": "A", "expected": 2, "collected": 1, "enriched": 1},
            {"category": "B", "expected": 3, "collected": 3, "enriched": 2},
        ]
    )

    assert payload["matches_current_category_counts"] is False
    assert payload["collected_minus_expected"] == -1
    assert payload["enriched_minus_collected"] == -1
    assert payload["mismatched_categories"] == [
        {"category": "A", "expected": 2, "collected": 1, "enriched": 1},
        {"category": "B", "expected": 3, "collected": 3, "enriched": 2},
    ]



def test_resolve_output_path_defaults_to_repository_profile(monkeypatch):
    from tools.profile_scraping_categories import DEFAULT_OUTPUT_PATH

    monkeypatch.delenv("FCM_PROFILE_OUTPUT_PATH", raising=False)

    assert _resolve_output_path() == DEFAULT_OUTPUT_PATH


def test_resolve_output_path_accepts_absolute_per_run_report(monkeypatch, tmp_path):
    output = tmp_path / "trial-12.json"
    monkeypatch.setenv("FCM_PROFILE_OUTPUT_PATH", str(output))

    assert _resolve_output_path() == output


def test_resolve_output_path_anchors_relative_path_to_project(monkeypatch):
    from tools.profile_scraping_categories import PROJECT_ROOT

    monkeypatch.setenv("FCM_PROFILE_OUTPUT_PATH", "temp/profile.json")

    assert _resolve_output_path() == PROJECT_ROOT / "temp" / "profile.json"
