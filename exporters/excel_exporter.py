from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar
from urllib.request import Request, urlopen

from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from PIL import Image

from config.runtime_paths import resolve_data_path
from exporters.catalog_export_schema import export_rows


class ExcelExporter:
    """Exporta el catálogo completo a un libro XLSX estándar y editable."""

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

    HEADER_TEXT: ClassVar[str] = "173F6D"

    HEADER_ROW_HEIGHT_POINTS: ClassVar[float] = 32.0
    MIN_ROW_HEIGHT_POINTS: ClassVar[float] = 92.0
    DEFAULT_ROW_HEIGHT_POINTS: ClassVar[float] = 14.4
    TEXT_LINE_HEIGHT_POINTS: ClassVar[float] = 15.0
    ROW_VERTICAL_PADDING_POINTS: ClassVar[float] = 8.0

    IMAGE_MAX_SIZE_PX: ClassVar[int] = 118
    IMAGE_CELL_PADDING_PX: ClassVar[int] = 2

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

        for index, header in enumerate(cls.EXCEL_HEADERS, start=1):
            sheet.column_dimensions[get_column_letter(index)].width = (
                cls.COLUMN_WIDTHS[header]
            )

        sheet.append(list(cls.EXCEL_HEADERS))
        for row in rows:
            colors, stocks = cls._split_color_stock(
                str(row.get("stock_by_color", "") or ""),
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
    def _style_sheet(cls, sheet: Worksheet) -> None:
        header_font = Font(
            name="Segoe UI",
            size=11,
            bold=True,
            color=cls.HEADER_TEXT,
        )
        data_font = Font(
            name="Segoe UI",
            size=10,
            color=cls.HEADER_TEXT,
        )

        for cell in sheet[1]:
            cell.font = header_font
            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
                wrap_text=True,
            )

        sheet.row_dimensions[1].height = cls.HEADER_ROW_HEIGHT_POINTS

        for row_number in range(2, sheet.max_row + 1):
            for column in range(1, sheet.max_column + 1):
                cell = sheet.cell(row=row_number, column=column)
                cell.font = data_font
                cell.alignment = Alignment(
                    vertical="center",
                    wrap_text=True,
                )
            cls._set_row_height(sheet, row_number)


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

            target_width, target_height = cls._image_size_for_cell(
                sheet,
                target_row,
            )
            cls._fit_image(image, target_width, target_height)
            image.anchor = sheet.cell(
                row=target_row,
                column=image_column,
            ).coordinate
            sheet.add_image(image)

    @classmethod
    def _image_size_for_cell(
        cls,
        sheet: Worksheet,
        row: int,
    ) -> tuple[int, int]:
        column_width = cls.COLUMN_WIDTHS["Imagen"]
        available_width = max(
            int(column_width * 7) - cls.IMAGE_CELL_PADDING_PX * 2,
            1,
        )
        row_height = sheet.row_dimensions[row].height
        if row_height is None:
            row_height = cls.DEFAULT_ROW_HEIGHT_POINTS
        available_height = max(
            int(row_height * 96 / 72) - cls.IMAGE_CELL_PADDING_PX * 2,
            1,
        )

        return (
            min(cls.IMAGE_MAX_SIZE_PX, available_width),
            min(cls.IMAGE_MAX_SIZE_PX, available_height),
        )

    @staticmethod
    def _fit_image(
        image: ExcelImage,
        max_width: int,
        max_height: int,
    ) -> None:
        source_width = int(image.width or 0)
        source_height = int(image.height or 0)
        if source_width <= 0 or source_height <= 0:
            return

        scale = min(
            max_width / source_width,
            max_height / source_height,
            1.0,
        )
        image.width = max(int(source_width * scale), 1)
        image.height = max(int(source_height * scale), 1)

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
