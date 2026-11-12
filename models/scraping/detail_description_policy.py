"""Shared policy for the catalog Detail field.

Preserve the visible product summary, including its Description label, and
other labeled attributes. Remove only color fields from that same summary.
Product-page tab panels are excluded by the extractor before this policy runs.
"""

from __future__ import annotations

import re
from copy import copy
from itertools import pairwise

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString, PageElement, Tag

_DETAIL_LITERAL_COLON_MARKER = "\uE001"
_WHITESPACE_PATTERN = re.compile(r"\s+")
# The visible product summary can end with the social-sharing control inside the
# same paragraph as Detail. It is interface chrome, never a product attribute.
_TRAILING_DETAIL_UI_NOISE_PATTERN = re.compile(
    r"(?:^|[\s\u241e])(?:compartir|share)\s*(?::|\uE001)\s*.*$",
    re.IGNORECASE | re.DOTALL,
)
_DETAIL_BOUNDARY = "\u241e"
_DESCRIPTION_FIELD_PATTERN = re.compile(
    r"(?<!\w)descripci[oó]n(?:\s+comercial)?\s*[:|\-]\s*",
    re.IGNORECASE,
)
# Product-variant color fields are redundant in Detail.
# Specific technical labels such as "Color de tinta" and "Color de impresión"
# remain valid because their labels continue after the word "Color".
_COLOR_FIELD_PATTERN = re.compile(
    r"(?<!\w)(?:(?:disponible\s+en)\s+)?"
    r"(?:color(?:es)?\s+disponibles?|color(?:es)?|tonos?|tonalidades?|"
    r"variantes?\s+de\s+color(?:es)?)"
    r"(?!\s+(?:"
    r"(?:de|del)\s+(?!producto\b)\w+|"
    r"de\s+la\s+\w+|exterior\b"
    r"))"
    r"(?:\s*[:|\-]\s*|\s+(?=\S))",
    re.IGNORECASE,
)

_COLOR_FIELD_PREFIX_PATTERN = re.compile(
    r"^\s*(?:(?:disponible\s+en)\s+)?"
    r"(?:color(?:es)?\s+disponibles?|color(?:es)?|tonos?|tonalidades?|"
    r"variantes?\s+de\s+color(?:es)?)"
    r"(?!\s+(?:"
    r"(?:de|del)\s+(?!producto\b)\w+|"
    r"de\s+la\s+\w+|exterior\b"
    r"))"
    r"(?:\s*[:|\-]\s*|\s+(?=\S))",
    re.IGNORECASE,
)

_COLOR_AVAILABILITY_FIELD_PREFIX_PATTERN = re.compile(
    r"(?:disponible\s+en\s+color(?:es)?|color(?:es)?\s+disponibles?)\s*$",
    re.IGNORECASE,
)
_COLOR_SEPARATOR_PATTERN = re.compile(
    r"[.;|\r\n" + re.escape(_DETAIL_BOUNDARY) + r"]\s*"
)
_DETAIL_FIELD_BOUNDARY_PATTERN = re.compile(
    r"(?:^|(?<=[.;|/\n\u241e]))\s*[^:\r\n]{1,80}:\s*"
)
TECHNICAL_DETAIL_FIELD_PATTERN = _DETAIL_FIELD_BOUNDARY_PATTERN
_DETAIL_FIELD_OR_DESCRIPTION_LABEL_PATTERN = _DETAIL_FIELD_BOUNDARY_PATTERN

_EMPTY_DETAIL_FIELD_FRAGMENT_PATTERN = re.compile(
    r"^\s*[^:\r\n]{1,80}:\s*$",
    re.IGNORECASE,
)

_TECHNICAL_DETAIL_PATTERN = re.compile(
    _DETAIL_FIELD_BOUNDARY_PATTERN.pattern + r"|\bcertificado\s+sgs\b",
    re.IGNORECASE,
)
_NON_TECHNICAL_SECTION_PREFIX_PATTERN = re.compile(
    r"^\s*(?:descripci[oó]n\s+comercial|informaci[oó]n adicional|reseñas?|valoraciones)\s*[:\-]",
    re.IGNORECASE,
)
_DESCRIPTION_TRUNCATION_PATTERN = re.compile(
    r"\.{3,}|…|"
    r"(?:^|[.;]\s*)[A-ZÁÉÍÓÚÜÑ][^:\d\r\n]{0,24}"
    r"(?:\s+[a-záéíóúñ]{1,5}){0,3}\s*$"
)



_DETAIL_HTML_BLOCK_TAGS = frozenset({
    "br", "p", "div", "li", "ul", "ol",
    "h1", "h2", "h3", "h4", "h5", "h6",
})


def _first_detail_html_inline_text(node: Tag) -> NavigableString | None:
    """Return the first visible text node before an inline/block boundary."""
    for child in node.children:
        if isinstance(child, Comment):
            continue
        if isinstance(child, NavigableString):
            return child
        if not isinstance(child, Tag):
            continue
        if child.name in _DETAIL_HTML_BLOCK_TAGS:
            return None
        nested = _first_detail_html_inline_text(child)
        if nested is not None:
            return nested
    return None


