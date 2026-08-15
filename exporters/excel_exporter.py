from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet


class ExcelExporter:
    @staticmethod
    def export(products, filename):
        workbook = Workbook()

        active_sheet = workbook.active

        if active_sheet is None:
            raise RuntimeError("No se pudo crear la hoja Excel")

        sheet: Worksheet = active_sheet

        sheet.title = "Productos"

        sheet.append(
            [
                "Código",
                "Nombre",
                "Categoría",
                "Descripción",
                "Precio",
                "Stock",
            ]
        )

        for product in products:
            sheet.append(
                [
                    product.code,
                    product.name,
                    product.category,
                    product.description,
                    product.price,
                    product.stock,
                ]
            )

        workbook.save(filename)
