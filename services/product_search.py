"""Búsqueda incremental con coincidencias directas en los datos del catálogo.

Los resultados se actualizan al escribir, sin requerir una tecla especial.
Se ignoran mayúsculas y acentos, y se permiten fragmentos de palabras, códigos
y números. No se aplican sinónimos ni correcciones automáticas de escritura.
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache

from models.product import Product


@lru_cache(maxsize=8192)
def normalize_search_text(text: str) -> str:
    """Normaliza mayúsculas y acentos y elimina puntuación para comparar."""

    value = unicodedata.normalize("NFKD", str(text)).casefold()
    value = "".join(
        character
        for character in value
        if not unicodedata.combining(character)
    )
    value = "".join(
        character if character.isalnum() or character.isspace() else ""
        for character in value
    )
    return " ".join(value.split())


def _product_search_values(product: Product) -> tuple[str, ...]:
    """Devuelve los valores del producto que el usuario puede buscar."""

    values = [
        product.code,
        product.name,
        product.description,
        product.category,
        str(product.stock),
        str(product.price),
        str(product.price_sample),
        str(product.price_hundred),
        str(product.price_thousand),
    ]
    for color, quantity in product.color_stock.items():
        values.extend((str(color), str(quantity)))
    return tuple(str(value) for value in values if value is not None)


def product_matches_search(product: Product, search_text: str) -> bool:
    """Indica si un producto coincide directamente con el texto escrito."""

    query = str(search_text).strip()
    if not query:
        return True

    values = _product_search_values(product)
    normalized_query = normalize_search_text(query)

    # Las consultas formadas solo por signos se comparan literalmente.
    if not normalized_query:
        literal_query = query.casefold()
        return any(literal_query in value.casefold() for value in values)

    normalized_values = tuple(normalize_search_text(value) for value in values)
    # Cada palabra escrita debe aparecer en algún campo del mismo producto.
    # Así se admite una búsqueda por varios datos sin inventar equivalencias.
    return all(
        any(term in value for value in normalized_values)
        for term in normalized_query.split()
    )
