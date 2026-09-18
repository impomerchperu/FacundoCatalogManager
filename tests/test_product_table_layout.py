from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics, QPixmap
from PySide6.QtWidgets import QApplication, QHeaderView, QLabel

from gui.product_table import ProductTable
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

    image = table.cellWidget(0, ProductTable.IMAGE_COLUMN)

    assert isinstance(image, QLabel)
    assert image.contentsMargins().left() == 0
    assert image.contentsMargins().right() == 0
    assert image.contentsMargins().top() == 0
    assert image.contentsMargins().bottom() == 0
    assert image.width() == table.columnWidth(ProductTable.IMAGE_COLUMN)
    assert image.height() == table.rowHeight(0)

    rendered = image.pixmap()
    assert rendered is not None
    assert rendered.width() == image.width()
    assert rendered.height() == image.height()

    table.resize(2200, 700)
    QApplication.processEvents()

    assert image.width() == table.columnWidth(ProductTable.IMAGE_COLUMN)
    assert image.height() == table.rowHeight(0)
    rendered = image.pixmap()
    assert rendered is not None
    assert rendered.width() == image.width()
    assert rendered.height() == image.height()

    table.close()


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
    table.resize(1200, 700)
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

    table.resize(1100, 700)
    QApplication.processEvents()

    header = table.horizontalHeader()
    total_width = sum(
        header.sectionSize(column) for column in range(table.columnCount())
    )

    assert table.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert total_width <= table.viewport().width()

    table.close()
