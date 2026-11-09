from itertools import pairwise
from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QFontMetricsF, QPainter, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QStyle,
    QStyleOptionViewItem,
)

from gui.product_table import (
    PriceDelegate,
    ProductCellDelegate,
    ProductDetailDelegate,
    ProductImageDelegate,
    ProductNameCategoryDelegate,
    ProductTable,
    StockColorDelegate,
)
from models.product import Product


def _qapp():
    return QApplication.instance() or QApplication([])


class _Controller:
    def get_products(self):
        return []


class _TrackingProductTable(ProductTable):
    def __init__(self, controller: _Controller) -> None:
        self.resize_to_contents_calls = 0
        super().__init__(controller)

    def resizeColumnsToContents(self) -> None:
        self.resize_to_contents_calls += 1
        super().resizeColumnsToContents()


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
    assert item.data(ProductImageDelegate.IMAGE_ROLE) == str(image_path)
    initial_image_column_width = table.columnWidth(ProductTable.IMAGE_COLUMN)
    assert initial_image_column_width == (
        ProductImageDelegate.MAIN_IMAGE_WIDTH
        + (2 * ProductImageDelegate.CELL_HORIZONTAL_PADDING)
        + ProductImageDelegate.GRIDLINE_RIGHT_ALLOWANCE
    )
    assert initial_image_column_width == ProductImageDelegate.DEFAULT_SIZE
    assert ProductImageDelegate.THUMBNAIL_GAP == 0

    cell_rect = table.visualRect(
        table.model().index(0, ProductTable.IMAGE_COLUMN),
    )
    main_rect, _thumbnail_top = ProductImageDelegate.main_image_layout(
        cell_rect,
        str(image_path),
        has_thumbnails=False,
    )
    assert main_rect.left() == cell_rect.left() + 1
    assert main_rect.top() == cell_rect.top() + 1
    assert main_rect.right() == cell_rect.right() - 1
    assert main_rect.bottom() == cell_rect.bottom() - 1
    assert main_rect.width() == ProductImageDelegate.MAIN_IMAGE_WIDTH
    assert (
        table.horizontalHeader().sectionResizeMode(ProductTable.IMAGE_COLUMN)
        == QHeaderView.ResizeMode.Fixed
    )
    assert (
        ProductImageDelegate.DEFAULT_HEIGHT
        - ProductImageDelegate.THUMBNAIL_STRIP_HEIGHT
        - ProductImageDelegate.THUMBNAIL_GAP
        - (2 * ProductImageDelegate.CELL_VERTICAL_PADDING)
        - ProductImageDelegate.GRIDLINE_BOTTOM_ALLOWANCE
        == ProductImageDelegate.MIN_PRIMARY_IMAGE_DISPLAY_SIZE
    )
    display_width = max(
        ProductImageDelegate.MAIN_IMAGE_WIDTH,
        table.columnWidth(ProductTable.IMAGE_COLUMN)
        - (2 * ProductImageDelegate.CELL_HORIZONTAL_PADDING),
    )
    expected_row_height = (
        ProductImageDelegate.main_image_height(str(image_path), display_width)
        + (2 * ProductImageDelegate.CELL_VERTICAL_PADDING)
        + ProductTable.ROW_VERTICAL_SPACING
        + ProductImageDelegate.GRIDLINE_BOTTOM_ALLOWANCE
    )
    assert table.rowHeight(0) == expected_row_height

    table.resize(2200, 700)
    QApplication.processEvents()

    assert table.rowHeight(0) == expected_row_height
    assert table.columnWidth(ProductTable.IMAGE_COLUMN) == initial_image_column_width

    table.close()


def test_product_table_keeps_gallery_order_and_centers_thumbnails_under_primary(
    tmp_path: Path,
):
    _qapp()
    paths = [tmp_path / f"image-{index}.png" for index in range(3)]
    gallery = []
    for index, path in enumerate(paths, start=1):
        pixmap = QPixmap(120 + index * 10, 80)
        pixmap.fill(QColor("#2f80ed" if index == 1 else "#ef4444"))
        assert pixmap.save(str(path))
        gallery.append(
            {
                "url": f"https://example.test/{index}.png",
                "image_path": str(path),
                "position": index,
                "source": "primary" if index == 1 else "gallery",
            },
        )

    product = Product(
        code="FB-100",
        name="Producto",
        image_path=str(paths[0]),
        gallery_images=gallery,
    )
    table = ProductTable(_Controller())
    table.resize(1500, 700)
    table.show()
    table.load_products([product])
    QApplication.processEvents()

    index = table.model().index(0, ProductTable.IMAGE_COLUMN)
    rect = table.visualRect(index)
    content_rect = ProductImageDelegate.cell_content_rect(rect)
    main_rect, thumbnail_top = ProductImageDelegate.main_image_layout(
        rect,
        str(paths[0]),
        has_thumbnails=True,
    )
    tiles, left_arrow, right_arrow, strip_top = (
        ProductImageDelegate.thumbnail_layout(
            content_rect,
            len(gallery),
            0,
            active_index=0,
            thumbnail_top=thumbnail_top,
        )
    )
    assert [image_index for image_index, _tile in tiles] == [0, 1, 2]
    assert left_arrow is None and right_arrow is None
    assert strip_top == main_rect.bottom() + 1 + ProductImageDelegate.THUMBNAIL_GAP
    assert strip_top == main_rect.bottom() + 1
    assert strip_top == tiles[0][1].top()
    assert all(
        following.left() == previous.right() + 1
        for previous, following in pairwise([tile for _, tile in tiles])
    )
    group_bottom = tiles[-1][1].bottom()
    assert abs(
        (main_rect.top() + group_bottom) / 2 - content_rect.center().y()
    ) <= 1
    assert abs(
        (tiles[0][1].left() + tiles[-1][1].right()) / 2
        - content_rect.center().x()
    ) <= 1
    fixed_tile_geometry = [
        (tile.left(), tile.width(), tile.height())
        for _image_index, tile in tiles
    ]
    image_content_height = (
        ProductImageDelegate.main_image_height(str(paths[0]))
        + ProductImageDelegate.THUMBNAIL_GAP
        + ProductImageDelegate.THUMBNAIL_STRIP_HEIGHT
    )
    assert table.rowHeight(0) == (
        image_content_height
        + (2 * ProductImageDelegate.CELL_VERTICAL_PADDING)
        + ProductTable.ROW_VERTICAL_SPACING
        + ProductImageDelegate.GRIDLINE_BOTTOM_ALLOWANCE
    )

    QTest.mouseClick(
        table.viewport(),
        Qt.MouseButton.LeftButton,
        pos=tiles[1][1].center(),
    )
    QApplication.processEvents()

    item = table.item(0, ProductTable.IMAGE_COLUMN)
    visible_gallery = item.data(ProductImageDelegate.GALLERY_ROLE)
    assert item.data(ProductImageDelegate.ACTIVE_INDEX_ROLE) == 1
    assert [image["image_path"] for image in visible_gallery] == [
        str(paths[0]),
        str(paths[1]),
        str(paths[2]),
    ]
    assert ProductImageDelegate._selected_path(
        visible_gallery,
        item.data(ProductImageDelegate.ACTIVE_INDEX_ROLE),
        "",
    ) == str(paths[1])
    assert [image["image_path"] for image in product.gallery_images] == [
        str(paths[0]),
        str(paths[1]),
        str(paths[2]),
    ]

    rect = table.visualRect(index)
    content_rect = ProductImageDelegate.cell_content_rect(rect)
    main_rect, thumbnail_top = ProductImageDelegate.main_image_layout(
        rect,
        str(paths[1]),
        has_thumbnails=True,
    )
    replacement_tiles, _, _, _ = ProductImageDelegate.thumbnail_layout(
        content_rect,
        len(gallery),
        0,
        active_index=1,
        thumbnail_top=thumbnail_top,
    )
    assert [image_index for image_index, _tile in replacement_tiles] == [0, 1, 2]
    assert [
        (tile.left(), tile.width(), tile.height())
        for _image_index, tile in replacement_tiles
    ] == fixed_tile_geometry
    assert replacement_tiles[0][0] == 0
    assert replacement_tiles[1][0] == 1
    assert replacement_tiles[0][1].top() == main_rect.bottom() + 1 + (
        ProductImageDelegate.THUMBNAIL_GAP
    )

    QTest.mouseClick(
        table.viewport(),
        Qt.MouseButton.LeftButton,
        pos=replacement_tiles[0][1].center(),
    )
    QApplication.processEvents()
    assert item.data(ProductImageDelegate.ACTIVE_INDEX_ROLE) == 0
    restored_tiles, _, _, _ = ProductImageDelegate.thumbnail_layout(
        content_rect,
        len(gallery),
        0,
        active_index=0,
        thumbnail_top=thumbnail_top,
    )
    assert [image_index for image_index, _tile in restored_tiles] == [0, 1, 2]
    assert table.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    table.close()


def test_keyboard_arrows_select_adjacent_gallery_thumbnails(tmp_path: Path):
    _qapp()
    paths = [tmp_path / f"keyboard-{index}.png" for index in range(6)]
    gallery = []
    for index, path in enumerate(paths):
        pixmap = QPixmap(80, 60)
        pixmap.fill(QColor("#2f80ed" if index % 2 == 0 else "#ef4444"))
        assert pixmap.save(str(path))
        gallery.append(
            {
                "url": f"https://example.test/keyboard-{index}.png",
                "image_path": str(path),
            },
        )

    table = ProductTable(_Controller())
    table.resize(1500, 700)
    table.show()
    table.load_products(
        [
            Product(
                code="FB-KEYS",
                name="Navegación por miniaturas",
                image_path=str(paths[0]),
                gallery_images=gallery,
            ),
        ],
    )
    QApplication.processEvents()
    table.setCurrentCell(0, ProductTable.IMAGE_COLUMN)
    table.setFocus()
    QApplication.processEvents()

    item = table.item(0, ProductTable.IMAGE_COLUMN)
    assert item is not None
    QTest.keyClick(table, Qt.Key.Key_Right)
    assert item.data(ProductImageDelegate.ACTIVE_INDEX_ROLE) == 1
    QTest.keyClick(table, Qt.Key.Key_Right)
    assert item.data(ProductImageDelegate.ACTIVE_INDEX_ROLE) == 2
    QTest.keyClick(table, Qt.Key.Key_Left)
    assert item.data(ProductImageDelegate.ACTIVE_INDEX_ROLE) == 1
    assert item.data(ProductImageDelegate.THUMBNAIL_START_ROLE) == 0

    QTest.keyClick(table, Qt.Key.Key_Right)
    QTest.keyClick(table, Qt.Key.Key_Right)
    QTest.keyClick(table, Qt.Key.Key_Right)
    assert item.data(ProductImageDelegate.ACTIVE_INDEX_ROLE) == 4
    assert item.data(ProductImageDelegate.THUMBNAIL_START_ROLE) == 1

    QTest.keyClick(table, Qt.Key.Key_Left)
    assert item.data(ProductImageDelegate.ACTIVE_INDEX_ROLE) == 3
    assert item.data(ProductImageDelegate.THUMBNAIL_START_ROLE) == 1

    table.close()


def test_horizontal_thumbnail_arrows_scroll_without_changing_primary(tmp_path: Path):
    _qapp()
    paths = [tmp_path / f"scroll-{index}.png" for index in range(6)]
    gallery = []
    for index, path in enumerate(paths, start=1):
        pixmap = QPixmap(60, 40)
        pixmap.fill(QColor("#2f80ed" if index % 2 else "#ef4444"))
        assert pixmap.save(str(path))
        gallery.append(
            {
                "url": f"https://example.test/scroll-{index}.png",
                "image_path": str(path),
                "position": index,
            },
        )
    product = Product(
        code="FB-101",
        name="Producto con muchas imágenes",
        image_path=str(paths[0]),
        gallery_images=gallery,
    )
    table = ProductTable(_Controller())
    table.resize(1500, 700)
    table.show()
    table.load_products([product])
    QApplication.processEvents()

    index = table.model().index(0, ProductTable.IMAGE_COLUMN)
    rect = table.visualRect(index)
    content_rect = ProductImageDelegate.cell_content_rect(rect)
    _main_rect, thumbnail_top = ProductImageDelegate.main_image_layout(
        rect,
        str(paths[0]),
        has_thumbnails=True,
    )
    initial_tiles, left_arrow, right_arrow, _ = (
        ProductImageDelegate.thumbnail_layout(
            content_rect,
            len(gallery),
            0,
            active_index=0,
            thumbnail_top=thumbnail_top,
        )
    )
    assert [image_index for image_index, _ in initial_tiles] == [0, 1, 2, 3]
    assert left_arrow is not None
    assert right_arrow is not None

    QTest.mouseClick(
        table.viewport(),
        Qt.MouseButton.LeftButton,
        pos=right_arrow.center(),
    )
    QApplication.processEvents()
    item = table.item(0, ProductTable.IMAGE_COLUMN)
    assert item.data(ProductImageDelegate.THUMBNAIL_START_ROLE) == 1
    assert item.data(ProductImageDelegate.ACTIVE_INDEX_ROLE) == 0

    rect = table.visualRect(index)
    scrolled_tiles, left_arrow, right_arrow, _ = (
        ProductImageDelegate.thumbnail_layout(
            content_rect,
            len(gallery),
            1,
            active_index=0,
            thumbnail_top=thumbnail_top,
        )
    )
    assert [image_index for image_index, _ in scrolled_tiles] == [1, 2, 3, 4]
    assert left_arrow is not None
    assert right_arrow is not None

    QTest.mouseClick(
        table.viewport(),
        Qt.MouseButton.LeftButton,
        pos=scrolled_tiles[2][1].center(),
    )
    QApplication.processEvents()
    visible_gallery = item.data(ProductImageDelegate.GALLERY_ROLE)
    assert [image["image_path"] for image in visible_gallery] == [
        str(path) for path in paths
    ]
    assert item.data(ProductImageDelegate.ACTIVE_INDEX_ROLE) == 3
    assert item.data(ProductImageDelegate.THUMBNAIL_START_ROLE) == 1
    assert [image["image_path"] for image in product.gallery_images] == [
        str(path) for path in paths
    ]
    table.close()


