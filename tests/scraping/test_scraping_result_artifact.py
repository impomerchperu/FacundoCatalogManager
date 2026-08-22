import json
from pathlib import Path


def test_scraping_result_artifact_has_single_result_contract() -> None:
    path = Path("data/scraping_result.json")
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] >= 2
    assert "run_id" in payload
    assert "codes" in payload
    assert "products_found" in payload
    assert "products_unique" in payload
    assert "coverage_complete" in payload
    assert "failures" in payload


def test_legacy_scraping_code_snapshot_is_removed() -> None:
    assert not Path("data/last_scraping_codes.json").exists()
