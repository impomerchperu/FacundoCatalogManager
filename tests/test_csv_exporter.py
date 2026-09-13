import csv

from exporters.csv_exporter import CSVExporter
from models.product import Product


def test_export_writes_catalog_fields(tmp_path):
    filename = tmp_path / "catalogo.csv"
    products = [
        Product(
            code="FB-5013",
            name="Producto de prueba",
            category="Categoría",
            description="Detalle",
            stock=12,
            price_sample=2.5,
            price_hundred=180,
            price_thousand=1600,
            image_path="images/FB-5013.jpg",
        )
    ]

    CSVExporter.export(products, filename)

    with filename.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file, delimiter=";"))

    assert rows == [
        {
            "Código": "FB-5013",
            "Imagen": "images/FB-5013.jpg",
            "Producto(s)": "Producto de prueba",
            "Detalle": "Detalle",
            "Stock disponible": "12",
            "Precio muestra": "2.5",
            "Precio ciento": "180",
            "Precio millar": "1600",
        }
    ]