def _next_detail_html_inline_text(
    node: Tag | NavigableString,
) -> NavigableString | None:
    """Find the next inline text node; existing whitespace/breaks end the search."""
    sibling = node.next_sibling
    while sibling is not None:
        if isinstance(sibling, Comment):
            sibling = sibling.next_sibling
            continue
        if isinstance(sibling, NavigableString):
            # Whitespace-only text already separates the label from its value.
            return sibling if str(sibling).strip() else None
        if isinstance(sibling, Tag):
            if sibling.name in _DETAIL_HTML_BLOCK_TAGS:
                return None
            nested = _first_detail_html_inline_text(sibling)
            if nested is not None:
                return nested
        sibling = sibling.next_sibling
    return None


def _ensure_detail_html_label_spacing(root: Tag) -> None:
    """Insert only a missing separator after a bold field label's colon."""
    for bold in list(root.find_all(["strong", "b"])):
        bold_text = bold.get_text("", strip=False)
        following_node = _next_detail_html_inline_text(bold)
        if following_node is None:
            continue

        following_text = str(following_node)
        if not following_text:
            continue

        if bold_text.rstrip().endswith(":"):
            # A trailing space inside the bold label is already visible in HTML.
            if bold_text[-1].isspace():
                continue
            if following_text[0].isspace() or following_text.startswith(":"):
                continue
            bold.insert_after(NavigableString(" "))
            continue

        # Some source templates put the colon immediately after </strong>.
        # Keep the colon in its original place and add a separator after it.
        colon_prefix = re.match(r"^(\s*:)(?=\S)", following_text)
        if colon_prefix is not None:
            following_node.replace_with(
                NavigableString(
                    following_text[: colon_prefix.end()]
                    + " "
                    + following_text[colon_prefix.end() :]
                )
            )
            continue

        # The colon can itself be a separate text node before an inline value.
        if following_text.rstrip().endswith(":") and not following_text[-1].isspace():
            after_colon = _next_detail_html_inline_text(following_node)
            if (
                after_colon is not None
                and str(after_colon)
                and not str(after_colon)[0].isspace()
            ):
                following_node.replace_with(
                    NavigableString(following_text + " ")
                )



def _split_bold_label_before_nested_span_value(root: Tag) -> None:
    """Keep a field label bold when its value is wrapped in a nested span."""
    for bold in list(root.find_all(["strong", "b"])):
        children = list(bold.contents)
        inline_tags = [
            child for child in children if isinstance(child, Tag)
        ]
        if len(inline_tags) != 1 or inline_tags[0].name != "span":
            continue

        value_tag = inline_tags[0]
        value_index = children.index(value_tag)
        prefix_nodes = children[:value_index]
        suffix_nodes = children[value_index + 1 :]
        if any(
            not isinstance(node, NavigableString)
            for node in (*prefix_nodes, *suffix_nodes)
        ):
            continue

        label = "".join(str(node) for node in prefix_nodes)
        if re.fullmatch(r"\s*[^:\r\n]{1,100}:\s*", label) is None:
            continue
        if not value_tag.get_text("", strip=False).strip():
            continue

        suffix = "".join(str(node) for node in suffix_nodes)
        detached_value = value_tag.extract()
        bold.clear()
        bold.append(label.rstrip())

        separator = NavigableString(" ")
        bold.insert_after(separator)
        separator.insert_after(detached_value)
        if suffix:
            detached_value.insert_after(NavigableString(suffix))


def _unwrap_punctuation_only_detail_emphasis(root: Tag) -> None:
    """Do not retain bold markup around a standalone punctuation fragment."""
    for bold in list(root.find_all(["strong", "b"])):
        text = bold.get_text("", strip=False)
        if re.fullmatch(r"\s*[.,;!?…]+\s*", text):
            bold.unwrap()

def extract_detail_text_from_element(
    element,
    *,
    ensure_field_label_spacing: bool = True,
) -> str:
    """Keep source emphasis and visible inline whitespace when parsing Detail."""
    boundary = "__FACUNDO_DETAIL_BOUNDARY__"
    source = BeautifulSoup(str(element), "lxml")
    bold_tags = source.find_all(["strong", "b"])

    if bold_tags:
        # Some templates place the colon just outside the emphasis element.
        # Move that colon into the bold span before protecting all plain text.
        for bold in bold_tags:
            if bold.get_text("", strip=True).endswith(":"):
                continue
            sibling = bold.next_sibling
            if isinstance(sibling, NavigableString):
                colon = re.match(r"^\s*:", str(sibling))
                if colon is not None:
                    bold.append(":")
                    remainder = str(sibling)[colon.end() :]
                    if remainder:
                        sibling.replace_with(NavigableString(remainder))
                    else:
                        sibling.extract()

        if ensure_field_label_spacing:
            _ensure_detail_html_label_spacing(source)

        # A colon outside <strong>/<b> is literal value text, not a label
        # delimiter. Protect it only after checking for a label/value boundary.
        for text_node in list(source.find_all(string=True)):
            if text_node.find_parent(["strong", "b"]) is not None:
                continue
            original = str(text_node)
            if ":" in original:
                text_node.replace_with(
                    NavigableString(
                        original.replace(":", _DETAIL_LITERAL_COLON_MARKER)
                    )
                )

    markup = str(source)
    markup = re.sub(
        r"<br\b[^>]*>",
        boundary,
        markup,
        flags=re.IGNORECASE,
    )
    markup = re.sub(
        r"<(?:li|p|div|h[1-6])\b[^>]*>",
        boundary,
        markup,
        flags=re.IGNORECASE,
    )
    markup = re.sub(
        r"</(?:li|p|div|h[1-6])\s*>",
        boundary,
        markup,
        flags=re.IGNORECASE,
    )
    text = BeautifulSoup(markup, "lxml").get_text("", strip=False)
    chunks = [
        re.sub(r"\s+", " ", chunk).strip()
        for chunk in text.split(boundary)
    ]
    return " ␞ ".join(chunk for chunk in chunks if chunk)


