from openpyxl import load_workbook

from exporters.catalog_export_schema import EXPORT_HEADERS
from exporters.excel_exporter import ExcelExporter
from models.product import Product


def test_export_writes_current_catalog_fields_and_formatting(tmp_path):
    filename = tmp_path / "catalogo.xlsx"
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
        image_path="images/FB-100.jpg",
    )

    ExcelExporter.export([product], filename)

    workbook = load_workbook(filename)
    sheet = workbook["Productos"]

    assert [cell.value for cell in sheet[1]] == list(EXPORT_HEADERS)
    assert [cell.value for cell in sheet[2]] == [
        "images/FB-100.jpg",
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
    assert sheet.freeze_panes == "A2"
    assert sheet["H2"].number_format == '"S/ " #,##0.00'
    assert sheet["J2"].number_format == '"S/ " #,##0.00'
