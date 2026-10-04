from openpyxl import load_workbook
from openpyxl.utils.units import pixels_to_EMU
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

    assert sheet.max_row == 4
    assert sheet.row_dimensions[2].height == ExcelExporter.INITIAL_ROW_HEIGHT
    assert sheet.max_column == len(ExcelExporter.EXCEL_HEADERS)
    assert [cell.value for cell in sheet[3]] == list(ExcelExporter.EXCEL_HEADERS)
    assert [cell.value for cell in sheet[4]] == [
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

    for cell in sheet[3]:
        assert cell.font.bold is True
        assert cell.alignment.horizontal == "center"

    for header in ("Producto", "Detalle", "Categoría", "Color"):
        cell = sheet.cell(
            row=4,
            column=ExcelExporter._header_index()[header],
        )
        assert cell.alignment.horizontal == "left"
        assert cell.alignment.indent == ExcelExporter.INDENT_LEVEL
        assert cell.alignment.vertical == "center"
        assert cell.alignment.wrap_text is True

    stock = sheet["G4"]
    assert stock.alignment.horizontal == "right"
    assert stock.alignment.indent == ExcelExporter.INDENT_LEVEL
    assert stock.alignment.vertical == "center"
    assert stock.alignment.wrap_text is True

    for coordinate in ("H4", "I4", "J4"):
        cell = sheet[coordinate]
        assert cell.alignment.horizontal == "center"
        assert cell.alignment.vertical == "center"
        assert cell.number_format == ExcelExporter.LOCAL_CURRENCY_FORMAT

    color = sheet["F4"]
    assert color.alignment.vertical == "center"
    assert color.alignment.wrap_text is True
    assert stock.value.count("\n") == color.value.count("\n")
    assert sheet.row_dimensions[4].height >= 30

    assert sheet.auto_filter.ref is None
    assert len(sheet.tables) == 0

    assert len(sheet._images) == 1
    image = sheet._images[0]
    expected_cell_width = int(
        ExcelExporter.COLUMN_WIDTHS["Imagen"]
        * ExcelExporter.EXCEL_COLUMN_PIXELS_PER_WIDTH_UNIT
    )
    expected_width = expected_cell_width - (2 * ExcelExporter.IMAGE_MARGIN_PIXELS)
    expected_height = round(expected_width * 180 / 120)
    assert type(image.anchor).__name__ == "TwoCellAnchor"
    assert image.anchor.editAs == "twoCell"
    assert image.width == expected_width
    assert image.height == expected_height
    assert image.anchor._from.col == 0
    assert image.anchor._from.row == 3
    assert image.anchor._from.colOff == pixels_to_EMU(ExcelExporter.IMAGE_MARGIN_PIXELS)
    assert image.anchor._from.rowOff == pixels_to_EMU(ExcelExporter.IMAGE_MARGIN_PIXELS)
    assert image.anchor.to.col == 0
    assert image.anchor.to.row == 3
    assert image.anchor.to.colOff == pixels_to_EMU(
        ExcelExporter.IMAGE_MARGIN_PIXELS + expected_width
    )
    assert image.anchor.to.rowOff == pixels_to_EMU(
        ExcelExporter.IMAGE_MARGIN_PIXELS + expected_height
    )


def test_export_scales_images_to_column_width_preserving_ratio(tmp_path):
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
    expected_image_width = expected_cell_width - (
        2 * ExcelExporter.IMAGE_MARGIN_PIXELS
    )
    expected_first_height = round(expected_image_width * 200 / 100)
    expected_second_height = round(expected_image_width * 100 / 200)

    assert len(sheet._images) == 2
    assert sheet._images[0].width == expected_image_width
    assert sheet._images[1].width == expected_image_width
    assert sheet._images[0].height == expected_first_height
    assert sheet._images[1].height == expected_second_height

    first_row_height_px = round(
        (sheet.row_dimensions[4].height or 0)
        * ExcelExporter.EXCEL_DPI
        / ExcelExporter.POINTS_PER_INCH
    )
    second_row_height_px = round(
        (sheet.row_dimensions[5].height or 0)
        * ExcelExporter.EXCEL_DPI
        / ExcelExporter.POINTS_PER_INCH
    )
    assert first_row_height_px == expected_first_height + (
        2 * ExcelExporter.IMAGE_MARGIN_PIXELS
    )
    assert second_row_height_px == expected_second_height + (
        2 * ExcelExporter.IMAGE_MARGIN_PIXELS
    )
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

    assert sheet["F4"].value == "Rojo\nAzul\nVerde"
    assert sheet["G4"].value == "100\n25\n8"
    assert sheet["F4"].alignment.vertical == "center"
    assert sheet["G4"].alignment.vertical == "center"
    assert sheet["F4"].alignment.horizontal == "left"
    assert sheet["G4"].alignment.horizontal == "right"
    assert sheet["F4"].alignment.indent == ExcelExporter.INDENT_LEVEL
    assert sheet["G4"].alignment.indent == ExcelExporter.INDENT_LEVEL
    assert sheet.row_dimensions[4].height >= 45


def test_export_with_no_products_creates_only_headers(tmp_path):
    filename = tmp_path / "catalogo.xlsx"

    ExcelExporter.export([], filename)

    workbook = load_workbook(filename)
    sheet = workbook["Productos"]

    assert [cell.value for cell in sheet[3]] == list(ExcelExporter.EXCEL_HEADERS)
    assert sheet.max_column == len(ExcelExporter.EXCEL_HEADERS)
    assert sheet.max_row == 3
    assert len(sheet.tables) == 0
    assert sheet.auto_filter.ref is None
