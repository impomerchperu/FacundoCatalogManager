import json
from pathlib import Path

import pytest

from tools import compare_catalog_codes


def test_load_result_reads_current_scraping_artifact(tmp_path: Path):
    path = tmp_path / "scraping_result.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "success": True,
                "coverage_complete": True,
                "codes": ["fb-001", "FB-002"],
            }
        ),
        encoding="utf-8",
    )

    result = compare_catalog_codes.load_result(path)

    assert result["schema_version"] == 2
    assert result["codes"] == ["fb-001", "FB-002"]


def test_compare_catalog_normalizes_codes_and_reports_differences():
    result = {"codes": [" fb-001 ", "fb-003"]}
    catalog = {
        "FB-001": (" fb-001 ", "Producto 1"),
        "FB-002": ("FB-002", "Producto 2"),
    }

    missing, new_codes = compare_catalog_codes.compare_catalog(result, catalog)

    assert missing == ["FB-002"]
    assert new_codes == ["FB-003"]


def test_incomplete_result_is_not_eligible_for_pruning(capsys):
    result = {
        "success": False,
        "coverage_complete": False,
        "codes": ["FB-001"],
        "scraped_at": "2026-09-19T00:00:00+00:00",
    }

    catalog = {"FB-001": ("FB-001", "Producto 1")}

    missing, new_codes = compare_catalog_codes.compare_catalog(result, catalog)

    assert missing == []
    assert new_codes == []

    captured = capsys.readouterr()
    assert captured.out == ""

    with pytest.raises(SystemExit) as error:
        compare_catalog_codes.load_result(
            Path("tests") / "does-not-exist-scraping-result.json"
        )
    missing_path = Path("tests") / "does-not-exist-scraping-result.json"
    assert str(error.value) == (
        f"No existe {missing_path}. Ejecute primero un scraping."
    )