def test_product_table_stock_shows_left_aligned_color_dot_and_right_aligned_quantity():
    _qapp()
    table = ProductTable(_Controller())
    table.resize(1500, 700)
    table.show()
    table.load_products(
        [
            Product(
                code="FB-6002",
                name="Mochilas de Lona",
                stock=5,
                color_stock={"Azul": 5},
            ),
        ],
    )
    QApplication.processEvents()

    viewport_pixmap = QPixmap(table.viewport().size())
    viewport_pixmap.fill(QColor("#ffffff"))
    table.viewport().render(viewport_pixmap)
    stock_rect = table.visualRect(
        table.model().index(0, ProductTable.STOCK_COLUMN),
    )
    image = viewport_pixmap.toImage()
    indicator = QColor(ProductTable._stock_color_style("Azul")[1])
    found_indicator = False
    for y in range(stock_rect.top(), stock_rect.bottom() + 1):
        for x in range(stock_rect.left(), stock_rect.right() + 1):
            if image.pixelColor(x, y) == indicator:
                found_indicator = True
                break
        if found_indicator:
            break
    assert found_indicator
    assert image.pixelColor(stock_rect.right() - 3, stock_rect.top() + 2) != (
        QColor(ProductTable._stock_color_style("Azul")[0])
    )
    table.close()


def test_product_table_category_uses_approved_two_line_layout():
    category = "Impresoras y Consumible Fotográficas Térmicas"

    formatted = ProductTable._format_categories(category)

    assert formatted.splitlines() == [
        "Impresoras y Consumible",
        "Fotográficas Térmicas",
    ]


def test_product_table_category_is_combined_with_product_name_and_detail_receives_space():
    _qapp()

    table = ProductTable(_Controller())
    table.resize(1800, 700)
    table.show()
    product = Product(
        code="FB-403",
        name="Producto",
        description="Detalle del producto",
        category="Enmicadoras / Laminadoras",
    )
    table.load_products([product])
    QApplication.processEvents()

    name_delegate = table.itemDelegateForColumn(ProductTable.NAME_COLUMN)
    category_item = table.item(0, ProductTable.CATEGORY_COLUMN)
    name_item = table.item(0, ProductTable.NAME_COLUMN)
    assert table.isColumnHidden(ProductTable.CATEGORY_COLUMN)
    assert table.columnWidth(ProductTable.CATEGORY_COLUMN) == 0
    assert table.horizontalHeaderItem(ProductTable.CODE_COLUMN).text() == "Código"
    assert (
        table.horizontalHeaderItem(ProductTable.NAME_COLUMN)
        .text()
        .replace("\n", " ")
        == "Producto / Categoría"
    )
    assert isinstance(name_delegate, ProductNameCategoryDelegate)
    assert name_item is not None
    assert name_item.text() == "Producto"
    assert category_item is not None
    assert category_item.text() == "Enmicadoras / Laminadoras"
    assert table.columnWidth(ProductTable.IMAGE_COLUMN) >= (
        ProductImageDelegate.DEFAULT_SIZE
    )
    expected_name_height = ProductNameCategoryDelegate.content_height(
        name_item.text(),
        category_item.text(),
        table.font(),
        table.columnWidth(ProductTable.NAME_COLUMN),
    )
    assert table.rowHeight(0) >= expected_name_height
    assert table.columnWidth(ProductTable.DETAIL_COLUMN) > (
        ProductTable.MIN_COLUMN_WIDTHS[ProductTable.DETAIL_COLUMN]
    )

    table.close()


def test_product_table_category_with_long_word_stays_on_one_line():
    category = "Categoria extraordinariamenteLargaSinEspacios"

    formatted = ProductTable._format_categories(category)

    assert formatted == category
    assert "\n" not in formatted


def test_product_table_category_sublimacion_is_shown_under_product_name():
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
    code_item = table.item(0, ProductTable.CODE_COLUMN)
    name_item = table.item(0, ProductTable.NAME_COLUMN)
    name_delegate = table.itemDelegateForColumn(ProductTable.NAME_COLUMN)
    assert item is not None
    assert code_item is not None
    assert name_item is not None
    assert isinstance(name_delegate, ProductNameCategoryDelegate)
    assert item.text() == "Artículos de Sublimación"
    assert item.data(ProductNameCategoryDelegate.CATEGORY_SOURCE_ROLE) == (
        "Artículos de Sublimación"
    )
    assert code_item.text() == "FB-400"
    assert name_item.text() == "Producto"
    assert table.isColumnHidden(ProductTable.CATEGORY_COLUMN)
    assert table.columnWidth(ProductTable.CATEGORY_COLUMN) == 0

    table.close()


def test_product_table_category_enmicadoras_is_combined_with_product_name():
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
    assert table.isColumnHidden(ProductTable.CATEGORY_COLUMN)
    assert table.columnWidth(ProductTable.CATEGORY_COLUMN) == 0

    table.close()


def test_product_table_keeps_category_data_when_products_are_filtered():
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

    assert table.isColumnHidden(ProductTable.CATEGORY_COLUMN)
    assert table.columnWidth(ProductTable.CATEGORY_COLUMN) == 0
    assert table.item(0, ProductTable.CATEGORY_COLUMN).text() == (
        "Enmicadoras / Laminadoras"
    )

    table.load_products([full_catalog[1]])
    QApplication.processEvents()

    assert table.columnWidth(ProductTable.CATEGORY_COLUMN) == 0
    assert table.item(0, ProductTable.CATEGORY_COLUMN).text() == "Estuches"

    table.close()


def test_filtering_rows_keeps_column_widths_and_row_heights_stable():
    _qapp()
    table = ProductTable(_Controller())
    table.resize(1500, 700)
    table.show()
    products = [
        Product(
            code="FB-511",
            name="Producto de prueba uno",
            description="Detalle técnico " * 12,
            category="Oficina",
        ),
        Product(
            code="FB-512",
            name="Producto de prueba dos",
            description="Detalle breve",
            category="Personales",
        ),
    ]
    table.load_products(products)
    QApplication.processEvents()
    widths_before = [
        table.columnWidth(column)
        for column in range(table.columnCount())
    ]
    heights_before = [
        table.rowHeight(row)
        for row in range(table.rowCount())
    ]

    table.show_only_products([products[0]])

    assert [
        table.columnWidth(column)
        for column in range(table.columnCount())
    ] == widths_before
    assert table.rowHeight(0) == heights_before[0]
    assert table.isRowHidden(1)

    table.show_all_rows()
    assert [
        table.rowHeight(row)
        for row in range(table.rowCount())
    ] == heights_before
    table.close()


def test_product_table_category_does_not_wrap_by_word_count():
    category = "Uno Dos Tres Cuatro Cinco Seis"

    formatted = ProductTable._format_categories(category)

    assert formatted == category
    assert ProductTable._format_categories("Artículos de Escritorio") == "Artículos de Escritorio"
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
    code_index = table.model().index(0, ProductTable.CODE_COLUMN)
    code_delegate = table.itemDelegate()
    assert isinstance(code_delegate, ProductCellDelegate)
    focus_option = QStyleOptionViewItem()
    focus_option.state |= QStyle.StateFlag.State_HasFocus
    code_delegate.initStyleOption(focus_option, code_index)
    assert not (focus_option.state & QStyle.StateFlag.State_HasFocus)

    assert (
        table.horizontalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert table.textElideMode() == Qt.TextElideMode.ElideNone
    assert "padding: 3px 4px" in table.styleSheet()
    assert "QTableWidget::item:focus" in table.styleSheet()
    assert "QTableWidget::item:focus {\n                border: 0px;\n                outline: none;" in table.styleSheet()
    assert "border: 1px solid #1675e8;" in table.styleSheet()
    assert "QTableWidget::item:selected:focus" in table.styleSheet()
    assert table.selectionBehavior() == QAbstractItemView.SelectionBehavior.SelectItems
    assert not (
        table.editTriggers()
        & QAbstractItemView.EditTrigger.DoubleClicked
    )
    assert "#f8fbff" in table.styleSheet()
    assert "#eef5fb" in table.styleSheet()
    assert "#173f6d" in table.styleSheet()
    assert "selection-background-color: #fbfdff;" in table.styleSheet()
    assert not table.alternatingRowColors()
    assert "QTableWidget::item:alternate" not in table.styleSheet()
    name_item = table.item(0, ProductTable.NAME_COLUMN)
    assert name_item is not None
    assert name_item.text() == product.name
    assert header.sectionSize(ProductTable.NAME_COLUMN) >= (
        ProductTable.MIN_COLUMN_WIDTHS[ProductTable.NAME_COLUMN]
    )
    for column in range(table.columnCount()):
        expected_mode = (
            QHeaderView.ResizeMode.Fixed
            if column == ProductTable.IMAGE_COLUMN
            else QHeaderView.ResizeMode.Interactive
        )
        assert header.sectionResizeMode(column) == expected_mode

    table.close()


def test_code_and_product_columns_stay_compact_while_detail_uses_extra_width():
    _qapp()
    table = ProductTable(_Controller())
    table.resize(1800, 700)
    table.show()
    table.load_products([
        Product(
            code="FB-300",
            name="Producto con un nombre amplio",
            description="Detalle técnico " * 15,
            category="Categoría de ejemplo",
        ),
    ])
    QApplication.processEvents()

    assert table.columnWidth(ProductTable.CODE_COLUMN) <= 112
    assert table.columnWidth(ProductTable.NAME_COLUMN) == 186
    assert table.columnWidth(ProductTable.DETAIL_COLUMN) > (
        table.MIN_COLUMN_WIDTHS[ProductTable.DETAIL_COLUMN]
    )
    table.close()


def test_text_column_padding_width_is_funded_by_code_column():
    _qapp()
    table = ProductTable(_Controller())
    table.resize(1500, 700)
    table.show()
    table.load_products(
        [
            Product(
                code="IKIOSK-ESTANDAR-EXTENDED-REFERENCE-CODE",
                name="Producto con nombre extenso",
                description="Detalle técnico del producto",
                category="Oficina",
            ),
        ],
    )
    QApplication.processEvents()

    preferred = table._preferred_column_widths(table.horizontalHeader())
    assert table._stable_code_width == 112
    assert preferred[ProductTable.CODE_COLUMN] == 80
    assert preferred[ProductTable.NAME_COLUMN] == 186
    assert preferred[ProductTable.DETAIL_COLUMN] == 276
    assert (
        preferred[ProductTable.CODE_COLUMN]
        + preferred[ProductTable.NAME_COLUMN]
        + preferred[ProductTable.DETAIL_COLUMN]
        == 112 + 170 + 260
    )
    table.close()


def test_product_table_reduces_flexible_columns_for_narrow_available_width():
    _qapp()
    table = ProductTable(_Controller())
    table.resize(900, 700)
    table.show()
    table.load_products(
        [
            Product(
                code="FB-300",
                name="Producto con un nombre amplio",
                description="Detalle técnico " * 15,
                category="Categoría de ejemplo",
                color_stock={
                    "Verde Oscuro": 12718,
                    "Azul": 3250,
                    "Rojo": 128,
                    "Negro": 420,
                },
                stock=16516,
            ),
        ],
    )
    QApplication.processEvents()

    header = table.horizontalHeader()
    total_width = sum(
        header.sectionSize(column)
        for column in range(table.columnCount())
        if not table.isColumnHidden(column)
    )
    assert table.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert total_width <= table.viewport().width()
    assert ProductTable.MIN_COLUMN_WIDTHS[ProductTable.IMAGE_COLUMN] <= (
        table.columnWidth(ProductTable.IMAGE_COLUMN)
    ) <= ProductImageDelegate.DEFAULT_SIZE
    assert table.columnWidth(ProductTable.DETAIL_COLUMN) >= (
        ProductTable.MIN_COLUMN_WIDTHS[ProductTable.DETAIL_COLUMN]
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

    item = table.item(0, ProductTable.STOCK_COLUMN)
    delegate = table.itemDelegateForColumn(ProductTable.STOCK_COLUMN)

    assert item is not None
    assert table.cellWidget(0, ProductTable.STOCK_COLUMN) is None
    assert isinstance(delegate, StockColorDelegate)
    assert item.data(StockColorDelegate.STOCK_ROLE) == [
        ("Azul", 528),
        ("Rojo", 124),
        ("Negro", 1686),
        ("Gris", 355),
    ]
    assert table.rowHeight(0) >= (
        4 * StockColorDelegate.MIN_LINE_HEIGHT
    )
    assert item.toolTip() == (
        "Azul: 528\n"
        "Rojo: 124\n"
        "Negro: 1686\n"
        "Gris: 355"
    )

    table.close()


def test_product_table_stock_color_rows_keep_reduced_horizontal_inset():
    assert StockColorDelegate.HORIZONTAL_PADDING == 5
    assert StockColorDelegate.TEXT_HORIZONTAL_PADDING == 4
    assert StockColorDelegate.TEXT_GAP == 4
    assert not hasattr(StockColorDelegate, "TEXT_PIXEL_SIZE")
    assert StockColorDelegate.MIN_LINE_HEIGHT == 24

    background, indicator = ProductTable._stock_color_style("Verde Oscuro")

    assert background == "#e6f4ee"
    assert indicator == "#2f9e72"


def test_product_table_stock_color_catalog_covers_all_site_variants():
    expected = {
        "Amarillo": "#f2c94c",
        "Amarillo Flurecente": "#efff00",
        "Azul": "#2f80ed",
        "Azul Claro": "#6eb6ff",
        "Azul Marino": "#123b6d",
        "Azul Oscuro": "#1d3f91",
        "Azulino": "#4f64d8",
        "Azulino Full": "#3046ff",
        "Bamboo": "#c8aa6e",
        "Black": "#1a1a1a",
        "Blanco": "#ffffff",
        "Brillante": "#c8d2dc",
        "Celeste": "#43a5e8",
        "Champagne": "#e7cfa1",
        "Crema": "#f4e7c3",
        "Cyan": "#00a9c7",
        "Dorado": "#d4af37",
        "Fucsia": "#ff1493",
        "Gris": "#8d98a5",
        "Kraft": "#b9895e",
        "Lila": "#c8a2c8",
        "Magenta": "#d600a9",
        "Manila": "#e3c66b",
        "Marron": "#795548",
        "Mate": "#6b7280",
        "Morado": "#9b51e0",
        "Naranja": "#f2994a",
        "Natural": "#cdb892",
        "Negro": "#343a40",
        "Negro Full": "#111111",
        "Pavonado": "#56616d",
        "Plateado": "#a7afb8",
        "Rojo": "#eb5757",
        "Rojo Full": "#ff1f1f",
        "Rosado": "#e66aa8",
        "Verde": "#4caf50",
        "Verde Claro": "#5cbd69",
        "Verde Oscuro": "#2f9e72",
        "Verde Oscuro Full": "#006b3c",
        "Verde Petroleo": "#006b5f",
        "Yellow": "#f2d21b",
    }

    assert len(expected) == 41
    for name, indicator in expected.items():
        _background, actual = ProductTable._stock_color_style(name)
        assert actual == indicator


def test_product_table_stock_color_variants_normalize_common_aliases():
    expected_aliases = {
        "amarillo fluorescente": "amarillo flurecente",
        "amarillo neon": "amarillo fluorescente",
        "fuchsia": "fucsia",
        "marron": "marrón",
        "verde limon": "verde limón",
        "azul electrico": "azul eléctrico",
        "verde petroleo": "verde petróleo",
        "azul petroleo": "azul petróleo",
    }

    for alias, reference in expected_aliases.items():
        _background, alias_indicator = ProductTable._stock_color_style(alias)
        _reference_background, reference_indicator = ProductTable._stock_color_style(
            reference,
        )
        assert alias_indicator == reference_indicator


def test_product_table_stock_color_variants_keep_magenta_and_fucsia_distinct():
    _background, magenta = ProductTable._stock_color_style("Magenta")
    _background, fucsia = ProductTable._stock_color_style("Fucsia")

    assert magenta != fucsia


def test_product_table_stock_width_shows_verde_oscuro_completely():
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
        StockColorDelegate.INDICATOR_SIZE
        + StockColorDelegate.TEXT_GAP
        + metrics.horizontalAdvance("Verde Oscuro")
        + StockColorDelegate.TEXT_GAP
        + metrics.horizontalAdvance("12,718")
        + (2 * StockColorDelegate.HORIZONTAL_PADDING)
    )

    header_width = (
        metrics.horizontalAdvance("Stock")
        + (2 * ProductTable.CONTENT_SIDE_PADDING)
    )
    assert table.columnWidth(ProductTable.STOCK_COLUMN) >= max(
        expected,
        header_width,
        1,
    )
    assert ProductImageDelegate.DEFAULT_SIZE == ProductTable.DEFAULT_IMAGE_CELL_SIZE
    assert ProductTable.IMAGE_SIZE == 144  # tamaño del preview en ProductDialog

    table.close()


def test_product_table_uses_reference_font_and_color():
    _qapp()

    table = ProductTable(_Controller())

    assert table.font().family() == "Segoe UI"
    assert table.font().pixelSize() == 13
    assert ProductTable.TABLE_TEXT_COLOR == "#173f6d"
    assert "font-family: \"Segoe UI\";" in table.styleSheet()
    assert "font-size: 13px;" in table.styleSheet()
    assert "font-size: 16px;" in table.styleSheet()
    assert "min-height: 56px;" in table.styleSheet()
    assert table.horizontalHeader().minimumHeight() == 56
    assert "selection-background-color: #fbfdff;" in table.styleSheet()
    assert "color: #173f6d;" in table.styleSheet()

    table.close()


def test_product_table_reuses_cached_widths_when_window_resizes():
    _qapp()

    table = _TrackingProductTable(_Controller())
    table.resize(1400, 700)
    table.show()
    table.load_products(
        [
            Product(
                code="FB-6006",
                name="Producto con nombre suficientemente largo",
                description="Detalle " * 20,
                category="Categoria de prueba",
                color_stock={"Verde Oscuro": 12718},
            ),
        ],
    )
    QApplication.processEvents()

    assert table.resize_to_contents_calls == 0
    assert table._preferred_widths_cache is not None
    preferred_widths = table._preferred_widths_cache.copy()

    table.resize(2200, 700)
    QApplication.processEvents()

    assert table.resize_to_contents_calls == 0
    assert table._preferred_widths_cache == preferred_widths

    table._sort_states = {
        ProductTable.NAME_COLUMN: Qt.SortOrder.DescendingOrder,
    }
    table._apply_current_sort()
    QApplication.processEvents()

    assert table._preferred_widths_cache is None

    table.resize(2100, 700)
    QApplication.processEvents()

    assert table.resize_to_contents_calls == 0
    assert table._preferred_widths_cache is not None

    table.load_products(
        [
            Product(
                code="FB-6007",
                name="Producto todavía más largo " * 4,
                description="Detalle nuevo " * 30,
                category="Enmicadoras / Laminadoras",
            ),
        ],
    )
    QApplication.processEvents()

    assert table.resize_to_contents_calls == 0
    assert table._preferred_widths_cache is not None

    table.close()


def test_product_table_stock_column_shares_extra_window_width():
    _qapp()

    table = ProductTable(_Controller())
    table.resize(1400, 700)
    table.show()
    product = Product(
        code="FB-6005",
        name="Producto",
        color_stock={"Verde Oscuro": 12718},
    )
    table.load_products([product])
    QApplication.processEvents()

    initial_width = table.columnWidth(ProductTable.STOCK_COLUMN)

    table.resize(2200, 700)
    QApplication.processEvents()

    assert table.columnWidth(ProductTable.STOCK_COLUMN) > initial_width

    table.close()


def test_price_delegate_paints_long_amount_on_one_line():
    _qapp()
    table = ProductTable(_Controller())
    table.resize(900, 700)
    table.show()
    table.load_products([
        Product(
            code="FB-8010",
            name="Precio largo",
            price_sample=123456789.0,
        ),
    ])
    QApplication.processEvents()

    index = table.model().index(0, ProductTable.PRICE_SAMPLE_COLUMN)
    delegate = table.itemDelegateForColumn(ProductTable.PRICE_SAMPLE_COLUMN)
    assert isinstance(delegate, PriceDelegate)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 72, 70)
    option.widget = table
    option.font = table.font()
    option.palette = table.palette()
    pixmap = QPixmap(option.rect.size())
    pixmap.fill(QColor("white"))
    painter = QPainter(pixmap)
    delegate.paint(painter, option, index)
    painter.end()

    image = pixmap.toImage()
    ink_rows = []
    for y in range(image.height()):
        for x in range(image.width()):
            pixel = image.pixelColor(x, y)
            if pixel.red() < 90 and pixel.green() < 130 and pixel.blue() < 190:
                ink_rows.append(y)
                break
    assert ink_rows
    line_bands = 1
    for previous, current in pairwise(ink_rows):
        if current - previous > 3:
            line_bands += 1
    assert line_bands == 1
    table.close()


