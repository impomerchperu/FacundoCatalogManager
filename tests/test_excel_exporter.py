from zipfile import ZipFile
from xml.etree import ElementTree

from openpyxl import load_workbook
from PIL import Image

from exporters.excel_exporter import ExcelExporter
from models.product import Product


def test_export_writes_table_images_color_and_stock_columns(tmp_path):
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

    assert sheet[1][0].value is None
    assert [cell.value for cell in sheet[1][1:11]] == list(
        ExcelExporter.EXCEL_HEADERS,
    )
    assert [cell.value for cell in sheet[2][1:11]] == [
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

    assert len(sheet._images) == 1
    assert type(sheet._images[0].anchor).__name__ == "TwoCellAnchor"

    assert sheet["G2"].fill.fill_type == "solid"
    assert sheet["G2"].fill.fgColor.rgb == "FFFFE8E8"
    assert sheet["H2"].fill.fill_type == "solid"
    assert sheet["H2"].fill.fgColor.rgb == "FFFFE8E8"

    assert sheet["C2"].alignment.horizontal == "center"
    assert sheet["H2"].alignment.horizontal == "center"
    for coordinate in ("I2", "J2", "K2"):
        assert sheet[coordinate].alignment.horizontal == "center"
        assert sheet[coordinate].number_format == '"S/ " #,##0.00'

    assert sheet["G2"].alignment.horizontal == "left"
    assert sheet["G2"].alignment.vertical == "center"
    assert sheet["H2"].alignment.vertical == "center"
    assert sheet.freeze_panes == "B2"
    assert sheet.auto_filter.ref is None

    assert len(sheet.tables) == 1
    table = sheet.tables["CatalogoProductos"]
    assert table.ref == "B1:K2"
    assert table.autoFilter is not None
    assert table.tableStyleInfo is not None
    assert table.tableStyleInfo.name == "TableStyleLight2"

    with ZipFile(filename) as archive:
        names = set(archive.namelist())
        assert "xl/slicerCaches/slicerCache1.xml" in names
        assert "xl/slicers/slicer1.xml" in names

        cache_xml = archive.read(
            "xl/slicerCaches/slicerCache1.xml",
        ).decode("utf-8")
        slicer_xml = archive.read(
            "xl/slicers/slicer1.xml",
        ).decode("utf-8")
        workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")
        sheet_xml = archive.read(
            "xl/worksheets/sheet1.xml",
        ).decode("utf-8")
        workbook_rels = archive.read(
            "xl/_rels/workbook.xml.rels",
        ).decode("utf-8")
        sheet_rels = archive.read(
            "xl/worksheets/_rels/sheet1.xml.rels",
        ).decode("utf-8")
        drawing_xml = archive.read(
            "xl/drawings/drawing1.xml",
        ).decode("utf-8")
        table_xml = archive.read(
            "xl/tables/table1.xml",
        ).decode("utf-8")

        for xml in (
            cache_xml,
            slicer_xml,
            workbook_xml,
            sheet_xml,
            workbook_rels,
            sheet_rels,
            drawing_xml,
            table_xml,
        ):
            ElementTree.fromstring(xml)

        assert 'tableId="1" column="5"' in cache_xml
        assert 'sourceName="Categoría"' in cache_xml
        assert 'name="Categoría"' in slicer_xml
        assert 'cache="SegmentaciónDeDatos_Categoría"' in slicer_xml
        assert "SegmentaciónDeDatos_Categoría" in workbook_xml
        assert "slicerCaches" in workbook_xml
        assert "slicerList" in sheet_xml
        assert "slicerCache" in workbook_rels
        assert "relationships/slicer" in sheet_rels
        assert '<xdr:twoCellAnchor>' in drawing_xml
        assert '<xdr:col>0</xdr:col>' in drawing_xml
        assert '<xdr:row>12</xdr:row>' in drawing_xml
        assert "Categoría" in drawing_xml
        assert '<table xmlns=' in table_xml
        assert 'ref="B1:K2"' in table_xml
        assert '<autoFilter ref="B1:K2"' in table_xml


def test_export_adjusts_row_height_for_text(tmp_path):
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

    assert sheet[1][0].value is None
    assert [cell.value for cell in sheet[1][1:11]] == list(
        ExcelExporter.EXCEL_HEADERS,
    )
    assert sheet.max_column == 11
    assert sheet.max_row == 1
    assert len(sheet.tables) == 0
