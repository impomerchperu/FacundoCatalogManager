from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from gui.scraping_history_dialog import ScrapingHistoryDialog


def _qapp():
    return QApplication.instance() or QApplication([])


def _history(history_id: int, status: str):
    return SimpleNamespace(
        history_id=history_id,
        status=status,
        finished_at="2026-09-17T21:10:05+00:00",
        applied_at="2026-09-17T21:15:05+00:00",
    )


def test_status_text_shows_only_applied_for_successful_scraping():
    assert ScrapingHistoryDialog._status_text(_history(11, "SUCCESS")) == "APLICADO"


def test_status_text_shows_only_error_for_failed_scraping():
    assert ScrapingHistoryDialog._status_text(_history(20, "ERROR")) == "ERROR"


def test_history_table_has_expected_columns_after_layout_cleanup():
    _qapp()
    dialog = ScrapingHistoryDialog()

    headers = [
        dialog.table.horizontalHeaderItem(column).text()
        for column in range(dialog.table.columnCount())
    ]

    assert dialog.table.columnCount() == 10
    assert headers == [
        "ID",
        "Fecha de descarga",
        "Duración",
        "Procesados",
        "Nuevos",
        "Actualizados",
        "Sin cambios",
        "Eliminados",
        "Estado",
        "Detalle",
    ]

    dialog.close()


def test_history_columns_use_responsive_resize_modes_without_horizontal_scroll():
    _qapp()
    dialog = ScrapingHistoryDialog()
    header = dialog.table.horizontalHeader()

    assert (
        dialog.table.horizontalScrollBarPolicy()
        .name
        == "ScrollBarAlwaysOff"
    )

    for column in (0, 1, 2, 8, 9):
        assert (
            header.sectionResizeMode(column).name
            == "ResizeToContents"
        )

    for column in (3, 4, 5, 6, 7):
        assert (
            header.sectionResizeMode(column).name
            == "Stretch"
        )

    dialog.close()


def test_history_dialog_centers_on_parent_when_shown():
    _qapp()
    parent = dialog = None
    try:
        from PySide6.QtWidgets import QWidget

        parent = QWidget()
        parent.resize(1200, 700)
        parent.show()

        dialog = ScrapingHistoryDialog(parent)
        dialog.show()
        dialog._center_on_parent()

        assert dialog.frameGeometry().center() == parent.frameGeometry().center()
    finally:
        if dialog is not None:
            dialog.close()
        if parent is not None:
            parent.close()