def test_price_columns_are_compact_and_currency_is_not_editable():
    _qapp()
    table = ProductTable(_Controller())
    product = Product(
        code="FB-8001",
        name="Producto",
        price_sample=23.8,
        price_hundred=240,
        price_thousand=2100,
    )
    table.resize(1700, 700)
    table.show()
    table.load_products([product])
    QApplication.processEvents()

    assert ProductTable.MIN_COLUMN_WIDTHS[ProductTable.PRICE_SAMPLE_COLUMN] == 72
    assert ProductTable.MIN_COLUMN_WIDTHS[ProductTable.PRICE_HUNDRED_COLUMN] == 72
    assert ProductTable.MIN_COLUMN_WIDTHS[ProductTable.PRICE_THOUSAND_COLUMN] == 72
    assert table.columnWidth(ProductTable.PRICE_SAMPLE_COLUMN) > 88
    assert table.columnWidth(ProductTable.PRICE_HUNDRED_COLUMN) > 88
    assert table.columnWidth(ProductTable.PRICE_THOUSAND_COLUMN) > 88

    index = table.model().index(0, ProductTable.PRICE_HUNDRED_COLUMN)
    delegate = table.itemDelegateForColumn(ProductTable.PRICE_HUNDRED_COLUMN)
    assert isinstance(delegate, PriceDelegate)
    editor = delegate.createEditor(table, None, index)
    delegate.setEditorData(editor, index)
    currency = editor.findChild(QLabel)
    number = editor.findChild(QLineEdit)

    assert currency is not None
    assert currency.text() == "S/"
    assert number is not None
    assert number.text() == "240.00"

    number.setText("321.50")
    delegate.setModelData(editor, table.model(), index)
    assert currency.text() == "S/"
    assert table.item(0, ProductTable.PRICE_HUNDRED_COLUMN).text() == "S/ 321.50"

    editor.close()
    table.close()


def test_detail_formats_attributes_without_color_line_or_trailing_periods():
    _qapp()
    description = (
        "Color: Azul. Potencia: 560W. Dimensiones: 30*34*33cm. "
        "Peso Unitario: 5.8 Kg.Uso Recomendado: Sublimado en tazas 11Oz. "
        "Empaque Individual: Esponja + Caja de carton. Cantidad por Caja: 1 Pza. "
        "Dimensiones Caja: 45*38*43cm. Cubicaje por Caja: 0.0735 m³/CBM "
        "Peso neto por caja: 5.8 Kg. Peso bruto por caja: 6.9 Kg."
    )
    table = ProductTable(_Controller())
    table.load_products(
        [
            Product(
                code="FB-9001",
                name="Plancha",
                description=description,
                color_stock={"Azul": 3},
                stock=3,
            ),
        ],
    )
    QApplication.processEvents()

    item = table.item(0, ProductTable.DETAIL_COLUMN)
    assert item is not None
    assert item.text().splitlines() == [
        "Potencia: 560W",
        "Dimensiones: 30*34*33cm",
        "Peso Unitario: 5.8 Kg",
        "Uso Recomendado: Sublimado en tazas 11Oz",
        "Empaque Individual: Esponja + Caja de cartón",
        "Cantidad por Caja: 1 Pza",
        "Dimensiones Caja: 45*38*43cm",
        "Cubicaje por Caja: 0.0735 m³/CBM",
        "Peso neto por caja: 5.8 Kg",
        "Peso bruto por caja: 6.9 Kg",
    ]
    assert all(not line.endswith(".") for line in item.text().splitlines())
    assert item.textAlignment() & Qt.AlignmentFlag.AlignVCenter
    assert item.textAlignment() & Qt.AlignmentFlag.AlignLeft
    expected_detail_height = (
        ProductDetailDelegate.content_height(
            item.text(),
            table.font(),
            max(
                table.columnWidth(ProductTable.DETAIL_COLUMN)
                - (2 * ProductDetailDelegate.HORIZONTAL_PADDING),
                1,
            ),
        )
        + (2 * ProductDetailDelegate.VERTICAL_PADDING)
    )
    assert table.rowHeight(0) >= expected_detail_height

    table.close()


def test_detail_table_filters_product_color_and_stale_html_without_stock_map():
    _qapp()
    product = Product(
        code="TEST-COLOR-STOCK-HTML",
        name="Producto con colores",
        description=(
            "Color: Azul. "
            "Descripción: Disponible en varios colores. "
            "Color de tinta: Negro. Material: ABS."
        ),
        description_html=(
            "<ul>"
            "<li><strong>Color:</strong> Azul.</li>"
            "<li><strong>Descripción:</strong> Disponible en varios colores.</li>"
            "<li><strong>Color de tinta:</strong> Negro.</li>"
            "<li><strong>Material:</strong> ABS.</li>"
            "</ul>"
        ),
    )
    table = ProductTable(_Controller())
    table.load_products([product])
    QApplication.processEvents()

    item = table.item(0, ProductTable.DETAIL_COLUMN)
    assert item is not None
    assert not item.data(ProductDetailDelegate.DETAIL_HTML_ROLE)
    assert item.text().splitlines() == [
        "Color de tinta: Negro",
        "Material: ABS",
    ]

    table.close()


def test_detail_removes_fields_that_repeat_product_row_data():
    _qapp()
    table = ProductTable(_Controller())
    table.load_products(
        [
            Product(
                code="FB-9010",
                name="Plancha",
                category="Oficina",
                stock=5,
                description=(
                    "Código: FB-9010. Producto: Plancha. Categoría: Oficina. "
                    "Stock: 5. Potencia: 500W."
                ),
            ),
        ],
    )
    QApplication.processEvents()

    item = table.item(0, ProductTable.DETAIL_COLUMN)
    assert item is not None
    assert item.text() == "Potencia: 500W"

    table.close()


def test_detail_table_preserves_summary_description_and_removes_only_color():
    _qapp()
    table = ProductTable(_Controller())
    table.load_products(
        [
            Product(
                code="FB-2107",
                name="Set de Vino con Juego de Ajedrez",
                description=(
                    "Descripción: texto promocional. Color: Azul. "
                    "Contiene: Tapón y sacacorchos. "
                    "Presentación: Caja. "
                    "Medidas del Estuche: 15 cm x 17 cm x 4.5 cm."
                ),
            ),
        ],
    )
    QApplication.processEvents()

    item = table.item(0, ProductTable.DETAIL_COLUMN)
    assert item is not None
    assert item.text().splitlines() == [
        "Descripción: texto promocional",
        "Contiene: Tapón y sacacorchos",
        "Presentación: Caja",
        "Medidas del Estuche: 15 cm x 17 cm x 4.5 cm",
    ]

    table.close()


def test_detail_formatter_splits_fb2107_fb2043_and_herra03_fields():
    cases = (
        (
            "FB-2107",
            (
                "Descripción: texto promocional. Color: Azul. "
                "Contiene: Tapón y sacacorchos. Presentación: Caja. "
                "Medidas del Estuche: 15 cm x 17 cm x 4.5 cm."
            ),
            [
                "Descripción: texto promocional",
                "Contiene: Tapón y sacacorchos",
                "Presentación: Caja",
                "Medidas del Estuche: 15 cm x 17 cm x 4.5 cm",
            ],
        ),
        (
            "FB2043",
            (
                "Calidad Superior: Tinta de alta calidad. "
                "Compatibilidad Confiable: Impresoras compatibles. "
                "Procedencia Coreana: Elaborada en Corea. "
                "Facilidad de Uso: Recarga sencilla."
            ),
            [
                "Calidad Superior: Tinta de alta calidad",
                "Compatibilidad Confiable: Impresoras compatibles",
                "Procedencia Coreana: Elaborada en Corea",
                "Facilidad de Uso: Recarga sencilla",
            ],
        ),
        (
            "HERRA-03",
            (
                "Levantamiento de materiales: Retira vinilo. "
                "Proyectos de manualidades: Uso creativo. "
                "Aplicaciones de vinilo: Posiciona adhesivos. "
                "Trabajo en scrapbooking: Manipula recortes."
            ),
            [
                "Levantamiento de materiales: Retira vinilo",
                "Proyectos de manualidades: Uso creativo",
                "Aplicaciones de vinilo: Posiciona adhesivos",
                "Trabajo en scrapbooking: Manipula recortes",
            ],
        ),
        (
            "OL381S",
            (
                "Número de rodillos: 2. Ancho de entrada: 330 mm. "
                "Espesor máximo de laminación: 0.5 mm. Soporta: 80 a 125 micrones. "
                "Tiempo de calentamiento: 3 a 5 minutos. "
                "Velocidad de laminación: 250 mm/min. "
                "Cortadora con 3 tipos de corte: Recto, Ondulado y Perforado."
            ),
            [
                "Número de rodillos: 2",
                "Ancho de entrada: 330 mm",
                "Espesor máximo de laminación: 0.5 mm",
                "Soporta: 80 a 125 micrones",
                "Tiempo de calentamiento: 3 a 5 minutos",
                "Velocidad de laminación: 250 mm/min",
                "Cortadora con 3 tipos de corte: Recto, Ondulado y Perforado",
            ],
        ),
        (
            "MITS-C-CK-D868",
            (
                "Tamaño de impresión (cm): 10 x 15. "
                "Rollos por caja: 2. Impresiones por rollo: 300. "
                "Válido para impresoras: CP-D90DW-P, CP-D80DW. "
                "Opciones de acabado: Brillante y mate."
            ),
            [
                "Tamaño de impresión (cm): 10 x 15",
                "Rollos por caja: 2",
                "Impresiones por rollo: 300",
                "Válido para impresoras: CP-D90DW-P, CP-D80DW",
                "Opciones de acabado: Brillante y mate",
            ],
        ),
    )

    for code, description, expected in cases:
        product = Product(
            code=code,
            name="Producto de prueba",
            description=description,
        )
        assert ProductTable._format_detail(product).splitlines() == expected


