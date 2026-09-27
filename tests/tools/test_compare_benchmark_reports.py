from __future__ import annotations

import json

import pytest

from tools.compare_benchmark_reports import (
    BenchmarkComparisonError,
    compare_benchmark_files,
    compare_benchmark_reports,
    main,
)


def _report(
    *,
    mode: str = "full",
    categories: int = 24,
    expected_occurrences: int = 523,
    found_occurrences: int = 523,
    pipeline_seconds: float = 100.0,
    http_requests: int = 337,
    http_terminal_errors: int = 0,
    detail_requests: int = 200,
) -> dict:
    return {
        "schema_version": 1,
        "mode": mode,
        "configuration": {
            "category_workers": 8,
            "detail_workers": 16,
            "http_workers": 28,
            "jsf_http_concurrency": 8,
            "jsf_page_workers": 2,
            "category_page_workers": 1,
            "thread_sessions": False,
        },
        "coverage": {
            "categories": categories,
            "expected_occurrences": expected_occurrences,
            "found_occurrences": found_occurrences,
        },
        "timing": {
            "pipeline_seconds": pipeline_seconds,
        },
        "http": {
            "http_requests": http_requests,
            "http_terminal_errors": http_terminal_errors,
        },
        "detail": {
            "detail_requests": detail_requests,
        },
    }


def test_compare_reports_preserves_configuration_and_calculates_deltas():
    baseline = _report(pipeline_seconds=100.0, http_requests=300)
    candidate = _report(pipeline_seconds=92.5, http_requests=310)
    candidate["configuration"]["detail_workers"] = 24

    comparison = compare_benchmark_reports(baseline, candidate)

    assert comparison["configuration"]["baseline"]["detail_workers"] == 16
    assert comparison["configuration"]["candidate"]["detail_workers"] == 24
    assert comparison["timing"]["pipeline_seconds"] == {
        "baseline": 100.0,
        "candidate": 92.5,
        "delta": -7.5,
        "relative_percent": -7.5,
    }
    assert comparison["http"]["http_requests"]["delta"] == 10


def test_compare_reports_rejects_incomplete_coverage():
    with pytest.raises(BenchmarkComparisonError, match="cobertura incompleta"):
        compare_benchmark_reports(
            _report(found_occurrences=522),
            _report(),
        )


def test_compare_reports_rejects_negative_coverage_counts():
    report = _report(expected_occurrences=-1, found_occurrences=-1)

    with pytest.raises(BenchmarkComparisonError, match="cobertura negativas"):
        compare_benchmark_reports(report, _report())


def test_compare_reports_rejects_nonzero_coverage_gap():
    report = _report()
    report["coverage"]["coverage_gap"] = 1

    with pytest.raises(BenchmarkComparisonError, match="coverage_gap=1"):
        compare_benchmark_reports(report, _report())


def test_compare_reports_rejects_noncomplete_coverage_flag():
    report = _report()
    report["coverage"]["coverage_complete"] = False

    with pytest.raises(
        BenchmarkComparisonError,
        match="coverage_complete=True",
    ):
        compare_benchmark_reports(report, _report())


def test_compare_reports_rejects_negative_coverage_gap():
    report = _report()
    report["coverage"]["coverage_gap"] = -1

    with pytest.raises(BenchmarkComparisonError, match="coverage_gap.*negativo"):
        compare_benchmark_reports(report, _report())


def test_compare_reports_rejects_coverage_errors():
    report = _report()
    report["coverage"]["error_count"] = 1

    with pytest.raises(BenchmarkComparisonError, match="error_count=1"):
        compare_benchmark_reports(report, _report())


def test_compare_reports_rejects_negative_error_count():
    report = _report()
    report["coverage"]["error_count"] = -1

    with pytest.raises(BenchmarkComparisonError, match="error_count.*negativo"):
        compare_benchmark_reports(report, _report())


def test_compare_reports_rejects_terminal_http_errors():
    report = _report(http_terminal_errors=2)

    with pytest.raises(
        BenchmarkComparisonError,
        match="http_terminal_errors=2",
    ):
        compare_benchmark_reports(report, _report())


def test_compare_reports_rejects_negative_terminal_http_errors():
    report = _report(http_terminal_errors=-1)

    with pytest.raises(
        BenchmarkComparisonError,
        match="http_terminal_errors.*negativo",
    ):
        compare_benchmark_reports(report, _report())


def test_compare_reports_rejects_different_modes():
    with pytest.raises(BenchmarkComparisonError, match="mismo modo"):
        compare_benchmark_reports(
            _report(mode="full"),
            _report(mode="collection_only"),
        )


def test_compare_reports_rejects_different_structural_coverage():
    with pytest.raises(
        BenchmarkComparisonError,
        match="cobertura estructural",
    ):
        compare_benchmark_reports(
            _report(expected_occurrences=523),
            _report(expected_occurrences=522, found_occurrences=522),
        )


def test_compare_files_loads_json_artifacts(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    baseline_path.write_text(
        json.dumps(_report(pipeline_seconds=100.0)),
        encoding="utf-8",
    )
    candidate_path.write_text(
        json.dumps(_report(pipeline_seconds=95.0)),
        encoding="utf-8",
    )

    comparison = compare_benchmark_files(baseline_path, candidate_path)

    assert comparison["timing"]["pipeline_seconds"]["delta"] == -5.0


def test_compare_files_rejects_unsupported_schema(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    baseline_path.write_text(
        json.dumps({**_report(), "schema_version": 2}),
        encoding="utf-8",
    )
    candidate_path.write_text(
        json.dumps(_report()),
        encoding="utf-8",
    )

    with pytest.raises(BenchmarkComparisonError, match="schema_version"):
        compare_benchmark_files(baseline_path, candidate_path)


def test_cli_returns_nonzero_for_incomparable_reports(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    baseline_path.write_text(
        json.dumps(_report(mode="full")),
        encoding="utf-8",
    )
    candidate_path.write_text(
        json.dumps(_report(mode="collection_only")),
        encoding="utf-8",
    )

    assert main([str(baseline_path), str(candidate_path)]) == 2


def test_cli_prints_comparison_for_valid_reports(tmp_path, capsys):
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    baseline_path.write_text(
        json.dumps(_report(pipeline_seconds=100.0)),
        encoding="utf-8",
    )
    candidate_path.write_text(
        json.dumps(_report(pipeline_seconds=90.0)),
        encoding="utf-8",
    )

    assert main([str(baseline_path), str(candidate_path)]) == 0
    output = capsys.readouterr().out
    assert "BENCHMARK COMPARISON" in output
    assert "timing.pipeline_seconds" in output
    assert "delta=-10" in output
