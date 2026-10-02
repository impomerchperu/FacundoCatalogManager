from pathlib import Path

from exporters.catalog_export_schema import EXPORT_HEADERS
from exporters.pdf_exporter import PDFExporter
from models.product import Product


def test_pdf_exporter_uses_current_catalog_fields(tmp_path, monkeypatch):
    output = tmp_path / "catalogo.pdf"
    product = Product(
        code="FB-100",
        name="Producto",
        category="Categoría",
        description="Detalle",
        price=99.0,
        price_sample=10.0,
        price_hundred=90.0,
        price_thousand=800.0,
        stock=5,
        color_stock={"Rojo": 3},
    )

    captured = {}

    class FakeTable:
        def __init__(self, data, **kwargs):
            captured["data"] = data
            captured["kwargs"] = kwargs

        def setStyle(self, style):
            captured["style"] = style

    class FakeDoc:
        def __init__(self, filename, **kwargs):
            captured["filename"] = filename
            captured["kwargs"] = kwargs

        def build(self, elements):
            captured["elements"] = elements
            Path(output).touch()

    monkeypatch.setattr("exporters.pdf_exporter.LongTable", FakeTable)
    monkeypatch.setattr("exporters.pdf_exporter.SimpleDocTemplate", FakeDoc)
    monkeypatch.setattr(
        "exporters.pdf_exporter.os.path.exists",
        lambda _: False,
    )

    PDFExporter.export([product], str(output))

    header = [
        cell.getPlainText()
        for cell in captured["data"][0]
    ]
    assert header == list(EXPORT_HEADERS)

    row = captured["data"][1]
    assert row[1].getPlainText() == "FB-100"
    assert row[2].getPlainText() == "Producto"
    assert row[3].getPlainText() == "Detalle"
    assert row[4].getPlainText() == "Categoría"
    assert row[5].getPlainText() == "5"
    assert row[6].getPlainText() == "Rojo: 3"
    assert row[7].getPlainText() == "S/ 10.00"
    assert row[8].getPlainText() == "S/ 90.00"
    assert row[9].getPlainText() == "S/ 800.00"
