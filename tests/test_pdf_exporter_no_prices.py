from pathlib import Path

from models.product import Product
from exporters.pdf_exporter import PDFExporter


def test_pdf_exporter_does_not_include_price_column(tmp_path, monkeypatch):
    output = tmp_path / "catalogo.pdf"
    product = Product(
        code="FB-100",
        name="Producto",
        category="Categoría",
        price=99.0,
        price_sample=10.0,
        price_hundred=90.0,
        price_thousand=800.0,
        stock=5,
    )

    captured = {}

    class FakeTable:
        def __init__(self, data):
            captured["data"] = data

        def setStyle(self, style):
            captured["style"] = style

    class FakeDoc:
        def __init__(self, filename, pagesize):
            captured["filename"] = filename
            captured["pagesize"] = pagesize

        def build(self, elements):
            captured["elements"] = elements
            Path(output).touch()

    class FakeImage:
        def __init__(self, *args, **kwargs):
            captured["image"] = (args, kwargs)

    monkeypatch.setattr("exporters.pdf_exporter.SimpleDocTemplate", FakeDoc)
    monkeypatch.setattr("exporters.pdf_exporter.Table", FakeTable)
    monkeypatch.setattr("exporters.pdf_exporter.Image", FakeImage)
    monkeypatch.setattr("exporters.pdf_exporter.os.path.exists", lambda _: False)

    PDFExporter.export([product], str(output))

    header = captured["data"][0]
    assert header == ["Imagen", "Código", "Nombre", "Categoría", "Stock"]
    assert "Precio" not in header
    assert "Precio muestra" not in header
    assert "Precio ciento" not in header
    assert "Precio millar" not in header
    assert captured["data"][1][-1] == "5"
