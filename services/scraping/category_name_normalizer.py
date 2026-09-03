import re
import unicodedata

_MOJIBAKE_MARKERS = ("Ã", "Â", "â", "ð", "�")
_COMPARISON_STOPWORDS = {"de"}
# Some legacy catalog text was already partially corrupted, so it cannot be
# repaired by a reversible latin1/UTF-8 round-trip. Keep only the observed
# lossy fragments here; this affects comparison keys, never stored names.
_LOSSY_MOJIBAKE_REPLACEMENTS = {
    "Ãculos": "ículos",
    "Ã©": "é",
}

_CANONICAL_CATEGORIES = {
    "cocina": "Cocina, Mesa y Hogar",
    "mesa": "Cocina, Mesa y Hogar",
    "hogar": "Cocina, Mesa y Hogar",
    "cocina mesa y hogar": "Cocina, Mesa y Hogar",
    "cocina mesa hogar": "Cocina, Mesa y Hogar",
    "mesa y hogar": "Cocina, Mesa y Hogar",
}


def _repair_text(value: str) -> str:
    text = value.strip()
    for _ in range(2):
        for broken, repaired in _LOSSY_MOJIBAKE_REPLACEMENTS.items():
            text = text.replace(broken, repaired)
        if not any(marker in text for marker in _MOJIBAKE_MARKERS):
            break
        try:
            decoded = text.encode("latin1").decode("utf-8")
        except UnicodeError:
            break
        if decoded == text:
            break
        text = decoded
    return text


def normalize_category_name(value: object) -> str:
    """Return a stable comparison key without changing the stored category."""
    if not isinstance(value, str):
        return ""

    text = _repair_text(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.casefold()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    tokens = [token for token in text.split() if token not in _COMPARISON_STOPWORDS]
    return " ".join(tokens)


def canonical_category_name(value: object) -> str:
    """Return the canonical display name for a catalog category."""
    if not isinstance(value, str):
        return ""
    repaired = _repair_text(value)
    key = normalize_category_name(repaired)
    return _CANONICAL_CATEGORIES.get(key, repaired.strip())


def split_category_names(value: object) -> list[str]:
    """Split multi-category values without breaking Cocina, Mesa y Hogar."""
    if not isinstance(value, str):
        return []

    text = _repair_text(value).strip()
    if not text:
        return []

    if normalize_category_name(text) in {
        "cocina mesa y hogar",
        "cocina mesa hogar",
    }:
        return ["Cocina, Mesa y Hogar"]

    result: list[str] = []
    seen: set[str] = set()
    for part in text.split(","):
        category = canonical_category_name(part)
        key = normalize_category_name(category)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(category)
    return result


def merge_category_names(*values: object) -> str:
    """Merge category values using normalized keys and canonical names."""
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        for category in split_category_names(value):
            key = normalize_category_name(category)
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(category)
    return ", ".join(merged)
