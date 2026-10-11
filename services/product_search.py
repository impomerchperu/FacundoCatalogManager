"""Búsqueda incremental tolerante para todos los datos visibles del catálogo.

La búsqueda no necesita una longitud mínima ni una tecla especial para
ejecutarse: cada cambio en la barra vuelve a evaluar texto, códigos, cantidades,
colores y precios. Se ignoran acentos y mayúsculas, se resuelven sinónimos y se
permiten errores ortográficos simples sin alterar los datos persistidos.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from models.product import Product

_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)

# Equivalencias comerciales habituales en catálogos promocionales, papelería,
# cocina y accesorios. Cada término se normaliza antes de compararse.
_SEARCH_TERM_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"basket", "basquet", "bascket", "canasta"}),
    frozenset({"abridor", "abridores", "destapador", "destapadores", "abrebotellas"}),
    frozenset({"mochila", "mochilas", "morral", "morrales", "backpack", "backpacks"}),
    frozenset({"bolso", "bolsos", "bolsa", "bolsas", "cartera", "carteras", "tote"}),
    frozenset({"lapicero", "lapiceros", "boligrafo", "boligrafos", "esfero", "esferos", "pluma", "plumas"}),
    frozenset({"marcador", "marcadores", "plumon", "plumones", "rotulador", "rotuladores"}),
    frozenset({"resaltador", "resaltadores", "marcatexto", "marcatextos", "highlighter"}),
    frozenset({"tomatodo", "tomatodos", "toma todo", "botella", "botellas", "cantimplora", "cantimploras", "botilito"}),
    frozenset({"mug", "mugs", "taza", "tazas", "jarro", "jarros", "tazon", "tazones"}),
    frozenset({"llavero", "llaveros", "keychain", "keychains"}),
    frozenset({"antiestrés", "antiestres", "anti stress", "stress ball", "antistress"}),
    frozenset({"pendrive", "usb", "memoria usb", "memoria flash"}),
    frozenset({"audifono", "audifonos", "auricular", "auriculares", "headphone", "headphones"}),
    frozenset({"paraguas", "sombrilla", "sombrillas"}),
    frozenset({"lonchera", "loncheras", "fiambrera", "fiambreras", "lunchera"}),
    frozenset({"cuaderno", "cuadernos", "libreta", "libretas"}),
    frozenset({"sacapuntas", "tajador", "tajadores", "afilalapiz"}),
    frozenset({"cutter", "cuter", "cúter", "trincheta", "cortador", "cortadores"}),
    frozenset({"engrapadora", "engrapadoras", "grapadora", "grapadoras"}),
    frozenset({"enmicadora", "enmicadoras", "laminadora", "laminadoras"}),
    frozenset({"portarretrato", "portarretratos", "marco de fotos", "portafoto", "portafotos"}),
    frozenset({"raton", "mouse", "mouses"}),
)

_SEARCH_TERM_ALIASES: dict[str, frozenset[str]] = {
    term: group for group in _SEARCH_TERM_GROUPS for term in group
}


@lru_cache(maxsize=8192)
def normalize_search_text(text: str) -> str:
    """Normaliza mayúsculas/acentos y elimina puntuación de comparación."""

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
    return tuple(_TOKEN_PATTERN.findall(normalize_search_text(text)))


def _edit_distance_at_most_one(left: str, right: str) -> bool:
    """Detecta una inserción, eliminación, sustitución o transposición simple."""

    if left == right:
        return True
    if not left or not right or abs(len(left) - len(right)) > 1:
        return False
    # Para palabras cortas se evita que una sola errata genere demasiados falsos
    # positivos; el prefijo/subcadena sigue siendo útil durante la escritura.
    if min(len(left), len(right)) < 4:
        return False

    if len(left) == len(right):
        differences = [
            index for index, pair in enumerate(zip(left, right, strict=True))
            if pair[0] != pair[1]
        ]
        if len(differences) <= 1:
            return True
        return (
            len(differences) == 2
            and differences[1] == differences[0] + 1
            and left[differences[0]] == right[differences[1]]
            and left[differences[1]] == right[differences[0]]
        )

    shorter, longer = (left, right) if len(left) < len(right) else (right, left)
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


def _product_search_values(product: Product) -> tuple[str, ...]:
    """Devuelve todos los datos textuales/numericos relevantes para el usuario."""

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
    """Indica si el producto coincide con una búsqueda incremental tolerante."""

    raw_query = str(search_text)
    query = raw_query.strip()
    if not query:
        return True

    query_tokens = _normalized_tokens(query)
    values = _product_search_values(product)

    # Si solo se escribieron signos (por ejemplo "-", "/", "#"), se buscan
    # literalmente; no se convierte una consulta de signos en "mostrar todo".
    if not query_tokens:
        literal_query = query.casefold()
        return any(literal_query in value.casefold() for value in values)

    normalized_fields = tuple(normalize_search_text(value) for value in values)
    normalized_text = " ".join(normalized_fields)
    tokens = tuple(
        token
        for value in values
        for token in _normalized_tokens(value)
    )

    # Coincidencia por secuencia para que códigos como FB-1600 y fragmentos
    # numéricos se puedan encontrar mientras el usuario todavía escribe.
    normalized_query = normalize_search_text(query)
    if normalized_query and normalized_query in normalized_text:
        return True

    return all(
        _term_matches(term, normalized_text, tokens)
        for term in query_tokens
    )
