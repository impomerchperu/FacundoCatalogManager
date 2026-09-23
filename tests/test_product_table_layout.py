from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics, QPixmap
from PySide6.QtWidgets import QApplication, QHeaderView, QLabel, QWidget

from gui.product_table import ProductImageDelegate, ProductTable
from models.product import Product


def _qapp():
    return QApplication.instance() or QApplication([])


class _Controller:
    def get_products(self):
        return []


def test_product_table_images_fill_the_cell_without_spacing(tmp_path: Path):
    _qapp()

    image_path = tmp_path / "product.png"
    pixmap = QPixmap(320, 180)
    assert pixmap.save(str(image_path))

    table = ProductTable(_Controller())
    table.resize(1800, 700)
    table.show()
    table.load_products(
        [
            Product(
                code="FB-100",
                name="Producto",
                image_path=str(image_path),
            ),
        ],
    )
    QApplication.processEvents()

    item = table.item(0, ProductTable.IMAGE_COLUMN)
    delegate = table.itemDelegateForColumn(ProductTable.IMAGE_COLUMN)

    assert table.cellWidget(0, ProductTable.IMAGE_COLUMN) is None
    assert isinstance(delegate, ProductImageDelegate)
    assert isinstance(item.data(ProductImageDelegate.IMAGE_ROLE), QPixmap)
    assert table.columnWidth(ProductTable.IMAGE_COLUMN) >= (
        ProductImageDelegate.DEFAULT_SIZE
    )
    assert table.rowHeight(0) == table.columnWidth(ProductTable.IMAGE_COLUMN)

    table.resize(2200, 700)
    QApplication.processEvents()

    assert table.rowHeight(0) == table.columnWidth(ProductTable.IMAGE_COLUMN)
    assert table.columnWidth(ProductTable.IMAGE_COLUMN) >= (
        ProductImageDelegate.DEFAULT_SIZE
    )

    table.close()


def test_product_table_category_uses_approved_two_line_layout():
    category = "Impresoras y Consumible Fotográficas Térmicas"

    formatted = ProductTable._format_categories(category)

    assert formatted.splitlines() == [
        "Impresoras y Consumible",
        "Fotográficas Térmicas",
    ]


def test_product_table_category_with_long_word_stays_on_one_line():
    category = "Categoria extraordinariamenteLargaSinEspacios"

    formatted = ProductTable._format_categories(category)

    assert formatted == category
    assert "\n" not in formatted


def test_product_table_category_sublimacion_stays_on_one_line():
    _qapp()

    table = ProductTable(_Controller())
    table.resize(1400, 700)
    table.show()
    product = Product(
        code="FB-400",
        name="Producto",
        category="Artículos de Sublimación",
    )
    table.load_products([product])
    QApplication.processEvents()

    item = table.item(0, ProductTable.CATEGORY_COLUMN)
    assert item is not None
    assert item.text() == "Artículos de Sublimación"
    assert "\n" not in item.text()

    expected_width = (
        QFontMetrics(table.font()).horizontalAdvance(item.text())
        + (2 * ProductTable.CONTENT_SIDE_PADDING)
    )
    assert table.columnWidth(ProductTable.CATEGORY_COLUMN) >= expected_width


def test_product_table_category_enmicadoras_stays_on_one_line():
    _qapp()

    table = ProductTable(_Controller())
    table.resize(1400, 700)
    table.show()
    product = Product(
        code="FB-401",
        name="Producto",
        category="Enmicadoras / Laminadoras",
    )
    table.set_category_reference_products([product])
    table.load_products([product])
    QApplication.processEvents()

    item = table.item(0, ProductTable.CATEGORY_COLUMN)
    assert item is not None
    assert item.text() == "Enmicadoras / Laminadoras"
    assert "\n" not in item.text()

    expected_width = (
        QFontMetrics(table.font()).horizontalAdvance(item.text())
        + (2 * ProductTable.CONTENT_SIDE_PADDING)
    )
    assert table.columnWidth(ProductTable.CATEGORY_COLUMN) >= expected_width

    table.close()


