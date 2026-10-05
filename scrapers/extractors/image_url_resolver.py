from __future__ import annotations

import re
from pathlib import PurePosixPath
from urllib.parse import urljoin, urlsplit


BASE_URL = "https://stock.importacionesfacundo.com"

_IMAGE_ATTRIBUTES = (
    "data-full",
    "data-original",
    "data-large-file",
    "data-src",
    "data-lazy-src",
    "data-image",
    "src",
    "content",
)
_SRCSET_ATTRIBUTES = ("data-srcset", "srcset")
_STYLE_URL_RE = re.compile(
    r"url\(\s*["']?([^"')]+)["']?\s*\)",
    re.IGNORECASE,
)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def resolve_image_url(
    soup,
    *,
    code: str = "",
    name: str = "",
    selectors: tuple[str, ...] = (),
) -> str:
    """Resuelve la imagen del producto priorizando la coincidencia exacta por código."""
    elements = _select_elements(soup, selectors)
    candidates: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    sequence = 0

    for element in elements:
        context = " ".join(
            (
                str(element.get("alt") or ""),
                str(element.get("title") or ""),
                str(element.get("aria-label") or ""),
            )
        )

        for attribute_rank, attribute in enumerate(_IMAGE_ATTRIBUTES):
            raw = element.get(attribute)
            if not isinstance(raw, str) or not raw.strip():
                continue
            for url in _expand_image_value(raw, is_srcset=False):
                sequence = _add_candidate(
                    candidates,
                    seen,
                    url,
                    context=context,
                    code=code,
                    name=name,
                    attribute_rank=attribute_rank,
                    sequence=sequence,
                )

        for attribute_rank, attribute in enumerate(_SRCSET_ATTRIBUTES, start=10):
            raw = element.get(attribute)
            if not isinstance(raw, str) or not raw.strip():
                continue
            for url in _expand_image_value(raw, is_srcset=True):
                sequence = _add_candidate(
                    candidates,
                    seen,
                    url,
                    context=context,
                    code=code,
                    name=name,
                    attribute_rank=attribute_rank,
                    sequence=sequence,
                )

        style = element.get("style")
        if isinstance(style, str):
            for url in _STYLE_URL_RE.findall(style):
                sequence = _add_candidate(
                    candidates,
                    seen,
                    url,
                    context=context,
                    code=code,
                    name=name,
                    attribute_rank=20,
                    sequence=sequence,
                )

    if not candidates:
        return ""

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][2]


def _select_elements(soup, selectors: tuple[str, ...]) -> list:
    if not selectors:
        return list(soup.find_all(("img", "source", "meta", "link")))

    result = []
    seen_ids: set[int] = set()
    for selector in selectors:
        for element in soup.select(selector):
            marker = id(element)
            if marker in seen_ids:
                continue
            seen_ids.add(marker)
            result.append(element)
    return result


def _expand_image_value(raw: str, *, is_srcset: bool) -> list[str]:
    if not is_srcset:
        return [raw.strip()]
    return [
        item.strip().split()[0]
        for item in raw.split(",")
        if item.strip()
    ]


def _add_candidate(
    candidates: list[tuple[int, int, str]],
    seen: set[str],
    raw_url: str,
    *,
    context: str,
    code: str,
    name: str,
    attribute_rank: int,
    sequence: int,
) -> int:
    normalized_url = _normalize_image_url(raw_url)
    if not normalized_url or normalized_url.startswith("data:image"):
        return sequence

    key = normalized_url.casefold()
    if key in seen:
        return sequence
    seen.add(key)

    filename = PurePosixPath(urlsplit(normalized_url).path).name
    score = (
        _code_score(normalized_url, filename, code)
        + _context_score(context, code, name)
        + (5 if "/uploads/" in normalized_url.casefold() else 0)
        + max(0, 20 - attribute_rank)
    )
    candidates.append((score, sequence, normalized_url))
    return sequence + 1


def _code_score(url: str, filename: str, code: str) -> int:
    if not code.strip():
        return 0
    if _contains_catalog_code(filename, code):
        return 10000
    if _contains_catalog_code(urlsplit(url).path, code):
        return 7000
    return 0


def _context_score(context: str, code: str, name: str) -> int:
    score = 0
    if code.strip() and _contains_catalog_code(context, code):
        score += 3000

    name_tokens = {
        token
        for token in _NON_ALNUM_RE.split(str(name).casefold())
        if len(token) >= 4
    }
    context_tokens = {
        token
        for token in _NON_ALNUM_RE.split(str(context).casefold())
        if token
    }
    score += min(len(name_tokens.intersection(context_tokens)), 6) * 100
    return score


def _contains_catalog_code(value: str, code: str) -> bool:
    tokens = [
        token
        for token in _NON_ALNUM_RE.split(str(code).casefold())
        if token
    ]
    if not tokens:
        return False

    pattern = r"(?<![a-z0-9])" + r"[^a-z0-9]*".join(
        re.escape(token) for token in tokens
    ) + r"(?![a-z0-9])"
    return re.search(pattern, str(value).casefold()) is not None


def _normalize_image_url(url: str) -> str:
    if not url:
        return ""
    value = url.strip()
    if value.startswith("//"):
        return "https:" + value
    if value.startswith("/"):
        return urljoin(BASE_URL, value)
    if value.startswith(("http://", "https://")):
        return value
    return urljoin(BASE_URL + "/", value)
