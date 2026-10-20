"""Shared policy for the catalog's Detail field.

Detail is extracted from the category card and, when truncated, repaired only
from the matching technical-detail block on the individual product page.
"""
from __future__ import annotations

import re

_WHITESPACE_PATTERN = re.compile(r"\s+")
_COLOR_FIELD_PREFIX_PATTERN = re.compile(
    r"^\s*col(?:or|ores)(?:\s+disponibles?)?(?:\s*[:|\-]\s*|\s+)",
    re.IGNORECASE,
)
_COLOR_SEPARATOR_PATTERN = re.compile(r"[.;]\s*")
_DETAIL_FIELD_LABEL_PATTERN = re.compile(
    r"\b(?:"
    r"funciones\s+adicionales|"
    r"rango\s+de\s+espesor(?:\s+polaseal)?|"
    r"tiempo\s+de\s+calentamiento|"
    r"consumo\s+de\s+energ[ií]a|"
    r"dimensi[oó]n(?:es)?(?:\s+(?:de\s+)?caja)?|"
    r"peso\s+(?:unitario|neto|bruto)(?:\s+por(?:\s+caja)?)?|"
    r"uso(?:\s+recomendado)?|"
    r"empaque\s+individual|"
    r"cantidad\s+por\s+caja|"
    r"cubicaje(?:\s+por\s+caja)?|"
    r"presentaci[oó]n|"
    r"gramaje|"
    r"capacidad|"
    r"(?:superficie|[aá]rea)\s+de\s+impresi[oó]n|"
    r"t[eé]cnica\s+de\s+impresi[oó]n|"
    r"material|"
    r"medida(?:s)?|"
    r"di[aá]metro|"
    r"velocidad|"
    r"voltaje|"
    r"potencia|"
    r"funci[oó]n(?:es)?|"
    r"temperatura|"
    r"presi[oó]n|"
    r"frecuencia|"
    r"resoluci[oó]n|"
    r"tama[ñn]o(?:\s+de\s+impresi[oó]n)?|"
    r"ancho|largo|alto|altura|peso|"
    r"modelo|tipo|formato|marca|"
    r"compatibilidad|contenido|incluye|empaque|"
    r"alimentaci[oó]n|tiempo|espesor|acabado|"
    r"aplicaci[oó]n|resistencia|"
    r"unidades\s+por\s+caja|cantidad|unidad|"
    r"propiedades|"
    r"micras"
    r")\s*:",
    re.IGNORECASE,
)
_TECHNICAL_DETAIL_PATTERN = re.compile(
    _DETAIL_FIELD_LABEL_PATTERN.pattern + r"|\bcertificado\s+sgs\b",
    re.IGNORECASE,
)
_NON_TECHNICAL_SECTION_PREFIX_PATTERN = re.compile(
    r"^\s*(?:descripci[oó]n(?:\s+comercial)?|"
    r"informaci[oó]n adicional|reseñas?|valoraciones)\s*[:\-]",
    re.IGNORECASE,
)
# Detect both visible ellipses and common product-detail labels cut off at
# the end of a category-card excerpt (e.g. "Peso brut" or "Dimens").
_DESCRIPTION_TRUNCATION_PATTERN = re.compile(
    r"\.{2,}|…|"
    r"(?<!\w)(?:"
    r"peso\s+(?:br(?:u(?:t(?:o)?)?)?|net(?:o)?)(?:\s+por(?:\s+caj(?:a)?)?)?|"
    r"dimens(?:i[oó]n(?:es)?)?(?:\s+(?:de\s+)?caj(?:a)?)?|"
    r"cantidad\s+por\s+caj(?:a)?|"
    r"cubicaje(?:\s+por\s+caj(?:a)?)?|"
    r"funci[oó]n(?:es)?(?:\s+adicionales?)?|"
    r"rango\s+de\s+espesor(?:\s+polaseal)?|"
    r"velocidad|tiempo\s+de\s+calentamiento|"
    r"consumo\s+de\s+energ[ií]a|voltaje|"
    r"material|medidas?|peso\s+unitario|"
    r"uso\s+recomendado|empaque\s+individual"
    r")\s*:?\s*$",
    re.IGNORECASE,
)


def strip_leading_color_field(value: object) -> str:
    """Remove a leading color label only when a caller explicitly requests it."""
    text = _WHITESPACE_PATTERN.sub(
        " ",
        re.sub(r"[•▪●‣◦]", " ", str(value or "")),
    ).strip()
    prefix = _COLOR_FIELD_PREFIX_PATTERN.match(text)
    if prefix is None:
        return text

    value_start = prefix.end()
    separator = _COLOR_SEPARATOR_PATTERN.search(text, value_start)
    next_detail_field = _DETAIL_FIELD_LABEL_PATTERN.search(text, value_start)

    if next_detail_field is not None:
        if separator is None:
            return text[next_detail_field.start() :].strip()
        between_color_and_detail = text[
            separator.end() : next_detail_field.start()
        ]
        if not between_color_and_detail.strip():
            return text[next_detail_field.start() :].strip()

    if separator is not None:
        return text[separator.end() :].strip()
    return ""


def normalize_detail_text(value: object) -> str:
    """Normalize whitespace without dropping technical color attributes."""
    text = re.sub(r"[•▪●‣◦]", " ", str(value or ""))
    return _WHITESPACE_PATTERN.sub(" ", text).strip()


def is_complete_detail(value: object) -> bool:
    """Whether Detail is technical, usable as-is, and free of cut-off fields."""
    text = normalize_detail_text(value)
    if (
        not text
        or not has_technical_detail(text)
        or text.endswith((",", ";", ":"))
    ):
        return False
    return _DESCRIPTION_TRUNCATION_PATTERN.search(text) is None


def has_technical_detail(value: object) -> bool:
    """Identify technical attributes, not text explicitly labeled as another section."""
    text = normalize_detail_text(value)
    if _NON_TECHNICAL_SECTION_PREFIX_PATTERN.match(text):
        return False
    return _TECHNICAL_DETAIL_PATTERN.search(text) is not None


def has_multiple_technical_detail_fields(value: object) -> bool:
    """Require at least two technical labels for lower-priority text fallbacks."""
    text = normalize_detail_text(value)
    return len(_DETAIL_FIELD_LABEL_PATTERN.findall(text)) >= 2
