from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from models.product import Product


EXPORT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("image", "Imagen"),
    ("code", "Código"),
    ("name", "Producto"),
    ("description", "Detalle"),
    ("category", "Categoría"),
    ("stock", "Stock"),
    ("stock_by_color", "Stock por color"),
    ("price_sample", "Precio muestra"),
    ("price_hundred", "Precio ciento"),
    ("price_thousand", "Precio millar"),
)

EXPORT_HEADERS: tuple[str, ...] = tuple(
    header for _, header in EXPORT_COLUMNS
)


def image_reference(product: Product) -> str:
    """Devuelve la referencia de imagen disponible en el catálogo."""
    return str(
        getattr(product, "image_path", "") or getattr(product, "image_url", "")
    ).strip()


def stock_by_color_lines(product: Product) -> list[str]:
    """Serializa el desglose de stock por color conservando su orden."""
    color_stock = getattr(product, "color_stock", {}) or {}
    lines: list[str] = []
    seen: set[str] = set()

    if not isinstance(color_stock, dict):
        return lines

    for color, stock in color_stock.items():
        normalized_color = str(color).strip()
        key = normalized_color.casefold()
        if not normalized_color or key in seen:
            continue
        seen.add(key)
        try:
            normalized_stock = max(int(stock), 0)
        except (TypeError, ValueError):
            normalized_stock = 0
        lines.append(f"{normalized_color}: {normalized_stock:,}")
    return lines


def stock_by_color_text(
    product: Product,
    *,
    separator: str = "\n",
) -> str:
    return separator.join(stock_by_color_lines(product))


def export_row(product: Product) -> dict[str, Any]:
    """Construye una fila común para CSV, Excel y PDF."""
    return {
        "image": image_reference(product),
        "code": str(getattr(product, "code", "")),
        "name": str(getattr(product, "name", "")),
        "description": str(getattr(product, "description", "")),
        "category": str(getattr(product, "category", "")),
        "stock": int(getattr(product, "stock", 0) or 0),
        "stock_by_color": stock_by_color_text(product),
        "price_sample": float(getattr(product, "price_sample", 0) or 0),
        "price_hundred": float(getattr(product, "price_hundred", 0) or 0),
        "price_thousand": float(getattr(product, "price_thousand", 0) or 0),
    }


def export_rows(products: Iterable[Product]) -> list[dict[str, Any]]:
    return [export_row(product) for product in products]
