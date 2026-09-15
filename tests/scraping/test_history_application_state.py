from datetime import datetime, timezone
from types import SimpleNamespace

from gui.scraping_history_dialog import ScrapingHistoryDialog


def _history(history_id: int, status: str, applied_at=None):
    return SimpleNamespace(
        history_id=history_id,
        status=status,
        applied_at=applied_at,
    )


def test_latest_applied_history_uses_persisted_application_marker():
    applied_at = datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc)
    history = [
        _history(12, "SUCCESS"),
        _history(11, "SUCCESS", applied_at),
        _history(10, "ERROR"),
    ]

    assert ScrapingHistoryDialog._latest_applied_history_id(history) == 11


def test_latest_applied_history_ignores_error_records_without_marker():
    history = [
        _history(20, "ERROR"),
        _history(18, "ERROR"),
        _history(17, "SUCCESS"),
    ]

    assert ScrapingHistoryDialog._latest_applied_history_id(history) is None
