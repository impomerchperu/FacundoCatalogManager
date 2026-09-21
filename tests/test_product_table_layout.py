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


