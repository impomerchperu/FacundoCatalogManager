from zipfile import ZipFile

from openpyxl import load_workbook
from PIL import Image

from exporters.catalog_export_schema import EXPORT_HEADERS
from exporters.excel_exporter import ExcelExporter
from models.product import Product


def test_export_embeds_images_and_keeps_one_stock_cell(tmp_path):
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

    workbook = load_workbook(filename)
    sheet = workbook["Productos"]

    assert [cell.value for cell in sheet[1]] == list(EXPORT_HEADERS)
    assert sheet["A2"].value is None
    assert [cell.value for cell in sheet[2]][1:] == [
        "FB-100",
        "Producto",
        "Detalle",
        "Categoría",
        5,
        "Rojo: 3\nAzul: 2",
        10.0,
        90.0,
        800.0,
    ]
    assert len(sheet._images) == 1

    image = sheet._images[0]
    assert image.width <= ExcelExporter.IMAGE_MAX_SIZE_PX
    assert image.height <= ExcelExporter.IMAGE_MAX_SIZE_PX
    assert sheet.row_dimensions[2].height is not None
    assert sheet.row_dimensions[2].height >= image.height * 0.75

    stock_cell = sheet["G2"]
    assert stock_cell.alignment.horizontal == "left"
    assert stock_cell.alignment.vertical == "center"
    assert stock_cell.alignment.wrap_text is True
    assert stock_cell.fill.fill_type == "solid"
    assert stock_cell.fill.fgColor.rgb == "FFFFE8E8"
    assert len(
        [image for image in sheet._images if image.anchor._from.col == 6]
    ) == 0

    assert sheet.freeze_panes == "A2"
    assert sheet.auto_filter.ref == "A1:J2"

    assert len(sheet.tables) == 1
    table = sheet.tables["CatalogoProductos"]
    assert table.ref == "A1:J2"
    assert table.autoFilter is not None

    with ZipFile(filename) as archive:
        names = set(archive.namelist())
        assert not any(
            name.startswith("xl/slicers/") for name in names
        )
        assert not any(
            name.startswith("xl/slicerCaches/") for name in names
        )


def test_export_adjusts_row_height_for_text_and_images(tmp_path):
    filename = tmp_path / "catalogo.xlsx"
    image_path = tmp_path / "FB-200.jpg"
    Image.new("RGB", (400, 100), "white").save(image_path)

    product = Product(
        code="FB-200",
        name="Producto con un nombre suficientemente largo para envolver",
        description=(
            "Detalle muy largo del producto que debe ocupar varias líneas "
            "en la columna correspondiente para conservar todo el contenido."
        )
        * 4,
        category="Categoría extensa",
        image_path=str(image_path),
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

    assert [cell.value for cell in sheet[1]] == list(EXPORT_HEADERS)
    assert sheet.max_column == len(EXPORT_HEADERS)
    assert sheet.max_row == 1
    assert len(sheet.tables) == 0