def test_detail_removes_color_line_when_variants_are_visible_in_stock():
    _qapp()
    colors = [
        "Azul", "Blanco", "Celeste", "Morado", "Naranja", "Negro",
        "Rojo", "Rosado", "Verde Claro", "Verde Oscuro", "Amarillo",
    ]
    description = (
        "Color: " + ", ".join(colors) + ". "
        "Material: Poliuretano. Dimensiones: 63mm. "
        "Peso Unitario: 19.4 G. Uso Recomendado: Antiestrés, Promocional. "
        "Empaque Individual: Bolsa de polietileno. Cantidad por Caja: 250 Pza. "
        "Dimensiones Caja: 53*34*33cm."
    )
    table = ProductTable(_Controller())
    table.load_products(
        [
            Product(
                code="FB-4009",
                name="Antiestrés",
                stock=len(colors),
                color_stock={color: 1 for color in colors},
                description=description,
            ),
        ],
    )
    QApplication.processEvents()

    detail = table.item(0, ProductTable.DETAIL_COLUMN)
    assert detail is not None
    assert detail.text().splitlines() == [
        "Material: Poliuretano",
        "Dimensiones: 63mm",
        "Peso Unitario: 19.4 G",
        "Uso Recomendado: Antiestrés, Promocional",
        "Empaque Individual: Bolsa de polietileno",
        "Cantidad por Caja: 250 Pza",
        "Dimensiones Caja: 53*34*33cm",
    ]
    table.close()


def test_product_table_stabilizes_code_and_price_widths_after_value_changes():
    _qapp()
    table = ProductTable(_Controller())
    table.resize(1600, 700)
    table.show()
    table.load_products(
        [
            Product(
                code="IKIOSK-ESTANDAR",
                name="Producto",
                description="Detalle",
                price_sample=5,
                price_hundred=50,
                price_thousand=500,
            ),
        ],
    )
    QApplication.processEvents()
    fixed_widths = {
        column: table.columnWidth(column)
        for column in (
            ProductTable.CODE_COLUMN,
            ProductTable.PRICE_SAMPLE_COLUMN,
            ProductTable.PRICE_HUNDRED_COLUMN,
            ProductTable.PRICE_THOUSAND_COLUMN,
        )
    }

    code_item = table.item(0, ProductTable.CODE_COLUMN)
    price_item = table.item(0, ProductTable.PRICE_HUNDRED_COLUMN)
    assert code_item is not None and price_item is not None
    code_item.setText("FB-999999999999999999")
    price_item.setText("S/ 999,999,999.99")
    table._preferred_widths_cache = None
    table._fit_columns_to_content()
    QApplication.processEvents()

    assert {
        column: table.columnWidth(column)
        for column in fixed_widths
    } == fixed_widths
    table.close()


def test_products_are_sorted_by_category_then_product_name_at_startup():
    _qapp()
    table = ProductTable(_Controller())
    table.load_products(
        [
            Product(code="FB-12", name="Producto 12", category="Oficina 10"),
            Product(code="FB-3", name="Zeta", category="Oficina 2"),
            Product(code="FB-2", name="Producto 2", category="Antiestrés"),
            Product(code="FB-11", name="Alfa", category="Oficina 2"),
        ],
    )

    assert [
        table.item(row, ProductTable.CATEGORY_COLUMN).text()
        for row in range(table.rowCount())
    ] == ["Antiestrés", "Oficina 2", "Oficina 2", "Oficina 10"]
    assert [
        table.item(row, ProductTable.CODE_COLUMN).text()
        for row in range(table.rowCount())
    ] == ["FB-2", "FB-11", "FB-3", "FB-12"]
    table.close()


def test_stock_and_price_headers_cycle_ascending_descending_and_normal():
    _qapp()
    products = [
        Product(
            code="FB-501",
            name="Producto A",
            category="Personales",
            stock=20,
            price_sample=2,
            price_hundred=200,
            price_thousand=2000,
        ),
        Product(
            code="FB-502",
            name="Producto B",
            category="Oficina",
            stock=5,
            price_sample=5,
            price_hundred=50,
            price_thousand=500,
        ),
        Product(
            code="FB-503",
            name="Producto C",
            category="Antiestrés",
            stock=10,
            price_sample=1,
            price_hundred=100,
            price_thousand=1000,
        ),
    ]
    cases = [
        (ProductTable.STOCK_COLUMN, ["FB-502", "FB-503", "FB-501"]),
        (ProductTable.PRICE_SAMPLE_COLUMN, ["FB-503", "FB-501", "FB-502"]),
        (ProductTable.PRICE_HUNDRED_COLUMN, ["FB-502", "FB-503", "FB-501"]),
        (ProductTable.PRICE_THOUSAND_COLUMN, ["FB-502", "FB-503", "FB-501"]),
    ]

    for column, ascending_codes in cases:
        table = ProductTable(_Controller())
        table.resize(1500, 700)
        table.show()
        table.load_products(products)
        QApplication.processEvents()

        table._handle_header_click(column)
        QApplication.processEvents()
        assert [
            table.item(row, ProductTable.CODE_COLUMN).text()
            for row in range(table.rowCount())
        ] == ascending_codes
        assert table._sort_states == {
            column: Qt.SortOrder.AscendingOrder,
        }

        table._handle_header_click(column)
        QApplication.processEvents()
        assert [
            table.item(row, ProductTable.CODE_COLUMN).text()
            for row in range(table.rowCount())
        ] == list(reversed(ascending_codes))
        assert table._sort_states == {
            column: Qt.SortOrder.DescendingOrder,
        }

        table._handle_header_click(column)
        QApplication.processEvents()
        assert [
            table.item(row, ProductTable.CODE_COLUMN).text()
            for row in range(table.rowCount())
        ] == ["FB-503", "FB-502", "FB-501"]
        assert table._sort_states == {
            ProductTable.CATEGORY_COLUMN: Qt.SortOrder.AscendingOrder,
        }
        table.close()


def test_third_sort_click_preserves_active_product_filter():
    _qapp()
    products = [
        Product(code="FB-610", name="Uno", category="Personales", stock=20),
        Product(code="FB-611", name="Dos", category="Oficina", stock=5),
        Product(code="FB-612", name="Tres", category="Antiestrés", stock=10),
    ]
    table = ProductTable(_Controller())
    table.resize(1500, 700)
    table.show()
    table.load_products(products)
    QApplication.processEvents()

    visible_products = [products[0], products[1]]
    table.show_only_products(visible_products)
    expected_visible_keys = {id(product) for product in visible_products}

    for _ in range(3):
        table._handle_header_click(ProductTable.STOCK_COLUMN)
        QApplication.processEvents()

    assert table._visible_product_keys == expected_visible_keys
    visible_keys = {
        id(table._rendered_products[row])
        for row in range(table.rowCount())
        if not table.isRowHidden(row)
    }
    assert visible_keys == expected_visible_keys
    assert table._sort_states == {
        ProductTable.CATEGORY_COLUMN: Qt.SortOrder.AscendingOrder,
    }
    table.close()


def test_main_image_size_remains_fixed_when_cell_width_changes(tmp_path: Path):
    _qapp()
    image_path = tmp_path / "portrait.png"
    pixmap = QPixmap(100, 200)
    assert pixmap.save(str(image_path))

    base_size = ProductImageDelegate.main_image_size(str(image_path))
    width_argument_size = ProductImageDelegate.main_image_size(str(image_path), 216)

    assert base_size == QSize(144, 288)
    assert width_argument_size == base_size
    assert ProductImageDelegate.main_image_height(str(image_path)) == 288
    assert ProductImageDelegate.main_image_height(str(image_path), 216) == 288


def test_thumbnail_tiles_keep_fixed_height_when_cell_width_changes():
    base_tiles, *_ = ProductImageDelegate.thumbnail_layout(
        QRect(0, 0, 144, 200), 2, main_height=144,
    )
    wider_tiles, *_ = ProductImageDelegate.thumbnail_layout(
        QRect(0, 0, 216, 300), 2, main_height=144,
    )

    assert base_tiles[0][1].height() == ProductImageDelegate.THUMBNAIL_HEIGHT
    assert wider_tiles[0][1].height() == ProductImageDelegate.THUMBNAIL_HEIGHT


def test_product_images_scale_and_center_inside_available_cell_area(tmp_path: Path):
    _qapp()
    image_path = tmp_path / "portrait.png"
    assert QPixmap(100, 200).save(str(image_path))

    portrait_rect = ProductImageDelegate.fitted_image_rect(
        QSize(100, 200),
        QRect(10, 20, 160, 100),
    )
    assert portrait_rect == QRect(65, 20, 50, 100)

    landscape_rect = ProductImageDelegate.fitted_image_rect(
        QSize(320, 180),
        QRect(10, 20, 160, 100),
    )
    assert landscape_rect == QRect(10, 25, 160, 90)


def test_row_height_expands_for_tall_primary_image_and_alternative_strip(
    tmp_path: Path,
):
    _qapp()
    main_path = tmp_path / "main-portrait.png"
    alt_path = tmp_path / "alt-landscape.png"
    assert QPixmap(100, 200).save(str(main_path))
    assert QPixmap(200, 100).save(str(alt_path))
    gallery = [
        {"url": "https://example.test/main.png", "image_path": str(main_path)},
        {"url": "https://example.test/alt.png", "image_path": str(alt_path)},
    ]
    table = ProductTable(_Controller())
    table.resize(1500, 700)
    table.show()
    table.load_products([
        Product(
            code="FB-144",
            name="Imagen vertical",
            image_path=str(main_path),
            gallery_images=gallery,
        ),
    ])
    QApplication.processEvents()
    code_item = table.item(0, ProductTable.CODE_COLUMN)
    assert code_item is not None
    assert code_item.textAlignment() & Qt.AlignmentFlag.AlignHCenter
    assert code_item.textAlignment() & Qt.AlignmentFlag.AlignVCenter
    expected_image_content = (
        ProductImageDelegate.main_image_height(str(main_path))
        + ProductImageDelegate.THUMBNAIL_GAP
        + ProductImageDelegate.THUMBNAIL_STRIP_HEIGHT
    )
    assert table.rowHeight(0) == (
        expected_image_content
        + (2 * ProductImageDelegate.CELL_VERTICAL_PADDING)
        + ProductImageDelegate.GRIDLINE_BOTTOM_ALLOWANCE
    )
    assert table.rowHeight(0) >= ProductTable.VERY_TALL_ROW_THRESHOLD
    table.close()


def test_thumbnail_layout_centers_alternatives_and_shows_four_tiles():
    rect = QRect(10, 20, 160, 360)
    tiles, left_arrow, right_arrow, strip_top = ProductImageDelegate.thumbnail_layout(
        rect, 2, main_height=288, active_index=0
    )
    assert [image_index for image_index, _tile in tiles] == [0, 1]
    assert left_arrow is None and right_arrow is None
    assert strip_top == rect.top() + 288
    assert tiles[0][1].left() > rect.left()
    assert tiles[-1][1].right() < rect.right()
    assert all(
        following.left() == previous.right() + 1
        for previous, following in pairwise([tile for _, tile in tiles])
    )
    assert abs(
        (tiles[0][1].left() + tiles[-1][1].right()) / 2 - rect.center().x()
    ) <= 1

    tiles, left_arrow, right_arrow, _ = ProductImageDelegate.thumbnail_layout(
        rect, 6, 1, main_height=288
    )
    assert [image_index for image_index, _tile in tiles] == [1, 2, 3, 4]
    assert left_arrow is not None and right_arrow is not None


def test_latest_sort_takes_priority_and_third_click_restores_default_order():
    _qapp()
    products = [
        Product(code="FB-701", name="Beta", category="Artículos de Escritorio", stock=2, price_sample=10),
        Product(code="FB-702", name="Alpha", category="Oficina", stock=1, price_sample=10),
        Product(code="FB-703", name="Gamma", category="Antiestrés", stock=3, price_sample=5),
    ]
    table = ProductTable(_Controller())
    table.resize(1500, 700)
    table.show()
    table.load_products(products)
    QApplication.processEvents()

    default_order = ["FB-703", "FB-701", "FB-702"]
    assert [
        table.item(row, ProductTable.CODE_COLUMN).text()
        for row in range(table.rowCount())
    ] == default_order

    table._handle_header_click(ProductTable.STOCK_COLUMN)
    QApplication.processEvents()
    assert [
        table.item(row, ProductTable.CODE_COLUMN).text()
        for row in range(table.rowCount())
    ] == ["FB-702", "FB-701", "FB-703"]

    # Clicking Price replaces Stock as the active sort, rather than retaining it
    # as a secondary key. The non-sort filters are handled separately.
    table._handle_header_click(ProductTable.PRICE_SAMPLE_COLUMN)
    QApplication.processEvents()
    assert table._sort_states == {
        ProductTable.PRICE_SAMPLE_COLUMN: Qt.SortOrder.AscendingOrder,
    }
    assert [
        table.item(row, ProductTable.CODE_COLUMN).text()
        for row in range(table.rowCount())
    ] == ["FB-703", "FB-701", "FB-702"]

    table._handle_header_click(ProductTable.PRICE_SAMPLE_COLUMN)
    QApplication.processEvents()
    assert [
        table.item(row, ProductTable.CODE_COLUMN).text()
        for row in range(table.rowCount())
    ] == ["FB-701", "FB-702", "FB-703"]

    table._handle_header_click(ProductTable.PRICE_SAMPLE_COLUMN)
    QApplication.processEvents()
    assert table._sort_states == {
        ProductTable.CATEGORY_COLUMN: Qt.SortOrder.AscendingOrder,
    }
    assert [
        table.item(row, ProductTable.CODE_COLUMN).text()
        for row in range(table.rowCount())
    ] == default_order
    table.close()


