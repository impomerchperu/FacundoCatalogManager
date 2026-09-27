from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from gui.scraping_history_dialog import ScrapingHistoryDialog


def test_history_groups_product_changes_into_one_display_row():
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

    assert len(rows) == 1
    assert rows[0]["code"] == "ABC-001"
    assert rows[0]["variation"] == "Stock\nPrecio"
    assert rows[0]["old"] == "20\n10"
    assert rows[0]["new"] == "18\n12"


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
    assert rows[0]["new"] == "Azul: 400\nVerde: 825"


def test_history_change_table_uses_compact_fixed_visual_widths():
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
                "new": "Azul: 400\nVerde: 825",
            }
        ]
    )

    expected = dialog.DETAIL_CHANGE_COLUMN_WIDTHS
    assert tuple(table.columnWidth(index) for index in range(6)) == expected
    assert table.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert table.item(0, 2).toolTip() == (
        "Producto con nombre suficientemente largo"
    )
    assert table.item(0, 4).toolTip() == "Azul: 500 · Verde: 1000"

    table.deleteLater()
