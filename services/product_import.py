"""Importación de productos desde formatos de catálogo compatibles."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import ClassVar

from openpyxl import load_workbook

from models.product import Product
from services.product_search import normalize_search_text


class ProductImportService:
    """Lee un registro de producto desde CSV o XLSX."""

    SUPPORTED_SUFFIXES: ClassVar[frozenset[str]] = frozenset(
        {".csv", ".xlsx", ".xlsm"}
    )

    FIELD_ALIASES: ClassVar[dict[str, str]] = {
        "imagen": "image_path",
        "codigo": "code",
        "codigo producto": "code",
        "sku": "code",
        "producto": "name",
        "nombre": "name",
        "detalle": "description",
        "categoria": "category",
        "stock": "stock",
        "stock por color": "stock_by_color",
        "color": "color",
        "precio": "price",
        "precio muestra": "price_sample",
        "precio ciento": "price_hundred",
        "precio millar": "price_thousand",
    }

    @classmethod
    def import_products(cls, filename: str | Path) -> list[Product]:
        """Import every non-empty product row from a supported bulk file."""
        path = Path(filename)
        if path.suffix.casefold() not in cls.SUPPORTED_SUFFIXES:
            raise ValueError(
                "Formato no compatible. Use CSV, XLSX o XLSM."
            )
        if not path.is_file():
            raise ValueError("El archivo seleccionado no existe.")

        rows = (
            cls._read_csv(path)
            if path.suffix.casefold() == ".csv"
            else cls._read_xlsx(path)
        )
        if not rows:
            raise ValueError("El archivo no contiene registros de productos.")
        return [cls._row_to_product(row) for row in rows]

    @classmethod
    def import_first_product(cls, filename: str | Path) -> Product:
        path = Path(filename)
        if path.suffix.casefold() not in cls.SUPPORTED_SUFFIXES:
            raise ValueError(
                "Formato no compatible. Use CSV, XLSX o XLSM."
            )
        if not path.is_file():
            raise ValueError("El archivo seleccionado no existe.")

        rows = (
            cls._read_csv(path)
            if path.suffix.casefold() == ".csv"
            else cls._read_xlsx(path)
        )
        if not rows:
            raise ValueError("El archivo no contiene registros de productos.")

        return cls._row_to_product(rows[0])

    @classmethod
    def _read_csv(cls, path: Path) -> list[dict[str, object]]:
        last_error: UnicodeDecodeError | None = None
        for encoding in ("utf-8-sig", "cp1252"):
            try:
                with path.open("r", encoding=encoding, newline="") as file:
                    sample = file.read(4096)
                    file.seek(0)
                    try:
                        dialect = csv.Sniffer().sniff(
                            sample,
                            delimiters=";,\t",
                        )
                    except csv.Error:
                        delimiter = ";" if ";" in sample else ","
                        reader = csv.DictReader(
                            file,
                            delimiter=delimiter,
                        )
                    else:
                        reader = csv.DictReader(file, dialect=dialect)
                    return [
                        dict(row)
                        for row in reader
                        if any(str(value or "").strip() for value in row.values())
                    ]
            except UnicodeDecodeError as error:
                last_error = error
        if last_error is not None:
            raise ValueError("No se pudo leer la codificación del CSV.") from last_error
        return []

    @classmethod
    def _read_xlsx(cls, path: Path) -> list[dict[str, object]]:
        workbook = load_workbook(
            filename=path,
            read_only=True,
            data_only=True,
        )
        try:
            sheet = workbook.active
            if sheet is None:
                return []

            header_row_index = None
            header_values: list[object] = []
            rows = sheet.iter_rows(values_only=True)
            for index, row in enumerate(rows):
                normalized = [normalize_search_text(str(value or "")) for value in row]
                if "codigo" in normalized and "producto" in normalized:
                    header_row_index = index
                    header_values = list(row)
                    break

            if header_row_index is None:
                return []

            headers = cls._normalize_headers(header_values)
            result: list[dict[str, object]] = []
            for row in rows:
                values = list(row)
                if not any(str(value or "").strip() for value in values):
                    continue
                result.append(
                    {
                        headers[index]: values[index] if index < len(values) else ""
                        for index in range(len(headers))
                        if headers[index]
                    }
                )
            return result
        finally:
            workbook.close()

    @classmethod
    def _normalize_headers(
        cls,
        headers: list[object],
    ) -> list[str]:
        normalized: list[str] = []
        for header in headers:
            key = normalize_search_text(str(header or ""))
            normalized.append(cls.FIELD_ALIASES.get(key, key))
        return normalized

    @classmethod
    def _row_to_product(cls, row: dict[str, object]) -> Product:
        values: dict[str, object] = {}
        for key, value in row.items():
            field_name = cls.FIELD_ALIASES.get(
                normalize_search_text(key),
                key,
            )
            values[field_name] = value

        stock_by_color = cls._parse_stock_by_color(
            values.get("stock_by_color", "")
        )
        color = str(values.get("color", "") or "").strip()
        if color and not stock_by_color:
            stock_by_color[color] = cls._int_value(values.get("stock"), 0)

        price_sample = cls._number(values.get("price_sample"), 0)
        price = cls._number(values.get("price"), price_sample)

        image_path = str(values.get("image_path", "") or "").strip()
        gallery_images = (
            [
                {
                    "url": "",
                    "image_path": image_path,
                    "image_hash": "",
                    "position": 1,
                    "source": "import",
                }
            ]
            if image_path
            else []
        )

        return Product(
            code=str(values.get("code", "") or "").strip(),
            name=str(values.get("name", "") or "").strip(),
            price=price,
            category=str(values.get("category", "") or "").strip(),
            description=str(values.get("description", "") or "").strip(),
            price_sample=price_sample,
            price_hundred=cls._number(values.get("price_hundred"), 0),
            price_thousand=cls._number(values.get("price_thousand"), 0),
            stock=cls._int_value(values.get("stock"), 0),
            color_stock=stock_by_color,
            image_path=image_path,
            gallery_images=gallery_images,
        )

    @staticmethod
    def _number(value: object, default: float) -> float:
        if value in (None, ""):
            return default
        text = str(value).strip().replace("S/", "").strip()
        if "," in text and "." in text:
            text = text.replace(",", "")
        elif "," in text:
            text = text.replace(",", ".")
        try:
            return float(text)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _int_value(cls, value: object, default: int) -> int:
        if value in (None, ""):
            return default
        number = cls._number(value, float(default))
        return max(round(number), 0)

    @classmethod
    def _parse_stock_by_color(cls, value: object) -> dict[str, int]:
        if not value:
            return {}
        result: dict[str, int] = {}
        for line in str(value).splitlines():
            try:
                color, stock = line.rsplit(":", 1)
            except ValueError:
                continue
            color = color.strip()
            if not color:
                continue
            result[color] = cls._int_value(stock, 0)
        return result
