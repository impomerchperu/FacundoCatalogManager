from openpyxl import Workbook


class ExcelExporter:
    @staticmethod
    def export(products, filename):

        workbook = Workbook()

        sheet = workbook.active

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
