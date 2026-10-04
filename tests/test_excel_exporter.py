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

    assert workbook.read_only is False
    assert sheet.max_row == 2
    assert sheet.max_column == 11
    assert [cell.value for cell in sheet[1]] == [
        None,
        *ExcelExporter.EXCEL_HEADERS,
    ]
    assert [cell.value for cell in sheet[2]] == [
        None,
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

    assert sheet.column_dimensions["A"].width == ExcelExporter.SIDEBAR_COLUMN_WIDTH
    for header, column in ExcelExporter._header_index().items():
        letter = sheet.cell(row=1, column=column).column_letter
        width = sheet.column_dimensions[letter].width
        assert width is not None
        assert ExcelExporter.COLUMN_MIN_WIDTHS[header] <= width
        assert width <= ExcelExporter.COLUMN_MAX_WIDTHS[header]

    assert sheet["A1"].value is None
    assert sheet["A2"].value is None
    assert sheet.freeze_panes == "B2"
    assert sheet.sheet_view.zoomScale == 85
    assert sheet.column_dimensions["F"].width >= 25.0
    assert sheet.column_dimensions["G"].width >= 14.0
    assert sheet.column_dimensions["B"].width >= 24.0

    assert sheet["C1"].font.name == "Segoe UI"
    assert sheet["C1"].font.size == 11
    assert sheet["C1"].font.bold is True
    assert sheet["D2"].font.name == "Segoe UI"
    assert sheet["D2"].font.size == 10

    assert sheet["C2"].alignment.horizontal == "center"
    assert sheet["F2"].value == "Enmicadoras / Laminadoras"
    assert sheet["G2"].alignment.horizontal == "left"
    assert sheet["G2"].alignment.wrap_text is False
    assert sheet["G2"].alignment.shrink_to_fit is True
    assert sheet["H2"].alignment.horizontal == "center"
    for coordinate in ("I2", "J2", "K2"):
        assert sheet[coordinate].alignment.horizontal == "center"
        assert sheet[coordinate].number_format == ExcelExporter.LOCAL_CURRENCY_FORMAT

    assert sheet.row_dimensions[1].height == 32
    assert sheet.row_dimensions[2].height == ExcelExporter.MIN_ROW_HEIGHT_POINTS

    assert len(sheet.tables) == 0
    assert sheet.auto_filter.ref is None
    assert sheet["A1"].fill.fill_type is None
    assert sheet["C2"].fill.fill_type is None

    assert len(sheet._images) == 1
    image = sheet._images[0]
    assert type(image.anchor).__name__ == "TwoCellAnchor"
    assert image.anchor.editAs == "twoCell"
    assert image.anchor._from.col == 1
    assert image.anchor._from.row == 1
    assert image.anchor.to.col == 2
    assert image.anchor.to.row == 2
    assert image.width >= int(ExcelExporter.COLUMN_MIN_WIDTHS["Imagen"] * 7)
    assert image.height > 0


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

    detail_column = ExcelExporter._header_index()["Detalle"]
    detail_letter = sheet.cell(row=1, column=detail_column).column_letter
    detail_width = sheet.column_dimensions[detail_letter].width
    assert detail_width is not None
    assert (
        ExcelExporter.COLUMN_MIN_WIDTHS["Detalle"]
        <= detail_width
        <= ExcelExporter.COLUMN_MAX_WIDTHS["Detalle"]
    )


def test_export_with_no_products_creates_only_headers(tmp_path):
    filename = tmp_path / "catalogo.xlsx"

    ExcelExporter.export([], filename)

    workbook = load_workbook(filename)
    sheet = workbook["Productos"]

    assert [cell.value for cell in sheet[1]] == [
        None,
        *ExcelExporter.EXCEL_HEADERS,
    ]
    assert sheet.max_column == 11
    assert sheet.max_row == 1
    assert len(sheet.tables) == 0
    assert sheet.auto_filter.ref is None
