"""Shared policy for the catalog's Detail field.

Detail contains labeled product features, not the short marketing paragraph or
standalone available-colors line. Category-card summaries and product-page
fallbacks use the same cleanup and completeness rules.
"""

from __future__ import annotations

import re

_WHITESPACE_PATTERN = re.compile(r"\s+")
_DETAIL_BOUNDARY = "\u241e"
_DESCRIPTION_FIELD_PATTERN = re.compile(
    r"(?<!\w)descripci[oó]n(?:\s+comercial)?\s*[:|\-]\s*",
    re.IGNORECASE,
)
_COLOR_FIELD_PATTERN = re.compile(
    r"(?<!\w)(?:colores\s+disponibles|colores|color)"
    r"(?!\s+de\s+(?:impresi[oó]n|tinta))"
    r"(?:\s*[:|\-]\s*|\s+(?=\S))",
    re.IGNORECASE,
)
_COLOR_FIELD_PREFIX_PATTERN = re.compile(
    r"^\s*col(?:or|ores)(?:\s+disponibles?)?(?:\s*[:|\-]\s*|\s+)",
    re.IGNORECASE,
)
_COLOR_SEPARATOR_PATTERN = re.compile(r"[.;]\s*")
_DETAIL_FIELD_LABEL_PATTERN = re.compile(
    r"\b(?:"
    r"medida y capacidad|"
    r"medida de impresi[oó]n|"
    r"medidas\s+del\s+estuche|"
    r"medidas\s+(?:de\s+)?(?:estuche|mochila|cartera|cartuchera)|"
    r"presentaci[oó]n\s+del\s+estuche|"
    r"envase\s+largo|"
    r"toalla\s+largo|"
    r"tama[ñn]o\s+cinta|"
    r"color\s+de\s+impresi[oó]n|"
    r"[aá]rea\s+de\s+trabajo|"
    r"empaque\s+por\s+caja|"
    r"n[uú]mero\s+de\s+rodillos|"
    r"velocidad\s+de\s+laminaci[oó]n|"
    r"espesor\s+m[aá]ximo\s+de\s+laminaci[oó]n|"
    r"rollos\s+por\s+caja|"
    r"impresiones\s+por\s+rollo|"
    r"v[aá]lido\s+para\s+impresoras|"
    r"opciones\s+de\s+acabado|"
    r"ancho\s+de\s+entrada|"
    r"cortadora(?:\s+con\s+\d+\s+tipos?\s+de\s+corte)?|"
    r"soporta|"
    r"levantamiento\s+de\s+materiales|"
    r"proyectos\s+de\s+manualidades|"
    r"aplicaciones\s+de\s+vinilo|"
    r"trabajo\s+en\s+scrapbooking|"
    r"calidad\s+superior|"
    r"calidad|"
    r"compatibilidad\s+confiable|"
    r"procedencia\s+coreana|"
    r"facilidad\s+de\s+uso|"
    r"espesor\s+m[aá]ximo\s+del\s+material|"
    r"[aá]rea\s+m[aá]xima\s+de\s+corte|"
    r"[aá]rea\s+de\s+corte|"
    r"ancho\s+de\s+corte|"
    r"longitud\s+de\s+corte|"
    r"fuerza\s+de\s+corte|"
    r"velocidad\s+de\s+corte|"
    r"sistema\s+de\s+motor|"
    r"tipo\s+de\s+luz|"
    r"interior|"
    r"espacio\s+libre|"
    r"interfaz|"
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
    r"presentaci[oó]n(?:\s+del\s+producto)?|"
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
    r"tama[ñn]o(?:\s+(?:de\s+)?impresi[oó]n)?(?:\s*\([^)]*\))?|"
    r"ancho|largo|alto|altura|peso|"
    r"modelo|tipo|formato|marca|"
    r"compatibilidad|contenido|incluye|contiene|empaque|"
    r"paquete|caja|forro|"
    r"alimentaci[oó]n|tiempo|espesor|acabado|"
    r"aplicaci[oó]n|resistencia|"
    r"unidades\s+por\s+caja|cantidad|unidad|"
    r"caracter[ií]sticas|"
    r"propiedades|"
    r"micras"
    r")\s*:",
    re.IGNORECASE,
)
TECHNICAL_DETAIL_FIELD_PATTERN = _DETAIL_FIELD_LABEL_PATTERN

_TECHNICAL_DETAIL_PATTERN = re.compile(
    _DETAIL_FIELD_LABEL_PATTERN.pattern + r"|\bcertificado\s+sgs\b",
    re.IGNORECASE,
)
_NON_TECHNICAL_SECTION_PREFIX_PATTERN = re.compile(
    r"^\s*(?:informaci[oó]n adicional|reseñas?|valoraciones)\s*[:\-]",
    re.IGNORECASE,
)
# Detect visible ellipses and field labels cut off at the end of a card summary.
_DESCRIPTION_TRUNCATION_PATTERN = re.compile(
    r"\.{2,}|…|"
    r"(?<!\w)(?:"
    r"peso\s+(?:br(?:u(?:t(?:o)?)?)?|net(?:o)?)(?:\s+por(?:\s+caj(?:a)?)?)?|"
    r"caja|"
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


def _remove_marked_fields(text: str, pattern: re.Pattern[str]) -> str:
    """Remove excluded field values up to the next recognized Detail label."""
    for match in reversed(list(pattern.finditer(text))):
        prefix = text[: match.start()].rstrip()
        if prefix and prefix[-1] not in ".;|" + _DETAIL_BOUNDARY:
            continue

        next_field = _DETAIL_FIELD_LABEL_PATTERN.search(text, match.end())
        before = text[: match.start()].rstrip(" \t;" + _DETAIL_BOUNDARY)
        if next_field is None:
            text = before
            continue

        after = text[next_field.start() :].lstrip(" \t.;" + _DETAIL_BOUNDARY)
        if before and after:
            separator = " " if before.endswith((".", ";")) else ". "
            text = before + separator + after
        else:
            text = before or after
    return text


def strip_leading_color_field(value: object) -> str:
    """Remove a leading color field from a legacy Detail value."""
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
    """Normalize Detail while excluding marketing Description and color fields."""
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[•▪●‣◦]+", _DETAIL_BOUNDARY, text)
    text = _WHITESPACE_PATTERN.sub(" ", text).strip()
    text = _remove_marked_fields(text, _DESCRIPTION_FIELD_PATTERN)
    text = _remove_marked_fields(text, _COLOR_FIELD_PATTERN)
    text = text.replace(_DETAIL_BOUNDARY, " ")
    return _WHITESPACE_PATTERN.sub(" ", text).strip()


def is_complete_detail(value: object) -> bool:
    """Whether Detail has recognized fields and contains no clipped ending."""
    text = normalize_detail_text(value)
    if (
        not text
        or not has_technical_detail(text)
        or text.endswith((",", ";", ":"))
    ):
        return False
    return _DESCRIPTION_TRUNCATION_PATTERN.search(text) is None


def has_technical_detail(value: object) -> bool:
    """Identify labeled product features, not commercial copy."""
    text = normalize_detail_text(value)
    if not text or _NON_TECHNICAL_SECTION_PREFIX_PATTERN.match(text):
        return False
    return _TECHNICAL_DETAIL_PATTERN.search(text) is not None


def has_multiple_technical_detail_fields(value: object) -> bool:
    """Require at least two labeled features for lower-priority fallbacks."""
    text = normalize_detail_text(value)
    return len(_DETAIL_FIELD_LABEL_PATTERN.findall(text)) >= 2