def test_initial_product_order_uses_full_category_names_alphabetically():
    _qapp()
    products = [
        Product(
            code="FB-801",
            name="Producto Escritorio",
            category="Artículos de Escritorio",
        ),
        Product(
            code="FB-802",
            name="Producto Antiestrés",
            category="Antiestrés",
        ),
        Product(
            code="FB-803",
            name="Producto Oficina",
            category="Artículos de Oficina",
        ),
    ]
    table = ProductTable(_Controller())
    table.resize(1500, 700)
    table.show()
    table.load_products(products)
    QApplication.processEvents()

    assert [
        table.item(row, ProductTable.CODE_COLUMN).text()
        for row in range(table.rowCount())
    ] == ["FB-802", "FB-801", "FB-803"]
    assert [
        table.item(row, ProductTable.CATEGORY_COLUMN).text()
        for row in range(table.rowCount())
    ] == [
        "Antiestrés",
        "Artículos de Escritorio",
        "Artículos de Oficina",
    ]
    assert [
        ProductTable._format_categories(product.category)
        for product in products
    ] == [
        "Artículos de Escritorio",
        "Antiestrés",
        "Artículos de Oficina",
    ]
    table.close()


def test_detail_cell_is_vertically_centered_and_left_aligned():
    _qapp()
    table = ProductTable(_Controller())
    table.resize(1500, 700)
    table.show()
    table.load_products(
        [
            Product(
                code="FB-520",
                name="Producto",
                description="Detalle técnico",
                category="Oficina",
            ),
        ],
    )
    QApplication.processEvents()

    item = table.item(0, ProductTable.DETAIL_COLUMN)
    assert item is not None
    assert item.textAlignment() & Qt.AlignmentFlag.AlignVCenter
    assert item.textAlignment() & Qt.AlignmentFlag.AlignLeft
    assert ProductImageDelegate.CELL_HORIZONTAL_PADDING == 1
    assert ProductImageDelegate.CELL_VERTICAL_PADDING == 1
    assert ProductImageDelegate.cell_content_rect(
        QRect(5, 6, 146, 162),
    ) == QRect(6, 7, 144, 160)
    assert ProductNameCategoryDelegate.HORIZONTAL_PADDING == 8
    assert ProductNameCategoryDelegate.VERTICAL_PADDING == 8
    assert ProductDetailDelegate.HORIZONTAL_PADDING == 8
    assert ProductDetailDelegate.VERTICAL_PADDING == 8
    assert ProductImageDelegate.MAIN_IMAGE_WIDTH == 144
    assert ProductImageDelegate.THUMBNAIL_HEIGHT == 34
    assert ProductImageDelegate.THUMBNAIL_STRIP_HEIGHT >= (
        ProductImageDelegate.THUMBNAIL_HEIGHT
    )
    expected_detail_height = (
        ProductDetailDelegate.content_height(
            item.text(),
            table.font(),
            max(
                table.columnWidth(ProductTable.DETAIL_COLUMN)
                - (2 * ProductDetailDelegate.HORIZONTAL_PADDING),
                1,
            ),
        )
        + (2 * ProductDetailDelegate.VERTICAL_PADDING)
    )
    assert table.rowHeight(0) >= expected_detail_height

    table.close()


def test_detail_delegate_centers_short_text_and_insets_tall_text():
    assert ProductDetailDelegate._vertical_text_offset(100, 40) == 30.0
    assert (
        ProductDetailDelegate._vertical_text_offset(60, 80)
        == float(ProductDetailDelegate.VERTICAL_PADDING)
    )


def test_row_height_tracks_tallest_text_or_image_and_skips_padding_for_tall_rows(
    tmp_path: Path,
):
    _qapp()
    landscape_path = tmp_path / "wide.png"
    portrait_path = tmp_path / "tall.png"
    assert QPixmap(320, 80).save(str(landscape_path))
    assert QPixmap(100, 400).save(str(portrait_path))

    table = ProductTable(_Controller())
    table.resize(1500, 700)
    table.show()
    table.load_products(
        [
            Product(
                code="FB-811",
                name="Producto con imagen panorámica",
                image_path=str(landscape_path),
            ),
            Product(
                code="FB-812",
                name="Producto con imagen vertical",
                image_path=str(portrait_path),
            ),
        ],
    )
    QApplication.processEvents()

    landscape_content = ProductImageDelegate.main_image_height(str(landscape_path))
    landscape_name = table.item(0, ProductTable.NAME_COLUMN)
    landscape_category = table.item(0, ProductTable.CATEGORY_COLUMN)
    assert landscape_name is not None
    assert landscape_category is not None
    landscape_text_height = ProductNameCategoryDelegate.content_height(
        landscape_name.text(),
        landscape_category.text(),
        table.font(),
        table.columnWidth(ProductTable.NAME_COLUMN),
    )
    assert table.rowHeight(0) == max(
        landscape_content
        + (2 * ProductImageDelegate.CELL_VERTICAL_PADDING)
        + ProductImageDelegate.GRIDLINE_BOTTOM_ALLOWANCE,
        landscape_text_height,
    )

    portrait_content = ProductImageDelegate.main_image_height(str(portrait_path))
    assert portrait_content >= ProductTable.VERY_TALL_ROW_THRESHOLD
    assert table.rowHeight(1) == (
        portrait_content
        + (2 * ProductImageDelegate.CELL_VERTICAL_PADDING)
        + ProductImageDelegate.GRIDLINE_BOTTOM_ALLOWANCE
    )
    assert table.rowHeight(1) > table.rowHeight(0)
    table.close()


def test_detail_delegate_compacts_spacing_between_attribute_lines():
    _qapp()
    table = ProductTable(_Controller())
    delegate = table.itemDelegateForColumn(ProductTable.DETAIL_COLUMN)
    assert isinstance(delegate, ProductDetailDelegate)
    text = "\n".join(
        f"Atributo {index}: valor" for index in range(8)
    )
    normal_height = (
        QFontMetricsF(table.font()).height()
        * len(text.splitlines())
    )

    compact_height = delegate.content_height(
        text,
        table.font(),
        600,
    )

    assert compact_height < normal_height
    table.close()


def test_stock_by_color_cell_opens_multiline_editor_for_color_and_quantity():
    _qapp()
    table = ProductTable(_Controller())
    table.resize(1800, 700)
    table.show()
    table.load_products(
        [
            Product(
                code="FB-8002",
                name="Producto",
                stock=15,
                color_stock={"Rojo": 10, "Azul": 5},
            ),
        ],
    )
    QApplication.processEvents()

    index = table.model().index(0, ProductTable.STOCK_COLUMN)
    delegate = table.itemDelegateForColumn(ProductTable.STOCK_COLUMN)
    assert isinstance(delegate, StockColorDelegate)
    editor = delegate.createEditor(table, None, index)
    delegate.setEditorData(editor, index)

    assert isinstance(editor, QPlainTextEdit)
    assert editor.toPlainText().splitlines() == ["Rojo: 10", "Azul: 5"]

    editor.close()
    table.close()


def test_tooltip_keeps_cell_width_and_text_alignment_when_filtered():
    left = ProductTable._cell_tooltip_html(
        "Detalle de producto " * 40,
        128,
        int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
    )
    centered = ProductTable._cell_tooltip_html(
        "Precio de muestra",
        84,
        int(Qt.AlignmentFlag.AlignCenter),
    )

    assert 'width="128"' in left
    assert "width:128px" in left
    assert 'align="left"' in left
    assert "word-wrap:break-word" in left
    assert 'width="84"' in centered
    assert 'align="center"' in centered


def test_changing_selected_row_resets_temporary_primary_images(tmp_path: Path):
    _qapp()
    paths = [tmp_path / f"reset-{index}.png" for index in range(3)]
    for path in paths:
        pixmap = QPixmap(120, 80)
        assert pixmap.save(str(path))
    products = [
        Product(
            code="FB-9001",
            name="Primero",
            image_path=str(paths[0]),
            gallery_images=[
                {"image_path": str(paths[0]), "url": "https://example.test/0"},
                {"image_path": str(paths[1]), "url": "https://example.test/1"},
            ],
        ),
        Product(
            code="FB-9002",
            name="Segundo",
            image_path=str(paths[2]),
            gallery_images=[
                {"image_path": str(paths[2]), "url": "https://example.test/2"},
                {"image_path": str(paths[1]), "url": "https://example.test/1b"},
            ],
        ),
    ]
    table = ProductTable(_Controller())
    table.resize(1500, 700)
    table.show()
    table.load_products(products)
    QApplication.processEvents()

    table.setCurrentCell(0, ProductTable.IMAGE_COLUMN)
    table._set_active_image(0, 1)
    assert table.item(0, ProductTable.IMAGE_COLUMN).data(
        ProductImageDelegate.ACTIVE_INDEX_ROLE,
    ) == 1

    table.setCurrentCell(1, ProductTable.CODE_COLUMN)
    QApplication.processEvents()

    assert table.item(0, ProductTable.IMAGE_COLUMN).data(
        ProductImageDelegate.ACTIVE_INDEX_ROLE,
    ) == 0
    assert table.item(1, ProductTable.IMAGE_COLUMN).data(
        ProductImageDelegate.ACTIVE_INDEX_ROLE,
    ) == 0
    table.close()


def test_visible_columns_share_extra_width_when_the_table_grows():
    _qapp()
    table = ProductTable(_Controller())
    table.resize(1400, 700)
    table.show()
    table.load_products(
        [
            Product(
                code="FB-8003",
                name="Producto con nombre largo",
                description="Detalle del producto " * 8,
                category="Oficina",
            ),
        ],
    )
    QApplication.processEvents()
    table.set_even_column_distribution(True)
    QApplication.processEvents()
    visible_columns = (
        ProductTable.CODE_COLUMN,
        ProductTable.NAME_COLUMN,
        ProductTable.DETAIL_COLUMN,
        ProductTable.STOCK_COLUMN,
        ProductTable.PRICE_SAMPLE_COLUMN,
        ProductTable.PRICE_HUNDRED_COLUMN,
        ProductTable.PRICE_THOUSAND_COLUMN,
    )
    image_width = table.columnWidth(ProductTable.IMAGE_COLUMN)
    first_widths = {
        column: table.columnWidth(column)
        for column in visible_columns
    }

    table.resize(2200, 700)
    QApplication.processEvents()

    assert table.columnWidth(ProductTable.IMAGE_COLUMN) == image_width
    width_increments = {
        column: table.columnWidth(column) - width
        for column, width in first_widths.items()
    }
    assert all(increment > 0 for increment in width_increments.values())
    growth_ratios = [
        width_increments[column] / width
        for column, width in first_widths.items()
    ]
    assert max(growth_ratios) - min(growth_ratios) < 0.02
    table.close()


def test_detail_format_preserves_complete_final_box_weight_without_color_line():
    product = Product(
        code="FB-4008",
        name="Producto peso por caja",
        description=(
            "Color: Blanco. Material: Poliuretano. "
            "Peso neto por caja: 5.5 Kg. Peso bruto por caja: 6.25 Kg."
        ),
        color_stock={"Blanco": 5},
        stock=5,
    )

    assert ProductTable._format_detail(product).splitlines() == [
        "Material: Poliuretano",
        "Peso neto por caja: 5.5 Kg",
        "Peso bruto por caja: 6.25 Kg",
    ]


def test_detail_format_aligns_fb1503_fields_without_color_line():
    product = Product(
        code="FB-1503",
        name="Enmicadora Metálica de Alta precisión A3 - 8309",
        description=(
            "Marca: Bright Office. Modelo: 8309. "
            "Material: Cuerpo metálico reforzado con base "
            "antideslizante y rodillos de alta precisión. "
            "Color: Blanco con detalles negros. "
            "Voltaje y Frecuencia: AC 220-240V / 50-60Hz. "
            "Potencia: 620W. Tiempo de precalentamiento: 3-5 minutos. "
            "Temperatura de trabajo: 80-180 °C. "
            "Sistema de calentamiento: Tubo de cuarzo (Quartz electric heating tube)"
        ),
    )

    assert ProductTable._format_detail(product).splitlines() == [
        "Marca: Bright Office",
        "Modelo: 8309",
        "Material: Cuerpo metálico reforzado con base antideslizante y rodillos de alta precisión",
        "Voltaje y Frecuencia: AC 220-240V / 50-60Hz",
        "Potencia: 620W",
        "Tiempo de precalentamiento: 3-5 minutos",
        "Temperatura de trabajo: 80-180 °C",
        "Sistema de calentamiento: Tubo de cuarzo (Quartz electric heating tube)",
    ]


def test_detail_format_preserves_fb1503_box_weights_on_source_line():
    product = Product(
        code="FB-1503",
        name="Enmicadora Metálica de Alta precisión A3 - 8309",
        description=(
            "Marca: Bright Office\n"
            "Modelo: 8309\n"
            "Material: Cuerpo metálico reforzado con base antideslizante y rodillos de alta precisión\n"
            "Voltaje y Frecuencia: AC 220\u2013240V / 50\u201360Hz\n"
            "Potencia: 620W\n"
            "Tiempo de precalentamiento: 3\u20135 minutos\n"
            "Temperatura de trabajo: 80\u2013180 °C\n"
            "Sistema de calentamiento: Tubo de cuarzo (Quartz electric heating tube)\n"
            "Cantidad de rodillos: 4\n"
            "Ancho máximo de enmicado: 330 mm (tamaño A3)\n"
            "Espesor máximo de lámina: 1 mm\n"
            "Velocidad de laminado: 0.5 m/min\n"
            "Dimensiones del producto: 500 \u00d7 240 \u00d7 105 mm\n"
            "Peso bruto / caja: 18 kg / Peso neto / caja: 16 kg\n"
            "Medidas de la caja máster: 56.5 \u00d7 30 \u00d7 32.5 cm"
        ),
    )

    assert ProductTable._format_detail(product).splitlines() == [
        "Marca: Bright Office",
        "Modelo: 8309",
        "Material: Cuerpo metálico reforzado con base antideslizante y rodillos de alta precisión",
        "Voltaje y Frecuencia: AC 220\u2013240V / 50\u201360Hz",
        "Potencia: 620W",
        "Tiempo de precalentamiento: 3\u20135 minutos",
        "Temperatura de trabajo: 80\u2013180 °C",
        "Sistema de calentamiento: Tubo de cuarzo (Quartz electric heating tube)",
        "Cantidad de rodillos: 4",
        "Ancho máximo de enmicado: 330 mm (tamaño A3)",
        "Espesor máximo de lámina: 1 mm",
        "Velocidad de laminado: 0.5 m/min",
        "Dimensiones del producto: 500 \u00d7 240 \u00d7 105 mm",
        "Peso bruto / caja: 18 kg / Peso neto / caja: 16 kg",
        "Medidas de la caja máster: 56.5 \u00d7 30 \u00d7 32.5 cm",
    ]


