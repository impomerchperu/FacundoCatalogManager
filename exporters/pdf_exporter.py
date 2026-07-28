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

        data = [["Imagen", "Código", "Nombre", "Categoría", "Precio", "Stock"]]

        for product in products:
            image = ""

            if product[7] and os.path.exists(product[7]):
                img = Image(product[7], width=1.5 * cm, height=1.5 * cm)

                image = img

            data.append(
                [
                    image,
                    product[1],
                    product[2],
                    product[3],
                    str(product[5]),
                    str(product[6]),
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
