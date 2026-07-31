import os

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

        elements = []

        styles = getSampleStyleSheet()

        title = Paragraph("Catálogo de Productos", styles["Title"])

        elements.append(title)

        elements.append(Spacer(1, 20))

        data = [
            [
                "Imagen",
                "Código",
                "Nombre",
                "Categoría",
                "Precio",
                "Stock",
            ]
        ]

        for product in products:
            image = ""

            if product.image_path and os.path.exists(product.image_path):
                img = Image(product.image_path, width=1.5 * cm, height=1.5 * cm)

                image = img

            data.append(
                [
                    image,
                    product.code,
                    product.name,
                    product.category,
                    str(product.price),
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