def test_product_table_category_width_persists_when_products_are_filtered():
    _qapp()

    table = ProductTable(_Controller())
    table.resize(1400, 700)
    table.show()
    full_catalog = [
        Product(
            code="FB-401",
            name="Producto largo",
            category="Enmicadoras / Laminadoras",
        ),
        Product(
            code="FB-402",
            name="Producto corto",
            category="Estuches",
        ),
    ]
    table.set_category_reference_products(full_catalog)
    table.load_products(full_catalog)
    QApplication.processEvents()

    expected_width = (
        QFontMetrics(table.font()).horizontalAdvance(
            "Enmicadoras / Laminadoras",
        )
        + (2 * ProductTable.CONTENT_SIDE_PADDING)
    )
    assert table.columnWidth(ProductTable.CATEGORY_COLUMN) >= expected_width

    table.load_products([full_catalog[1]])
    QApplication.processEvents()

    assert table.columnWidth(ProductTable.CATEGORY_COLUMN) >= expected_width

    table.close()


def test_product_table_category_does_not_wrap_by_word_count():
    category = "Uno Dos Tres Cuatro Cinco Seis"

    formatted = ProductTable._format_categories(category)

    assert formatted == category
    assert "\n" not in formatted


def test_product_table_category_does_not_wrap_by_character_count():
    category = "123456 123456 123456 123456 1234"

    formatted = ProductTable._format_categories(category)

    assert formatted == category
    assert "\n" not in formatted


