from datetime import datetime, timezone
from types import SimpleNamespace

from gui.scraping_history_dialog import ScrapingHistoryDialog


def _history(history_id: int, status: str, applied_at=None, finished_at=None):
    return SimpleNamespace(
        history_id=history_id,
        status=status,
        applied_at=applied_at,
        finished_at=finished_at or applied_at,
    )


def test_status_displays_applied_with_application_datetime():
    applied_at = datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc)
    record = _history(11, "SUCCESS", applied_at=applied_at)

    dialog = ScrapingHistoryDialog.__new__(ScrapingHistoryDialog)
    dialog.table = SimpleNamespace(setItem=lambda *args: None)
    captured = {}

    class Item:
        def __init__(self, text):
            captured["text"] = text

        def setTextAlignment(self, *args): pass
        def setToolTip(self, *args): pass
        def setFont(self, *args): pass

    import gui.scraping_history_dialog as module
    original = module.QTableWidgetItem
    module.QTableWidgetItem = Item
    try:
        dialog._set_status_item(0, 10, record)
    finally:
        module.QTableWidgetItem = original

    assert "APLICADO" in captured["text"]
    assert ScrapingHistoryDialog._format_datetime(applied_at) in captured["text"]


def test_status_displays_error_for_failed_history():
    record = _history(
        20,
        "ERROR",
        finished_at=datetime(2026, 9, 12, 11, 0, tzinfo=timezone.utc),
    )

    dialog = ScrapingHistoryDialog.__new__(ScrapingHistoryDialog)
    dialog.table = SimpleNamespace(setItem=lambda *args: None)
    captured = {}

    class Item:
        def __init__(self, text):
            captured["text"] = text

        def setTextAlignment(self, *args): pass
        def setToolTip(self, *args): pass
        def setFont(self, *args): pass

    import gui.scraping_history_dialog as module
    original = module.QTableWidgetItem
    module.QTableWidgetItem = Item
    try:
        dialog._set_status_item(0, 10, record)
    finally:
        module.QTableWidgetItem = original

    assert captured["text"] == "ERROR"


def test_history_detail_button_uses_last_visible_column():
    from PySide6.QtWidgets import QApplication, QTableWidget

    app = QApplication.instance() or QApplication([])
    table = QTableWidget(1, 12)
    dialog = SimpleNamespace(table=table, show_row_details=lambda: None)

    ScrapingHistoryDialog._set_detail_button(dialog, 0, 42)
    app.processEvents()

    assert table.cellWidget(0, 11) is not None
