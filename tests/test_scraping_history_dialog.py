from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

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
    assert rows[0]["new"] == "18"
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
    assert rows[0]["old"] == "500"
    assert rows[0]["new"] == "400"


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
    assert rows[0]["old"] == "Azul: 500\nVerde: 1000"
    assert rows[0]["new"] == "Azul: 400 (-100)\nVerde: 825 (+825)"


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

    header = table.horizontalHeader()
    assert table.verticalHeader().isVisible()
    assert table.verticalHeader().sectionSize(0) >= 32
    assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Fixed
    assert header.sectionResizeMode(1) == QHeaderView.ResizeMode.Fixed
    assert header.sectionResizeMode(2) == QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(3) == QHeaderView.ResizeMode.Fixed
    assert header.sectionResizeMode(4) == QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(5) == QHeaderView.ResizeMode.Stretch
    assert table.item(0, 4).toolTip() == "Azul: 500 · Verde: 1000"
    assert table.item(0, 5).toolTip() == (
        "Azul: 400 (-100) · Verde: 825 (+825)"
    )

    table.resize(900, 220)
    table.show()
    QApplication.processEvents()
    small_width = table.columnWidth(2)

    table.resize(1200, 220)
    QApplication.processEvents()
    large_width = table.columnWidth(2)

    assert large_width > small_width
    assert table.columnWidth(4) > 0
    assert table.columnWidth(5) > 0

    table.deleteLater()
