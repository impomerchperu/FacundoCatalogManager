"""Búsqueda tolerante para el catálogo de productos.

La barra de búsqueda comparte esta lógica para ignorar diferencias de
acentos y puntuación, resolver sinónimos y tolerar errores tipográficos
simples sin modificar los datos persistidos.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from models.product import Product

_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)

# Cada grupo reúne equivalencias comerciales o variantes ortográficas que
# deben producir el mismo resultado de búsqueda. Las variantes se normalizan
# antes de compararse, por lo que "básquet" y "basket" ya son equivalentes.
_SEARCH_TERM_GROUPS: tuple[frozenset[str], ...] = (
    frozenset(
        {
            "basket",
            "basquet",
            "bascket",
        }
    ),
    frozenset(
        {
            "abridor",
            "abridores",
            "destapador",
            "destapadores",
            "abrebotellas",
        }
    ),
)

_SEARCH_TERM_ALIASES: dict[str, frozenset[str]] = {
    term: group for group in _SEARCH_TERM_GROUPS for term in group
}


@lru_cache(maxsize=8192)
def normalize_search_text(text: str) -> str:
    """Normaliza mayúsculas, acentos y signos para comparar texto."""

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


@lru_cache(maxsize=8192)
def _normalized_tokens(text: str) -> tuple[str, ...]:
    normalized = normalize_search_text(text)
    return tuple(_TOKEN_PATTERN.findall(normalized))


def _edit_distance_at_most_one(left: str, right: str) -> bool:
    """Detecta una única inserción, eliminación o sustitución."""

    if left == right:
        return True
    if not left or not right or abs(len(left) - len(right)) > 1:
        return False
    if len(left) < 5 or len(right) < 5:
        return False

    shorter, longer = (
        (left, right)
        if len(left) <= len(right)
        else (right, left)
    )

    if len(shorter) == len(longer):
        differences = sum(
            first != second
            for first, second in zip(shorter, longer, strict=True)
        )
        return differences <= 1

    short_index = 0
    long_index = 0
    differences = 0
    while short_index < len(shorter) and long_index < len(longer):
        if shorter[short_index] == longer[long_index]:
            short_index += 1
            long_index += 1
            continue
        differences += 1
        long_index += 1
        if differences > 1:
            return False

    return True


def _term_matches(
    term: str,
    normalized_text: str,
    tokens: tuple[str, ...],
) -> bool:
    aliases = _SEARCH_TERM_ALIASES.get(term, frozenset({term}))
    for alias in aliases:
        normalized_alias = normalize_search_text(alias)
        if " " in normalized_alias:
            if normalized_alias in normalized_text:
                return True
            continue

        if any(
            normalized_alias in candidate
            or _edit_distance_at_most_one(normalized_alias, candidate)
            for candidate in tokens
        ):
            return True

    return False


def product_matches_search(product: Product, search_text: str) -> bool:
    """Indica si un producto coincide con una consulta tolerante."""

    query_tokens = _normalized_tokens(search_text)
    if not query_tokens:
        return True

    # Stock y precios no son campos de búsqueda: la consulta se limita a
    # referencias, nombre, descripción y categoría del producto.
    values = (
        product.code,
        product.name,
        product.description,
        product.category,
    )

    normalized_fields = tuple(normalize_search_text(value) for value in values)
    field_tokens = tuple(
        tokens
        for tokens in (_normalized_tokens(value) for value in values)
    )
    normalized_text = " ".join(normalized_fields)
    tokens = tuple(token for group in field_tokens for token in group)

    return all(
        _term_matches(term, normalized_text, tokens)
        for term in query_tokens
    )