def restore_literal_detail_colons(value: object) -> str:
    """Restore colons that belonged to unbolded source text."""
    return str(value or "").replace(_DETAIL_LITERAL_COLON_MARKER, ":")


def remove_incomplete_trailing_dimension_field(value: object) -> str:
    """Compatibility shim: retain every field exactly as published in Detail."""
    return str(value or "")


# These source logistics labels may legitimately have no supplied value. Keep
# the labels in the saved Detail, but omit a chain of empty terminal labels only
# while validating completeness. Other terminal labels still signal truncation.
_EMPTY_TRAILING_DETAIL_FIELD_PATTERN = re.compile(
    r"(?:[.;]\s*)?\b(?:"
    r"dimensiones\s+(?:de\s+)?(?:la\s+)?caja(?:\s+m[aá]ster)?|"
    r"cubicaje(?:\s+por\s+caja)?|"
    r"peso\s+(?:neto|bruto)(?:\s+(?:por\s+caja|/\s*caja))?|"
    r"caja"
    r")\s*:\s*$",
    re.IGNORECASE,
)


def _strip_allowed_empty_trailing_detail_fields(value: object) -> str:
    """Remove whitelisted empty terminal shipping labels for validation only."""
    text = str(value or "").rstrip()
    while text:
        match = _EMPTY_TRAILING_DETAIL_FIELD_PATTERN.search(text)
        if match is None:
            break
        prefix = text[: match.start()].rstrip(" .;\t\r\n")
        if not prefix:
            return ""
        text = prefix
    return text

# This is catalog-wide commercial noise, not a product attribute. Strip it
# consistently from every Detail value instead of special-casing one SKU.
_PRICE_INCLUDES_IGV_PATTERN = re.compile(
    r"(?:\s*,\s*|\s+)?\bprecio\s+incluye\s+igv\b\.?",
    re.IGNORECASE,
)


def _remove_marked_fields(
    text: str,
    pattern: re.Pattern[str],
    *,
    allow_embedded_label: bool = False,
    preserve_boundaries: bool = False,
) -> str:
    """Remove excluded field values up to the next recognized Detail label."""
    for match in reversed(list(pattern.finditer(text))):
        raw_prefix = text[: match.start()]
        prefix = raw_prefix.rstrip()
        prefix_has_boundary = raw_prefix.rstrip(" \t").endswith(
            ("\n", _DETAIL_BOUNDARY)
        )
        explicit_label = re.search(r"[:|\-]\s*$", match.group(0)) is not None
        availability_label = (
            _COLOR_AVAILABILITY_FIELD_PREFIX_PATTERN.search(match.group(0))
            is not None
        )
        if _is_description_color_enumeration(text, match):
            continue
        # Remove known availability labels when flattened into Description,
        # but preserve unlabelled descriptive prose such as "5 colores".
        if (
            prefix
            and prefix[-1] not in ".;|" + _DETAIL_BOUNDARY
            and not prefix_has_boundary
            and (
                not allow_embedded_label
                or (not explicit_label and not availability_label)
            )
        ):
            continue

        next_field = _DETAIL_FIELD_OR_DESCRIPTION_LABEL_PATTERN.search(
            text,
            match.end(),
        )
        before = text[: match.start()].rstrip(" \t;\n" + _DETAIL_BOUNDARY)
        if next_field is None:
            # A color field can be followed by ordinary summary prose rather
            # than another labeled field. Remove only the color sentence.
            separator_match = _COLOR_SEPARATOR_PATTERN.search(text, match.end())
            after = (
                text[separator_match.end() :].lstrip(" \t.;\n" + _DETAIL_BOUNDARY)
                if separator_match is not None
                else ""
            )
        else:
            after = text[next_field.start() :].lstrip(
                " \t.;\n" + _DETAIL_BOUNDARY
            )

        if before and after:
            boundary_end = (
                next_field.start()
                if next_field is not None
                else (
                    separator_match.end()
                    if separator_match is not None
                    else match.end()
                )
            )
            removed_region = text[match.start():boundary_end]
            has_source_boundary = (
                prefix_has_boundary
                or "\n" in removed_region
                or _DETAIL_BOUNDARY in removed_region
            )
            if preserve_boundaries and has_source_boundary:
                separator = "\n"
            else:
                separator = " " if before.endswith((".", ";")) else ". "
            text = before + separator + after
        else:
            text = before or after
    return text


def strip_leading_color_field(value: object) -> str:
    """Remove a leading product-variant color field from a legacy Detail value."""
    text = _WHITESPACE_PATTERN.sub(
        " ",
        re.sub(r"[•▪●‣◦]", " ", str(value or "")),
    ).strip()
    prefix = _COLOR_FIELD_PREFIX_PATTERN.match(text)
    if prefix is None:
        return text

    value_start = prefix.end()
    separator = _COLOR_SEPARATOR_PATTERN.search(text, value_start)
    next_detail_field = _DETAIL_FIELD_BOUNDARY_PATTERN.search(text, value_start)

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