def test_detail_bold_format_covers_only_mousepad_field_label():
    areas = ("31 x 21 cm", "21 x 21 cm", "20.5 x 24.5 cm", "21 x 21 cm")
    label = "Técnica de impresión:"
    for area in areas:
        paragraph = (
            f"{label} Sublimación "
            f"(área de impresión recomendada: {area})"
        )
        layouts, _height = ProductDetailDelegate._layout_text(
            paragraph,
            _qapp().font(),
            600,
        )
        formats = layouts[0][0].formats()
        assert len(formats) == 1
        assert formats[0].start == 0
        assert formats[0].length == len(label)
        assert paragraph[formats[0].start : formats[0].start + formats[0].length] == label


def test_imp_cz01_detail_format_preserves_combined_usb_and_modes_label():
    product = Product(
        code="IMP-CZ-01",
        name="Impresora Fotográfica Térmica \u2013 Modelo CZ-01 \u2013 Citizen",
        description=(
            "Sublimación térmica (300/600 ppp) \u241e "
            "Rápida: Desde 16.3s por impresión \u241e "
            "USB 2.0 | Modos: Alta velocidad / calidad \u241e "
            "Capacidad: Hasta 150 hojas por rollo \u241e "
            "Acabado: Brillante / Mate \u241e "
            "Compacta: 208x240x198mm | 5.8kg"
        ),
    )

    expected = [
        "Sublimación térmica (300/600 ppp)",
        "Rápida: Desde 16.3s por impresión",
        "USB 2.0 | Modos: Alta velocidad / calidad",
        "Capacidad: Hasta 150 hojas por rollo",
        "Acabado: Brillante / Mate",
        "Compacta: 208x240x198mm | 5.8kg",
    ]
    formatted = ProductTable._format_detail(product)
    assert formatted.splitlines() == expected

    delegate = ProductDetailDelegate()
    font = _qapp().font()
    bold_labels = {
        "Rápida:": "Rápida: Desde 16.3s por impresión",
        "USB 2.0 | Modos:": "USB 2.0 | Modos: Alta velocidad / calidad",
        "Capacidad:": "Capacidad: Hasta 150 hojas por rollo",
        "Acabado:": "Acabado: Brillante / Mate",
        "Compacta:": "Compacta: 208x240x198mm | 5.8kg",
    }
    for line in expected:
        layouts, _height = delegate._layout_text(line, font, 600)
        formats = layouts[0][0].formats()
        expected_label = next(
            (label for label, value in bold_labels.items() if value == line),
            None,
        )
        if expected_label is None:
            assert formats == []
            continue
        assert len(formats) == 1
        assert formats[0].start == 0
        assert formats[0].length == len(expected_label)
        assert line[: formats[0].length] == expected_label

    table = ProductTable(_Controller())
    table.resize(1700, 700)
    table.show()
    table.load_products([product])
    QApplication.processEvents()

    item = table.item(0, ProductTable.DETAIL_COLUMN)
    assert item is not None
    assert item.text().splitlines() == expected
    assert item.textAlignment() & Qt.AlignmentFlag.AlignVCenter
    assert item.textAlignment() & Qt.AlignmentFlag.AlignLeft

    detail_width = max(
        table.columnWidth(ProductTable.DETAIL_COLUMN)
        - (2 * ProductDetailDelegate.HORIZONTAL_PADDING),
        1,
    )
    detail_height = ProductDetailDelegate.content_height(
        item.text(),
        table.font(),
        detail_width,
    )
    expected_offset = max(
        (table.rowHeight(0) - detail_height) / 2,
        float(ProductDetailDelegate.VERTICAL_PADDING),
    )
    assert ProductDetailDelegate._vertical_text_offset(
        table.rowHeight(0),
        detail_height,
    ) == expected_offset
    table.close()


def test_detail_format_aligns_unlisted_source_field_labels_and_source_lines():
    product = Product(
        code="IMP-CY02",
        name="Impresora fotográfica",
        description=(
            "Impresión térmica (300/600 ppp) \u241e "
            "Velocidad : 12.4s por 4\u00d76″ | 21.9s por 6\u00d78″ \u241e "
            "Modos : Alta velocidad / calidad \u241e "
            "Capacidad : 700 hojas (4\u00d76″) | 350 hojas (6\u00d78″) \u241e "
            "Acabado : Brillante / Mate \u241e "
            "Tamaño : 322x351x281mm | 13.8kg"
        ),
    )

    assert ProductTable._format_detail(product).splitlines() == [
        "Impresión térmica (300/600 ppp)",
        "Velocidad: 12.4s por 4\u00d76″ | 21.9s por 6\u00d78″",
        "Modos: Alta velocidad / calidad",
        "Capacidad: 700 hojas (4\u00d76″) | 350 hojas (6\u00d78″)",
        "Acabado: Brillante / Mate",
        "Tamaño: 322x351x281mm | 13.8kg",
    ]


def test_detail_format_keeps_unlabelled_source_paragraphs_separate():
    product = Product(
        code="FB-1902",
        name="Espiraladora",
        description=(
            "Tipo de encuadernado: Espiral simple (tipo coil) \u241e "
            "Hasta 12 hojas (70 g/m²) por pasada \u241e "
            "Capacidad de encuadernado: Hasta 450 hojas"
        ),
    )

    assert ProductTable._format_detail(product).splitlines() == [
        "Tipo de encuadernado: Espiral simple (tipo coil)",
        "Hasta 12 hojas (70 g/m²) por pasada",
        "Capacidad de encuadernado: Hasta 450 hojas",
    ]


def test_detail_format_keeps_abbreviated_dimensions_under_medida():
    product = Product(
        code="FB-1310",
        name="Resaltador de mano",
        description=(
            "Medida: Alt: 7.40 cm Ancho: 9.40 cm Esp: 1.90 cm "
            "Descripción: Resaltador en forma de Mano, con 5 puntas. "
            "Colores Anaranjado, Verde, Amarillo, Turqueza y Rosado. "
            "Presentación: Individual, en bolsa de plástico transparente."
        ),
    )

    lines = ProductTable._format_detail(product).splitlines()
    assert lines[0] == "Medida: Alt: 7.40 cm Ancho: 9.40 cm Esp: 1.90 cm"
    assert (
        "Descripción: Resaltador en forma de Mano, con 5 puntas. "
        "Colores Anaranjado, Verde, Amarillo, Turqueza y Rosado"
    ) in lines
    assert "Presentación: Individual, en bolsa de plástico transparente" in lines


def test_detail_format_removes_available_color_line_for_fb6005_and_fb6002():
    for code, color_detail in (
        ("FB-6005", "Colores disponibles: Azul, Rojo, Negro"),
        ("FB-6002", "Colores disponibles: Azul, Rojo, Negro, Gris"),
    ):
        product = Product(
            code=code,
            name="Producto con varios colores",
            description=(
                "Medidas: Alto 30 cm, Ancho 29 cm. "
                "Material: Poliéster 230T. "
                f"{color_detail}. Presentación: Individual."
            ),
            color_stock={"Azul": 330, "Rojo": 1022, "Negro": 4},
            stock=1356,
        )

        lines = ProductTable._format_detail(product).splitlines()
        assert color_detail not in lines
        assert any(line.startswith("Material: ") for line in lines)
        assert any(line.startswith("Presentación: ") for line in lines)


def test_detail_format_keeps_fb1700_nested_measurements_together():
    product = Product(
        code="FB-1700",
        name="Toalla en Tubo",
        description=(
            "Medidas: Envase Largo: 16 cm, Diámetro: 6.5 cm (Aprox), "
            "Toalla Largo: 80 cm, Ancho: 30 cm. "
            "Material: Poliéster y Acrílico Transparente. "
            "Presentación: Individual, Bolsa Plástica."
        ),
    )

    assert ProductTable._format_detail(product).splitlines() == [
        "Medidas: Envase Largo: 16 cm, Diámetro: 6.5 cm (Aprox), "
        "Toalla Largo: 80 cm, Ancho: 30 cm",
        "Material: Poliéster y Acrílico Transparente",
        "Presentación: Individual, Bolsa Plástica",
    ]


def test_detail_format_removes_bullets_and_separates_laminator_fields():
    product = Product(
        code="FB-1500",
        name="LAMINADORA",
        description=(
            "• Función: Caliente / Frío • "
            "Rango de espesor Polaseal: 75 micras (005) / 125 micras (007) / "
            "250 micras (010) • Velocidad: 30 mm/min • "
            "Tiempo de calentamiento: 3-5 min • Consumo de energía: 400W • "
            "Voltaje: 220v"
        ),
    )

    assert ProductTable._format_detail(product).splitlines() == [
        "Función: Caliente / Frío",
        "Rango de espesor Polaseal: 75 micras (005) / 125 micras (007) / 250 micras (010)",
        "Velocidad: 30 mm/min",
        "Tiempo de calentamiento: 3-5 min",
        "Consumo de energía: 400W",
        "Voltaje: 220v",
    ]

def test_detail_formatter_removes_inline_color_and_aligns_technical_fields():
    product = Product(
        code="HL-3000",
        name="Producto de impresión",
        description=(
            "Material: PVC Color: Blanco. Presentación: Caja. "
            "Interfaz: USB. Técnica de impresión: Térmica directa. "
            "Dimensión: 220 x 140 mm. Características: Velocidad alta. "
            "Propiedades: Resistente. Micras: 75."
        ),
    )

    assert ProductTable._format_detail(product).splitlines() == [
        "Material: PVC",
        "Presentación: Caja",
        "Interfaz: USB",
        "Técnica de impresión: Térmica directa",
        "Dimensión: 220 x 140 mm",
        "Características: Velocidad alta",
        "Propiedades: Resistente",
        "Micras: 75",
    ]


def test_detail_formatter_preserves_fb1503_compound_labels_and_alignment():
    product = Product(
        code="FB-1503",
        name="Enmicadora Metálica de Alta precisión A3",
        description=(
            "\u00a0Dimensiones del producto: 500 \u00d7 240 \u00d7 105 mm\n"
            "\u00a0Peso bruto / caja: 18 kg / Peso neto / caja: 16 kg\n"
            "\u00a0Medidas de la caja máster: 56.5 \u00d7 30 \u00d7 32.5 cm"
        ),
    )

    expected = [
        "Dimensiones del producto: 500 \u00d7 240 \u00d7 105 mm",
        "Peso bruto / caja: 18 kg / Peso neto / caja: 16 kg",
        "Medidas de la caja máster: 56.5 \u00d7 30 \u00d7 32.5 cm",
    ]
    assert ProductTable._format_detail(product).splitlines() == expected

    delegate = ProductDetailDelegate()
    for line, bold_label in (
        (expected[0], "Dimensiones del producto:"),
        (expected[1], None),
        (expected[2], None),
    ):
        layouts, _height = delegate._layout_text(line, _qapp().font(), 600)
        formats = layouts[0][0].formats()
        if bold_label is None:
            assert formats == []
        else:
            assert len(formats) == 1
            assert formats[0].start == 0
            assert formats[0].length == len(bold_label)


def test_fb1503_detail_cell_is_vertically_centered_and_row_height_fits():
    _qapp()
    product = Product(
        code="FB-1503",
        name="Enmicadora Metálica de Alta precisión A3",
        description=(
            "\u00a0Dimensiones del producto: 500 \u00d7 240 \u00d7 105 mm\n"
            "\u00a0Peso bruto / caja: 18 kg / Peso neto / caja: 16 kg\n"
            "\u00a0Medidas de la caja máster: 56.5 \u00d7 30 \u00d7 32.5 cm"
        ),
    )
    table = ProductTable(_Controller())
    table.resize(1500, 700)
    table.show()
    table.load_products([product])
    QApplication.processEvents()

    item = table.item(0, ProductTable.DETAIL_COLUMN)
    assert item is not None
    assert item.text().splitlines() == [
        "Dimensiones del producto: 500 \u00d7 240 \u00d7 105 mm",
        "Peso bruto / caja: 18 kg / Peso neto / caja: 16 kg",
        "Medidas de la caja máster: 56.5 \u00d7 30 \u00d7 32.5 cm",
    ]
    assert item.textAlignment() & Qt.AlignmentFlag.AlignVCenter
    assert item.textAlignment() & Qt.AlignmentFlag.AlignLeft
    expected_height = (
        ProductDetailDelegate.content_height(
            item.text(),
            table.font(),
            max(
                table.columnWidth(ProductTable.DETAIL_COLUMN)
                - (2 * ProductDetailDelegate.HORIZONTAL_PADDING),
                1,
            ),
        )
        + (2 * ProductDetailDelegate.VERTICAL_PADDING)
    )
    assert table.rowHeight(0) >= expected_height
    detail_height = ProductDetailDelegate.content_height(
        item.text(),
        table.font(),
        max(
            table.columnWidth(ProductTable.DETAIL_COLUMN)
            - (2 * ProductDetailDelegate.HORIZONTAL_PADDING),
            1,
        ),
    )
    assert ProductDetailDelegate._vertical_text_offset(
        table.rowHeight(0),
        detail_height,
    ) == max(
        (table.rowHeight(0) - detail_height) / 2,
        float(ProductDetailDelegate.VERTICAL_PADDING),
    )
    table.close()


def test_detail_formatter_recognizes_printing_technique_for_mouse_pads():
    products = [
        (
            "FB-2035",
            "Mouse Pad A4 30 x 20 cm x 5 mm",
            "30 x 20 cm (espesor: 5 mm)",
            "31 x 21 cm",
        ),
        (
            "FB-2015",
            "Mouse Pad Cuadrado 20 x 20 cm x 5 mm",
            "20 x 20 cm (espesor: 5 mm)",
            "21 x 21 cm",
        ),
        (
            "FB-2013",
            "Mouse Pad Rectangular 19.5 x 23.5 cm x 5 mm",
            "19.5 x 23.5 cm (espesor: 5 mm)",
            "20.5 x 24.5 cm",
        ),
        (
            "FB-2032",
            "Mouse Pad Redondo 20 x 20 cm x 5 mm",
            "20 x 20 cm (espesor: 5 mm)",
            "21 x 21 cm",
        ),
    ]

    for code, name, measure, print_area in products:
        product = Product(
            code=code,
            name=name,
            description=(
                f"Medida: {measure}\n"
                "Material: Neopreno para sublimación\n"
                "Técnica de impresión: Sublimación "
                f"(área de impresión recomendada: {print_area})"
            ),
        )

        assert ProductTable._format_detail(product).splitlines() == [
            f"Medida: {measure}",
            "Material: Neopreno para sublimación",
            (
                "Técnica de impresión: Sublimación "
                f"(área de impresión recomendada: {print_area})"
            ),
        ], code


