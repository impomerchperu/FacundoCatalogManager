from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from typing import Any, ClassVar
from urllib.request import Request, urlopen

from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from openpyxl.drawing.spreadsheet_drawing import AnchorMarker, TwoCellAnchor
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from openpyxl.utils.units import pixels_to_EMU
from openpyxl.worksheet.worksheet import Worksheet
from PIL import Image

from config.runtime_paths import resolve_data_path
from exporters.catalog_export_schema import export_rows


class ExcelExporter:
    """Exporta un catálogo XLSX sencillo, editable y sin automatización externa."""

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

    LEFT_INDENT_HEADERS: ClassVar[frozenset[str]] = frozenset(
        {"Producto", "Detalle", "Categoría", "Color"}
    )
    RIGHT_INDENT_HEADERS: ClassVar[frozenset[str]] = frozenset({"Stock"})
    PRICE_HEADERS: ClassVar[frozenset[str]] = frozenset(
        {"Precio muestra", "Precio ciento", "Precio millar"}
    )
    INDENT_LEVEL: ClassVar[int] = 1

    COLUMN_WIDTHS: ClassVar[dict[str, float]] = {
        "Imagen": 20.0,
        "Código": 14.0,
        "Producto": 32.0,
        "Detalle": 40.0,
        "Categoría": 26.0,
        "Color": 20.0,
        "Stock": 12.0,
        "Precio muestra": 16.0,
        "Precio ciento": 16.0,
        "Precio millar": 16.0,
    }

    LOCAL_CURRENCY_FORMAT: ClassVar[str] = '"S/" #,##0.00'
    HEADER_ROW_HEIGHT: ClassVar[float] = 44.0
    INITIAL_ROW_HEIGHT: ClassVar[float] = 78.0
    BASE_ROW_HEIGHT: ClassVar[float] = 36.0
    HEADER_FONT_SIZE: ClassVar[float] = 14.0
    INITIAL_ROWS: ClassVar[int] = 2
    LINE_HEIGHT: ClassVar[float] = 15.0
    EXCEL_COLUMN_PIXELS_PER_WIDTH_UNIT: ClassVar[float] = 7.0
    EXCEL_DPI: ClassVar[float] = 96.0
    IMAGE_MARGIN_PIXELS: ClassVar[int] = 4
    POINTS_PER_INCH: ClassVar[float] = 72.0

    @classmethod
    def export(cls, products: Iterable, filename) -> None:
        product_list = sorted(
            products,
            key=lambda product: cls._alphanumeric_key(
                getattr(product, "category", ""),
            ),
        )
        rows = export_rows(product_list)

        workbook = Workbook()
        sheet = workbook.active
        if sheet is None:
            raise RuntimeError("No se pudo crear la hoja Excel")

        sheet.title = "Productos"
        for _ in range(cls.INITIAL_ROWS):
            sheet.append([None] * len(cls.EXCEL_HEADERS))
        sheet.append(list(cls.EXCEL_HEADERS))

        for row in rows:
            colors, stocks = cls._split_color_stock(
                str(row.get("stock_by_color", "") or "")
            )
            sheet.append(
                [
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

        cls._set_column_widths(sheet)
        cls._style_sheet(sheet)

        with TemporaryDirectory(prefix="fcm_excel_") as temp_dir:
            cls._embed_product_images(
                sheet,
                product_list,
                rows,
                Path(temp_dir),
            )
            workbook.save(filename)

    @classmethod
    def _set_column_widths(cls, sheet: Worksheet) -> None:
        for index, header in enumerate(cls.EXCEL_HEADERS, start=1):
            sheet.column_dimensions[get_column_letter(index)].width = (
                cls.COLUMN_WIDTHS[header]
            )

    @classmethod
    def _style_sheet(cls, sheet: Worksheet) -> None:
        header_font = Font(bold=True, size=cls.HEADER_FONT_SIZE)

        for cell in sheet[cls.INITIAL_ROWS + 1]:
            cell.font = header_font
            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
            )
        sheet.row_dimensions[cls.INITIAL_ROWS + 1].height = cls.HEADER_ROW_HEIGHT
        sheet.row_dimensions[2].height = cls.INITIAL_ROW_HEIGHT

        for row in range(cls.INITIAL_ROWS + 2, sheet.max_row + 1):
            for header, column in cls._header_index().items():
                cell = sheet.cell(row=row, column=column)
                cell.alignment = cls._data_alignment(header)

                if header in cls.PRICE_HEADERS:
                    cell.number_format = cls.LOCAL_CURRENCY_FORMAT
                elif header == "Stock":
                    cell.number_format = "#,##0"

            sheet.row_dimensions[row].height = cls._row_height(sheet, row)

    @classmethod
    def _data_alignment(cls, header: str) -> Alignment:
        if header in cls.LEFT_INDENT_HEADERS:
            return Alignment(
                horizontal="left",
                vertical="center",
                indent=cls.INDENT_LEVEL,
                wrap_text=True,
            )
        if header in cls.RIGHT_INDENT_HEADERS:
            return Alignment(
                horizontal="right",
                vertical="center",
                indent=cls.INDENT_LEVEL,
                wrap_text=True,
            )
        if header in cls.PRICE_HEADERS:
            return Alignment(
                horizontal="center",
                vertical="center",
            )
        return Alignment(
            horizontal="center",
            vertical="center",
        )

    @classmethod
    def _row_height(cls, sheet: Worksheet, row: int) -> float:
        header_index = cls._header_index()
        max_lines = 1

        for header in ("Producto", "Detalle", "Categoría", "Color", "Stock"):
            value = str(
                sheet.cell(row=row, column=header_index[header]).value or ""
            )
            width = cls.COLUMN_WIDTHS[header]
            max_lines = max(
                max_lines,
                cls._estimate_lines(value, width),
            )

        return max(
            cls.BASE_ROW_HEIGHT,
            max_lines * cls.LINE_HEIGHT,
        )

    @staticmethod
    def _alphanumeric_key(value: object) -> tuple[tuple[int, object], ...]:
        text = str(value or "").strip().casefold()
        return tuple(
            (0, int(part)) if part.isdigit() else (1, part)
            for part in re.split(r"(\d+)", text)
            if part
        )

    @staticmethod
    def _estimate_lines(text: str, width: float) -> int:
        if not text:
            return 1

        max_chars = max(int(width * 0.9), 1)
        return sum(
            max(1, (len(line) + max_chars - 1) // max_chars)
            for line in text.splitlines() or [""]
        )

    @classmethod
    def _embed_product_images(
        cls,
        sheet: Worksheet,
        products: list[Any],
        rows: list[dict[str, object]],
        temp_dir: Path,
    ) -> None:
        for row_number, (product, row) in enumerate(
            zip(products, rows, strict=True),
            start=cls.INITIAL_ROWS + 2,
        ):
            reference = str(row.get("image", "") or "").strip()
            fallback_url = str(
                getattr(product, "image_url", "") or ""
            ).strip()

            source_path = cls._local_image_path(reference)
            if source_path is None and fallback_url:
                source_path = cls._download_image(
                    fallback_url,
                    temp_dir / f"source_{row_number}",
                )
            if source_path is None:
                continue

            target_path = temp_dir / f"product_{row_number}.png"
            image = cls._prepare_image(
                source_path,
                target_path,
                sheet,
                row_number,
            )
            if image is None:
                continue

            sheet.add_image(image)

    @classmethod
    def _prepare_image(
        cls,
        source_path: Path,
        target_path: Path,
        sheet: Worksheet,
        row: int,
    ) -> ExcelImage | None:
        cell_width, _current_cell_height = cls._image_cell_size(sheet, row)
        image_width = max(
            cell_width - (2 * cls.IMAGE_MARGIN_PIXELS),
            1,
        )

        try:
            with Image.open(source_path) as source:
                prepared = source.convert("RGBA")
                if prepared.width <= 0 or prepared.height <= 0:
                    return None

                image_height = max(
                    round(image_width * prepared.height / prepared.width),
                    1,
                )
                required_row_height = (
                    (image_height + (2 * cls.IMAGE_MARGIN_PIXELS))
                    * cls.POINTS_PER_INCH
                    / cls.EXCEL_DPI
                )
                text_row_height = cls._row_height(sheet, row)
                final_row_height = max(
                    text_row_height,
                    required_row_height,
                    cls.BASE_ROW_HEIGHT,
                )
                sheet.row_dimensions[row].height = final_row_height

                prepared = prepared.resize(
                    (image_width, image_height),
                    Image.Resampling.LANCZOS,
                )
                prepared.save(target_path, format="PNG")
        except (OSError, ValueError):
            return None

        image = ExcelImage(str(target_path))
        image.width = image_width
        image.height = image_height
        image.anchor = cls._one_cell_anchor(
            cls._header_index()["Imagen"],
            row,
            image_width,
            image_height,
            final_row_height,
        )
        return image

    @classmethod
    def _image_cell_size(
        cls,
        sheet: Worksheet,
        row: int,
    ) -> tuple[int, int]:
        image_column = cls._header_index()["Imagen"]
        column_width = float(
            sheet.column_dimensions[
                get_column_letter(image_column)
            ].width
            or cls.COLUMN_WIDTHS["Imagen"],
        )
        cell_width = max(
            int(column_width * cls.EXCEL_COLUMN_PIXELS_PER_WIDTH_UNIT),
            1,
        )

        row_height = sheet.row_dimensions[row].height or cls.BASE_ROW_HEIGHT
        cell_height = max(
            int(row_height * cls.EXCEL_DPI / cls.POINTS_PER_INCH),
            1,
        )
        return cell_width, cell_height

    @classmethod
    def _one_cell_anchor(
        cls,
        column: int,
        row: int,
        width: int,
        height: int,
        row_height_points: float,
    ) -> TwoCellAnchor:
        row_height_px = max(
            round(row_height_points * cls.EXCEL_DPI / cls.POINTS_PER_INCH),
            height,
        )
        vertical_offset_px = max((row_height_px - height) // 2, cls.IMAGE_MARGIN_PIXELS)
        start_col = column - 1
        start_row = row - 1
        start_col_offset = pixels_to_EMU(cls.IMAGE_MARGIN_PIXELS)
        start_row_offset = pixels_to_EMU(vertical_offset_px)
        end_col_offset = start_col_offset + pixels_to_EMU(width)
        end_row_offset = start_row_offset + pixels_to_EMU(height)

        return TwoCellAnchor(
            editAs="twoCell",
            _from=AnchorMarker(
                col=start_col,
                row=start_row,
                colOff=start_col_offset,
                rowOff=start_row_offset,
            ),
            to=AnchorMarker(
                col=start_col,
                row=start_row,
                colOff=end_col_offset,
                rowOff=end_row_offset,
            ),
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
            for index, header in enumerate(cls.EXCEL_HEADERS, start=1)
        }
