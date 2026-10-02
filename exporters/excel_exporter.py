from typing import ClassVar

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.worksheet import Worksheet

from exporters.catalog_export_schema import EXPORT_HEADERS, export_rows


class ExcelExporter:
    """Exporta el catálogo respetando la estructura de la tabla principal."""

    CURRENCY_COLUMNS: ClassVar[set[str]] = {
        "Precio muestra",
        "Precio ciento",
        "Precio millar",
    }

    COLUMN_WIDTHS: ClassVar[dict[str, int]] = {
        "Imagen": 28,
        "Código": 14,
        "Producto": 42,
        "Detalle": 48,
        "Categoría": 28,
        "Stock": 12,
        "Stock por color": 28,
        "Precio muestra": 18,
        "Precio ciento": 18,
        "Precio millar": 18,
    }

    HEADER_FILL: ClassVar[str] = "EAF3FA"
    HEADER_TEXT: ClassVar[str] = "173F6D"
    BORDER_COLOR: ClassVar[str] = "CBDDEA"
    ALT_ROW_FILL: ClassVar[str] = "F8FBFF"

    @classmethod
    def export(cls, products, filename) -> None:
        workbook = Workbook()
        active_sheet = workbook.active
        if active_sheet is None:
            raise RuntimeError("No se pudo crear la hoja Excel")

        sheet: Worksheet = active_sheet
        sheet.title = "Productos"
        rows = export_rows(products)

        sheet.append(list(EXPORT_HEADERS))
        for row in rows:
            sheet.append(
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

        cls._style_sheet(sheet)
        workbook.save(filename)

    @classmethod
    def _style_sheet(cls, sheet: Worksheet) -> None:
        thin = Side(style="thin", color=cls.BORDER_COLOR)
        border = Border(bottom=thin)

        for cell in sheet[1]:
            cell.fill = PatternFill("solid", fgColor=cls.HEADER_FILL)
            cell.font = Font(
                name="Segoe UI",
                size=11,
                bold=True,
                color=cls.HEADER_TEXT,
            )
            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
                wrap_text=True,
            )
            cell.border = border

        sheet.row_dimensions[1].height = 32
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions

        header_index: dict[str, int] = {}
        for cell in sheet[1]:
            if cell.value is None or cell.column is None:
                continue
            header_index[str(cell.value)] = cell.column

        for row in range(2, sheet.max_row + 1):
            if row % 2 == 0:
                for cell in sheet[row]:
                    cell.fill = PatternFill(
                        "solid",
                        fgColor=cls.ALT_ROW_FILL,
                    )

            for cell in sheet[row]:
                cell.font = Font(
                    name="Segoe UI",
                    size=10,
                    color=cls.HEADER_TEXT,
                )
                cell.alignment = Alignment(
                    vertical="top",
                    wrap_text=True,
                )
                cell.border = border

            for header in cls.CURRENCY_COLUMNS:
                column = header_index[header]
                cell = sheet.cell(row=row, column=column)
                cell.number_format = '"S/ " #,##0.00'
                cell.alignment = Alignment(
                    horizontal="right",
                    vertical="top",
                )

            stock_cell = sheet.cell(
                row=row,
                column=header_index["Stock"],
            )
            stock_cell.number_format = "#,##0"
            stock_cell.alignment = Alignment(
                horizontal="right",
                vertical="top",
            )

            sheet.row_dimensions[row].height = 36

        for header, width in cls.COLUMN_WIDTHS.items():
            column = header_index[header]
            sheet.column_dimensions[get_column_letter(column)].width = width

        if sheet.max_row >= 2:
            table = Table(
                displayName="CatalogoProductos",
                ref=sheet.dimensions,
            )
            table.tableStyleInfo = TableStyleInfo(
                name="TableStyleMedium2",
                showFirstColumn=False,
                showLastColumn=False,
                showRowStripes=False,
                showColumnStripes=False,
            )
            sheet.add_table(table)
