from datetime import datetime, timezone
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from gui.scraping_history_dialog import ScrapingHistoryDialog


def _qapp():
    return QApplication.instance() or QApplication([])


def _history(
    history_id: int,
    status: str,
    *,
    finished_at: datetime | None = None,
    applied_at: datetime | None = None,
):
    return SimpleNamespace(
        history_id=history_id,
        status=status,
        finished_at=finished_at
        or datetime(2026, 9, 17, 18, 30, tzinfo=timezone.utc),
        applied_at=applied_at,
    )


def test_status_text_shows_applied_with_application_datetime():
    applied_at = datetime(2026, 9, 17, 20, 45, 12, tzinfo=timezone.utc)

    text = ScrapingHistoryDialog._status_text(
        _history(11, "SUCCESS", applied_at=applied_at),
    )

    assert text.startswith("APLICADO\n")
    assert "2026" not in text
    assert text.endswith(applied_at.astimezone().strftime("%d/%m/%Y %H:%M:%S"))


def test_status_text_falls_back_to_finished_datetime_for_success_without_applied_marker():
    finished_at = datetime(2026, 9, 17, 21, 10, 5, tzinfo=timezone.utc)

    text = ScrapingHistoryDialog._status_text(
        _history(12, "SUCCESS", finished_at=finished_at),
    )

    assert text.endswith(
        finished_at.astimezone().strftime("%d/%m/%Y %H:%M:%S"),
    )


def test_status_text_shows_only_error_for_failed_scraping():
    text = ScrapingHistoryDialog._status_text(_history(20, "ERROR"))

    assert text == "ERROR"


def test_history_table_has_no_application_column_and_fits_columns():
    _qapp()
    dialog = ScrapingHistoryDialog()

    assert dialog.table.columnCount() == 12
    headers = [
        dialog.table.horizontalHeaderItem(column).text()
        for column in range(dialog.table.columnCount())
    ]
    assert "Aplicación" not in headers
    assert headers[10] == "Estado"
    assert headers[11] == "Detalle"

    dialog._fit_window_to_table()
    assert dialog.width() >= (
        dialog.table.horizontalHeader().length()
        + dialog.layout().contentsMargins().left()
        + dialog.layout().contentsMargins().right()
    )

    dialog.close()
