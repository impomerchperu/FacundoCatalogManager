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
    expected_widths = {
        "B": 25.0,
        "C": 12.11,
        "D": 31.67,
        "E": 41.22,
        "F": 25.22,
        "G": 16.89,
        "H": 9.44,
        "I": 12.11,
        "J": 12.11,
        "K": 12.11,
    }
    for column, width in expected_widths.items():
        assert sheet.column_dimensions[column].width == width

    assert sheet["A1"].value is None
    assert sheet["A2"].value is None
    assert sheet.freeze_panes == "B2"
    assert sheet.sheet_view.zoomScale == 85
    assert sheet.column_dimensions["C"].width == 12.11
    assert sheet.column_dimensions["D"].width == 31.67
    assert sheet.column_dimensions["E"].width == 41.22
    assert sheet.column_dimensions["F"].width == 25.22
    assert sheet.column_dimensions["G"].width == 16.89
    assert sheet.column_dimensions["H"].width == 9.44
    assert sheet.column_dimensions["B"].width == 25.0

    assert sheet["C1"].font.name == "Segoe UI"
    assert sheet["C1"].font.size == 14
    assert sheet["C1"].font.bold is True
    assert sheet["D2"].font.name == "Segoe UI"
    assert sheet["D2"].font.size == 10

    assert sheet["C2"].alignment.horizontal == "center"
    assert sheet["F2"].value == "Enmicadoras / Laminadoras"
    assert sheet["G2"].alignment.horizontal == "center"
    assert sheet["G2"].alignment.wrap_text is True
    assert sheet["G2"].alignment.shrink_to_fit is None
    assert sheet["H2"].alignment.horizontal == "center"
    for coordinate in ("I2", "J2", "K2"):
        assert sheet[coordinate].alignment.horizontal == "center"
        assert sheet[coordinate].number_format == ExcelExporter.LOCAL_CURRENCY_FORMAT

    assert sheet.row_dimensions[1].height == 42
    assert sheet.row_dimensions[2].height == ExcelExporter.MIN_ROW_HEIGHT_POINTS

    assert len(sheet.tables) == 1
    table = sheet.tables["CatalogoProductos"]
    assert table.ref == "B1:K2"
    assert table.tableStyleInfo is not None
    assert table.tableStyleInfo.name == "TableStyleLight1"
    assert table.autoFilter is not None
    assert len(table.autoFilter.filterColumn) == len(ExcelExporter.EXCEL_HEADERS)
    assert all(
        filter_column.showButton is False
        for filter_column in table.autoFilter.filterColumn
    )
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
    assert image.width >= int(ExcelExporter.COLUMN_WIDTHS["Imagen"] * 7)
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
    assert detail_width == ExcelExporter.COLUMN_WIDTHS["Detalle"]


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
