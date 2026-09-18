from types import SimpleNamespace

from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QApplication, QTableWidgetItem

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


def test_history_columns_use_content_width_without_horizontal_scroll():
    _qapp()
    dialog = ScrapingHistoryDialog()
    header = dialog.table.horizontalHeader()

    assert (
        dialog.table.horizontalScrollBarPolicy()
        .name
        == "ScrollBarAlwaysOff"
    )
    assert dialog.table.textElideMode().name == "ElideNone"
    assert "padding-left: 4px" in dialog.table.styleSheet()
    assert "padding-right: 4px" in dialog.table.styleSheet()

    for column in range(dialog.table.columnCount()):
        assert (
            header.sectionResizeMode(column).name
            == "Interactive"
        )

    dialog.close()


def test_history_columns_include_content_plus_minimum_side_padding():
    _qapp()
    dialog = ScrapingHistoryDialog()
    long_text = "Texto suficientemente largo para comprobar que no se recorta"

    dialog.table.setRowCount(1)
    dialog.table.setItem(0, 5, QTableWidgetItem(long_text))
    dialog._fit_table_to_content()

    header = dialog.table.horizontalHeader()
    text_width = QFontMetrics(dialog.table.font()).horizontalAdvance(long_text)

    assert header.sectionSize(5) >= (
        text_width + (2 * ScrapingHistoryDialog.CONTENT_SIDE_PADDING)
    )
    assert dialog.table.textElideMode().name == "ElideNone"

    dialog.close()


def test_history_columns_expand_when_window_is_wider():
    _qapp()
    dialog = ScrapingHistoryDialog()
    dialog.show()
    dialog.table.setRowCount(1)
    for column in range(dialog.table.columnCount()):
        dialog.table.setItem(
            0,
            column,
            QTableWidgetItem("Contenido"),
        )

    dialog._fit_table_to_content()
    header = dialog.table.horizontalHeader()
    initial_width = sum(
        header.sectionSize(column)
        for column in range(dialog.table.columnCount())
    )

    dialog.resize(dialog.width() + 400, dialog.height())
    dialog._fit_table_to_content(expand_window=False)

    expanded_width = sum(
        header.sectionSize(column)
        for column in range(dialog.table.columnCount())
    )

    assert expanded_width > initial_width

    dialog.close()


def test_history_window_expands_to_fit_content_with_side_padding():
    _qapp()
    dialog = ScrapingHistoryDialog()
    dialog.table.setRowCount(1)
    dialog.table.setItem(
        0,
        5,
        QTableWidgetItem(
            "Texto suficientemente largo para comprobar que la ventana se adapte",
        ),
    )

    dialog._fit_table_to_content()

    header = dialog.table.horizontalHeader()
    margins = dialog.layout().contentsMargins()
    expected_minimum = (
        header.length()
        + (2 * dialog.table.frameWidth())
        + margins.left()
        + margins.right()
    )

    assert header.sectionSize(5) >= 8
    assert dialog.minimumWidth() >= expected_minimum
    assert dialog.width() >= dialog.minimumWidth()

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
