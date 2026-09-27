from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from gui.scraping_history_dialog import ScrapingHistoryDialog


def test_history_keeps_unrelated_product_changes_as_separate_rows():
    changes = [
        {
            "type": "UPDATED",
            "code": "ABC-001",
            "name": "Producto de prueba",
            "field": "price",
            "label": "Precio",
            "old": 10,
            "new": 12,
        },
        {
            "type": "UPDATED",
            "code": "ABC-001",
            "name": "Producto de prueba",
            "field": "stock",
            "label": "Stock",
            "old": 20,
            "new": 18,
        },
    ]

    rows = ScrapingHistoryDialog._prepare_change_rows(changes)

    assert len(rows) == 2
    assert rows[0]["code"] == "ABC-001"
    assert rows[0]["variation"] == "Stock"
    assert rows[0]["old"] == "20"
    assert rows[0]["new"] == "18 (-2)"
    assert rows[1]["variation"] == "Precio"
    assert rows[1]["old"] == "10"
    assert rows[1]["new"] == "12"


def test_history_uses_stock_for_single_color_and_does_not_duplicate_it():
    changes = [
        {
            "type": "UPDATED",
            "code": "ABC-001",
            "name": "Producto de un color",
            "field": "stock",
            "label": "Stock",
            "old": 500,
            "new": 400,
        },
        {
            "type": "UPDATED",
            "code": "ABC-001",
            "name": "Producto de un color",
            "field": "color_stock",
            "label": "Stock por color",
            "old": {"Azul": 500},
            "new": {"Azul": 400},
        },
    ]

    rows = ScrapingHistoryDialog._prepare_change_rows(changes)

    assert len(rows) == 1
    assert rows[0]["variation"] == "Stock"
    assert rows[0]["old"] == "Azul: 500"
    assert rows[0]["new"] == "Azul: 400 (-100)"


def test_history_uses_stock_by_color_for_multi_color_products():
    changes = [
        {
            "type": "UPDATED",
            "code": "ABC-002",
            "name": "Producto multicolor",
            "field": "stock",
            "label": "Stock",
            "old": 1500,
            "new": 1225,
        },
        {
            "type": "UPDATED",
            "code": "ABC-002",
            "name": "Producto multicolor",
            "field": "color_stock",
            "label": "Stock por color",
            "old": {"Azul": 500, "Verde": 1000},
            "new": {"Azul": 400, "Verde": 825},
        },
    ]

    rows = ScrapingHistoryDialog._prepare_change_rows(changes)

    assert len(rows) == 1
    assert rows[0]["variation"] == "Stock por color"
    assert rows[0]["old"] == "Azul: 500\nVerde: 1,000"
    assert rows[0]["new"] == "Azul: 400 (-100)\nVerde: 825 (-175)"


def test_history_hides_unchanged_price_lines():
    changes = [
        {
            "type": "UPDATED",
            "code": "ABC-007",
            "name": "Producto con precios parcialmente cambiados",
            "field": "price_sample",
            "label": "Precio muestra",
            "old": 3.00,
            "new": 3.50,
        },
        {
            "type": "UPDATED",
            "code": "ABC-007",
            "name": "Producto con precios parcialmente cambiados",
            "field": "price_hundred",
            "label": "Precio ciento",
            "old": 4.00,
            "new": 4.00,
        },
    ]

    rows = ScrapingHistoryDialog._prepare_change_rows(changes)

    assert len(rows) == 1
    assert rows[0]["variation"] == "Precios"
    assert rows[0]["old"] == "muestra: s/3.00"
    assert rows[0]["new"] == "muestra: s/3.50 (+s/0.50)"
    assert "ciento" not in rows[0]["old"]
    assert "ciento" not in rows[0]["new"]


def test_history_hides_unchanged_stock_colors():
    changes = [
        {
            "type": "UPDATED",
            "code": "ABC-008",
            "name": "Producto multicolor parcialmente cambiado",
            "field": "stock",
            "label": "Stock",
            "old": 900,
            "new": 850,
        },
        {
            "type": "UPDATED",
            "code": "ABC-008",
            "name": "Producto multicolor parcialmente cambiado",
            "field": "color_stock",
            "label": "Stock por color",
            "old": {"Azul": 500, "Verde": 400},
            "new": {"Azul": 450, "Verde": 400},
        },
    ]

    rows = ScrapingHistoryDialog._prepare_change_rows(changes)

    assert len(rows) == 1
    assert rows[0]["variation"] == "Stock por color"
    assert rows[0]["old"] == "Azul: 500"
    assert rows[0]["new"] == "Azul: 450 (-50)"
    assert "Verde" not in rows[0]["old"]
    assert "Verde" not in rows[0]["new"]


