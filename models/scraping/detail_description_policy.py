"""Shared policy for the catalog Detail field.

Preserve the visible product summary, including its Description label, and
other labeled attributes. Remove only color fields from that same summary.
Product-page tab panels are excluded by the extractor before this policy runs.
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
    r"(?<!\w)(?:(?:disponible\s+en)\s+)?"
    r"(?:colores\s+disponibles|colores|color)"
    r"(?!\s+de\s+(?:impresión|tinta))"
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
    r"acceso|"
    r"conectividad|"
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
    r"materiales|"
    r"material|"
    r"medida(?:s)?|"
    r"di[aá]metro|"
    r"velocidad|"
    r"voltaje\s+y\s+frecuencia|"
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
_DETAIL_FIELD_OR_DESCRIPTION_LABEL_PATTERN = re.compile(
    r"(?<!\w)descripci[oó]n(?:\s+comercial)?\s*:\s*|"
    + _DETAIL_FIELD_LABEL_PATTERN.pattern,
    re.IGNORECASE,
)

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
    r"\.{3,}|…|"
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
_EMPTY_TRAILING_BOX_FIELD_PATTERN = re.compile(
    r"(?:[.;]\s*)?\bcaja\s*:\s*$",
    re.IGNORECASE,
)


def _remove_marked_fields(
    text: str,
    pattern: re.Pattern[str],
    *,
    allow_embedded_label: bool = False,
) -> str:
    """Remove excluded field values up to the next recognized Detail label."""
    for match in reversed(list(pattern.finditer(text))):
        prefix = text[: match.start()].rstrip()
        if prefix and prefix[-1] not in ".;|" + _DETAIL_BOUNDARY:
            # Flattened WooCommerce cards sometimes place "Color: ..." inline
            # without a period. Only strip such embedded matches when the
            # field label itself uses an explicit delimiter.
            explicit_label = re.search(r"[:|\-]\s*$", match.group(0)) is not None
            if not allow_embedded_label or not explicit_label:
                continue

        next_field = _DETAIL_FIELD_OR_DESCRIPTION_LABEL_PATTERN.search(
            text,
            match.end(),
        )
        before = text[: match.start()].rstrip(" \t;" + _DETAIL_BOUNDARY)
        if next_field is None:
            # A color field can be followed by ordinary summary prose rather
            # than another labeled field. Remove only the color sentence.
            separator_match = _COLOR_SEPARATOR_PATTERN.search(text, match.end())
            after = (
                text[separator_match.end() :].lstrip(" \t.;" + _DETAIL_BOUNDARY)
                if separator_match is not None
                else ""
            )
        else:
            after = text[next_field.start() :].lstrip(
                " \t.;" + _DETAIL_BOUNDARY
            )

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
    """Preserve the summary Description and remove only color fields."""
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[•▪●‣◦]+", _DETAIL_BOUNDARY, text)
    text = _WHITESPACE_PATTERN.sub(" ", text).strip()
    # Repair doubled sentence punctuation while preserving three-dot ellipses,
    # which remain a signal that the source Detail may be truncated.
    text = re.sub(r"(?<!\.)\.\.(?!\.)", ".", text)
    text = re.sub(r"\s+:", ":", text)
    text = _remove_marked_fields(
        text,
        _COLOR_FIELD_PATTERN,
        allow_embedded_label=True,
    )
    text = text.replace(_DETAIL_BOUNDARY, " ")
    # Preserve an empty terminal "Caja:" field: if the source fills it later,
    # the label remains part of the Detail payload and can be compared on sync.
    return _WHITESPACE_PATTERN.sub(" ", text).strip(" ;")


def is_complete_detail(value: object) -> bool:
    """Whether Detail is complete, allowing an empty final Caja field."""
    text = normalize_detail_text(value)
    # An empty Caja label is a real source field, not a truncation marker.
    # Validate the fields before it, but keep the label in the normalized text.
    validation_text = _EMPTY_TRAILING_BOX_FIELD_PATTERN.sub("", text).rstrip(" ;")
    if (
        not validation_text
        or not has_technical_detail(validation_text)
        or validation_text.endswith((",", ";", ":"))
    ):
        return False
    return _DESCRIPTION_TRUNCATION_PATTERN.search(validation_text) is None


def has_technical_detail(value: object) -> bool:
    """Identify labeled product features, not commercial copy."""
    text = normalize_detail_text(value)
    # The empty Caja label alone should not turn a prose-only description into
    # a technical detail. A populated Caja field remains a recognized label.
    text = _EMPTY_TRAILING_BOX_FIELD_PATTERN.sub("", text).rstrip(" .;")
    if not text or _NON_TECHNICAL_SECTION_PREFIX_PATTERN.match(text):
        return False
    return _TECHNICAL_DETAIL_PATTERN.search(text) is not None


_SUMMARY_NOISE_PATTERN = re.compile(
    r"^(?:"
    r"precio\b|sku\b|stock\b|categor[ií]as?\b|"
    r"colores?\b|disponible\b|añadir al carrito\b|limpiar\b|"
    r"compartir\b|informaci[oó]n adicional\b|reseñas?\b|"
    r"valoraciones\b|"
    r"este producto no está disponible\b|sin stock\b|agotado\b"
    r")",
    re.IGNORECASE,
)


def is_valid_detail_content(value: object) -> bool:
    """Accept technical fields or meaningful prose from the visible summary.

    The extractor excludes Description, Additional Information and Reviews tab
    panels before calling this policy, so ordinary summary prose is valid too.
    """
    text = normalize_detail_text(value)
    has_empty_terminal_box = (
        _EMPTY_TRAILING_BOX_FIELD_PATTERN.search(text) is not None
    )
    if (
        not text
        or _NON_TECHNICAL_SECTION_PREFIX_PATTERN.match(text)
        or text.endswith((",", ";"))
        or (text.endswith(":") and not has_empty_terminal_box)
        or _SUMMARY_NOISE_PATTERN.match(text)
    ):
        return False
    if has_technical_detail(text):
        return is_complete_detail(text)
    return len(text) >= 20


def has_multiple_technical_detail_fields(value: object) -> bool:
    """Require at least two labeled features for lower-priority fallbacks."""
    text = normalize_detail_text(value)
    return len(_DETAIL_FIELD_LABEL_PATTERN.findall(text)) >= 2
