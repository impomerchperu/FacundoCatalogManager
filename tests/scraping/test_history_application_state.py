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
    assert text.endswith(
        applied_at.astimezone().strftime("%d/%m/%Y %H:%M:%S"),
    )


def test_status_text_falls_back_to_finished_datetime_for_success_without_applied_marker():
    finished_at = datetime(2026, 9, 17, 21, 10, 5, tzinfo=timezone.utc)

    text = ScrapingHistoryDialog._status_text(
        _history(12, "SUCCESS", finished_at=finished_at),
    )

    assert text == (
        "APLICADO\n"
        + finished_at.astimezone().strftime("%d/%m/%Y %H:%M:%S")
    )


def test_status_text_shows_only_error_for_failed_scraping():
    assert ScrapingHistoryDialog._status_text(_history(20, "ERROR")) == "ERROR"


def test_history_table_has_expected_columns_after_layout_cleanup():
    _qapp()
    dialog = ScrapingHistoryDialog()

    headers = [
        dialog.table.horizontalHeaderItem(column).text()
        for column in range(dialog.table.columnCount())
    ]

    assert dialog.table.columnCount() == 9
    assert headers == [
        "ID",
        "Fecha y duración",
        "Procesados",
        "Nuevos",
        "Actualizados",
        "Sin cambios",
        "Eliminados",
        "Estado",
        "Detalle",
    ]

    dialog.close()


def test_history_dialog_fit_keeps_table_columns_within_window_width():
    _qapp()
    dialog = ScrapingHistoryDialog()
    dialog._fit_window_to_table()

    layout = dialog.layout()
    assert layout is not None
    margins = layout.contentsMargins()
    required = (
        dialog.table.horizontalHeader().length()
        + dialog.table.frameWidth() * 2
        + margins.left()
        + margins.right()
    )
    assert dialog.width() >= required

    dialog.close()
