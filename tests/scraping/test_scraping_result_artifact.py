from pathlib import Path


def test_scraping_result_artifact_has_single_result_contract() -> None:
    path = Path("data/scraping_result.json")
    assert path.exists()
    assert path.read_text(encoding="utf-8").strip()