def test_history_uses_spanish_change_type_labels():
    assert ScrapingHistoryDialog._change_type_text("UPDATED") == "ACTUALIZADO"
    assert ScrapingHistoryDialog._change_type_text("NEW") == "NUEVO"
    assert ScrapingHistoryDialog._change_type_text("DELETED") == "ELIMINADO"


def test_history_groups_price_changes_into_one_vertical_variation():
    changes = [
        {
            "type": "UPDATED",
            "code": "ABC-005",
            "name": "Producto con precios",
            "field": "price_sample",
            "label": "Precio muestra",
            "old": 3.50,
            "new": 4.00,
        },
        {
            "type": "UPDATED",
            "code": "ABC-005",
            "name": "Producto con precios",
            "field": "price_hundred",
            "label": "Precio ciento",
            "old": 3.50,
            "new": 2.00,
        },
    ]

    rows = ScrapingHistoryDialog._prepare_change_rows(changes)

    assert len(rows) == 1
    assert rows[0]["variation"] == "Precios"
    assert rows[0]["old"] == "muestra: s/3.50\nciento: s/3.50"
    assert rows[0]["new"] == "muestra: s/4.00 (+s/0.50)\nciento: s/2.00 (-s/1.50)"
    assert "#188038" in rows[0]["new_html"]
    assert "#d93025" in rows[0]["new_html"]


def test_history_formats_category_values_vertically():
    changes = [
        {
            "type": "UPDATED",
            "code": "ABC-006",
            "name": "Producto con categoría",
            "field": "category",
            "label": "Categoría",
            "old": "Azul",
            "new": "Azul, Verde",
        }
    ]

    rows = ScrapingHistoryDialog._prepare_change_rows(changes)

    assert len(rows) == 1
    assert rows[0]["variation"] == "Categoría"
    assert rows[0]["old"] == "Azul"
    assert rows[0]["new"] == "Azul\nVerde"


def test_history_stock_new_value_shows_signed_delta_for_single_stock():
    assert ScrapingHistoryDialog._format_stock_new_value(500, 400) == "400 (-100)"
    assert ScrapingHistoryDialog._format_stock_new_value(1000, 1825) == "1825 (+825)"
    assert ScrapingHistoryDialog._format_stock_new_value(500, 500) == "500"


def test_history_stock_new_value_shows_signed_delta_by_color():
    value = ScrapingHistoryDialog._format_stock_new_value(
        {"Azul": 500, "Verde": 1000},
        {"Azul": 400, "Verde": 1825},
        by_color=True,
    )
    assert value == "Azul: 400 (-100)\nVerde: 1825 (+825)"