def test_detail_table_preserves_fb1504_published_truncated_dimension_source_text():
    product = Product(
        code="FB-1504",
        name="Enmicadora Metálica A4",
        description=(
            "Marca: Bright Office\n"
            "Dimensiones del producto: 410 \u00d7 208 \u00d7"
        ),
    )

    assert ProductTable._format_detail(product).splitlines() == [
        "Marca: Bright Office",
        "Dimensiones del producto: 410 \u00d7 208 \u00d7",
    ]



def test_detail_delegate_bolds_labels_not_in_a_fixed_allowlist():
    text = (
        "Medida y capacidad: 10 ml. "
        "Composición: Algodón. "
        "Características especiales: Resistente. "
        "Tamaño del paquete: 5 unidades."
    )

    labels = [
        match.group(0)
        for match in ProductDetailDelegate._BOLD_DETAIL_LABEL_PATTERN.finditer(text)
    ]

    assert labels == [
        "Medida y capacidad:",
        "Composición:",
        "Características especiales:",
        "Tamaño del paquete:",
    ]



def test_detail_row_height_matches_wrapped_content_width_and_gridline():
    _qapp()
    table = ProductTable(_Controller())
    table.resize(1080, 700)
    table.show()
    table.load_products(
        [
            Product(
                code="FB-1507",
                name="Laminadora A3 PAMUNDO Multi PRO800 8 en 1",
                category="Enmicadoras / Laminadoras",
                description=(
                    "Marca: PAMUNDO. Modelo: Multi PRO800. "
                    "Material: Cuerpo compacto y ligero con rodillos de alta precisión. "
                    "Potencia: 390 W. Tiempo de precalentamiento: 2-3 minutos. "
                    "Temperatura de trabajo: Modo caliente y frío con interruptor. "
                    "Sistema de calentamiento: Sistema de 2 rodillos de alta eficiencia. "
                    "Ancho máximo de laminado: 325 mm (Hasta tamaño A3). "
                    "Velocidad de laminado: 280 mm/min. "
                    "Espesor de mica compatible: 75 - 125 micrones. "
                    "Espesor máximo de laminado: 0.5 mm. "
                    "Sistema antiatasco: Palanca de liberación manual."
                ),
            ),
        ],
    )
    QApplication.processEvents()

    def assert_detail_fits_row():
        item = table.item(0, ProductTable.DETAIL_COLUMN)
        assert item is not None
        paint_width = max(
            table.columnWidth(ProductTable.DETAIL_COLUMN)
            - ProductDetailDelegate.GRIDLINE_ALLOWANCE
            - (2 * ProductDetailDelegate.HORIZONTAL_PADDING),
            1,
        )
        required_height = (
            ProductDetailDelegate.content_height(
                item.text(),
                table.font(),
                paint_width,
            )
            + (2 * ProductDetailDelegate.VERTICAL_PADDING)
            + ProductDetailDelegate.GRIDLINE_ALLOWANCE
        )
        assert table.rowHeight(0) >= required_height

    table.setColumnWidth(ProductTable.DETAIL_COLUMN, 220)
    QApplication.processEvents()
    assert_detail_fits_row()

    table.setColumnWidth(ProductTable.DETAIL_COLUMN, 340)
    QApplication.processEvents()
    assert_detail_fits_row()
    table.close()


def test_detail_delegate_centers_content_when_row_has_extra_height():
    delegate = ProductDetailDelegate()

    assert delegate._vertical_text_offset(rect_height=80, content_height=24) == 28
    assert delegate._vertical_text_offset(rect_height=40, content_height=24) == 8
    assert delegate._vertical_text_offset(rect_height=20, content_height=24) == 8


def test_detail_formatter_preserves_source_grouping_without_product_specific_rules():
    product = Product(
        code="TEST-GROUPING-01",
        name="Producto de prueba",
        description=(
            "Atributo: Primero / Segundo campo: Segundo valor\n"
            "Prefijo de conexión | Modo: Activo"
        ),
    )

    assert ProductTable._format_detail(product).splitlines() == [
        "Atributo: Primero / Segundo campo: Segundo valor",
        "Prefijo de conexión | Modo: Activo",
    ]


def test_detail_formatter_preserves_empty_caja_field_for_future_updates():
    product = Product(
        code="FB-7080",
        name="Laminado en frío",
        description="Medida: A4. Paquete: 20 Unidades. Caja:",
    )

    assert ProductTable._format_detail(product).splitlines() == [
        "Medida: A4",
        "Paquete: 20 Unidades",
        "Caja:",
    ]

    product.description = "Medida: A4. Paquete: 20 Unidades. Caja: 100 unidades."
    assert ProductTable._format_detail(product).splitlines() == [
        "Medida: A4",
        "Paquete: 20 Unidades",
        "Caja: 100 unidades",
    ]



def test_detail_format_preserves_fb8024_usage_ideal_after_removing_color_variants():
    product = Product(
        code="FB-8024",
        name="Producto",
        description=(
            "Colores disponibles: Azul, Rojo. "
            "Uso ideal: Oficina y escritorio. "
            "Presentación: Individual, bolsa plástica."
        ),
    )

    assert ProductTable._format_detail(product).splitlines() == [
        "Uso ideal: Oficina y escritorio",
        "Presentación: Individual, bolsa plástica",
    ]


def test_detail_format_preserves_color_of_ink_for_fb2005_and_fb2200():
    description = (
        "Medidas: Largo: 14.5 cm. Diámetro: 1 cm. "
        "Colores: Rojo, Negro, Azul, Gris Gun y Silver. "
        "Color de tinta: Líquida color negro. "
        "Presentación: Bolsa plástica transparente."
    )
    for code in ("FB-2005", "FB-2200"):
        product = Product(
            code=code,
            name="Lapicero metálico",
            description=description,
        )

        lines = ProductTable._format_detail(product).splitlines()
        assert "Color de tinta: Líquida color negro" in lines
        assert not any(line.startswith("Colores:") for line in lines)


def test_detail_format_preserves_each_highlighter_page_text_without_sku_substitution():
    source_descriptions = {
        "FB-1313": (
            "Descripción: Resaltador con 5 puntas. "
            "Colores anaranjado, Verde, Amarillo, Turqueza y Rosado. "
            "Presentación: Individual, en bolsa de plástico transparente."
        ),
        "FB-1300": (
            "Descripción: Resaltador en forma de estrella con 5 puntas. "
            "Colores Anaranjado, Verde, Amarillo, Turqueza y Rosado. "
            "Presentación: Individual, en bolsa de plástico transparente."
        ),
        "FB-1315": (
            "Descripción: Resaltador en forma de estrella con 5 puntas. "
            "Colores Anaranjado, Verde, Amarillo, Turqueza y Rosado. "
            "Material: Fibra de Trigo. "
            "Presentación: Individual, en bolsa de plástico transparente."
        ),
        "FB-1310": (
            "Descripción: Resaltador en forma de Mano, con 5 puntas. "
            "Colores Anaranjado, Verde, Amarillo, Turqueza y Rosado. "
            "Presentación: Individual, en bolsa de plástico transparente."
        ),
        "FB-1304": (
            "Descripción: Resaltador en forma de Mano, con 5 puntas. "
            "Colores Anaranjado, Verde, Amarillo, Turqueza y Rosado "
            "Presentación: Individual, en bolsa de plástico transparente."
        ),
    }

    for code, description in source_descriptions.items():
        product = Product(code=code, name="Resaltador", description=description)
        lines = ProductTable._format_detail(product).splitlines()
        expected_description = description.split(" Presentación:")[0]
        expected_description = expected_description.split(" Material:")[0].rstrip(".")
        assert expected_description in lines
        assert "Presentación: Individual, en bolsa de plástico transparente" in lines
        if code == "FB-1315":
            assert "Material: Fibra de Trigo" in lines


def test_detail_format_aligns_requested_fb1003_and_fb1004_fields():
    product_1003 = Product(
        code="FB-1003",
        name="Calendario",
        description=(
            "Presentación: Individual, Bolsa Plástica. "
            "Fecha: 2026 \u2013 2027."
        ),
    )
    product_1004 = Product(
        code="FB-1004",
        name="Producto",
        description=(
            "Técnica de aplicación: Serigrafía. "
            "Forma: Rectángulo. "
            "Presentación: Individual, en bolsita plástica transparente."
        ),
    )

    assert ProductTable._format_detail(product_1003).splitlines() == [
        "Presentación: Individual, Bolsa Plástica",
        "Fecha: 2026 \u2013 2027",
    ]
    assert ProductTable._format_detail(product_1004).splitlines() == [
        "Técnica de aplicación: Serigrafía",
        "Forma: Rectángulo",
        "Presentación: Individual, en bolsita plástica transparente",
    ]


def test_detail_format_splits_fb1305_nested_estuche_and_resaltador_measurements():
    product = Product(
        code="FB-1305",
        name="Set de resaltadores",
        description=(
            "Medida: 1.Estuche: Alto: 8 cm Ancho: 12.5 cm "
            "2.Resaltador: Alto 6 cm Ancho: 2.00 cm. "
            "Descripción: Estuche modelo maletín rectangular. "
            "Colores: Blanco transparente. "
            "Presentación del producto: Individual, en bolsa de plástico transparente."
        ),
    )

    assert ProductTable._format_detail(product).splitlines() == [
        "Medida: 1. Estuche: Alto: 8 cm Ancho: 12.5 cm",
        "2. Resaltador: Alto 6 cm Ancho: 2.00 cm",
        "Descripción: Estuche modelo maletín rectangular",
        "Presentación del producto: Individual, en bolsa de plástico transparente",
    ]


def test_detail_format_removes_price_includes_igv_for_every_product():
    description = (
        "Material: Metal. Precio incluye IGV. "
        "Presentación: Bolsa plástica transparente."
    )
    for code in ("FB-8041", "FB-8042", "OTRO-01"):
        product = Product(
            code=code,
            name="Producto",
            description=description,
        )

        lines = ProductTable._format_detail(product).splitlines()
        assert lines == [
            "Material: Metal",
            "Presentación: Bolsa plástica transparente",
        ]
        assert not any("precio incluye igv" in line.casefold() for line in lines)


def test_detail_column_resize_recalculates_row_height_for_wrapped_content():
    _qapp()
    table = ProductTable(_Controller())
    table.resize(1500, 700)
    table.show()
    table.load_products(
        [
            Product(
                code="FB-2009",
                name="Producto con detalle extenso",
                description=(
                    "Descripción: " + "texto descriptivo de prueba " * 18
                ),
                category="Oficina",
            ),
        ],
    )
    QApplication.processEvents()

    header = table.horizontalHeader()
    header.resizeSection(ProductTable.DETAIL_COLUMN, 700)
    QApplication.processEvents()
    wide_height = table.rowHeight(0)

    header.resizeSection(ProductTable.DETAIL_COLUMN, 110)
    QApplication.processEvents()
    narrow_height = table.rowHeight(0)

    assert narrow_height > wide_height
    table.close()


def test_product_table_renders_authoritative_hl9400_html_with_embedded_contiene():
    _qapp()
    description = (
        "Medidas: 7.5 x 7 cm. (Aprox.)\n"
        "Descripción: Pote de plástico traslúcido que contiene: "
        "1 Saca grapas, 1 Engrapadora, repuestos, 1 Cinta Adhesiva, "
        "1 Perforadora de un hueco.\n"
        "Presentación del Producto: Individual, en bolsa de plástico transparente."
    )
    description_html = (
        "<ul>"
        '<li style="text-align: left"><strong>Medidas: </strong>'
        "7.5 x 7 cm. (Aprox.)</li>"
        '<li style="text-align: left"><b>Descripción: </b>'
        "Pote de plástico traslúcido que contiene: "
        "1 Saca grapas, 1 Engrapadora, repuestos, 1 Cinta Adhesiva, "
        "1 Perforadora de un hueco.</li>"
        '<li style="text-align: left"><strong>Presentación del Producto: </strong>'
        "Individual, en bolsa de plástico transparente.</li>"
        "</ul>"
    )
    table = ProductTable(_Controller())
    table.load_products(
        [
            Product(
                code="HL-9400",
                name="Set de Escritorio Pote",
                description=description,
                description_html=description_html,
            ),
        ],
    )
    QApplication.processEvents()

    item = table.item(0, ProductTable.DETAIL_COLUMN)
    assert item is not None
    assert item.text().splitlines() == description.splitlines()
    rendered_html = item.data(ProductDetailDelegate.DETAIL_HTML_ROLE)
    assert rendered_html == description_html

    document = ProductDetailDelegate._document_for_html(
        rendered_html,
        table.font(),
        700,
    )
    rendered_text = document.toPlainText().replace("\u2022 ", "")
    assert "Pote de plástico traslúcido que contiene:" in rendered_text
    assert not any(
        line.strip().casefold().startswith("contiene:")
        for line in rendered_text.splitlines()
    )
    measure_cursor = document.find("Medidas:")
    description_cursor = document.find("Descripción:")
    assert measure_cursor.hasSelection()
    assert description_cursor.hasSelection()
    assert measure_cursor.charFormat().fontWeight() >= 700
    assert description_cursor.charFormat().fontWeight() >= 700
    assert "<strong>Medidas:" in rendered_html
    assert "<b>Descripción:" in rendered_html
    assert "<strong>Presentación del Producto:" in rendered_html

    table.close()


