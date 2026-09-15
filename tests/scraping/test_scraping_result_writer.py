import json

from models.scraping.sync_result import SyncResult
from services.scraping import scraping_result_writer
from services.scraping.scraping_result_writer import ScrapingResultWriter


def test_result_writer_keeps_codes_and_run_id_together(tmp_path, monkeypatch):
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
    timing = timing_path.read_text(encoding="utf-8")

    assert payload["run_id"] == result.run_id
    assert payload["codes"] == ["P001", "P002"]
    assert payload["scraped_unique_products"] == 2
    assert f"run_id={result.run_id}" in timing


def test_result_writer_replaces_previous_result_atomically(tmp_path, monkeypatch):
    result_path = tmp_path / "scraping_result.json"
    timing_path = tmp_path / "scraping_timing.log"
    monkeypatch.setattr(scraping_result_writer, "RESULT_PATH", result_path)
    monkeypatch.setattr(scraping_result_writer, "TIMING_LOG", timing_path)

    writer = ScrapingResultWriter()
    first = SyncResult()
    first.finish()
    writer.write(first, {"OLD"})

    second = SyncResult()
    second.finish()
    writer.write(second, {"NEW"})

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == second.run_id
    assert payload["codes"] == ["NEW"]
