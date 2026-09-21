"""Ordering rules for Importaciones Facundo color stock variants."""

from __future__ import annotations

IMPORTACIONES_FACUNDO_COLOR_ORDER = (
    "azul",
    "negro",
    "rojo",
    "gris",
)


def order_color_names(colors: list[str]) -> list[str]:
    """Order known inventory colors without disturbing unknown colors."""
    indexed = {
        color.casefold(): index
        for index, color in enumerate(
            IMPORTACIONES_FACUNDO_COLOR_ORDER,
        )
    }
    known = [
        color
        for color in colors
        if color.casefold() in indexed
    ]
    unknown = [
        color
        for color in colors
        if color.casefold() not in indexed
    ]
    known.sort(key=lambda color: indexed[color.casefold()])
    return known + unknown
