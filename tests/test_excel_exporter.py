from xml.etree import ElementTree
from zipfile import ZipFile

from openpyxl import load_workbook
from PIL import Image

from exporters import excel_exporter as excel_module
from exporters.excel_exporter import ExcelExporter
from models.product import Product


def test_export_writes_table_images_color_and_stock_columns(tmp_path, monkeypatch):
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

    monkeypatch.setenv("FCM_EXCEL_SLICER_MODE", "disabled")
    ExcelExporter.export([product], filename)

    workbook = load_workbook(filename)
    sheet = workbook["Productos"]

    assert sheet[1][0].value is None
    assert [cell.value for cell in sheet[1][1:11]] == list(
        ExcelExporter.EXCEL_HEADERS,
    )
    assert [cell.value for cell in sheet[2][1:11]] == [
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

    assert len(sheet._images) == 1
    image_anchor = sheet._images[0].anchor
    assert type(image_anchor).__name__ == "TwoCellAnchor"
    assert image_anchor.editAs == "twoCell"
    assert image_anchor._from.col == 1
    assert image_anchor._from.row == 1
    assert image_anchor.to.col == 1
    assert image_anchor.to.row == 1
    assert image_anchor.to.colOff > 0
    assert image_anchor.to.rowOff > 0

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
        assert "xl/slicerCaches/slicerCache.xml" not in names
        assert "xl/slicers/slicer.xml" not in names

        workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")
        sheet_xml = archive.read(
            "xl/worksheets/sheet1.xml",
        ).decode("utf-8")
        drawing_xml = archive.read(
            "xl/drawings/drawing1.xml",
        ).decode("utf-8")
        table_xml = archive.read(
            "xl/tables/table1.xml",
        ).decode("utf-8")

        for xml in (
            workbook_xml,
            sheet_xml,
            drawing_xml,
            table_xml,
        ):
            ElementTree.fromstring(xml)

        drawing_root = ElementTree.fromstring(drawing_xml)
        table_root = ElementTree.fromstring(table_xml)

        assert (
            drawing_root.tag
            == "{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}"
            "wsDr"
        )
        anchor_elements = drawing_root.findall(
            "{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}"
            "twoCellAnchor",
        )
        assert len(anchor_elements) == 1
        assert anchor_elements[0].attrib["editAs"] == "twoCell"

        assert (
            table_root.tag
            == "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}table"
        )
        assert 'ref="B1:K2"' in table_xml
        assert '<autoFilter ref="B1:K2"' in table_xml


def test_export_auto_delegates_slicer_to_native_helper(tmp_path, monkeypatch):
    filename = tmp_path / "catalogo.xlsx"
    product = Product(
        code="FB-300",
        name="Producto",
        category="Categoría",
    )
    captured = {}

    def fake_add_category_slicer(filename_arg, *, table_name, field_name):
        captured["filename"] = filename_arg
        captured["table_name"] = table_name
        captured["field_name"] = field_name

    monkeypatch.setattr(
        excel_module,
        "add_category_slicer",
        fake_add_category_slicer,
    )

    ExcelExporter.export([product], filename)

    assert captured["filename"] == filename
    assert captured["table_name"] == "CatalogoProductos"
    assert captured["field_name"] == "Categoría"


def test_export_disabled_slicer_does_not_inject_unsupported_ooxml(
    tmp_path,
):
    filename = tmp_path / "catalogo.xlsx"
    product = Product(
        code="FB-400",
        name="Producto seguro",
        category="Categoría",
    )

    import os

    previous = os.environ.get("FCM_EXCEL_SLICER_MODE")
    os.environ["FCM_EXCEL_SLICER_MODE"] = "disabled"
    try:
        ExcelExporter.export([product], filename)
    finally:
        if previous is None:
            os.environ.pop("FCM_EXCEL_SLICER_MODE", None)
        else:
            os.environ["FCM_EXCEL_SLICER_MODE"] = previous

    with ZipFile(filename) as archive:
        names = set(archive.namelist())
        assert not any(
            name.startswith("xl/slicerCaches/")
            for name in names
        )
        assert not any(
            name.startswith("xl/slicers/")
            for name in names
        )


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
