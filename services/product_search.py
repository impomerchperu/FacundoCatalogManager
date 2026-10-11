"""Búsqueda incremental con coincidencias directas y sinónimos comerciales.

Los resultados se actualizan al escribir. Se ignoran mayúsculas y acentos y
se admiten fragmentos de códigos, nombres, cantidades, colores y precios.
Los sinónimos amplían la consulta sin corregir automáticamente errores de
escritura.
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache

from models.product import Product

# Equivalencias comerciales habituales en catálogos promocionales, papelería,
# cocina y accesorios. No se incluyen reglas de corrección ortográfica.
_SEARCH_TERM_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"basket", "basquet", "canasta", "canastas"}),
    frozenset(
        {
            "abridor",
            "abridores",
            "destapador",
            "destapadores",
            "abrebotellas",
        }
    ),
    frozenset(
        {
            "mochila",
            "mochilas",
            "morral",
            "morrales",
            "backpack",
            "backpacks",
        }
    ),
    frozenset(
        {
            "bolso",
            "bolsos",
            "bolsa",
            "bolsas",
            "cartera",
            "carteras",
            "tote",
        }
    ),
    frozenset(
        {
            "lapicero",
            "lapiceros",
            "boligrafo",
            "boligrafos",
            "esfero",
            "esferos",
            "pluma",
            "plumas",
        }
    ),
    frozenset(
        {
            "marcador",
            "marcadores",
            "plumon",
            "plumones",
            "rotulador",
            "rotuladores",
        }
    ),
    frozenset(
        {
            "resaltador",
            "resaltadores",
            "marcatexto",
            "marcatextos",
            "highlighter",
        }
    ),
    frozenset(
        {
            "tomatodo",
            "tomatodos",
            "toma todo",
            "botella",
            "botellas",
            "cantimplora",
            "cantimploras",
            "botilito",
        }
    ),
    frozenset(
        {"mug", "mugs", "taza", "tazas", "jarro", "jarros", "tazon", "tazones"}
    ),
    frozenset({"llavero", "llaveros", "keychain", "keychains"}),
    frozenset(
        {"antiestrés", "antiestres", "anti stress", "stress ball", "antistress"}
    ),
    frozenset({"pendrive", "usb", "memoria usb", "memoria flash"}),
    frozenset(
        {
            "audifono",
            "audifonos",
            "auricular",
            "auriculares",
            "headphone",
            "headphones",
        }
    ),
    frozenset({"paraguas", "sombrilla", "sombrillas"}),
    frozenset(
        {"lonchera", "loncheras", "fiambrera", "fiambreras", "lunchera"}
    ),
    frozenset({"cuaderno", "cuadernos", "libreta", "libretas"}),
    frozenset({"sacapuntas", "tajador", "tajadores", "afilalapiz"}),
    frozenset({"cutter", "cuter", "cúter", "trincheta", "cortador", "cortadores"}),
    frozenset({"engrapadora", "engrapadoras", "grapadora", "grapadoras"}),
    frozenset({"enmicadora", "enmicadoras", "laminadora", "laminadoras"}),
    frozenset(
        {
            "portarretrato",
            "portarretratos",
            "marco de fotos",
            "portafoto",
            "portafotos",
        }
    ),
    frozenset({"raton", "mouse", "mouses"}),
)


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


_SEARCH_TERM_ALIASES: dict[str, frozenset[str]] = {}
for group in _SEARCH_TERM_GROUPS:
    normalized_group = frozenset(
        normalize_search_text(alias) for alias in group
    )
    for term in normalized_group:
        _SEARCH_TERM_ALIASES[term] = normalized_group

_MULTIWORD_SEARCH_ALIASES = sorted(
    (
        (term, aliases)
        for term, aliases in _SEARCH_TERM_ALIASES.items()
        if " " in term
    ),
    key=lambda item: len(item[0].split()),
    reverse=True,
)


def _query_alias_groups(query: str) -> tuple[frozenset[str], ...]:
    """Group multiword synonyms so extra query terms remain independently usable."""

    terms = query.split()
    groups: list[frozenset[str]] = []
    index = 0
    while index < len(terms):
        for phrase, aliases in _MULTIWORD_SEARCH_ALIASES:
            phrase_terms = phrase.split()
            end = index + len(phrase_terms)
            if terms[index:end] == phrase_terms:
                groups.append(aliases)
                index = end
                break
        else:
            term = terms[index]
            groups.append(_SEARCH_TERM_ALIASES.get(term, frozenset({term})))
            index += 1
    return tuple(groups)


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
    """Indica si un producto coincide con el texto escrito o sus sinónimos."""

    query = str(search_text).strip()
    if not query:
        return True

    values = _product_search_values(product)
    normalized_values = tuple(normalize_search_text(value) for value in values)
    normalized_query = normalize_search_text(query)

    # Las consultas formadas solo por signos se comparan literalmente.
    if not normalized_query:
        literal_query = query.casefold()
        return any(literal_query in value.casefold() for value in values)

    # Una consulta que sea una expresión sinónima completa puede coincidir
    # directamente con cualquiera de sus equivalencias, incluso si tiene
    # varias palabras (por ejemplo, "toma todo" / "botella").
    phrase_aliases = _SEARCH_TERM_ALIASES.get(normalized_query)
    if phrase_aliases and any(
        alias in value
        for alias in phrase_aliases
        for value in normalized_values
    ):
        return True

    # Agrupa expresiones como "toma todo" para que consultas como
    # "toma todo rojo" encuentren botellas rojas sin perder el término "rojo".
    # No se infieren letras ni se corrigen errores ortográficos.
    return all(
        any(
            alias in value
            for alias in aliases
            for value in normalized_values
        )
        for aliases in _query_alias_groups(normalized_query)
    )
