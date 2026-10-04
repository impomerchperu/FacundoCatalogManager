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

    SIDEBAR_COLUMN_WIDTH: ClassVar[float] = 34.89
    DATA_WIDTH_BUDGET: ClassVar[float] = 230.0

    COLUMN_MIN_WIDTHS: ClassVar[dict[str, float]] = {
        "Imagen": 24.0,
        "Código": 11.0,
        "Producto": 42.0,
        "Detalle": 42.0,
        "Categoría": 25.0,
        "Color": 14.0,
        "Stock": 8.0,
        "Precio muestra": 11.5,
        "Precio ciento": 11.5,
        "Precio millar": 11.5,
    }

    COLUMN_MAX_WIDTHS: ClassVar[dict[str, float]] = {
        "Imagen": 26.0,
        "Código": 13.0,
        "Producto": 42.0,
        "Detalle": 42.0,
        "Categoría": 26.0,
        "Color": 28.0,
        "Stock": 9.0,
        "Precio muestra": 13.0,
        "Precio ciento": 13.0,
        "Precio millar": 13.0,
    }

    # Mantiene una referencia pública de anchos de diseño para compatibilidad
    # con código externo que pueda consultar esta configuración.
    COLUMN_WIDTHS: ClassVar[dict[str, float]] = {
        "Imagen": 25.0,
        "Código": 12.0,
        "Producto": 42.0,
        "Detalle": 42.0,
        "Categoría": 25.0,
        "Color": 19.0,
        "Stock": 8.5,
        "Precio muestra": 12.25,
        "Precio ciento": 12.25,
        "Precio millar": 12.25,
    }

    CENTER_HEADERS: ClassVar[frozenset[str]] = frozenset(
        {
            "Código",
            "Stock",
            "Precio muestra",
            "Precio ciento",
            "Precio millar",
        }
    )

    CURRENCY_COLUMNS: ClassVar[frozenset[str]] = frozenset(
        {
            "Precio muestra",
            "Precio ciento",
            "Precio millar",
        }
    )

    LOCAL_CURRENCY_FORMAT: ClassVar[str] = '"S/" #,##0.00'

    HEADER_TEXT: ClassVar[str] = "173F6D"

    HEADER_ROW_HEIGHT_POINTS: ClassVar[float] = 42.0
    MIN_ROW_HEIGHT_POINTS: ClassVar[float] = 92.0
    DEFAULT_ROW_HEIGHT_POINTS: ClassVar[float] = 14.4
    TEXT_LINE_HEIGHT_POINTS: ClassVar[float] = 15.0
    ROW_VERTICAL_PADDING_POINTS: ClassVar[float] = 8.0

    IMAGE_MAX_SIZE_PX: ClassVar[int] = 180
    IMAGE_CELL_PADDING_PX: ClassVar[int] = 4
    EXCEL_COLUMN_PIXELS_PER_WIDTH_UNIT: ClassVar[float] = 7.0
    EXCEL_DPI: ClassVar[float] = 96.0
    POINTS_PER_INCH: ClassVar[float] = 72.0

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
        sheet.sheet_view.zoomScale = 85
        sheet.sheet_view.zoomScaleNormal = 85
        sheet.sheet_format.defaultRowHeight = cls.DEFAULT_ROW_HEIGHT_POINTS

        cls._initialize_sheet_layout(sheet)

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
    def _initialize_sheet_layout(cls, sheet: Worksheet) -> None:
        """Reserva la columna lateral A y deja la tabla de datos desde B."""
        sheet.column_dimensions["A"].width = cls.SIDEBAR_COLUMN_WIDTH
        sheet.freeze_panes = "B2"
        sheet.auto_filter.ref = None

        sheet.append([None, *cls.EXCEL_HEADERS])

    @classmethod
    def _set_column_widths(cls, sheet: Worksheet) -> None:
        """Ajusta anchos según el contenido, dentro de un presupuesto compacto."""
        header_index = cls._header_index()
        desired_widths: dict[str, float] = {}

        for header in cls.EXCEL_HEADERS:
            column = header_index[header]
            max_line_length = len(header)

            for row_number in range(2, sheet.max_row + 1):
                value = sheet.cell(
                    row=row_number,
                    column=column,
                ).value
                if value is None:
                    continue

                for line in str(value).splitlines() or [""]:
                    max_line_length = max(max_line_length, len(line))

            desired = max_line_length * 0.90 + 1.5
            desired_widths[header] = min(
                max(cls.COLUMN_MIN_WIDTHS[header], desired),
                cls.COLUMN_MAX_WIDTHS[header],
            )

        if sum(desired_widths.values()) > cls.DATA_WIDTH_BUDGET:
            excess = sum(desired_widths.values()) - cls.DATA_WIDTH_BUDGET
            capacity = sum(
                desired_widths[header] - cls.COLUMN_MIN_WIDTHS[header]
                for header in cls.EXCEL_HEADERS
            )
            if capacity > 0:
                for header in cls.EXCEL_HEADERS:
                    reducible = (
                        desired_widths[header]
                        - cls.COLUMN_MIN_WIDTHS[header]
                    )
                    desired_widths[header] = round(
                        desired_widths[header]
                        - excess * reducible / capacity,
                        2,
                    )

        for header in cls.EXCEL_HEADERS:
            column = header_index[header]
            sheet.column_dimensions[
                get_column_letter(column)
            ].width = desired_widths[header]

    @classmethod
    def _style_sheet(cls, sheet: Worksheet) -> None:
        header_font = Font(
            name="Segoe UI",
            size=14,
            bold=True,
            color=cls.HEADER_TEXT,
        )
        data_font = Font(
            name="Segoe UI",
            size=10,
            color=cls.HEADER_TEXT,
        )
        header_index = cls._header_index()

        for cell in sheet[1]:
            if cell.value is None:
                continue
            cell.font = header_font
            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
                wrap_text=True,
            )

        sheet.row_dimensions[1].height = cls.HEADER_ROW_HEIGHT_POINTS

        for row_number in range(2, sheet.max_row + 1):
            for header, column in header_index.items():
                cell = sheet.cell(row=row_number, column=column)
                cell.font = data_font
                cell.alignment = Alignment(
                    horizontal=(
                        "center"
                        if header in cls.CENTER_HEADERS
                        else "left"
                    ),
                    vertical="center",
                    wrap_text=True,
                )
                if header in cls.CURRENCY_COLUMNS:
                    cell.number_format = cls.LOCAL_CURRENCY_FORMAT

            cls._set_row_height(sheet, row_number)

    @classmethod
    def _set_row_height(cls, sheet: Worksheet, row: int) -> None:
        header_index = cls._header_index()
        lines = 1

        for header in (
            "Producto",
            "Detalle",
            "Categoría",
            "Color",
        ):
            column = header_index[header]
            value = str(
                sheet.cell(
                    row=row,
                    column=column,
                ).value
                or "",
            )
            width = float(
                sheet.column_dimensions[
                    get_column_letter(column)
                ].width
                or cls.COLUMN_WIDTHS[header],
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
    def _estimate_wrapped_lines(text: str, width: float) -> int:
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
            image_size = cls._image_canvas_size(
                sheet,
                target_row,
            )
            image = cls._prepare_image(
                source_path,
                image_path,
                image_size,
            )
            if image is None:
                continue

            image.anchor = cls._two_cell_anchor(
                image_column,
                target_row,
            )
            sheet.add_image(image)

    @classmethod
    def _image_canvas_size(
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
            int(
                column_width
                * cls.EXCEL_COLUMN_PIXELS_PER_WIDTH_UNIT
            ),
            cls.IMAGE_CELL_PADDING_PX + 1,
        )

        row_height = sheet.row_dimensions[row].height
        if row_height is None:
            row_height = cls.DEFAULT_ROW_HEIGHT_POINTS
        cell_height = max(
            int(
                row_height
                * cls.EXCEL_DPI
                / cls.POINTS_PER_INCH
            ),
            cls.IMAGE_CELL_PADDING_PX + 1,
        )

        return cell_width, cell_height

    @staticmethod
    def _two_cell_anchor(
        column: int,
        row: int,
    ) -> TwoCellAnchor:
        start = AnchorMarker(
            col=column - 1,
            row=row - 1,
        )
        end = AnchorMarker(
            col=column,
            row=row,
        )
        return TwoCellAnchor(
            editAs="twoCell",
            _from=start,
            to=end,
        )

    @classmethod
    def _prepare_image(
        cls,
        source_path: Path,
        target_path: Path,
        canvas_size: tuple[int, int],
    ) -> ExcelImage | None:
        canvas_width, canvas_height = canvas_size
        try:
            with Image.open(source_path) as source:
                prepared = source.convert("RGBA")
                inner_width = max(
                    canvas_width - cls.IMAGE_CELL_PADDING_PX * 2,
                    1,
                )
                inner_height = max(
                    canvas_height - cls.IMAGE_CELL_PADDING_PX * 2,
                    1,
                )
                prepared.thumbnail(
                    (
                        inner_width,
                        inner_height,
                    ),
                    Image.Resampling.LANCZOS,
                )

                canvas = Image.new(
                    "RGBA",
                    (canvas_width, canvas_height),
                    (255, 255, 255, 0),
                )
                left = max(
                    (canvas_width - prepared.width) // 2,
                    0,
                )
                top = max(
                    (canvas_height - prepared.height) // 2,
                    0,
                )
                canvas.alpha_composite(prepared, (left, top))
                canvas.save(target_path, format="PNG")
        except (OSError, ValueError):
            return None

        if canvas_width <= 0 or canvas_height <= 0:
            return None

        image = ExcelImage(str(target_path))
        image.width = canvas_width
        image.height = canvas_height
        return image

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
            for index, header in enumerate(cls.EXCEL_HEADERS, start=2)
        }
