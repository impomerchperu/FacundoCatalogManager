import csv

from exporters.catalog_export_schema import EXPORT_HEADERS, export_rows


class CSVExporter:
    """Exporta el catálogo con el mismo contenido de la tabla principal."""

    FIELDNAMES = EXPORT_HEADERS

    @classmethod
    def export(cls, products, filename) -> None:
        rows = export_rows(products)
        with open(filename, "w", encoding="utf-8-sig", newline="") as file:
            writer = csv.writer(
                file,
                delimiter=";",
                quoting=csv.QUOTE_MINIMAL,
            )
            writer.writerow(cls.FIELDNAMES)
            for row in rows:
                writer.writerow(
                    [
                        row["image"],
                        row["code"],
                        row["name"],
                        row["description"],
                        row["category"],
                        row["stock"],
                        row["stock_by_color"],
                        row["price_sample"],
                        row["price_hundred"],
                        row["price_thousand"],
                    ]
                )
