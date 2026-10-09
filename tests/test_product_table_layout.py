from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontMetrics, QFontMetricsF, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
)

from gui.product_table import (
    PriceDelegate,
    ProductCodeCategoryDelegate,
    ProductDetailDelegate,
    ProductImageDelegate,
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
    assert table.columnWidth(ProductTable.IMAGE_COLUMN) == (
        ProductImageDelegate.DEFAULT_SIZE
    )
    assert table.rowHeight(0) >= ProductImageDelegate.DEFAULT_HEIGHT

    table.resize(2200, 700)
    QApplication.processEvents()

    assert table.rowHeight(0) >= ProductImageDelegate.DEFAULT_HEIGHT
    assert table.columnWidth(ProductTable.IMAGE_COLUMN) == (
        ProductImageDelegate.DEFAULT_SIZE
    )

    table.close()


def test_product_table_uses_horizontal_thumbnails_and_click_changes_temporary_primary(
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

    table = ProductTable(_Controller())
    table.resize(1500, 700)
    table.show()
    table.load_products(
        [
            Product(
                code="FB-100",
                name="Producto",
                image_path=str(paths[0]),
                gallery_images=gallery,
            ),
        ],
    )
    QApplication.processEvents()

    index = table.model().index(0, ProductTable.IMAGE_COLUMN)
    rect = table.visualRect(index)
    tiles, left_arrow, right_arrow, strip_top = ProductImageDelegate.thumbnail_layout(
        rect,
        len(gallery),
        0,
    )
    assert len(tiles) == 3
    assert left_arrow is None and right_arrow is None
    assert strip_top > rect.top()
    assert table.rowHeight(0) >= ProductImageDelegate.DEFAULT_HEIGHT

    QTest.mouseClick(
        table.viewport(),
        Qt.MouseButton.LeftButton,
        pos=tiles[1][1].center(),
    )
    QApplication.processEvents()

    item = table.item(0, ProductTable.IMAGE_COLUMN)
    assert item.data(ProductImageDelegate.ACTIVE_INDEX_ROLE) == 1
    assert table._active_image_indices["fb-100"] == 1
    assert table.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
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


def test_product_table_category_is_combined_with_code_and_detail_receives_space():
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

    code_delegate = table.itemDelegateForColumn(ProductTable.CODE_COLUMN)
    category_item = table.item(0, ProductTable.CATEGORY_COLUMN)
    assert table.isColumnHidden(ProductTable.CATEGORY_COLUMN)
    assert table.columnWidth(ProductTable.CATEGORY_COLUMN) == 0
    assert table.horizontalHeaderItem(ProductTable.CODE_COLUMN).text() == (
        "Código / Categoría"
    )
    assert isinstance(code_delegate, ProductCodeCategoryDelegate)
    assert category_item is not None
    assert category_item.text() == "Enmicadoras / Laminadoras"
    assert table.columnWidth(ProductTable.IMAGE_COLUMN) == (
        ProductImageDelegate.DEFAULT_SIZE
    )
    assert table.rowHeight(0) >= ProductImageDelegate.DEFAULT_HEIGHT
    assert table.columnWidth(ProductTable.DETAIL_COLUMN) > (
        ProductTable.MIN_COLUMN_WIDTHS[ProductTable.DETAIL_COLUMN]
    )

    table.close()


def test_product_table_category_with_long_word_stays_on_one_line():
    category = "Categoria extraordinariamenteLargaSinEspacios"

    formatted = ProductTable._format_categories(category)

    assert formatted == category
    assert "\n" not in formatted


def test_product_table_category_sublimacion_is_shown_under_code():
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
    assert item is not None
    assert code_item is not None
    assert item.text() == "Artículos de Sublimación"
    assert code_item.text() == "FB-400"
    assert table.isColumnHidden(ProductTable.CATEGORY_COLUMN)
    assert table.columnWidth(ProductTable.CATEGORY_COLUMN) == 0

    table.close()


def test_product_table_category_enmicadoras_is_combined_with_code():
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

    assert (
        table.horizontalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert table.textElideMode() == Qt.TextElideMode.ElideNone
    assert "padding: 4px" in table.styleSheet()
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


def test_product_table_stock_color_rows_have_no_outer_spacing():
    assert StockColorDelegate.HORIZONTAL_PADDING == 4
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
    assert table.columnWidth(ProductTable.STOCK_COLUMN) == max(
        expected,
        header_width,
        1,
    )
    assert ProductImageDelegate.DEFAULT_SIZE == ProductTable.DEFAULT_IMAGE_CELL_SIZE

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

    calls_after_render = table.resize_to_contents_calls
    assert calls_after_render >= 1
    assert table._preferred_widths_cache is not None

    table.resize(2200, 700)
    QApplication.processEvents()

    assert table.resize_to_contents_calls == calls_after_render

    table._sort_states = {
        ProductTable.NAME_COLUMN: Qt.SortOrder.DescendingOrder,
    }
    table._apply_current_sort()
    QApplication.processEvents()

    calls_after_sort = table.resize_to_contents_calls
    assert table._preferred_widths_cache is None

    table.resize(2100, 700)
    QApplication.processEvents()

    assert table.resize_to_contents_calls > calls_after_sort

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

    assert table.resize_to_contents_calls > calls_after_render
    assert table._preferred_widths_cache is not None

    table.close()


def test_product_table_stock_width_stays_content_fitted_when_window_grows():
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

    assert table.columnWidth(ProductTable.STOCK_COLUMN) == initial_width

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

    assert ProductTable.MIN_COLUMN_WIDTHS[ProductTable.PRICE_SAMPLE_COLUMN] == 88
    assert ProductTable.MIN_COLUMN_WIDTHS[ProductTable.PRICE_HUNDRED_COLUMN] == 88
    assert ProductTable.MIN_COLUMN_WIDTHS[ProductTable.PRICE_THOUSAND_COLUMN] == 88
    assert table.columnWidth(ProductTable.PRICE_SAMPLE_COLUMN) == 88
    assert table.columnWidth(ProductTable.PRICE_HUNDRED_COLUMN) == 88
    assert table.columnWidth(ProductTable.PRICE_THOUSAND_COLUMN) == 88

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


def test_detail_formats_attributes_removes_duplicate_color_and_trailing_periods():
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
    assert item.textAlignment() & Qt.AlignmentFlag.AlignTop
    assert item.textAlignment() & Qt.AlignmentFlag.AlignLeft
    assert table.rowHeight(0) >= ProductImageDelegate.DEFAULT_HEIGHT

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


def test_detail_removes_multiple_colors_already_visible_in_stock():
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


def test_code_column_does_not_grow_when_the_table_has_more_space():
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
    first_width = table.columnWidth(ProductTable.CODE_COLUMN)

    table.resize(2200, 700)
    QApplication.processEvents()

    assert table.columnWidth(ProductTable.CODE_COLUMN) == first_width
    table.close()
