from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar
from urllib.request import Request, urlopen
from zipfile import ZIP_DEFLATED, ZipFile

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
from services.stock_color_palette import known_stock_color_style


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
        "Imagen": 18,
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
            cls._inject_category_slicer(Path(filename))

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

        for offset, row in enumerate(rows):
            value = str(row.get("stock_by_color", "") or "").strip()
            if not value:
                continue

            stock_cell = sheet.cell(
                row=2 + offset,
                column=stock_index,
            )
            color_cell = sheet.cell(
                row=2 + offset,
                column=color_index,
            )
            background, text_color = cls._stock_cell_colors(value)
            if background is None:
                continue

            for target in (color_cell, stock_cell):
                target.fill = PatternFill(
                    "solid",
                    fgColor=background,
                )
                target.font = Font(
                    name="Segoe UI",
                    size=10,
                    color=text_color,
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
                stock = max(
                    int(stock_text.strip().replace(",", "")),
                    0,
                )
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

    @classmethod
    def _inject_category_slicer(cls, filename: Path) -> None:
        source = filename
        temp = filename.with_suffix(".slicer.tmp")

        with ZipFile(source, "r") as archive, ZipFile(
            temp,
            "w",
            ZIP_DEFLATED,
        ) as output:
            workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")
            workbook_rels = archive.read(
                "xl/_rels/workbook.xml.rels",
            ).decode("utf-8")
            sheet_xml = archive.read(
                "xl/worksheets/sheet1.xml",
            ).decode("utf-8")
            sheet_rels = archive.read(
                "xl/worksheets/_rels/sheet1.xml.rels",
            ).decode("utf-8")
            content_types = archive.read(
                "[Content_Types].xml",
            ).decode("utf-8")

            workbook_cache_rel_id = cls._next_rel_id(workbook_rels)
            sheet_slicer_rel_id = cls._next_rel_id(sheet_rels)

            workbook_rels = cls._append_relationship(
                workbook_rels,
                workbook_cache_rel_id,
                "http://schemas.microsoft.com/office/2007/relationships/slicerCache",
                "/xl/slicerCaches/slicerCache.xml",
            )
            sheet_rels = cls._append_relationship(
                sheet_rels,
                sheet_slicer_rel_id,
                "http://schemas.microsoft.com/office/2007/relationships/slicer",
                "/xl/slicers/slicer.xml",
            )

            workbook_xml = cls._append_workbook_slicer_parts(
                workbook_xml,
                workbook_cache_rel_id,
            )
            sheet_xml = cls._append_sheet_slicer_parts(
                sheet_xml,
                sheet_slicer_rel_id,
            )
            content_types = cls._append_content_types(content_types)

            rewritten = {
                "xl/workbook.xml": workbook_xml.encode("utf-8"),
                "xl/_rels/workbook.xml.rels": workbook_rels.encode("utf-8"),
                "xl/worksheets/sheet1.xml": sheet_xml.encode("utf-8"),
                "xl/worksheets/_rels/sheet1.xml.rels": sheet_rels.encode("utf-8"),
                "[Content_Types].xml": content_types.encode("utf-8"),
                "xl/slicerCaches/slicerCache.xml": cls._slicer_cache_xml(),
                "xl/slicers/slicer.xml": cls._slicer_xml(),
            }

            for item in archive.infolist():
                if item.filename in rewritten:
                    continue
                output.writestr(item, archive.read(item.filename))

            for name, data in rewritten.items():
                output.writestr(name, data)

        temp.replace(source)

    @staticmethod
    def _next_rel_id(xml: str) -> str:
        import re

        ids = [
            int(match)
            for match in re.findall(r'Id="rId([0-9]+)"', xml)
        ]
        return f"rId{max(ids, default=0) + 1}"

    @staticmethod
    def _append_relationship(
        xml: str,
        rel_id: str,
        relationship_type: str,
        target: str,
    ) -> str:
        payload = (
            f'<Relationship Id="{rel_id}" '
            f'Type="{relationship_type}" '
            f'Target="{target}"/>'
        )
        return xml.replace(
            "</Relationships>",
            payload + "</Relationships>",
        )

    @classmethod
    def _ensure_drawing_part(
        cls,
        names: set[str],
        sheet_xml: str,
        sheet_rels: str,
    ) -> tuple[str, str, str, str]:
        import re

        for relationship in sheet_rels.split("<Relationship")[1:]:
            type_match = re.search(r'Type="([^"]+)"', relationship)
            target_match = re.search(r'Target="([^"]+)"', relationship)
            id_match = re.search(r'Id="([^"]+)"', relationship)
            if not type_match or "drawing" not in type_match.group(1):
                continue
            if not target_match or not id_match:
                continue

            target = target_match.group(1)
            if target.startswith("/xl/drawings/"):
                drawing_name = target.lstrip("/")
            elif target.startswith("../drawings/"):
                drawing_name = (
                    f"xl/drawings/{target[len('../drawings/'):]}"
                )
            else:
                continue

            if drawing_name in names:
                return (
                    drawing_name,
                    id_match.group(1),
                    sheet_xml,
                    sheet_rels,
                )

        drawing_name = "xl/drawings/drawing1.xml"
        rel_id = cls._next_rel_id(sheet_rels)
        sheet_rels = cls._append_relationship(
            sheet_rels,
            rel_id,
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing",
            "../drawings/drawing1.xml",
        )
        sheet_xml = sheet_xml.replace(
            "</pageMargins>",
            f'</pageMargins><drawing r:id="{rel_id}"/>',
        )
        return drawing_name, rel_id, sheet_xml, sheet_rels

    @staticmethod
    def _append_workbook_slicer_parts(
        xml: str,
        cache_rel_id: str,
    ) -> str:
        if "<definedNames>" not in xml:
            defined_names = (
                "<definedNames>"
                '<definedName name="SegmentaciónDeDatos_Categoría">#N/A'
                "</definedName>"
                "</definedNames>"
            )
            xml = xml.replace("</sheets>", f"</sheets>{defined_names}")

        extension = (
            '<extLst><ext '
            'uri="{BBE1A952-AA13-448e-AADC-164F8A28A991}">'
            '<x14:slicerCaches '
            'xmlns:x14="http://schemas.microsoft.com/office/'
            'spreadsheetml/2009/9/main">'
            f'<x14:slicerCache r:id="{cache_rel_id}" '
            'xmlns:r="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships" />'
            "</x14:slicerCaches></ext></extLst>"
        )
        return xml.replace("</workbook>", extension + "</workbook>")

    @staticmethod
    def _append_sheet_slicer_parts(
        xml: str,
        slicer_rel_id: str,
    ) -> str:
        extension = (
            '<extLst><ext '
            'uri="{A8765BA9-456A-4dab-B4F3-ACF838C121DE}">'
            '<x14:slicerList xmlns:x14="http://schemas.microsoft.com/office/'
            'spreadsheetml/2009/9/main">'
            f'<x14:slicer r:id="{slicer_rel_id}" '
            'xmlns:r="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships" />'
            "</x14:slicerList></ext></extLst>"
        )
        return xml.replace("</worksheet>", extension + "</worksheet>")

    @staticmethod
    def _append_content_types(xml: str) -> str:
        additions = (
            '<Override PartName="/xl/slicerCaches/slicerCache.xml" '
            'ContentType="application/vnd.ms-excel.slicerCache+xml"/>'
            '<Override PartName="/xl/slicers/slicer.xml" '
            'ContentType="application/vnd.ms-excel.slicer+xml"/>'
        )
        return xml.replace("</Types>", additions + "</Types>")

    @classmethod
    def _slicer_cache_xml(cls) -> bytes:
        xml = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<x14:slicerCacheDefinition '
            'name="' + cls.SLICER_CACHE_NAME + '" '
            'sourceName="Categoría" '
            'xmlns:x14="http://schemas.microsoft.com/office/'
            'spreadsheetml/2009/9/main">'
            '<x14:data><x14:tabular /></x14:data>'
            '</x14:slicerCacheDefinition>'
        )
        return xml.encode("utf-8")

    @classmethod
    def _slicer_xml(cls) -> bytes:
        xml = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<x14:slicers '
            'xmlns:x14="http://schemas.microsoft.com/office/'
            'spreadsheetml/2009/9/main">'
            '<x14:slicer '
            'name="' + cls.SLICER_NAME + '" '
            'cache="' + cls.SLICER_CACHE_NAME + '" '
            'caption="Categoría" '
            'style="' + cls.SLICER_STYLE + '" '
            'rowHeight="234950" />'
            '</x14:slicers>'
        )
        return xml.encode("utf-8")
