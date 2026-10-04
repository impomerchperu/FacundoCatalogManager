from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar
from urllib.request import Request, urlopen

from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from openpyxl.drawing.spreadsheet_drawing import AnchorMarker, TwoCellAnchor
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from PIL import Image

from config.runtime_paths import resolve_data_path
from exporters.catalog_export_schema import export_rows


class ExcelExporter:
    """Exporta el catálogo de productos a un libro XLSX sencillo y editable."""

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
    CENTER_HEADERS: ClassVar[frozenset[str]] = frozenset(
        {"Imagen", "Código", "Precio muestra", "Precio ciento", "Precio millar"}
    )
    CURRENCY_COLUMNS: ClassVar[frozenset[str]] = frozenset(
        {"Precio muestra", "Precio ciento", "Precio millar"}
    )

    HEADER_FONT_NAME: ClassVar[str] = "Segoe UI"
    HEADER_FONT_SIZE: ClassVar[int] = 11
    DATA_FONT_SIZE: ClassVar[int] = 10
    HEADER_TEXT_COLOR: ClassVar[str] = "173F6D"
    INDENT_LEVEL: ClassVar[int] = 1
    IMAGE_COLUMN_WIDTH: ClassVar[float] = 28.0
    DEFAULT_ROW_HEIGHT: ClassVar[float] = 90.0
    HEADER_ROW_HEIGHT: ClassVar[float] = 30.0
    IMAGE_CELL_PADDING_PX: ClassVar[int] = 4
    EXCEL_COLUMN_PIXELS_PER_WIDTH_UNIT: ClassVar[float] = 7.0
    EXCEL_DPI: ClassVar[float] = 96.0
    POINTS_PER_INCH: ClassVar[float] = 72.0
    LOCAL_CURRENCY_FORMAT: ClassVar[str] = '"S/" #,##0.00'

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
        sheet.sheet_format.defaultRowHeight = cls.DEFAULT_ROW_HEIGHT
        cls._initialize_sheet(sheet)

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
    def _initialize_sheet(cls, sheet: Worksheet) -> None:
        sheet.auto_filter.ref = None
        sheet.append(list(cls.EXCEL_HEADERS))
        sheet.row_dimensions[1].height = cls.HEADER_ROW_HEIGHT

    @classmethod
    def _set_column_widths(cls, sheet: Worksheet) -> None:
        widths = (
            cls.IMAGE_COLUMN_WIDTH,
            14.0,
            34.0,
            42.0,
            28.0,
            18.0,
            12.0,
            16.0,
            16.0,
            16.0,
        )
        for column_index, width in enumerate(widths, start=1):
            sheet.column_dimensions[get_column_letter(column_index)].width = width

    @classmethod
    def _style_sheet(cls, sheet: Worksheet) -> None:
        header_font = Font(
            name=cls.HEADER_FONT_NAME,
            size=cls.HEADER_FONT_SIZE,
            bold=True,
            color=cls.HEADER_TEXT_COLOR,
        )
        data_font = Font(
            name=cls.HEADER_FONT_NAME,
            size=cls.DATA_FONT_SIZE,
        )

        header_index = cls._header_index()

        for cell in sheet[1]:
            cell.font = header_font
            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
                wrap_text=True,
            )

        for row in range(2, sheet.max_row + 1):
            sheet.row_dimensions[row].height = cls.DEFAULT_ROW_HEIGHT
            for header, column in header_index.items():
                cell = sheet.cell(row=row, column=column)
                cell.font = data_font
                cell.alignment = cls._data_alignment(header)
                if header in cls.CURRENCY_COLUMNS:
                    cell.number_format = cls.LOCAL_CURRENCY_FORMAT
                elif header == "Stock":
                    cell.number_format = "#,##0"

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
        return Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True,
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
            start=2,
        ):
            reference = str(row.get("image", "") or "").strip()
            fallback_url = str(
                getattr(product, "image_url", "") or ""
            ).strip()

            source_path = cls._local_image_path(reference)
            if source_path is None and fallback_url:
                source_path = cls._download_image(
                    fallback_url,
                    temp_dir / f"source_{offset}",
                )
            if source_path is None:
                continue

            image_path = temp_dir / f"product_{offset}.png"
            image = cls._prepare_image(source_path, image_path, sheet, offset)
            if image is None:
                continue

            image.anchor = cls._two_cell_anchor(image_column, offset)
            sheet.add_image(image)

    @classmethod
    def _prepare_image(
        cls,
        source_path: Path,
        target_path: Path,
        sheet: Worksheet,
        row: int,
    ) -> ExcelImage | None:
        width, height = cls._image_cell_size(sheet, row)

        try:
            with Image.open(source_path) as source:
                prepared = source.convert("RGBA")
                inner_width = max(
                    width - cls.IMAGE_CELL_PADDING_PX * 2,
                    1,
                )
                inner_height = max(
                    height - cls.IMAGE_CELL_PADDING_PX * 2,
                    1,
                )
                prepared.thumbnail(
                    (inner_width, inner_height),
                    Image.Resampling.LANCZOS,
                )

                canvas = Image.new(
                    "RGBA",
                    (width, height),
                    (255, 255, 255, 0),
                )
                left = max((width - prepared.width) // 2, 0)
                top = max((height - prepared.height) // 2, 0)
                canvas.alpha_composite(prepared, (left, top))
                canvas.save(target_path, format="PNG")
        except (OSError, ValueError):
            return None

        image = ExcelImage(str(target_path))
        image.width = width
        image.height = height
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
            or cls.IMAGE_COLUMN_WIDTH,
        )
        cell_width = max(
            int(column_width * cls.EXCEL_COLUMN_PIXELS_PER_WIDTH_UNIT),
            cls.IMAGE_CELL_PADDING_PX + 1,
        )

        row_height = sheet.row_dimensions[row].height or cls.DEFAULT_ROW_HEIGHT
        cell_height = max(
            int(row_height * cls.EXCEL_DPI / cls.POINTS_PER_INCH),
            cls.IMAGE_CELL_PADDING_PX + 1,
        )
        return cell_width, cell_height

    @staticmethod
    def _two_cell_anchor(column: int, row: int) -> TwoCellAnchor:
        return TwoCellAnchor(
            editAs="twoCell",
            _from=AnchorMarker(col=column - 1, row=row - 1),
            to=AnchorMarker(col=column, row=row),
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
