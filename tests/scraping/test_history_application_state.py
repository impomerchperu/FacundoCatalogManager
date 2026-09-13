from types import SimpleNamespace

from gui.scraping_history_dialog import ScrapingHistoryDialog


def _history(history_id: int, status: str):
    return SimpleNamespace(history_id=history_id, status=status)


def test_latest_successful_history_is_the_currently_applied_version():
    history = [
        _history(12, "SUCCESS"),
        _history(11, "SUCCESS"),
        _history(10, "ERROR"),
    ]

    assert ScrapingHistoryDialog._latest_applied_history_id(history) == 12


def test_latest_applied_history_ignores_error_records():
    history = [
        _history(20, "ERROR"),
        _history(18, "ERROR"),
    ]

    assert ScrapingHistoryDialog._latest_applied_history_id(history) is None