def test_history_change_table_has_row_numbers_and_dynamic_columns():
    QApplication.instance() or QApplication([])
    dialog = ScrapingHistoryDialog.__new__(ScrapingHistoryDialog)
    table = dialog._build_changes_table(
        [
            {
                "type": "UPDATED",
                "code": "ABC-003",
                "name": "Producto con nombre suficientemente largo",
                "variation": "Stock por color",
                "old": "Azul: 500\nVerde: 1000",
                "new": "Azul: 400 (-100)\nVerde: 825 (+825)",
            },
            {
                "type": "UPDATED",
                "code": "ABC-004",
                "name": "Segundo producto",
                "variation": "Stock por color",
                "old": "Rojo: 100",
                "new": "Rojo: 80 (-20)",
            },
        ]
    )

    table.show()
    QApplication.processEvents()
    header = table.horizontalHeader()
    assert table.verticalHeader().isVisible()
    assert table.verticalHeader().sectionSize(0) >= 32
    assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.ResizeToContents
    assert header.sectionResizeMode(1) == QHeaderView.ResizeMode.ResizeToContents
    assert header.sectionResizeMode(2) == QHeaderView.ResizeMode.Stretch
    product_item = table.item(0, 2)
    assert product_item is not None
    assert product_item.toolTip() == "Producto con nombre suficientemente largo"
    assert len(product_item.text().splitlines()) <= 2
    assert " ".join(product_item.text().splitlines()) == product_item.toolTip()
    assert table.textElideMode() == Qt.TextElideMode.ElideNone
    assert table.item(0, 0).text() == "ACTUALIZADO"
    assert header.sectionResizeMode(3) == QHeaderView.ResizeMode.ResizeToContents
    assert header.sectionResizeMode(4) == QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(5) == QHeaderView.ResizeMode.Stretch
    assert (
        table.columnWidth(0)
        + table.columnWidth(1)
        + table.columnWidth(2)
    ) > table.verticalHeader().width()
    assert table.item(0, 4).toolTip() == "Azul: 500 · Verde: 1000"
    new_widget = table.cellWidget(0, 5)
    assert isinstance(new_widget, QLabel)
    assert new_widget.toolTip() == "Azul: 400 (-100) · Verde: 825 (+825)"
    assert "#188038" in new_widget.text()

    detail_dialog = QDialog()
    detail_layout = QVBoxLayout(detail_dialog)
    detail_layout.addWidget(table)
    detail_dialog.setMaximumHeight(800)
    detail_dialog.resize(900, 500)
    detail_dialog.show()
    table.show()
    QApplication.processEvents()
    dialog._fit_changes_table_to_dialog(detail_dialog, table)
    QApplication.processEvents()
    assert table.height() == table.minimumHeight()
    small_product_width = table.columnWidth(2)
    small_old_width = table.columnWidth(4)
    small_new_width = table.columnWidth(5)

    table.resize(1200, 220)
    QApplication.processEvents()
    large_product_width = table.columnWidth(2)
    large_old_width = table.columnWidth(4)
    large_new_width = table.columnWidth(5)

    assert large_product_width > small_product_width
    assert large_old_width > small_old_width
    assert large_new_width > small_new_width
    assert table.columnWidth(4) > 0
    assert table.columnWidth(5) > 0
    dialog._fit_changes_table_to_dialog(detail_dialog, table)
    QApplication.processEvents()
    assert table.height() == table.minimumHeight()
    assert (
        sum(table.columnWidth(column) for column in range(table.columnCount()))
        <= table.viewport().width() + table.verticalHeader().width() + 4
    )

    detail_dialog.close()
    table.deleteLater()


def test_multiple_category_table_shows_every_row_without_partial_clipping():
    QApplication.instance() or QApplication([])
    owner = ScrapingHistoryDialog.__new__(ScrapingHistoryDialog)
    dialog = QDialog()
    dialog.setMaximumHeight(800)
    layout = QVBoxLayout(dialog)
    table = QTableWidget()
    table.setColumnCount(3)
    table.setHorizontalHeaderLabels(["Código", "Producto", "Categorías"])
    table.setRowCount(4)
    table.setWordWrap(True)
    table.setTextElideMode(Qt.TextElideMode.ElideNone)
    for row, code in enumerate(["FB-4028", "FB-1060", "FB-9000", "FB-5003"]):
        table.setItem(row, 0, QTableWidgetItem(code))
        table.setItem(row, 1, QTableWidgetItem(f"Producto {code}"))
        table.setItem(
            row,
            2,
            QTableWidgetItem("Enmicadoras / Laminadoras, Oficina"),
        )
    table.horizontalHeader().setSectionResizeMode(
        0,
        QHeaderView.ResizeMode.ResizeToContents,
    )
    table.horizontalHeader().setSectionResizeMode(
        1,
        QHeaderView.ResizeMode.Stretch,
    )
    table.horizontalHeader().setSectionResizeMode(
        2,
        QHeaderView.ResizeMode.Stretch,
    )
    layout.addWidget(table)

    dialog.resize(900, 500)
    dialog.show()
    table.show()
    QApplication.processEvents()

    owner._fit_multiple_category_table(dialog, table)
    QApplication.processEvents()

    assert table.verticalScrollBar().maximum() == 0
    assert all(
        table.visualItemRect(table.item(row, 0)).bottom()
        < table.viewport().height()
        for row in range(4)
    )
    expected_height = (
        table.horizontalHeader().height()
        + sum(table.rowHeight(row) for row in range(4))
        + 2 * table.frameWidth()
        + 2
    )
    assert table.height() >= expected_height

    dialog.close()