def _is_description_color_enumeration(
    text: str,
    match: re.Match[str],
) -> bool:
    """Keep color prose within Description, not explicit product-color fields."""
    prefix = text[: match.start()]
    if (
        _DESCRIPTION_FIELD_PATTERN.search(prefix)
        and re.search(r"\ben\s+\d+\s*$", prefix, re.IGNORECASE)
    ):
        return True

    # Unlabelled color words inside Description are descriptive prose. An
    # explicit "Color:"/"Colores:" label remains removable even in that field.
    explicit_label = re.search(r"[:|\-]\s*$", match.group(0)) is not None
    availability_label = (
        _COLOR_AVAILABILITY_FIELD_PREFIX_PATTERN.search(match.group(0))
        is not None
    )
    if explicit_label or availability_label:
        return False
    preceding_labels = list(
        _DETAIL_FIELD_OR_DESCRIPTION_LABEL_PATTERN.finditer(prefix)
    )
    return bool(
        preceding_labels
        and re.match(
            r"descripci[oó]n(?:\s+comercial)?\s*:",
            preceding_labels[-1].group(0),
            re.IGNORECASE,
        )
    )


def has_redundant_product_color_detail(value: object) -> bool:
    """Whether Detail contains an explicit product-variant color field.

    Color language inside a product Description is descriptive content, not a
    variant selector. Only standalone generic color fields are excluded.
    """
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    return any(
        not _is_description_color_enumeration(text, match)
        for match in _COLOR_FIELD_PATTERN.finditer(text)
    )


def normalize_detail_text(
    value: object,
    *,
    preserve_boundaries: bool = False,
) -> str:
    """Normalize Detail text, optionally preserving source HTML field boundaries.

    The default remains a single-line canonical form for comparisons and policy
    checks. Repair/display paths may request preserved line boundaries so that
    unlabeled source paragraphs are not merged into the preceding attribute.
    """
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    # Remove invisible direction controls that can make source labels/values
    # look misaligned when copied from product pages.
    text = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]", "", text)
    text = _PRICE_INCLUDES_IGV_PATTERN.sub("", text)
    text = re.sub(r"[•▪●‣◦]+", _DETAIL_BOUNDARY, text)
    if preserve_boundaries:
        # Retain explicit source line breaks and the marker used by the HTML
        # extractor, while normalizing whitespace within each individual line.
        text = re.sub(r"[^\S\n]+", " ", text)
        text = re.sub(r"[ \t]*" + re.escape(_DETAIL_BOUNDARY) + r"[ \t]*", "\n", text)
        text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
        text = re.sub(r"\n{2,}", "\n", text).strip()
    else:
        text = _WHITESPACE_PATTERN.sub(" ", text).strip()
    # Protect visible ellipses before repairing doubled sentence punctuation:
    # an ellipsis indicates a clipped source and must remain detectable below.
    ellipsis_placeholder = "\uE000"
    text = re.sub(r"\.{3,}", ellipsis_placeholder, text)
    text = re.sub(r"(?<!\.)\.\.(?!\.)", ".", text)
    text = re.sub(r"([.;|])[ \t]*(?:[.;|][ \t]*)+", r"\1 ", text)
    text = re.sub(r"^[ \t]*[.;|]+[ \t]*|[ \t]*[;|]+[ \t]*$", "", text)
    text = text.replace(ellipsis_placeholder, "...")
    text = re.sub(r"\s+:", ":", text)
    text = _remove_marked_fields(
        text,
        _COLOR_FIELD_PATTERN,
        allow_embedded_label=True,
        preserve_boundaries=preserve_boundaries,
    )
    text = text.replace(_DETAIL_BOUNDARY, "\n" if preserve_boundaries else " ")
    text = re.sub(r"\s+:", ":", text)
    if preserve_boundaries:
        text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
        text = re.sub(r"\n{2,}", "\n", text)
        return text.strip(" \n;")
    # Preserve an explicitly empty terminal source field for future updates.
    return _WHITESPACE_PATTERN.sub(" ", text).strip(" ;")


def is_complete_detail(value: object) -> bool:
    """Whether Detail is complete, allowing an explicitly empty final source field."""
    text = normalize_detail_text(value)
    # Validate without allowed blank logistics labels at the end. The original
    # text remains untouched, so those source labels are preserved in the catalog.
    validation_text = _strip_allowed_empty_trailing_detail_fields(text).rstrip(" ;")
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
    # Empty terminal logistics labels are retained in source text but do not
    # establish technical content by themselves.
    text = _strip_allowed_empty_trailing_detail_fields(text).rstrip(" .;")
    if not text or _NON_TECHNICAL_SECTION_PREFIX_PATTERN.match(text):
        return False
    return _TECHNICAL_DETAIL_PATTERN.search(text) is not None


