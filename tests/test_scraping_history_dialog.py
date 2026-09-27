from PySide6.QtWidgets import QApplication, QHeaderView, QLabel

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
    assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Fixed
    assert header.sectionResizeMode(1) == QHeaderView.ResizeMode.Fixed
    assert header.sectionResizeMode(2) == QHeaderView.ResizeMode.ResizeToContents
    assert table.item(0, 0).text() == "ACTUALIZADO"
    assert header.sectionResizeMode(3) == QHeaderView.ResizeMode.Fixed
    assert header.sectionResizeMode(4) == QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(5) == QHeaderView.ResizeMode.Stretch
    assert table.item(0, 4).toolTip() == "Azul: 500 · Verde: 1000"
    new_widget = table.cellWidget(0, 5)
    assert isinstance(new_widget, QLabel)
    assert new_widget.toolTip() == "Azul: 400 (-100) · Verde: 825 (+825)"
    assert "#188038" in new_widget.text()

    table.resize(900, 220)
    table.show()
    QApplication.processEvents()
    small_product_width = table.columnWidth(2)
    small_old_width = table.columnWidth(4)
    small_new_width = table.columnWidth(5)

    table.resize(1200, 220)
    QApplication.processEvents()
    large_product_width = table.columnWidth(2)
    large_old_width = table.columnWidth(4)
    large_new_width = table.columnWidth(5)

    assert large_product_width == small_product_width
    assert large_old_width > small_old_width
    assert large_new_width > small_new_width
    assert table.columnWidth(4) > 0
    assert table.columnWidth(5) > 0

    table.deleteLater()
