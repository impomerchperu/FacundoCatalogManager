from __future__ import annotations

import json

from tools.benchmark_report import write_benchmark_report


def test_write_benchmark_report_creates_nested_json_file(tmp_path):
    output_path = tmp_path / "reports" / "run.json"
    payload = {
        "schema_version": 1,
        "mode": "full",
        "coverage": {"categories": 24, "occurrences": 523},
    }

    result = write_benchmark_report(output_path, payload)

    assert result == output_path
    assert json.loads(output_path.read_text(encoding="utf-8")) == payload


def test_write_benchmark_report_replaces_existing_artifact(tmp_path):
    output_path = tmp_path / "run.json"
    output_path.write_text('{"old": true}\n', encoding="utf-8")

    write_benchmark_report(
        output_path,
        {"schema_version": 1, "mode": "collection_only"},
    )

    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "mode": "collection_only",
    }


def test_write_benchmark_report_ignores_missing_output_path(tmp_path):
    assert write_benchmark_report(None, {"schema_version": 1}) is None
    assert list(tmp_path.iterdir()) == []
