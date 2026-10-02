import csv

from exporters.catalog_export_schema import EXPORT_HEADERS
from exporters.csv_exporter import CSVExporter
from models.product import Product


def test_export_writes_current_catalog_fields(tmp_path):
    filename = tmp_path / "catalogo.csv"
    products = [
        Product(
            code="FB-5013",
            name="Producto de prueba",
            category="Categoría",
            description="Detalle",
            stock=12,
            color_stock={"Rojo": 5, "Azul": 7},
            price_sample=2.5,
            price_hundred=180,
            price_thousand=1600,
            image_path="images/FB-5013.jpg",
        )
    ]

    CSVExporter.export(products, filename)

    with filename.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.reader(file, delimiter=";"))

    assert rows[0] == list(EXPORT_HEADERS)
    assert rows[1] == [
        "images/FB-5013.jpg",
        "FB-5013",
        "Producto de prueba",
        "Detalle",
        "Categoría",
        "12",
        "Rojo: 5\nAzul: 7",
        "2.5",
        "180.0",
        "1600.0",
    ]
