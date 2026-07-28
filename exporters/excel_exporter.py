from openpyxl import Workbook


class ExcelExporter:
    @staticmethod
    def export(products, filename):

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Productos"

        sheet.append(
            ["Código", "Nombre", "Categoría", "Descripción", "Precio", "Stock"]
        )

        for product in products:
            sheet.append(
                [product[1], product[2], product[3], product[4], product[5], product[6]]
            )

        workbook.save(filename)
