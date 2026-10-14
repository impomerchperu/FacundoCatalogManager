"""Shared policy for the catalog's Detail field.

Detail is extracted from the category card and, when truncated, repaired only
from the matching technical-detail block on the individual product page.
"""
from __future__ import annotations

import re

_WHITESPACE_PATTERN = re.compile(r"\s+")
_COLOR_FIELD_PREFIX_PATTERN = re.compile(
    r"^\s*col(?:or|ores)(?:\s+disponibles?)?\s*[:|\-]\s*",
    re.IGNORECASE,
)
_COLOR_SEPARATOR_PATTERN = re.compile(r"[.;]\s*")
_DETAIL_FIELD_LABEL_PATTERN = re.compile(
    r"\b(?:"
    r"material|"
    r"dimensi[oó]n(?:es)?(?:\s+(?:de\s+)?caja)?|"
    r"medida(?:s)?|"
    r"di[aá]metro|"
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
    r"propiedades|"
    r"micras"
    r")\s*:",
    re.IGNORECASE,
)
_TECHNICAL_DETAIL_PATTERN = re.compile(
    _DETAIL_FIELD_LABEL_PATTERN.pattern + r"|\bcertificado\s+sgs\b",
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
    r"material|medidas?|peso\s+unitario|"
    r"uso\s+recomendado|empaque\s+individual"
    r")\s*:?\s*$",
    re.IGNORECASE,
)


def strip_leading_color_field(value: object) -> str:
    """Remove a leading Color(s) attribute because it belongs to stock data."""
    text = _WHITESPACE_PATTERN.sub(" ", str(value or "")).strip()
    prefix = _COLOR_FIELD_PREFIX_PATTERN.match(text)
    if prefix is None:
        return text

    value_start = prefix.end()
    separator = _COLOR_SEPARATOR_PATTERN.search(text, value_start)
    next_detail_field = _DETAIL_FIELD_LABEL_PATTERN.search(text, value_start)

    if next_detail_field is not None and (
        separator is None
        or next_detail_field.start() < value_start + separator.end()
    ):
        return text[next_detail_field.start() :].strip()

    if separator is not None:
        return text[value_start + separator.end() :].strip()
    return ""


def normalize_detail_text(value: object) -> str:
    """Normalize whitespace and remove any leading color-only field."""
    return _WHITESPACE_PATTERN.sub(" ", strip_leading_color_field(value)).strip()


def is_complete_detail(value: object) -> bool:
    """Whether Detail is usable as-is, without an ellipsis or cut-off field."""
    text = normalize_detail_text(value)
    if not text or text.endswith((",", ";", ":")):
        return False
    return _DESCRIPTION_TRUNCATION_PATTERN.search(text) is None


def has_technical_detail(value: object) -> bool:
    """Identify a technical-detail block rather than prose from another tab."""
    return _TECHNICAL_DETAIL_PATTERN.search(normalize_detail_text(value)) is not None
