import re
import unicodedata

_MOJIBAKE_MARKERS = ("Ã", "Â", "â", "ð", "�")
_COMPARISON_STOPWORDS = {"de"}
# Some legacy catalog text was already partially corrupted, so it cannot be
# repaired by a reversible latin1/UTF-8 round-trip. Keep only the observed
# lossy fragments here; this affects comparison keys, never stored names.
_LOSSY_MOJIBAKE_REPLACEMENTS = {
    "Ãculos": "ículos",
}


def normalize_category_name(value: object) -> str:
    """Return a stable comparison key without changing the stored category."""
    if not isinstance(value, str):
        return ""

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

    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.casefold()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    tokens = [token for token in text.split() if token not in _COMPARISON_STOPWORDS]
    return " ".join(tokens)