_SUMMARY_NOISE_PATTERN = re.compile(
    r"^(?:"
    r"precio\b|sku\b|stock\b|categor[ií]as?\b|"
    r"color(?:es)?(?!\s+(?:de(?:\s+(?!producto\b)\w+){1,2}|"
    r"del\s+(?!producto\b)\w+|exterior\b))\b|"
    r"disponible\b|añadir al carrito\b|limpiar\b|"
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
    validation_text = _strip_allowed_empty_trailing_detail_fields(text)
    if (
        not text
        or not validation_text
        or _NON_TECHNICAL_SECTION_PREFIX_PATTERN.match(validation_text)
        or validation_text.endswith((",", ";", ":"))
        or _SUMMARY_NOISE_PATTERN.match(validation_text)
        or _DESCRIPTION_TRUNCATION_PATTERN.search(validation_text)
    ):
        return False
    if has_technical_detail(validation_text):
        return is_complete_detail(text)
    return len(validation_text) >= 20


def is_empty_detail_field_fragment(value: object) -> bool:
    """Recognize an empty source field by its colon/value structure."""
    text = normalize_detail_text(value)
    return bool(text) and _EMPTY_DETAIL_FIELD_FRAGMENT_PATTERN.fullmatch(text) is not None


_SOURCE_FIELD_START_PATTERN = re.compile(
    r"^\s*(?:" + _DETAIL_FIELD_OR_DESCRIPTION_LABEL_PATTERN.pattern + r")",
    re.IGNORECASE,
)
_EMPTY_DETAIL_FIELD_AT_END_PATTERN = re.compile(
    r"(?:^|[.;]\s*)(?:"
    + _DETAIL_FIELD_OR_DESCRIPTION_LABEL_PATTERN.pattern
    + r")\s*$",
    re.IGNORECASE,
)


_SOURCE_FIELD_START_PATTERN = re.compile(
    r"^\s*[^:\r\n]{1,80}:\s*",
    re.IGNORECASE,
)
_EMPTY_DETAIL_FIELD_AT_END_PATTERN = re.compile(
    r"(?:^|[.;]\s*)[^:\r\n]{1,80}:\s*$",
    re.IGNORECASE,
)
_POTENTIAL_SOURCE_LABEL_PATTERN = re.compile(
    r"(?<!\w)([A-ZÁÉÍÓÚÜÑ][\wÁÉÍÓÚÜÑáéíóúüñ()/_-]{0,30}"
    r"(?:\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9()/_-]{1,30}){0,5}):\s*",
    re.UNICODE,
)


def is_detail_grouping_label(value: object) -> bool:
    """Treat an empty field heading as a possible group; its children decide."""
    return is_empty_detail_field_fragment(value)


def _is_grouping_detail_child(parent_label: str, child_source: str) -> bool:
    """A blank heading groups following content when it contains sibling fields."""
    if not str(parent_label or "").strip():
        return False
    return len(_DETAIL_FIELD_BOUNDARY_PATTERN.findall(str(child_source or ""))) >= 2


def _separate_adjacent_empty_detail_field_labels(value: str) -> str:
    """Split a field label from the next label when the first value is empty."""
    matches = list(_POTENTIAL_SOURCE_LABEL_PATTERN.finditer(value))
    split_positions = []
    for previous, current in pairwise(matches):
        between = value[previous.end() : current.start()]
        previous_label = normalize_detail_text(previous.group()).removesuffix(":").strip()
        if (
            all(char.isspace() or char in ".;" for char in between)
            and not _is_grouping_detail_child(previous_label, current.group())
        ):
            split_positions.append(current.start())

    for position in reversed(split_positions):
        before = value[:position].rstrip()
        while before.endswith((".", ";")):
            before = before[:-1].rstrip()
        after = value[position:].lstrip()
        while after.startswith((".", ";")):
            after = after[1:].lstrip()
        value = before + "\n" + after
    return value


def clean_extracted_detail_text(
    value: object,
    *,
    restore_literal_colons: bool = True,
) -> str:
    """Prepare extracted Detail for storage without empty labels or lost split values.

    The raw normalizer intentionally keeps empty labels available to the repair
    audit so it can distinguish an explicitly identified empty field from a
    missing field. This output-only step removes labels with no value and joins
    a label-only paragraph to its following value paragraph when the HTML splits
    them (commonly around <strong>/<b> markup).
    """
    normalized = normalize_detail_text(value, preserve_boundaries=True)
    # Some Bricks templates append the social-sharing label to the same
    # paragraph as the last Detail field. Strip that UI suffix while retaining
    # the original source field, including any incomplete value the page shows.
    normalized = _TRAILING_DETAIL_UI_NOISE_PATTERN.sub("", normalized).rstrip()
    normalized = _separate_adjacent_empty_detail_field_labels(normalized)
    lines = [line.strip() for line in normalized.splitlines()]
    cleaned: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        if not line:
            index += 1
            continue

        if is_empty_detail_field_fragment(line):
            next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""
            if next_line:
                label = line.rstrip().removesuffix(":").strip()
                label_key = normalize_detail_text(label).casefold()
                next_is_field = bool(
                    _SOURCE_FIELD_START_PATTERN.match(next_line)
                )
                if not next_is_field or _is_grouping_detail_child(label_key, next_line):
                    cleaned.append(f"{label}: {next_line}")
                    index += 2
                    continue
            # Empty fields and structural labels without a value are omitted.
            index += 1
            continue

        # A trailing empty field may share a paragraph with populated fields:
        # "Medida: A4. Paquete: 20. Caja:". Remove only the empty suffix.
        while line:
            match = _EMPTY_DETAIL_FIELD_AT_END_PATTERN.search(line)
            if match is None:
                break
            separator = (
                match.group(0)[0]
                if match.group(0) and match.group(0)[0] in ".;"
                else ""
            )
            line = line[: match.start()].rstrip(" .;") + separator

        if (
            cleaned
            and re.search(r"[x\u00d7*]\s*$", cleaned[-1])
            and re.match(r"^\d", line)
        ):
            # A supplier may split the final dimension component into its own
            # paragraph. Join only a numeric continuation after a trailing
            # multiplication separator; unrelated prose/fields stay separate.
            cleaned[-1] = f"{cleaned[-1].rstrip()} {line}"
            index += 1
            continue

        if line:
            cleaned.append(line)
        index += 1

    result = "\n".join(cleaned).strip()
    if restore_literal_colons:
        return restore_literal_detail_colons(result)
    return result


def has_multiple_technical_detail_fields(value: object) -> bool:
    """Require at least two labeled features for lower-priority fallbacks."""
    text = normalize_detail_text(value)
    return len(_DETAIL_FIELD_BOUNDARY_PATTERN.findall(text)) >= 2


_DETAIL_HTML_ALLOWED_TAGS = frozenset({
    "b", "strong", "i", "em", "u", "s", "del", "mark", "span",
    "sub", "sup", "small", "br", "p", "div", "ul", "ol", "li",
    "h1", "h2", "h3", "h4", "h5", "h6",
})
_DETAIL_HTML_REMOVED_TAGS = frozenset({
    "script", "style", "noscript", "template", "button", "form",
    "input", "select", "option", "textarea", "iframe", "svg", "canvas",
    "img", "video", "audio",
})
_DETAIL_HTML_STYLE_VALUES = {
    "text-align": frozenset({"left", "right", "center", "justify", "start", "end"}),
    "font-weight": frozenset({"normal", "bold", "bolder", "lighter", "400", "500", "600", "700", "800", "900"}),
    "font-style": frozenset({"normal", "italic", "oblique"}),
    "text-decoration": frozenset({"none", "underline", "line-through", "overline"}),
}


def _detail_html_alignment(element: Tag) -> str:
    """Find the nearest source paragraph alignment, including inherited wrappers."""
    node: Tag | None = element
    while node is not None:
        style = str(node.get("style", "") or "")
        for declaration in style.split(";"):
            name, separator, value = declaration.partition(":")
            if separator and name.strip().casefold() == "text-align":
                alignment = value.strip().casefold()
                if alignment in _DETAIL_HTML_STYLE_VALUES["text-align"]:
                    return alignment
        alignment = str(node.get("align", "") or "").strip().casefold()
        if alignment in _DETAIL_HTML_STYLE_VALUES["text-align"]:
            return alignment
        parent = node.parent
        node = parent if isinstance(parent, Tag) else None
    return ""


def _sanitize_detail_html_tag(tag: Tag) -> None:
    """Keep only text semantics and safe inline/paragraph presentation attributes."""
    styles: dict[str, str] = {}
    for declaration in str(tag.get("style", "") or "").split(";"):
        name, separator, value = declaration.partition(":")
        key = name.strip().casefold()
        normalized_value = value.strip().casefold()
        if (
            separator
            and key in _DETAIL_HTML_STYLE_VALUES
            and normalized_value in _DETAIL_HTML_STYLE_VALUES[key]
        ):
            styles[key] = normalized_value
    alignment = str(tag.get("align", "") or "").strip().casefold()
    if "text-align" not in styles and alignment in _DETAIL_HTML_STYLE_VALUES["text-align"]:
        styles["text-align"] = alignment
    tag.attrs.clear()
    if styles:
        tag["style"] = "; ".join(f"{name}: {value}" for name, value in styles.items())


def _detail_source_text_key(value: object) -> str:
    """Compare source text without applying exclusions or guessing missing values."""
    text = restore_literal_detail_colons(value)
    text = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]", "", text)
    text = re.sub(r"[•▪●‣◦]+", "\n", text).replace(_DETAIL_BOUNDARY, "\n")
    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ]
    return "\n".join(line for line in lines if line)


