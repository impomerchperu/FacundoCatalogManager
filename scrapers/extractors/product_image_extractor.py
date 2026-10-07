from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit


class ProductImageExtractor:
    """Extrae la imagen principal y alternativas desde HTML WooCommerce."""

    BASE_URL = "https://stock.importacionesfacundo.com"

    _IMAGE_ATTRIBUTES = (
        "data-large_image",
        "data-large-file",
        "data-full",
        "data-original",
        "data-src",
        "data-lazy-src",
        "data-image",
        "src",
    )
    _SRCSET_ATTRIBUTES = ("data-srcset", "srcset")
    _GENERIC_IMAGE_MARKERS = (
        "placeholder",
        "woocommerce-placeholder",
        "site-logo",
        "wordpress-logo",
        "agotado",
        "ausente",
        "no-image",
        "no_image",
        "sin-imagen",
        "sin_imagen",
        "default-image",
        "default_image",
        "logo",
        "brand-",
        "brand_",
        "marca-",
        "marca_",
        "box-product",
        "proximo",
    )

    @classmethod
    def extract(cls, soup, *, code="", name="", base_url="") -> str:
        candidates = cls.extract_candidates(
            soup,
            code=code,
            name=name,
            base_url=base_url,
        )
        if not candidates:
            return ""

        gallery = [
            candidate
            for candidate in candidates
            if candidate.get("gallery")
            and not candidate.get("generic")
        ]
        if gallery:
            return gallery[0]["url"]

        valid = [
            candidate
            for candidate in candidates
            if not candidate.get("generic")
        ]
        return (valid or candidates)[0]["url"]

    @classmethod
    def extract_candidates(
        cls,
        soup,
        *,
        code="",
        name="",
        base_url="",
    ) -> list[dict]:
        name_text = cls._normalize_text(name)
        code_text = str(code or "").strip()
        candidates: list[dict] = []
        seen: set[str] = set()
        sequence = 0

        for element in soup.find_all(("img", "source")):
            parent = element.find_parent("a")
            href = (
                str(parent.get("href", "") or "").strip()
                if parent is not None
                else ""
            )
            href_folded = href.casefold()
            gallery = bool(
                element.find_parent(
                    class_=lambda value: cls._has_gallery_class(value),
                )
            )
            if not gallery and parent is not None:
                gallery = cls._is_image_reference(href_folded)

            alt = cls._normalize_text(
                element.get("alt") or element.get("title") or "",
            )
            context = " ".join(
                part
                for part in (
                    alt,
                    cls._normalize_text(element.get("aria-label") or ""),
                )
                if part
            )

            for attribute in cls._IMAGE_ATTRIBUTES:
                raw = element.get(attribute)
                if not isinstance(raw, str) or not raw.strip():
                    continue
                candidate = cls._build_candidate(
                    raw,
                    base_url=base_url,
                    code=code_text,
                    name=name_text,
                    href=href_folded,
                    context=context,
                    source=f"{element.name}[{attribute}]",
                    width_hint=0,
                    sequence=sequence,
                    gallery=gallery,
                )
                sequence += 1
                cls._append_candidate(candidates, seen, candidate)

            for attribute in cls._SRCSET_ATTRIBUTES:
                raw = element.get(attribute)
                if not isinstance(raw, str) or not raw.strip():
                    continue
                for raw_url, width_hint in cls._srcset_items(raw):
                    candidate = cls._build_candidate(
                        raw_url,
                        base_url=base_url,
                        code=code_text,
                        name=name_text,
                        href=href_folded,
                        context=context,
                        source=f"{element.name}[{attribute}]",
                        width_hint=width_hint,
                        sequence=sequence,
                        gallery=gallery,
                    )
                    sequence += 1
                    cls._append_candidate(candidates, seen, candidate)

            if parent is not None:
                linked_url = href.strip()
                if (
                    linked_url
                    and not linked_url.casefold().startswith(
                        ("javascript:", "#"),
                    )
                    and cls._looks_like_image_url(linked_url)
                ):
                    candidate = cls._build_candidate(
                        linked_url,
                        base_url=base_url,
                        code=code_text,
                        name=name_text,
                        href=href_folded,
                        context=context,
                        source=f"{parent.name}[href]",
                        width_hint=0,
                        sequence=sequence,
                        gallery=gallery,
                    )
                    sequence += 1
                    cls._append_candidate(candidates, seen, candidate)

        candidates.sort(
            key=lambda item: (
                -int(bool(item.get("gallery"))),
                bool(item.get("generic")),
                item["sequence"] if item.get("gallery") else -item["score"],
            ),
        )
        valid = [
            candidate
            for candidate in candidates
            if not candidate.get("generic")
        ]
        invalid = [
            candidate
            for candidate in candidates
            if candidate.get("generic")
        ]
        ordered = valid + invalid
        for rank, candidate in enumerate(ordered, start=1):
            candidate["rank"] = rank
        return ordered

    @classmethod
    def _build_candidate(  # noqa: PLR0912
        cls,
        raw_url,
        *,
        base_url,
        code,
        name,
        href,
        context,
        source,
        width_hint,
        sequence,
        gallery,
    ) -> dict | None:
        normalized_url = cls._normalize_url(raw_url, base_url=base_url)
        if not normalized_url or normalized_url.startswith("data:image"):
            return None

        path = urlsplit(normalized_url).path
        filename = path.rsplit("/", 1)[-1]
        exact_filename = cls._contains_catalog_code(filename, code)
        exact_path = cls._contains_catalog_code(path, code)

        score = 0
        if gallery:
            score += 300
        if source.endswith("[data-large_image]"):
            score += 120
        elif source.endswith("[data-full]"):
            score += 100
        if exact_filename:
            score += 1000
        elif exact_path:
            score += 700
        if "/producto/" in href:
            score += 45
        if "/wp-content/uploads/" in normalized_url.casefold():
            score += 10
        if name and context:
            if name == context:
                score += 20
            elif name in context:
                score += 10
        generic = cls._looks_generic(filename, context)
        if generic:
            score -= 100
        if width_hint:
            score += min(max(width_hint // 300, 0), 5)

        return {
            "url": normalized_url,
            "score": score,
            "exact_code": bool(exact_filename or exact_path),
            "generic": generic,
            "gallery": gallery,
            "source": source,
            "sequence": sequence,
        }

    @staticmethod
    def _contains_catalog_code(text, code) -> bool:
        normalized_code = re.sub(r"[^a-z0-9]+", "", str(code or "").casefold())
        normalized_text = re.sub(r"[^a-z0-9]+", "", str(text or "").casefold())
        return bool(normalized_code and normalized_code in normalized_text)

    @staticmethod
    def _append_candidate(candidates, seen, candidate) -> None:
        if candidate is None:
            return
        key = candidate["url"].casefold()
        if key in seen:
            return
        seen.add(key)
        candidates.append(candidate)

    @staticmethod
    def _srcset_items(raw: str) -> list[tuple[str, int]]:
        items: list[tuple[str, int]] = []
        for item in raw.split(","):
            parts = item.strip().split()
            if not parts:
                continue
            width = 0
            if len(parts) > 1 and parts[1].endswith("w"):
                try:
                    width = int(parts[1][:-1])
                except ValueError:
                    width = 0
            items.append((parts[0], width))
        return items

    @staticmethod
    def _normalize_url(url, *, base_url):
        value = str(url or "").strip()
        if not value or value.startswith("data:image"):
            return ""
        if value.startswith("//"):
            value = "https:" + value
        elif base_url:
            value = urljoin(base_url.rstrip("/") + "/", value)
        return re.sub(
            r"-\d+x\d+(?=(?:\.[A-Za-z0-9]+)(?:[?#]|$))",
            "",
            value,
            flags=re.IGNORECASE,
        )

    @staticmethod
    def _normalize_text(value):
        return re.sub(r"\s+", " ", str(value or "")).strip().casefold()

    @classmethod
    def is_generic_asset(cls, value) -> bool:
        text = str(value or "").casefold()
        filename = text.rsplit("/", 1)[-1].split("?", 1)[0]
        return any(
            marker in f"{filename} {text}"
            for marker in cls._GENERIC_IMAGE_MARKERS
        )

    @classmethod
    def _looks_generic(cls, filename, context="") -> bool:
        text = f"{filename} {context}".casefold()
        if context in {"logo", "site logo", "wordpress", "ausente", "sin imagen"}:
            return True
        return any(marker in text for marker in cls._GENERIC_IMAGE_MARKERS)

    @staticmethod
    def _has_gallery_class(value) -> bool:
        if isinstance(value, str):
            values = value.split()
        elif isinstance(value, (list, tuple, set)):
            values = [str(item) for item in value]
        else:
            return False
        return any(
            "woocommerce-product-gallery" in item.casefold()
            or item.casefold() in {"product-gallery", "product-images"}
            for item in values
        )

    @staticmethod
    def _is_image_reference(value: str) -> bool:
        folded = str(value or "").casefold()
        return any(
            token in folded
            for token in (
                "/wp-content/uploads/",
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
                ".gif",
            )
        )

    @staticmethod
    def _looks_like_image_url(value: str) -> bool:
        path = urlsplit(str(value or "")).path.casefold()
        return path.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))
