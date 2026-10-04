from openpyxl import load_workbook
from PIL import Image

from exporters.excel_exporter import ExcelExporter
from models.product import Product


def test_export_writes_complete_editable_catalog_with_image(tmp_path):
    filename = tmp_path / "catalogo.xlsx"
    image_path = tmp_path / "FB-100.jpg"
    Image.new("RGB", (120, 180), "white").save(image_path)

    product = Product(
        code="FB-100",
        name="Producto",
        category="Categoría",
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

    assert workbook.read_only is False
    assert sheet.max_row == 2
    assert sheet.max_column == 10
    assert [cell.value for cell in sheet[1]] == list(
        ExcelExporter.EXCEL_HEADERS,
    )
    assert [cell.value for cell in sheet[2]] == [
        None,
        "FB-100",
        "Producto",
        "Detalle",
        "Categoría",
        "Rojo\nAzul",
        "3\n2",
        10.0,
        90.0,
        800.0,
    ]

    expected_widths = {
        "A": 17,
        "B": 14,
        "C": 42,
        "D": 48,
        "E": 28,
        "F": 24,
        "G": 12,
        "H": 18,
        "I": 18,
        "J": 18,
    }
    for column, width in expected_widths.items():
        assert sheet.column_dimensions[column].width == width

    assert sheet["A1"].font.name == "Segoe UI"
    assert sheet["A1"].font.size == 11
    assert sheet["A1"].font.bold is True
    assert sheet["B2"].font.name == "Segoe UI"
    assert sheet["B2"].font.size == 10

    assert sheet.row_dimensions[1].height == 32
    assert sheet.row_dimensions[2].height == ExcelExporter.MIN_ROW_HEIGHT_POINTS

    assert len(sheet.tables) == 0

    assert len(sheet._images) == 1
    image = sheet._images[0]
    assert type(image.anchor).__name__ == "OneCellAnchor"
    assert image.anchor._from.col == 0
    assert image.anchor._from.row == 1
    assert image.width <= ExcelExporter.IMAGE_MAX_SIZE_PX
    assert image.height <= ExcelExporter.IMAGE_MAX_SIZE_PX
    assert image.width <= int(17 * 7) - 4
    assert image.height <= int(92 * 96 / 72) - 4


def test_export_adjusts_row_height_to_long_text(tmp_path):
    filename = tmp_path / "catalogo.xlsx"
    product = Product(
        code="FB-200",
        name="Producto con un nombre suficientemente largo para envolver",
        description=(
            "Detalle muy largo del producto que debe ocupar varias líneas "
            "en la columna correspondiente para conservar todo el contenido."
        )
        * 4,
        category="Categoría extensa",
        color_stock={"Rojo": 5, "Azul": 2},
    )

    ExcelExporter.export([product], filename)

    workbook = load_workbook(filename)
    sheet = workbook["Productos"]

    assert sheet.row_dimensions[2].height is not None
    assert sheet.row_dimensions[2].height > ExcelExporter.MIN_ROW_HEIGHT_POINTS


def test_export_with_no_products_creates_only_headers(tmp_path):
    filename = tmp_path / "catalogo.xlsx"

    ExcelExporter.export([], filename)

    workbook = load_workbook(filename)
    sheet = workbook["Productos"]

    assert [cell.value for cell in sheet[1]] == list(
        ExcelExporter.EXCEL_HEADERS,
    )
    assert sheet.max_column == 10
    assert sheet.max_row == 1
    assert len(sheet.tables) == 0
