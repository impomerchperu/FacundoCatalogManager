from openpyxl import load_workbook
from PIL import Image

from exporters.excel_exporter import ExcelExporter
from models.product import Product


def test_export_writes_requested_layout_and_embeds_image(tmp_path):
    filename = tmp_path / "catalogo.xlsx"
    image_path = tmp_path / "FB-100.jpg"
    Image.new("RGB", (120, 180), "white").save(image_path)

    product = Product(
        code="FB-100",
        name="Producto",
        category="Enmicadoras / Laminadoras",
        description="Detalle",
        stock=5,
        color_stock={"Rojo": 3, "Azul": 2},
        price_sample=10,
        price_hundred=90,
        price_thousand=800,
        image_path=str(image_path),
    )

    ExcelExporter.export([product], filename)

    workbook = load_workbook(filename, read_only=False)
    sheet = workbook["Productos"]

    assert sheet.max_row == 2
    assert sheet.max_column == len(ExcelExporter.EXCEL_HEADERS)
    assert [cell.value for cell in sheet[1]] == list(ExcelExporter.EXCEL_HEADERS)
    assert [cell.value for cell in sheet[2]] == [
        None,
        "FB-100",
        "Producto",
        "Detalle",
        "Enmicadoras / Laminadoras",
        "Rojo\nAzul",
        "3\n2",
        10.0,
        90.0,
        800.0,
    ]

    for cell in sheet[1]:
        assert cell.font.bold is True
        assert cell.alignment.horizontal == "center"

    for header in ("Producto", "Detalle", "Categoría", "Color"):
        cell = sheet.cell(
            row=2,
            column=ExcelExporter._header_index()[header],
        )
        assert cell.alignment.horizontal == "left"
        assert cell.alignment.indent == ExcelExporter.INDENT_LEVEL
        assert cell.alignment.vertical == "center"
        assert cell.alignment.wrap_text is True

    stock = sheet["G2"]
    assert stock.alignment.horizontal == "right"
    assert stock.alignment.indent == ExcelExporter.INDENT_LEVEL
    assert stock.alignment.vertical == "center"
    assert stock.alignment.wrap_text is True

    for coordinate in ("H2", "I2", "J2"):
        cell = sheet[coordinate]
        assert cell.alignment.horizontal == "center"
        assert cell.alignment.vertical == "center"
        assert cell.number_format == ExcelExporter.LOCAL_CURRENCY_FORMAT

    color = sheet["F2"]
    assert color.alignment.vertical == "center"
    assert color.alignment.wrap_text is True
    assert stock.value.count("\n") == color.value.count("\n")
    assert sheet.row_dimensions[2].height >= 30

    assert sheet.auto_filter.ref is None
    assert len(sheet.tables) == 0

    assert len(sheet._images) == 1
    image = sheet._images[0]
    assert type(image.anchor).__name__ == "TwoCellAnchor"
    assert image.anchor.editAs == "twoCell"
    assert image.anchor._from.col == 0
    assert image.anchor._from.row == 1
    assert image.anchor.to.col == 1
    assert image.anchor.to.row == 2


def test_export_scales_images_to_image_column_width_preserving_ratio(tmp_path):
    filename = tmp_path / "catalogo.xlsx"
    image_path_a = tmp_path / "FB-200.jpg"
    image_path_b = tmp_path / "FB-201.jpg"
    Image.new("RGB", (100, 200), "white").save(image_path_a)
    Image.new("RGB", (200, 100), "white").save(image_path_b)

    products = [
        Product(
            code="FB-200",
            name="Producto A",
            category="Categoría",
            description="Detalle",
            image_path=str(image_path_a),
        ),
        Product(
            code="FB-201",
            name="Producto B",
            category="Categoría",
            description="Detalle",
            image_path=str(image_path_b),
        ),
    ]

    ExcelExporter.export(products, filename)

    workbook = load_workbook(filename)
    sheet = workbook["Productos"]

    expected_cell_width = int(
        ExcelExporter.COLUMN_WIDTHS["Imagen"]
        * ExcelExporter.EXCEL_COLUMN_PIXELS_PER_WIDTH_UNIT
    )
    expected_inner_width = (
        expected_cell_width - ExcelExporter.IMAGE_CELL_PADDING_PX * 2
    )

    assert len(sheet._images) == 2
    assert all(image.width == expected_cell_width for image in sheet._images)

    first_row_height_px = round(
        (sheet.row_dimensions[2].height or 0)
        * ExcelExporter.EXCEL_DPI
        / ExcelExporter.POINTS_PER_INCH
    )
    second_row_height_px = round(
        (sheet.row_dimensions[3].height or 0)
        * ExcelExporter.EXCEL_DPI
        / ExcelExporter.POINTS_PER_INCH
    )
    assert first_row_height_px >= expected_inner_width * 2 + 2 * ExcelExporter.IMAGE_CELL_PADDING_PX
    assert second_row_height_px >= expected_inner_width / 2 + 2 * ExcelExporter.IMAGE_CELL_PADDING_PX
    assert first_row_height_px > second_row_height_px


def test_export_preserves_multiple_color_stock_lines_at_same_height(tmp_path):
    filename = tmp_path / "catalogo.xlsx"
    product = Product(
        code="FB-200",
        name="Producto",
        category="Categoría",
        description="Detalle",
        color_stock={
            "Rojo": 100,
            "Azul": 25,
            "Verde": 8,
        },
    )

    ExcelExporter.export([product], filename)

    workbook = load_workbook(filename)
    sheet = workbook["Productos"]

    assert sheet["F2"].value == "Rojo\nAzul\nVerde"
    assert sheet["G2"].value == "100\n25\n8"
    assert sheet["F2"].alignment.vertical == "center"
    assert sheet["G2"].alignment.vertical == "center"
    assert sheet["F2"].alignment.horizontal == "left"
    assert sheet["G2"].alignment.horizontal == "right"
    assert sheet["F2"].alignment.indent == ExcelExporter.INDENT_LEVEL
    assert sheet["G2"].alignment.indent == ExcelExporter.INDENT_LEVEL
    assert sheet.row_dimensions[2].height >= 45


def test_export_with_no_products_creates_only_headers(tmp_path):
    filename = tmp_path / "catalogo.xlsx"

    ExcelExporter.export([], filename)

    workbook = load_workbook(filename)
    sheet = workbook["Productos"]

    assert [cell.value for cell in sheet[1]] == list(ExcelExporter.EXCEL_HEADERS)
    assert sheet.max_column == len(ExcelExporter.EXCEL_HEADERS)
    assert sheet.max_row == 1
    assert len(sheet.tables) == 0
    assert sheet.auto_filter.ref is None
