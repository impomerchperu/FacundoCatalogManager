import json

import pytest

from tools.benchmark_category_workers import (
    TRIAL_WORKERS,
    _build_summary,
    _validate_profile_payload,
)


def _valid_payload(workers=12):
    return {
        "categories": 24,
        "category_workers": workers,
        "detail_workers": 24,
        "http_workers": 28,
        "jsf_http_concurrency": 8,
        "download_images": False,
        "thread_sessions": True,
        "discovery_seconds": 2.0,
        "profile_seconds": 10.0,
        "coverage": {
            "expected_category_occurrences": 522,
            "collected_category_occurrences": 522,
            "enriched_category_occurrences": 522,
            "matches_current_category_counts": True,
            "mismatched_categories": [],
        },
        "http": {
            "requests": 20,
            "category_requests": 10,
            "detail_requests": 10,
            "retries": 0,
            "errors": 0,
            "terminal_errors": 0,
            "category_total_seconds": 9.0,
            "latency_percentiles": {
                "category": {"p50": 0.2, "p95": 1.5, "p99": 2.0}
            },
            "semaphore_wait_seconds": 0.1,
        },
    }


def test_trial_order_has_three_repetitions_for_each_setting():
    assert TRIAL_WORKERS == (12, 8, 8, 12, 12, 8)
    assert TRIAL_WORKERS.count(8) == 3
    assert TRIAL_WORKERS.count(12) == 3


def test_valid_profile_payload_is_normalized(tmp_path):
    record = _validate_profile_payload(
        _valid_payload(8),
        trial_number=2,
        workers=8,
        report_path=tmp_path / "trial.json",
    )

    assert record["category_workers"] == 8
    assert record["profile_seconds"] == 10.0
    assert record["total_measured_seconds"] == 12.0
    assert record["terminal_errors"] == 0


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda p: p.update(categories=23), "categories"),
        (lambda p: p["coverage"].update(collected_category_occurrences=521), "collected_occurrences"),
        (lambda p: p["http"].update(terminal_errors=1), "no_terminal_http_errors"),
        (lambda p: p.update(download_images=True), "fixed_configuration"),
        (lambda p: p.update(category_workers=16), "category_workers"),
    ],
)
def test_invalid_profile_payload_is_rejected(tmp_path, mutation, message):
    payload = _valid_payload()
    mutation(payload)

    with pytest.raises(RuntimeError, match=message):
        _validate_profile_payload(
            payload,
            trial_number=1,
            workers=12,
            report_path=tmp_path / "trial.json",
        )


def test_summary_compares_medians_and_preserves_no_default_change(tmp_path):
    trials = []
    for index, seconds in enumerate((12.0, 8.0, 9.0), start=1):
        trials.append({
            "trial": index,
            "category_workers": 12,
            "profile_seconds": seconds,
            "total_measured_seconds": seconds + 2,
            "category_http_p50_seconds": 0.5,
            "category_http_p95_seconds": 1.5,
            "category_http_p99_seconds": 2.0,
            "http_requests": 10,
            "retries": 0,
            "errors": 0,
            "semaphore_wait_seconds": 0.1,
        })
    for index, seconds in enumerate((9.0, 7.0, 8.0), start=4):
        trials.append({
            "trial": index,
            "category_workers": 8,
            "profile_seconds": seconds,
            "total_measured_seconds": seconds + 2,
            "category_http_p50_seconds": 0.4,
            "category_http_p95_seconds": 1.2,
            "category_http_p99_seconds": 1.8,
            "http_requests": 9,
            "retries": 0,
            "errors": 0,
            "semaphore_wait_seconds": 0.1,
        })

    summary = _build_summary(
        {
            "integrity": "ok",
            "schema_version": 6,
            "counts": {
                "products": 518,
                "categories": 24,
                "product_categories": 522,
            },
        },
        trials,
        tmp_path,
    )

    assert summary["comparison"]["median_profile_seconds"] == {
        "workers_8": 8.0,
        "workers_12": 9.0,
    }
    assert round(summary["comparison"]["relative_improvement_8_vs_12_pct"], 2) == 11.11
    assert summary["protocol"]["default_category_workers_changed"] is False
    assert json.loads(json.dumps(summary))["baseline"]["category_occurrences"] == 522