def _detail_html_candidates(element: object) -> list[Tag]:
    """Expand a selected Detail source element into its top-level paragraphs."""
    parsed = BeautifulSoup(str(element), "lxml")
    body = parsed.body
    candidates = (
        [child for child in body.contents if isinstance(child, Tag)]
        if body is not None
        else [child for child in parsed.contents if isinstance(child, Tag)]
    )
    structural_tags = ["li", "p", "h1", "h2", "h3", "h4", "h5", "h6"]
    roots: list[Tag] = []
    for candidate in candidates:
        if candidate.name in structural_tags:
            roots.append(candidate)
            continue
        blocks = candidate.find_all(structural_tags)
        top_level = [
            block
            for block in blocks
            if block.find_parent(structural_tags) is None
        ]
        roots.extend(top_level or [candidate])
    return roots


def _is_detail_html_ui_node(tag: Tag) -> bool:
    """Identify interface elements excluded from the source Detail field."""
    classes = {
        str(value).strip().casefold()
        for value in tag.get_attribute_list("class")
    }
    node_id = str(tag.get("id", "") or "").strip().casefold()
    return (
        tag.name in _DETAIL_HTML_REMOVED_TAGS
        or node_id.startswith(("share", "social", "brxe-miyybm"))
        or any("share" in item or "social" in item for item in classes)
    )