def test_detail_table_keeps_unbolded_source_values_for_observed_codes():
    cases = (
        (
            "FB-5012",
            (
                "Medidas: Alt. de base: 4.50 cm Ancho: 5 cm. "
                "Alt. Total: 13.50 cm. Aprox.\n"
                "Descripción: Artículo de base acrílica de colores, en forma de "
                "media luna; con clip sujetador de metal para los memos.\n"
                "Presentación: Individual, bolsa de plástico transparente."
            ),
            ("Alt. de base: 4.50 cm", "Ancho: 5 cm", "Alt. Total: 13.50 cm"),
            None,
        ),
        (
            "HL-9398",
            (
                "Medidas: 16 cm x 10 cm (Aprox.) Espesor: 2,5 cm.\n"
                "Descripción: Estuche de plástico traslucido, contiene: 1 Tijera, "
                "2 Lapiceros, 3 Ganchitos, 1 Cinta Adhesiva, 1 Perforadora de un "
                "hueco, 1 Engrapadora + repuestos.\n"
                "Presentación del producto: Individual, en bolsa de plástico "
                "transparente."
            ),
            ("16 cm x 10 cm", "Espesor: 2,5 cm"),
            "contiene: 1 Tijera",
        ),
        (
            "HL-9401A",
            (
                "Medidas: Ancho: 8 cm. Largo: 9.0 cm. Espesor 7.9\n"
                "Descripción: 1 engrapadora, grapas, 1 tijera con tapa, "
                "1 dispensador con cinta adhesiva, 1 borrador, 1 regla de 12 cms., "
                "1 lapicero con tinta negra, 1 lápiz de minas."
            ),
            ("Ancho: 8 cm", "Largo: 9.0 cm"),
            None,
        ),
        (
            "HL-9403",
            (
                "Medidas: Ancho: 10.4 cm. Largo: 11.0 cm. Espesor 2.9 cm. (Aprox.)\n"
                "Descripción: Estuche de plástico blanco traslúcido, contiene: "
                "1 engrapadora, 1 tajador, 1 perforadora de 1 hueco, 1 saca grapas, "
                "1 tijera, 1 dispensador con cinta adhesiva, 1 cinta adhesiva de "
                "repuesto y grapas.\n"
                "Presentación del producto: Individual, en bolsa de plástico transparente."
            ),
            ("Ancho: 10.4 cm", "Largo: 11.0 cm", "Espesor 2.9 cm"),
            "contiene: 1 engrapadora",
        ),
        (
            "HL-9400",
            (
                "Medidas: 7.5 x 7 cm. (Aprox.)\n"
                "Descripción: Pote de plástico traslúcido que contiene: "
                "1 Saca grapas, 1 Engrapadora, repuestos, 1 Cinta Adhesiva, "
                "1 Perforadora de un hueco.\n"
                "Presentación del Producto: Individual, en bolsa de plástico "
                "transparente."
            ),
            ("7.5 x 7 cm.",),
            "contiene: 1 Saca grapas",
        ),
    )

    for code, description, measure_values, description_value in cases:
        product = Product(code=code, name="Producto de prueba", description=description)
        lines = ProductTable._format_detail(product).splitlines()

        measure_line = next(line for line in lines if line.startswith("Medidas:"))
        for value in measure_values:
            assert value in measure_line, (code, measure_line, value)

        if description_value is not None:
            description_line = next(
                line for line in lines if line.startswith("Descripción:")
            )
            assert description_value in description_line, (code, description_line)
            assert not any(
                line.startswith("Contiene:") for line in lines
            ), (code, lines)

        for line in lines:
            layouts, _height = ProductDetailDelegate._layout_text(
                line,
                _qapp().font(),
                900,
            )
            formats = layouts[0][0].formats()
            bold_text = [
                line[item.start : item.start + item.length]
                for item in formats
            ]
            assert not any(
                label.casefold() in value.casefold()
                for value in bold_text
                for label in ("Largo:", "Total:", "Contiene:")
            ), (code, line, bold_text)


def test_detail_table_keeps_fb3019_visible_product_fields_in_separate_paragraphs():
    description = (
        "Potencia: 1500 W.\n"
        "Dimensiones: 54.8 \u00d7 40 \u00d7 36.5 cm.\n"
        "Peso unitario: 20.3 kg.\n"
        "Uso recomendado: Estampado en camisetas.\n"
        "Empaque individual: Esponja + caja de cartón.\n"
        "Cantidad por caja: 1 pza.\n"
        "Dimensiones de caja: 60 \u00d7 47.5 \u00d7 44 cm.\n"
        "Cubicaje por caja: 0.1254 m\u00b3/CBM.\n"
        "Peso neto por caja: 20.3 kg.\n"
        "Peso bruto por caja: 23.6 kg."
    )
    product = Product(
        code="FB-3019",
        name="Prensa térmica automática",
        description=description,
    )

    lines = ProductTable._format_detail(product).splitlines()

    assert len(lines) == 10
    assert lines[0] == "Potencia: 1500 W"
    assert lines[1] == "Dimensiones: 54.8 \u00d7 40 \u00d7 36.5 cm"
    assert lines[2] == "Peso Unitario: 20.3 kg"
    assert lines[3] == "Uso Recomendado: Estampado en camisetas"
    assert lines[4] == "Empaque Individual: Esponja + caja de cartón"
    assert lines[5] == "Cantidad por Caja: 1 pza"
    assert lines[6] == "Dimensiones de caja: 60 \u00d7 47.5 \u00d7 44 cm"
    assert lines[7] == "Cubicaje por Caja: 0.1254 m\u00b3/CBM"
    assert lines[8] == "Peso neto por caja: 20.3 kg"
    assert lines[9] == "Peso bruto por caja: 23.6 kg"

    for line in lines:
        layouts, _height = ProductDetailDelegate._layout_text(
            line,
            _qapp().font(),
            900,
        )
        bold_text = [
            line[item.start : item.start + item.length]
            for item in layouts[0][0].formats()
        ]
        assert len(bold_text) == 1, (line, bold_text)
        assert bold_text[0].endswith(":"), (line, bold_text)


def test_detail_table_keeps_nested_measure_values_for_ty_p35aw_and_mu511():
    cases = (
        (
            "TY-P35AW",
            "Medidas: Alto: 15.5 cm, Diámetro (Base): 10 cm (Aprox)",
            ("Alto:", "Diámetro (Base):"),
        ),
        (
            "MU-511",
            "Medidas: Estuche: 10.5 x 7 cm, Tarjeta: 8.5 x 5 cm",
            ("Estuche:", "Tarjeta:"),
        ),
        (
            "SKB05X-1",
            "Medida y Capacidad: Diámetro: 8,5 cm \u2013 11 onzas (aproximadamente 300 ml)",
            ("Diámetro:",),
        ),
    )

    for code, description, nested_labels in cases:
        product = Product(
            code=code,
            name="Producto de prueba",
            description=description,
        )
        lines = ProductTable._format_detail(product).splitlines()

        assert lines == [description], (code, lines)
        layouts, _height = ProductDetailDelegate._layout_text(
            lines[0],
            _qapp().font(),
            900,
        )
        bold_text = [
            lines[0][item.start : item.start + item.length]
            for item in layouts[0][0].formats()
        ]
        assert not any(
            label.casefold() in value.casefold()
            for value in bold_text
            for label in nested_labels
        ), (code, lines, bold_text)


def test_detail_table_keeps_nested_caja_and_paquete_inside_empaque_for_observed_codes():
    cases = (
        ("FD-2041", "Medida: 23.5x32cm .", "Paquete 25 unid caja: 1/2 millar"),
        ("FD-2046", "Medida: 23.5x32cm", "Paquete 25 unid / caja: 20 paq. 1/2 millar"),
        ("SB-2027", "Medida: 24x34cm", "Paquete 50 unid caja: 1/2 millar"),
        ("SB-2028", "Medida: 11\u00d722 cm", "Paquete 50 unid caja: 1 millar"),
        ("SB-2029", "Medida: 25x38cm", "50 unid / 10 unid caja: 1/2 millar"),
        ("SB-2030", "Medida: 19\u00d725.5cm", "Paquete 50 / 10 unid caja: 1/2 millar"),
        ("SB-2031", "Medida: 13.4\u00d718.4cm", "Paquete 50 unid caja: 1/2 millar"),
        ("SB-2032", "Medida: 11.5\u00d716.2cm", "Paquete 50 unid caja: 1 millar"),
        ("SB-2033", "Medida: 11x22cm", "Paquete de 50 unid caja: 1 millar"),
        ("KF-2034", "Medida: 24x34cm", "Paquete 50 unid caja: 1/2 millar"),
        ("KF-2035", "Medida: 19\u00d725.5cm", "Paquete 50 unid caja: 1/2 millar"),
        ("KF-2036", "Medida: 10.8x18cm", "Paquete 100 unid caja: 1 millar"),
        ("KF-2037", "Medida: 9X22.5cm\nGramaje: 75 grs", "Paquete 100 unid"),
        ("GP-2020", "Medida: 24x34cm", "Paquete 50 unid / 10 unid caja: 1/2 millar"),
        ("GP-2021", "Medida: 25x38cm", "Paquete 50 unid / 10 unid caja: 1/2 millar"),
        ("GP-2022", "Medida: 30x38cm", "Paquete 50 unid / 10 unid caja: 1/2 millar"),
        ("GP-2023", "Medida: 23\u00d730.5cm", "Paquete 50 unid caja: 1/2 millar"),
        ("GP-2024", "Medida: 19\u00d725.5cm", "Paquete: 50 unid/10 unid caja: 1/2 millar"),
        ("GP-2025", "Medida: 11x18cm", "paquete 100 unid / 10 unid caja: 01 millar"),
        ("GP-2026", "Medida: 10.8x18cm", "Paquete 50 unid caja: 1 millar"),
    )

    for code, other_fields, empaque_value in cases:
        description = f"{other_fields}\nEmpaque: {empaque_value}"
        product = Product(
            code=code,
            name="Producto de prueba",
            description=description,
        )
        lines = ProductTable._format_detail(product).splitlines()
        expected_empaque = f"Empaque: {empaque_value}"

        assert expected_empaque in lines, (code, lines, expected_empaque)
        assert not any(
            line.startswith(("Caja:", "Paquete:"))
            for line in lines
        ), (code, lines)

    explicit_caja_field = Product(
        code="TEST-EMPAQUE-CAJA",
        name="Producto de prueba",
        description="Empaque: Bolsa plástica. Caja: 100 unidades",
    )
    assert ProductTable._format_detail(explicit_caja_field).splitlines() == [
        "Empaque: Bolsa plástica",
        "Caja: 100 unidades",
    ]



def test_fb1504_table_uses_verified_rich_detail_without_rewriting_source_paragraphs():
    _qapp()
    description = (
        "Marca: Bright Office\n"
        "Modelo: 230\n"
        "Material: Cuerpo metálico con base antideslizante.\n"
        "Dimensiones del producto: 410 \u00d7 208 \u00d7 275 mm"
    )
    rich_html = (
        '<p style="text-align: left"><strong>Marca:</strong> Bright Office</p>'
        '<p style="text-align: center"><strong>Modelo:</strong> 230</p>'
        '<p style="text-align: right"><strong>Material:</strong> '
        "Cuerpo metálico con base antideslizante.</p>"
        '<p style="text-align: left"><strong>Dimensiones del producto:</strong> '
        "410 \u00d7 208 \u00d7 275 mm</p>"
    )
    table = ProductTable(_Controller())
    table.resize(1500, 700)
    table.show()
    product = Product(
        code="FB-1504",
        name="Enmicadora Metálica A4",
        description=description,
        description_html=rich_html,
    )
    table.load_products([product])
    QApplication.processEvents()

    item = table.item(0, ProductTable.DETAIL_COLUMN)
    assert item is not None
    assert item.text() == description
    assert item.data(ProductDetailDelegate.DETAIL_HTML_ROLE) == rich_html

    width = max(
        table.columnWidth(ProductTable.DETAIL_COLUMN)
        - (2 * ProductDetailDelegate.HORIZONTAL_PADDING),
        1,
    )
    document = ProductDetailDelegate._document_for_html(
        rich_html,
        table.font(),
        width,
    )
    assert document.toPlainText().splitlines() == description.splitlines()
    assert ProductDetailDelegate.rich_content_height(
        rich_html,
        table.font(),
        width,
    ) > 0
    first_block = document.begin()
    horizontal_mask = Qt.AlignmentFlag.AlignHorizontal_Mask
    assert first_block.blockFormat().alignment() & horizontal_mask == Qt.AlignmentFlag.AlignLeft
    second_block = first_block.next()
    assert second_block.blockFormat().alignment() & horizontal_mask == Qt.AlignmentFlag.AlignHCenter
    third_block = second_block.next()
    assert third_block.blockFormat().alignment() & horizontal_mask == Qt.AlignmentFlag.AlignRight
    table.close()


def test_table_rejects_rich_detail_when_its_visible_text_differs_from_canonical_text():
    _qapp()
    product = Product(
        code="FB-1504",
        name="Enmicadora Metálica A4",
        description="Marca: Bright Office",
        description_html=(
            "<p><strong>Marca:</strong> Bright Office</p>"
            "<p>Texto adicional no autorizado</p>"
        ),
    )
    table = ProductTable(_Controller())
    table.resize(1500, 700)
    table.show()
    table.load_products([product])
    QApplication.processEvents()

    item = table.item(0, ProductTable.DETAIL_COLUMN)
    assert item is not None
    assert item.data(ProductDetailDelegate.DETAIL_HTML_ROLE) in (None, "")
    assert item.text() == ProductTable._format_detail(product)
    table.close()

def test_detail_table_preserves_semantic_measure_and_packaging_group_headings():
    cases = (
        (
            "GP-2024",
            (
                "Medida: 19×25.5cm\n"
                "Empaque: Paquete: 50 unid/10 unid caja: 1/2 millar"
            ),
            [
                "Medida: 19×25.5cm",
                "Empaque: Paquete: 50 unid/10 unid caja: 1/2 millar",
            ],
        ),
        (
            "MU-0021",
            (
                "Medidas Estuche: Largo: 9 cm, Ancho: 4.5 cm, "
                "Alto: 2 cm (Aprox)\n"
                "Medidas USB: 5.5 cm x 2.5 cm"
            ),
            [
                "Medidas Estuche: Largo: 9 cm, Ancho: 4.5 cm, Alto: 2 cm (Aprox)",
                "Medidas USB: 5.5 cm x 2.5 cm",
            ],
        ),
        (
            "R7512",
            (
                "Medidas: Dimensiones: 13 x 10.5 x 3 cm\n"
                "Material: Cartón Reutilizable Ecológico"
            ),
            [
                "Medidas: Dimensiones: 13 x 10.5 x 3 cm",
                "Material: Cartón Reutilizable Ecológico",
            ],
        ),
    )

    for code, description, expected_lines in cases:
        product = Product(
            code=code,
            name="Producto de prueba",
            description=description,
        )
        lines = ProductTable._format_detail(product).splitlines()
        assert lines == expected_lines, (code, lines)

    # Group headings remain the emphasized field; nested labels are part
    # of that value and are not promoted to independent table fields.
    for line in (
        "Empaque: Paquete: 50 unid/10 unid caja: 1/2 millar",
        "Medidas Estuche: Largo: 9 cm, Ancho: 4.5 cm, Alto: 2 cm (Aprox)",
        "Medidas: Dimensiones: 13 x 10.5 x 3 cm",
    ):
        layouts, _height = ProductDetailDelegate._layout_text(
            line,
            _qapp().font(),
            900,
        )
        bold_text = [
            line[item.start : item.start + item.length]
            for item in layouts[0][0].formats()
        ]
        assert len(bold_text) == 1, (line, bold_text)
        assert bold_text[0].endswith(":"), (line, bold_text)