def test_product_table_columns_fit_content_and_never_enable_horizontal_scroll():
    _qapp()

    table = ProductTable(_Controller())
    table.resize(2200, 700)
    table.show()
    product = Product(
        code="FB-200",
        name="Nombre de producto suficientemente largo",
        description="Detalle suficientemente largo para comprobar el ajuste",
        category="Categoria de prueba",
    )
    table.load_products([product])
    QApplication.processEvents()
    table._fit_columns_to_content()

    header = table.horizontalHeader()
    name_width = QFontMetrics(table.font()).horizontalAdvance(product.name)

    assert (
        table.horizontalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert table.textElideMode() == Qt.TextElideMode.ElideNone
    assert "padding: 4px" in table.styleSheet()
    assert "#f8fbff" in table.styleSheet()
    assert "#eef5fb" in table.styleSheet()
    assert "#173f6d" in table.styleSheet()
    assert sum(header.sectionSize(column) for column in range(table.columnCount())) <= (
        table.viewport().width()
    )
    assert header.sectionSize(ProductTable.NAME_COLUMN) >= name_width + (
        2 * ProductTable.CONTENT_SIDE_PADDING
    )
    for column in range(table.columnCount()):
        assert (
            header.sectionResizeMode(column)
            == QHeaderView.ResizeMode.Interactive
        )

    table.close()


def test_product_table_columns_reflow_to_narrow_window_without_scroll():
    _qapp()

    table = ProductTable(_Controller())
    table.resize(1300, 700)
    table.show()
    table.load_products(
        [
            Product(
                code="FB-300",
                name="Producto con texto largo",
                description="Detalle " * 20,
                category="Categoria " * 8,
            ),
        ],
    )
    QApplication.processEvents()

    table.resize(1300, 700)
    QApplication.processEvents()

    header = table.horizontalHeader()
    total_width = sum(
        header.sectionSize(column) for column in range(table.columnCount())
    )

    assert table.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert total_width <= table.viewport().width()

    table.close()

def test_product_table_renders_stock_by_color_in_stock_cell():
    _qapp()

    table = ProductTable(_Controller())
    table.resize(1800, 700)
    table.show()
    table.load_products(
        [
            Product(
                code="FB-6002",
                name="Mochilas de Lona",
                stock=2693,
                color_stock={
                    "Azul": 528,
                    "Rojo": 124,
                    "Negro": 1686,
                    "Gris": 355,
                },
            ),
        ],
    )
    QApplication.processEvents()

    widget = table.cellWidget(0, ProductTable.STOCK_COLUMN)

    assert isinstance(widget, QWidget)
    labels = widget.findChildren(QLabel)
    rendered_texts = [label.text() for label in labels]

    assert "Azul" in rendered_texts
    assert "528" in rendered_texts
    assert "Rojo" in rendered_texts
    assert "124" in rendered_texts
    assert "Negro" in rendered_texts
    assert "1,686" in rendered_texts
    assert "Gris" in rendered_texts
    assert "355" in rendered_texts
    assert all("\n" not in text for text in rendered_texts)
    assert table.rowHeight(0) >= widget.sizeHint().height()
    assert widget.toolTip() == (
        "Azul: 528\n"
        "Rojo: 124\n"
        "Negro: 1686\n"
        "Gris: 355"
    )

    table.close()



def test_product_table_stock_color_rows_fill_the_cell_without_outer_spacing():
    _qapp()

    table = ProductTable(_Controller())
    table.resize(1800, 700)
    table.show()
    table.load_products(
        [
            Product(
                code="FB-6003",
                name="Pelota Antiestrés",
                color_stock={
                    "Amarillo": 1031,
                    "Azul": 0,
                    "Blanco": 20,
                    "Celeste": 9442,
                    "Morado": 5939,
                    "Naranja": 0,
                    "Negro": 4340,
                    "Rojo": 48,
                    "Rosado": 14545,
                    "Verde Claro": 6952,
                    "Verde Oscuro": 12718,
                },
            ),
        ],
    )
    QApplication.processEvents()

    container = table.cellWidget(0, ProductTable.STOCK_COLUMN)
    assert isinstance(container, QWidget)
    container_layout = container.layout()
    assert container_layout is not None
    margins = container_layout.contentsMargins()
    assert margins.left() == 0
    assert margins.top() == 0
    assert margins.right() == 0
    assert margins.bottom() == 0
    assert container_layout.verticalSpacing() == 0

    row_widgets = container.findChildren(QWidget, "stockColorRow")
    assert len(row_widgets) == 11
    expected_backgrounds = {
        color: background
        for color, (background, _indicator) in ProductTable.STOCK_COLOR_STYLES.items()
    }
    for row_widget in row_widgets:
        row_layout = row_widget.layout()
        assert row_layout is not None
        row_margins = row_layout.contentsMargins()
        assert row_margins.left() == ProductTable.STOCK_ROW_CONTENT_HORIZONTAL_PADDING
        assert row_margins.top() == 0
        assert row_margins.right() == ProductTable.STOCK_ROW_CONTENT_HORIZONTAL_PADDING
        assert row_margins.bottom() == 0

        labels = row_widget.findChildren(QLabel)
        color_labels = [
            label.text()
            for label in labels
            if label.text() and not label.text().replace(",", "").isdigit()
        ]
        assert len(color_labels) == 1
        normalized_color = " ".join(color_labels[0].casefold().split())
        assert expected_backgrounds[normalized_color] in row_widget.styleSheet()

    assert (
        table.columnWidth(ProductTable.STOCK_COLUMN)
        >= table._stock_minimum_width()
    )

    table.close()


def test_product_table_stock_width_accounts_for_indicator_color_and_quantity():
    _qapp()

    table = ProductTable(_Controller())
    table.resize(1800, 700)
    table.show()
    product = Product(
        code="FB-6004",
        name="Producto",
        color_stock={"Verde Oscuro": 12718},
    )
    table.load_products([product])
    QApplication.processEvents()

    metrics = QFontMetrics(table.font())
    expected = (
        table.STOCK_INDICATOR_SIZE
        + (2 * table.STOCK_ROW_CONTENT_GAP)
        + metrics.horizontalAdvance("Verde Oscuro")
        + metrics.horizontalAdvance("12,718")
        + (2 * table.STOCK_ROW_CONTENT_HORIZONTAL_PADDING)
        + (2 * table.CONTENT_SIDE_PADDING)
    )
    assert table.columnWidth(ProductTable.STOCK_COLUMN) >= expected

    table.close()