def _clean_detail_html_root(root: Tag, inherited_alignment: str) -> bool:
    """Sanitize one candidate paragraph while retaining safe source formatting."""
    for child in list(root.find_all(True)):
        if _is_detail_html_ui_node(child):
            child.decompose()
            continue
        if child.name not in _DETAIL_HTML_ALLOWED_TAGS:
            child.unwrap()
            continue
        _sanitize_detail_html_tag(child)

    if _is_detail_html_ui_node(root):
        return False
    if root.name not in _DETAIL_HTML_ALLOWED_TAGS:
        return False

    _sanitize_detail_html_tag(root)
    _ensure_detail_html_label_spacing(root)
    _split_bold_label_before_nested_span_value(root)
    _unwrap_punctuation_only_detail_emphasis(root)
    style = str(root.get("style", "") or "")
    if inherited_alignment and "text-align:" not in style:
        root["style"] = (f"{style}; " if style else "") + f"text-align: {inherited_alignment}"

    for text_node in list(root.find_all(string=True)):
        cleaned = re.sub(r"[•▪●‣◦]+", " ", str(text_node))
        cleaned = re.sub(
            r"(?:^|[\s\u241e])(?:compartir|share)\s*(?::|\uE001).*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        if cleaned != str(text_node):
            text_node.replace_with(NavigableString(cleaned))

    raw_text = restore_literal_detail_colons(
        extract_detail_text_from_element(
            root,
            ensure_field_label_spacing=False,
        )
    )
    if not raw_text.strip() or re.match(
        r"^\s*(?:compartir|share)\s*:?\s*$",
        raw_text,
        re.IGNORECASE,
    ):
        return False

    # Drop source blocks that contain variant colors removed from the canonical
    # Detail. Separate <li>/<p> blocks are filtered independently; if a source
    # paragraph mixes color and other fields, the caller safely falls back to
    # the plain-text formatter instead of persisting mismatched HTML.
    return not has_redundant_product_color_detail(raw_text)


def _append_detail_html_child(
    fragments: list[list[PageElement]],
    child: PageElement,
    *,
    split_bullets: bool,
) -> None:
    """Append one source node, expanding nested line breaks and bullet markers."""
    if isinstance(child, Tag) and child.name == "br":
        if fragments[-1]:
            fragments.append([])
        return

    if isinstance(child, Tag):
        nested_fragments = _split_detail_html_children(
            child.contents,
            split_bullets=split_bullets,
        )
        for nested_index, nested_content in enumerate(nested_fragments):
            if nested_index and fragments[-1]:
                fragments.append([])
            if not nested_content:
                continue
            cloned = copy(child)
            cloned.clear()
            for nested_child in nested_content:
                cloned.append(nested_child)
            fragments[-1].append(cloned)
        return

    if split_bullets and isinstance(child, NavigableString):
        for piece in re.split(r"([•▪●‣◦])", str(child)):
            if not piece:
                continue
            if re.fullmatch(r"[•▪●‣◦]", piece):
                if fragments[-1]:
                    fragments.append([])
                continue
            fragments[-1].append(NavigableString(piece))
        return

    fragments[-1].append(copy(child))


def _split_detail_html_children(
    children: list[PageElement],
    *,
    split_bullets: bool,
) -> list[list[PageElement]]:
    """Split a source block at visual line breaks without flattening inline markup."""
    fragments: list[list[PageElement]] = [[]]
    for child in children:
        _append_detail_html_child(
            fragments,
            child,
            split_bullets=split_bullets,
        )
    return fragments

def _split_detail_html_source_block(root: Tag) -> list[Tag]:
    """Keep each source line independently filterable while preserving its tags."""
    has_breaks = root.find("br") is not None
    has_bullets = any(
        re.search(r"[•▪●‣◦]", str(text_node))
        for text_node in root.find_all(string=True)
    )
    if not has_breaks and not has_bullets:
        return [root]

    fragments = _split_detail_html_children(
        root.contents,
        split_bullets=has_bullets,
    )
    meaningful_fragments = [
        fragment
        for fragment in fragments
        if "".join(str(node) for node in fragment).strip()
    ]
    if len(meaningful_fragments) <= 1:
        return [root]

    result: list[Tag] = []
    for fragment in meaningful_fragments:
        cloned = copy(root)
        cloned.clear()
        if has_bullets:
            cloned.name = "li"
        for child in fragment:
            cloned.append(child)
        result.append(cloned)
    return result


def _extract_detail_html_roots(elements) -> list[Tag]:
    """Build sanitized source blocks and filter variant-color lines individually."""
    roots: list[Tag] = []
    for element in list(elements or []):
        alignment = _detail_html_alignment(element)
        for source_root in _detail_html_candidates(element):
            for root in _split_detail_html_source_block(source_root):
                if _clean_detail_html_root(root, alignment):
                    roots.append(root)
    return roots


def _merge_detail_html_empty_labels(roots: list[Tag]) -> list[Tag] | None:
    """Join label-only paragraphs to their values without changing alignment."""
    index = 0
    while index < len(roots):
        current = roots[index]
        current_text = restore_literal_detail_colons(
            extract_detail_text_from_element(
                current,
                ensure_field_label_spacing=False,
            )
        )
        normalized_current = normalize_detail_text(current_text)
        if not is_empty_detail_field_fragment(normalized_current):
            index += 1
            continue

        label = normalized_current.removesuffix(":").strip()
        next_index = index + 1
        if next_index >= len(roots):
            roots.pop(index)
            continue

        following = roots[next_index]
        following_text = restore_literal_detail_colons(
            extract_detail_text_from_element(
                following,
                ensure_field_label_spacing=False,
            )
        )
        following_normalized = normalize_detail_text(following_text)
        following_is_field = bool(
            _SOURCE_FIELD_START_PATTERN.match(following_normalized)
        )
        if (
            following_is_field
            and not _is_grouping_detail_child(label, following_normalized)
        ):
            roots.pop(index)
            continue

        current_alignment = _detail_html_alignment(current) or "left"
        following_alignment = _detail_html_alignment(following) or "left"
        if current_alignment != following_alignment:
            # One HTML paragraph cannot faithfully represent two alignments.
            return None

        current.append(NavigableString(" "))
        for child in list(following.contents):
            current.append(child.extract())
        following.decompose()
        roots.pop(next_index)
    return roots


def _detail_html_has_meaningful_style(tag: Tag) -> bool:
    """Return whether sanitized inline styles change the default cell appearance."""
    for declaration in str(tag.get("style", "") or "").split(";"):
        name, separator, value = declaration.partition(":")
        if not separator:
            continue
        key = name.strip().casefold()
        normalized = value.strip().casefold()
        if key == "text-align" and normalized not in {"left", "start"}:
            return True
        if key == "font-weight" and normalized not in {"normal", "400"}:
            return True
        if key == "font-style" and normalized not in {"normal"}:
            return True
        if key == "text-decoration" and normalized not in {"none"}:
            return True
    return False


def _detail_html_has_meaningful_formatting(roots: list[Tag]) -> bool:
    """Do not persist wrapper-only HTML when the plain table renderer is enough."""
    formatting_tags = {
        "b", "strong", "i", "em", "u", "s", "del", "mark",
        "sub", "sup", "small", "ul", "ol",
        "h1", "h2", "h3", "h4", "h5", "h6",
    }
    for root in roots:
        if root.name in formatting_tags:
            return True
        if any(
            tag.name in formatting_tags or _detail_html_has_meaningful_style(tag)
            for tag in root.find_all(True)
        ):
            return True
        if _detail_html_has_meaningful_style(root):
            return True
    return False


def extract_detail_html_from_elements(elements, expected_text: object) -> str:
    """Return safe rich markup only when it represents the exact saved Detail."""
    expected_key = _detail_source_text_key(expected_text)
    if not expected_key:
        return ""

    roots = _extract_detail_html_roots(elements)
    if not roots:
        return ""
    merged_roots = _merge_detail_html_empty_labels(roots)
    if not merged_roots:
        return ""

    raw_parts = [
        restore_literal_detail_colons(
            extract_detail_text_from_element(
                root,
                ensure_field_label_spacing=False,
            )
        )
        for root in merged_roots
    ]
    if _detail_source_text_key(" ␞ ".join(raw_parts)) != expected_key:
        return ""
    if not _detail_html_has_meaningful_formatting(merged_roots):
        return ""
    if all(root.name == "li" for root in merged_roots):
        return "<ul>" + "".join(str(root) for root in merged_roots) + "</ul>"
    return "".join(str(root) for root in merged_roots)


def detail_html_block_alignments(markup: object) -> list[str]:
    """Return visible source-block alignments in their rendered document order."""
    soup = BeautifulSoup(str(markup or ""), "lxml")
    structural_names = ["p", "li", "h1", "h2", "h3", "h4", "h5", "h6"]
    source_blocks = [
        tag
        for tag in soup.find_all(structural_names)
        if tag.find_parent(structural_names) is None
    ]
    if not source_blocks:
        source_blocks = [
            tag
            for tag in soup.find_all("div")
            if tag.find_parent("div") is None
        ]

    alignments: list[str] = []
    for block in source_blocks:
        node: Tag | None = block
        alignment = ""
        while node is not None:
            for declaration in str(node.get("style", "") or "").split(";"):
                name, separator, value = declaration.partition(":")
                if separator and name.strip().casefold() == "text-align":
                    candidate = value.strip().casefold()
                    if candidate in {"left", "right", "center", "justify"}:
                        alignment = candidate
                        break
            if alignment:
                break
            candidate = str(node.get("align", "") or "").strip().casefold()
            if candidate in {"left", "right", "center", "justify"}:
                alignment = candidate
                break
            parent = node.parent
            node = parent if isinstance(parent, Tag) else None
        alignments.append(alignment)
    return alignments


def detail_html_matches_text(fragment: object, expected_text: object) -> bool:
    """Check that a stored rich fragment cannot display text outside canonical Detail."""
    markup = str(fragment or "").strip()
    expected_key = _detail_source_text_key(expected_text)
    if not markup or not expected_key:
        return False
    soup = BeautifulSoup(markup, "lxml")
    for tag in list(soup.find_all(True)):
        if tag.name not in _DETAIL_HTML_ALLOWED_TAGS:
            tag.unwrap()
    actual_key = _detail_source_text_key(
        extract_detail_text_from_element(
            soup,
            ensure_field_label_spacing=False,
        )
    )
    return actual_key == expected_key
