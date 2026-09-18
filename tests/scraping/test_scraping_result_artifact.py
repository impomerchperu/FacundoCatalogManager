import json

from models.scraping.sync_result import SyncResult
from services.scraping import scraping_result_writer
from services.scraping.scraping_result_writer import ScrapingResultWriter


def test_scraping_result_artifact_has_single_result_contract(tmp_path, monkeypatch):
    result_path = tmp_path / "scraping_result.json"
    timing_path = tmp_path / "scraping_timing.log"
    monkeypatch.setattr(scraping_result_writer, "RESULT_PATH", result_path)
    monkeypatch.setattr(scraping_result_writer, "TIMING_LOG", timing_path)

    result = SyncResult()
    result.products_expected = 2
    result.products_found = 2
    result.products_unique = 2
    result.finish()

    ScrapingResultWriter().write(result, {"P002", "P001"})

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] >= 2
    assert payload["run_id"] == result.run_id
    assert payload["codes"] == ["P001", "P002"]
    assert payload["scraped_unique_products"] == 2
    assert "products_found" in payload
    assert "products_unique" in payload
    assert "coverage_complete" in payload
    assert "failures" in payload


def test_legacy_scraping_code_snapshot_is_removed() -> None:
    from pathlib import Path

    assert not Path("data/last_scraping_codes.json").exists()
