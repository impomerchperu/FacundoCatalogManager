import os
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class PDFExporter:
    @staticmethod
    def export(products, filename):
        doc = SimpleDocTemplate(filename, pagesize=A4)

        elements: list[Any] = []
        styles = getSampleStyleSheet()

        elements.append(Paragraph("Catálogo de Productos", styles["Title"]))
        elements.append(Spacer(1, 20))

        data: list[list[Any]] = [
            [
                "Imagen",
                "Código",
                "Nombre",
                "Categoría",
                "Stock",
            ]
        ]

        for product in products:
            image: Any = ""
            image_path = getattr(product, "image_path", "")
            if image_path and os.path.exists(image_path):
                image = Image(
                    image_path,
                    width=1.5 * cm,
                    height=1.5 * cm,
                )

            data.append(
                [
                    image,
                    product.code,
                    product.name,
                    product.category,
                    str(product.stock),
                ]
            )

        table = Table(data)
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, None),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        elements.append(table)
        doc.build(elements)
