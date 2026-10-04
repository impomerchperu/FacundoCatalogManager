from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar
from urllib.request import Request, urlopen

from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from openpyxl.drawing.spreadsheet_drawing import AnchorMarker, TwoCellAnchor
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.worksheet import Worksheet
from PIL import Image

from config.runtime_paths import resolve_data_path
from exporters.catalog_export_schema import export_rows
from exporters.excel_slicer import add_category_slicer


class ExcelExporter:
    """Exporta el catálogo con tabla, imágenes y segmentación por categoría."""

    EXCEL_HEADERS: ClassVar[tuple[str, ...]] = (
        "Imagen",
        "Código",
        "Producto",
        "Detalle",
        "Categoría",
        "Color",
        "Stock",
        "Precio muestra",
        "Precio ciento",
        "Precio millar",
    )

    CURRENCY_HEADERS: ClassVar[set[str]] = {
        "Precio muestra",
        "Precio ciento",
        "Precio millar",
    }

    COLUMN_WIDTHS: ClassVar[dict[str, int]] = {
        "Imagen": 17,
        "Código": 14,
        "Producto": 42,
        "Detalle": 48,
        "Categoría": 28,
        "Color": 24,
        "Stock": 12,
        "Precio muestra": 18,
        "Precio ciento": 18,
        "Precio millar": 18,
    }

    SLICER_COLUMN_WIDTH: ClassVar[int] = 39
    HEADER_FILL: ClassVar[str] = "EAF3FA"
    HEADER_TEXT: ClassVar[str] = "173F6D"
    BORDER_COLOR: ClassVar[str] = "CBDDEA"
    ALT_ROW_FILL: ClassVar[str] = "F8FBFF"
    DEFAULT_ROW_HEIGHT_POINTS: ClassVar[float] = 14.4

    IMAGE_MAX_SIZE_PX: ClassVar[int] = 118
    MIN_ROW_HEIGHT_POINTS: ClassVar[float] = 92.0
    TEXT_LINE_HEIGHT_POINTS: ClassVar[float] = 15.0
    ROW_VERTICAL_PADDING_POINTS: ClassVar[float] = 8.0

    SLICER_CACHE_NAME: ClassVar[str] = "SegmentaciónDeDatos_Categoría"
    SLICER_NAME: ClassVar[str] = "Categoría"
    SLICER_STYLE: ClassVar[str] = "SlicerStyleLight5"
    SLICER_DRAWING_ID: ClassVar[int] = 521

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
        sheet.sheet_format.defaultRowHeight = cls.DEFAULT_ROW_HEIGHT_POINTS
        sheet.sheet_view.zoomScale = 85
        sheet.freeze_panes = "B2"

        sheet.column_dimensions["A"].width = cls.SLICER_COLUMN_WIDTH
        for index, header in enumerate(cls.EXCEL_HEADERS, start=2):
            sheet.column_dimensions[get_column_letter(index)].width = (
                cls.COLUMN_WIDTHS[header]
            )

        sheet.append([None, *cls.EXCEL_HEADERS])
        for row in rows:
            colors, stocks = cls._split_color_stock(
                str(row.get("stock_by_color", "") or ""),
            )
            sheet.append(
                [
                    None,
                    None,
                    row["code"],
                    row["name"],
                    row["description"],
                    row["category"],
                    colors,
                    stocks,
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

        if rows:
            try:
                add_category_slicer(
                    Path(filename),
                    table_name="CatalogoProductos",
                    field_name="Categoría",
                )
            except RuntimeError:
                Path(filename).unlink(missing_ok=True)
                raise

    @classmethod
    def _style_sheet(cls, sheet: Worksheet) -> None:
        thin = Side(style="thin", color=cls.BORDER_COLOR)
        border = Border(bottom=thin)
        header_index = cls._header_index()

        for cell in sheet[1]:
            cell.fill = (
                PatternFill("solid", fgColor=cls.HEADER_FILL)
                if cell.column != 1
                else PatternFill("solid", fgColor="FFFFFF")
            )
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

        for row_number in range(2, sheet.max_row + 1):
            for column in range(1, sheet.max_column + 1):
                cell = sheet.cell(row=row_number, column=column)
                if row_number % 2 == 0 and column != 1:
                    cell.fill = PatternFill(
                        "solid",
                        fgColor=cls.ALT_ROW_FILL,
                    )
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

            centered_headers = {
                "Código",
                "Stock",
            } | cls.CURRENCY_HEADERS
            for header in centered_headers:
                cell = sheet.cell(
                    row=row_number,
                    column=header_index[header],
                )
                cell.alignment = Alignment(
                    horizontal="center",
                    vertical="center",
                    wrap_text=True,
                )
                if header in cls.CURRENCY_HEADERS:
                    cell.number_format = '"S/ " #,##0.00'

            cls._set_row_height(sheet, row_number)

        if sheet.max_row >= 2:
            table = Table(
                displayName="CatalogoProductos",
                ref=f"B1:K{sheet.max_row}",
            )
            table.tableStyleInfo = TableStyleInfo(
                name="TableStyleLight2",
                showFirstColumn=False,
                showLastColumn=False,
                showRowStripes=True,
                showColumnStripes=False,
            )
            sheet.add_table(table)

    @classmethod
    def _set_row_height(cls, sheet: Worksheet, row: int) -> None:
        widths = {
            "Producto": cls.COLUMN_WIDTHS["Producto"],
            "Detalle": cls.COLUMN_WIDTHS["Detalle"],
            "Categoría": cls.COLUMN_WIDTHS["Categoría"],
            "Color": cls.COLUMN_WIDTHS["Color"],
        }
        lines = 1
        header_index = cls._header_index()

        for header, width in widths.items():
            value = str(
                sheet.cell(
                    row=row,
                    column=header_index[header],
                ).value
                or "",
            )
            lines = max(
                lines,
                cls._estimate_wrapped_lines(value, width),
            )

        stock_text = str(
            sheet.cell(
                row=row,
                column=header_index["Stock"],
            ).value
            or "",
        )
        lines = max(
            lines,
            len(stock_text.splitlines()) if stock_text else 1,
        )

        sheet.row_dimensions[row].height = max(
            cls.MIN_ROW_HEIGHT_POINTS,
            lines * cls.TEXT_LINE_HEIGHT_POINTS
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
        image_column = cls._header_index()["Imagen"]

        for offset, (product, row) in enumerate(
            zip(products, rows, strict=True),
        ):
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

            row_index = target_row - 1
            col_index = image_column - 1
            width_emu = int((image.width or 0) / 96 * 914400)
            height_emu = int((image.height or 0) / 96 * 914400)
            image.anchor = TwoCellAnchor(
                editAs="twoCell",
                _from=AnchorMarker(
                    col=col_index,
                    row=row_index,
                    colOff=0,
                    rowOff=0,
                ),
                to=AnchorMarker(
                    col=col_index,
                    row=row_index,
                    colOff=width_emu,
                    rowOff=height_emu,
                ),
            )
            sheet.add_image(image)

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
        stock_index = cls._header_index()["Stock"]
        color_index = cls._header_index()["Color"]
        no_fill = PatternFill(fill_type=None)

        for offset in range(len(rows)):
            stock_cell = sheet.cell(
                row=2 + offset,
                column=stock_index,
            )
            color_cell = sheet.cell(
                row=2 + offset,
                column=color_index,
            )

            for target in (color_cell, stock_cell):
                target.fill = no_fill
                target.font = Font(
                    name="Segoe UI",
                    size=10,
                    color=cls.HEADER_TEXT,
                )

            color_cell.alignment = Alignment(
                horizontal="left",
                vertical="center",
                wrap_text=True,
            )
            stock_cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
                wrap_text=True,
            )

    @staticmethod
    def _split_color_stock(value: str) -> tuple[str, str]:
        colors: list[str] = []
        stocks: list[str] = []

        for line in value.splitlines():
            try:
                color_name, stock_text = line.rsplit(":", 1)
            except ValueError:
                color_name = line.strip()
                stock_text = ""
            color_name = color_name.strip()
            stock_text = stock_text.strip()
            if not color_name:
                continue
            colors.append(color_name)
            stocks.append(stock_text)

        return "\n".join(colors), "\n".join(stocks)

    @classmethod
    def _header_index(cls) -> dict[str, int]:
        return {
            header: index
            for index, header in enumerate(cls.EXCEL_HEADERS, start=2)
        }

