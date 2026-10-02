import os
from datetime import datetime, timezone
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)

from config.runtime_paths import resolve_data_path
from exporters.catalog_export_schema import EXPORT_HEADERS, export_rows


class PDFExporter:
    """Genera un PDF alineado con la tabla principal del catálogo."""

    PAGE_SIZE = landscape(A4)
    LEFT_MARGIN = 0.6 * cm
    RIGHT_MARGIN = 0.6 * cm
    TOP_MARGIN = 0.7 * cm
    BOTTOM_MARGIN = 0.7 * cm
    IMAGE_SIZE = 1.25 * cm

    HEADER_BACKGROUND = colors.HexColor("#173F6D")
    HEADER_TEXT = colors.white
    BODY_TEXT = colors.HexColor("#173F6D")
    GRID_COLOR = colors.HexColor("#CBDDEA")
    ALT_BACKGROUND = colors.HexColor("#F8FBFF")

    COLUMN_WIDTHS = (
        1.65 * cm,
        2.05 * cm,
        4.0 * cm,
        4.35 * cm,
        3.15 * cm,
        1.45 * cm,
        3.55 * cm,
        2.25 * cm,
        2.25 * cm,
        2.25 * cm,
    )

    @classmethod
    def export(cls, products, filename) -> None:
        products = list(products)
        doc = SimpleDocTemplate(
            filename,
            pagesize=cls.PAGE_SIZE,
            leftMargin=cls.LEFT_MARGIN,
            rightMargin=cls.RIGHT_MARGIN,
            topMargin=cls.TOP_MARGIN,
            bottomMargin=cls.BOTTOM_MARGIN,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CatalogTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=21,
            textColor=cls.HEADER_BACKGROUND,
            spaceAfter=4,
            alignment=TA_LEFT,
        )
        meta_style = ParagraphStyle(
            "CatalogMeta",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=10,
            textColor=colors.HexColor("#5F6F7E"),
            spaceAfter=8,
        )
        header_style = ParagraphStyle(
            "CatalogHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.7,
            leading=9,
            textColor=cls.HEADER_TEXT,
            alignment=TA_CENTER,
        )
        body_style = ParagraphStyle(
            "CatalogBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7.1,
            leading=8.5,
            textColor=cls.BODY_TEXT,
        )
        body_center_style = ParagraphStyle(
            "CatalogBodyCenter",
            parent=body_style,
            alignment=TA_CENTER,
        )
        price_style = ParagraphStyle(
            "CatalogPrice",
            parent=body_center_style,
            fontName="Helvetica-Bold",
        )

        generated_at = datetime.now(timezone.utc).astimezone()
        elements: list[Any] = [
            Paragraph("Catálogo de Productos", title_style),
            Paragraph(
                f"{len(products)} productos · Generado "
                f"{generated_at.strftime('%d/%m/%Y %H:%M')}",
                meta_style,
            ),
            Spacer(1, 2),
        ]

        header = [
            Paragraph(cls._header_text(label), header_style)
            for label in EXPORT_HEADERS
        ]
        data: list[list[Any]] = [header]

        for row in export_rows(products):
            data.append(
                [
                    cls._image_cell(row["image"]),
                    Paragraph(cls._escape(row["code"]), body_center_style),
                    Paragraph(cls._escape(row["name"]), body_style),
                    Paragraph(cls._escape(row["description"]), body_style),
                    Paragraph(cls._escape(row["category"]), body_style),
                    Paragraph(str(row["stock"]), body_center_style),
                    Paragraph(
                        cls._escape(row["stock_by_color"]).replace(
                            "\n",
                            "<br/>",
                        ),
                        body_style,
                    ),
                    Paragraph(
                        cls._price(row["price_sample"]),
                        price_style,
                    ),
                    Paragraph(
                        cls._price(row["price_hundred"]),
                        price_style,
                    ),
                    Paragraph(
                        cls._price(row["price_thousand"]),
                        price_style,
                    ),
                ]
            )

        table = LongTable(
            data,
            colWidths=cls.COLUMN_WIDTHS,
            repeatRows=1,
            hAlign="LEFT",
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), cls.HEADER_BACKGROUND),
                    ("TEXTCOLOR", (0, 0), (-1, 0), cls.HEADER_TEXT),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.35, cls.GRID_COLOR),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, cls.ALT_BACKGROUND],
                    ),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        elements.append(table)
        doc.build(elements)

    @classmethod
    def _image_cell(cls, image_reference: str) -> Any:
        if not image_reference:
            return ""
        path = resolve_data_path(image_reference)
        if not os.path.exists(path):
            return ""
        return Image(
            str(path),
            width=cls.IMAGE_SIZE,
            height=cls.IMAGE_SIZE,
            kind="proportional",
        )

    @staticmethod
    def _escape(value: object) -> str:
        return escape(str(value or ""))

    @staticmethod
    def _price(value: object) -> str:
        amount = float(value) if isinstance(value, (int, float)) else 0.0
        return f"S/ {amount:,.2f}"

    @staticmethod
    def _header_text(value: str) -> str:
        return value.replace(" ", "<br/>", 1)
