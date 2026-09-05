import csv


class CSVExporter:
    """Exporta el catálogo en CSV UTF-8 compatible con hojas de cálculo."""

    FIELDNAMES = (
        "Código",
        "Imagen",
        "Producto(s)",
        "Detalle",
        "Stock disponible",
        "Precio muestra",
        "Precio ciento",
        "Precio millar",
    )

    @classmethod
    def export(cls, products, filename) -> None:
        with open(filename, "w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=cls.FIELDNAMES,
                delimiter=";",
                extrasaction="ignore",
            )
            writer.writeheader()
            for product in products:
                writer.writerow(
                    {
                        "Código": product.code,
                        "Imagen": product.image_path or product.image_url,
                        "Producto(s)": product.name,
                        "Detalle": product.description,
                        "Stock disponible": product.stock,
                        "Precio muestra": product.price_sample,
                        "Precio ciento": product.price_hundred,
                        "Precio millar": product.price_thousand,
                    }
                )
