"""Ordering rules for Importaciones Facundo color stock variants."""

from __future__ import annotations

IMPORTACIONES_FACUNDO_COLOR_ORDER = (
    "azul",
    "negro",
    "rojo",
    "gris",
)


def order_color_names(colors: list[str]) -> list[str]:
    """Order the demonstrated multi-color inventory variants safely."""
    indexed = {
        color.casefold(): index
        for index, color in enumerate(
            IMPORTACIONES_FACUNDO_COLOR_ORDER,
        )
    }
    unknown = [
        color
        for color in colors
        if color.casefold() not in indexed
    ]
    known = [
        color
        for color in colors
        if color.casefold() in indexed
    ]

    if unknown or len(known) < 3:
        return list(colors)

    known.sort(key=lambda color: indexed[color.casefold()])
    return known
