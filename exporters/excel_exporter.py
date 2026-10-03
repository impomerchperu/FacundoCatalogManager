from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar
from urllib.request import Request, urlopen

from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.worksheet import Worksheet
from PIL import Image

from config.runtime_paths import resolve_data_path
from exporters.catalog_export_schema import EXPORT_HEADERS, export_rows
from services.stock_color_palette import known_stock_color_style


class ExcelExporter:
    """Exporta únicamente la tabla del catálogo con imágenes incrustadas."""

    CURRENCY_COLUMNS: ClassVar[set[str]] = {
        "Precio muestra",
        "Precio ciento",
        "Precio millar",
    }

    COLUMN_WIDTHS: ClassVar[dict[str, int]] = {
        "Imagen": 18,
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

    IMAGE_MAX_SIZE_PX: ClassVar[int] = 118
    IMAGE_ROW_PADDING_POINTS: ClassVar[float] = 4.0
    MIN_ROW_HEIGHT_POINTS: ClassVar[float] = 36.0
    TEXT_LINE_HEIGHT_POINTS: ClassVar[float] = 15.0
    ROW_VERTICAL_PADDING_POINTS: ClassVar[float] = 8.0

    @classmethod
    def export(cls, products: Iterable, filename) -> None:
        product_list = list(products)
        rows = export_rows(product_list)

        workbook = Workbook()
        active_sheet = workbook.active
        if active_sheet is None:
            raise RuntimeError("No se pudo crear la hoja Excel")

        sheet: Worksheet = active_sheet
        sheet.title = "Productos"
        sheet.sheet_view.showGridLines = False


        sheet.append(list(EXPORT_HEADERS))
        for row in rows:
            sheet.append(
                [
                    None,
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

        with TemporaryDirectory(prefix="fcm_excel_") as temp_dir:
            cls._embed_product_images(
                sheet,
                product_list,
                rows,
                Path(temp_dir),
            )
            cls._style_stock_cells(sheet, rows)
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
        sheet.sheet_view.zoomScale = 80

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
                    vertical="center",
                    wrap_text=True,
                )
                cell.border = border

            for header in cls.CURRENCY_COLUMNS:
                column = header_index[header]
                cell = sheet.cell(row=row, column=column)
                cell.number_format = '"S/ " #,##0.00'
                cell.alignment = Alignment(
                    horizontal="right",
                    vertical="center",
                )

            stock_cell = sheet.cell(
                row=row,
                column=header_index["Stock"],
            )
            stock_cell.number_format = "#,##0"
            stock_cell.alignment = Alignment(
                horizontal="right",
                vertical="center",
            )

            stock_color_cell = sheet.cell(
                row=row,
                column=header_index["Stock por color"],
            )
            stock_color_cell.alignment = Alignment(
                horizontal="left",
                vertical="center",
                wrap_text=True,
            )

            cls._set_row_height(sheet, row)

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

    @classmethod
    def _set_row_height(cls, sheet: Worksheet, row: int) -> None:
        text_widths = {
            "Producto": cls.COLUMN_WIDTHS["Producto"],
            "Detalle": cls.COLUMN_WIDTHS["Detalle"],
            "Categoría": cls.COLUMN_WIDTHS["Categoría"],
        }
        text_lines = 1
        for header, width in text_widths.items():
            value = str(
                sheet.cell(
                    row=row,
                    column=cls._header_column(sheet, header),
                ).value
                or "",
            )
            text_lines = max(
                text_lines,
                cls._estimate_wrapped_lines(value, width),
            )

        stock_text = str(
            sheet.cell(
                row=row,
                column=cls._header_column(sheet, "Stock por color"),
            ).value
            or "",
        )
        stock_lines = len(stock_text.splitlines()) if stock_text else 0
        total_lines = max(text_lines, stock_lines or 1)

        sheet.row_dimensions[row].height = max(
            cls.MIN_ROW_HEIGHT_POINTS,
            total_lines * cls.TEXT_LINE_HEIGHT_POINTS
            + cls.ROW_VERTICAL_PADDING_POINTS,
        )

    @staticmethod
    def _estimate_wrapped_lines(text: str, width: int) -> int:
        if not text:
            return 1
        max_chars = max(int(width * 0.92), 1)
        return sum(
            max(1, (len(line) + max_chars - 1) // max_chars)
            for line in text.splitlines() or [""]
        )

    @classmethod
    def _embed_product_images(
        cls,
        sheet: Worksheet,
        products: list,
        rows: list[dict[str, object]],
        temp_dir: Path,
    ) -> None:
        image_column = cls._header_column(sheet, "Imagen")

        for offset, (product, row) in enumerate(zip(products, rows, strict=True)):
            reference = str(row.get("image", "") or "").strip()
            fallback_url = str(
                getattr(product, "image_url", "") or "",
            ).strip()
            target_row = 2 + offset

            source_path = cls._local_image_path(reference)
            if source_path is None and fallback_url:
                source_path = cls._download_image(
                    fallback_url,
                    temp_dir / f"source_{offset + 1}",
                )
            if source_path is None:
                continue

            image_path = temp_dir / f"product_{offset + 1}.png"
            image = cls._prepare_image(source_path, image_path)
            if image is None:
                continue

            image.anchor = f"{get_column_letter(image_column)}{target_row}"
            sheet.add_image(image)

            image_height_points = (
                float(image.height or 0) * 0.75
                + cls.IMAGE_ROW_PADDING_POINTS
            )
            current_height = (
                sheet.row_dimensions[target_row].height or 0
            )
            sheet.row_dimensions[target_row].height = max(
                current_height,
                image_height_points,
            )

            image_cell = sheet.cell(
                row=target_row,
                column=image_column,
            )
            image_cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
            )

    @staticmethod
    def _local_image_path(reference: str) -> Path | None:
        if not reference:
            return None

        candidate = Path(reference)
        if not candidate.is_absolute():
            candidate = resolve_data_path(candidate)

        if candidate.exists() and candidate.is_file():
            return candidate

        return None

    @staticmethod
    def _download_image(url: str, target_base: Path) -> Path | None:
        if not url.startswith(("http://", "https://")):
            return None

        target = target_base.with_suffix(".download")
        request = Request(
            url,
            headers={"User-Agent": "FacundoCatalogManager/1.0"},
        )
        try:
            with urlopen(request, timeout=8) as response:
                target.write_bytes(response.read())
        except (OSError, ValueError):
            return None
        return target

    @classmethod
    def _prepare_image(
        cls,
        source_path: Path,
        target_path: Path,
    ) -> ExcelImage | None:
        try:
            with Image.open(source_path) as source:
                prepared = source.convert(
                    "RGBA" if "A" in source.getbands() else "RGB",
                )
                prepared.thumbnail(
                    (cls.IMAGE_MAX_SIZE_PX, cls.IMAGE_MAX_SIZE_PX),
                    Image.Resampling.LANCZOS,
                )
                prepared.save(target_path, format="PNG")
                width, height = prepared.size
        except (OSError, ValueError):
            return None

        if width <= 0 or height <= 0:
            return None

        image = ExcelImage(str(target_path))
        image.width = width
        image.height = height
        return image

    @classmethod
    def _style_stock_cells(
        cls,
        sheet: Worksheet,
        rows: list[dict[str, object]],
    ) -> None:
        column = cls._header_column(sheet, "Stock por color")
        for offset, row in enumerate(rows):
            value = str(row.get("stock_by_color", "") or "").strip()
            cell = sheet.cell(row=2 + offset, column=column)
            background, text_color = cls._stock_cell_colors(value)
            if background is None:
                continue

            cell.fill = PatternFill("solid", fgColor=background)
            cell.font = Font(
                name="Segoe UI",
                size=10,
                color=text_color,
            )

    @staticmethod
    def _stock_cell_colors(
        value: str,
    ) -> tuple[str | None, str]:
        if not value:
            return None, "173F6D"

        best_color = ""
        best_stock = -1
        first_color = ""

        for line in value.splitlines():
            try:
                color_name, stock_text = line.rsplit(":", 1)
            except ValueError:
                continue

            color_name = color_name.strip()
            if not color_name:
                continue
            if not first_color:
                first_color = color_name

            try:
                stock = max(int(stock_text.strip().replace(",", "")), 0)
            except ValueError:
                stock = 0

            if stock > best_stock:
                best_stock = stock
                best_color = color_name

        color_name = best_color or first_color
        style = known_stock_color_style(color_name)
        if style is None:
            return "EEF3F7", "173F6D"

        background = style[0].lstrip("#").upper()
        if len(background) == 6:
            background = f"FF{background}"
        return background, "173F6D"

    @staticmethod
    def _header_column(sheet: Worksheet, header: str) -> int:
        for cell in sheet[1]:
            if cell.value == header and cell.column is not None:
                return cell.column
        raise KeyError(f"Encabezado no encontrado: {header}")
