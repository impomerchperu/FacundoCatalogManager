from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import partial
from typing import Any, cast
from urllib.parse import urlsplit

import requests

from scrapers.extractors.product_image_extractor import ProductImageExtractor
from scrapers.images.image_repository import ImageRepository
from scrapers.images.safe_image_manager import SafeImageManager


class ImageSync:
    """Sincronización incremental de imágenes por código y URL."""

    def __init__(
        self,
        image_manager=None,
        image_repository=None,
        max_workers=8,
        review_service: Any = None,
        image_downloader: Any = None,
    ):
        self.image_manager = image_manager or SafeImageManager()
        self.image_repository = image_repository or ImageRepository()
        self.review_service = review_service
        self.image_downloader = image_downloader
        self.max_workers = int(max_workers)
        if self.max_workers <= 0:
            raise ValueError("max_workers debe ser mayor que cero.")

    def synchronize(self, product, old_product=None):
        result = self.sync_product(product, old_product)
        return {
            "image_path": getattr(result, "image_path", ""),
            "image_hash": getattr(result, "image_hash", ""),
        }

    def process(self, products, *, refresh_remote_images: bool = False):
        items = list(products or [])
        if not items:
            return []

        current_products = self._load_current_products(items)
        if len(items) == 1 or self.max_workers == 1:
            return [
                self.sync_product(
                    product,
                    current_product=current_products.get(
                        str(product.code).strip().casefold(),
                    ),
                    refresh_remote_images=refresh_remote_images,
                )
                for product in items
            ]

        worker_count = min(self.max_workers, len(items))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(
                    partial(
                        self.sync_product,
                        current_product=current_products.get(
                            str(product.code).strip().casefold(),
                        ),
                        refresh_remote_images=refresh_remote_images,
                    ),
                    product,
                )
                for product in items
            ]
            return [future.result() for future in futures]

    def sync_product(  # noqa: PLR0912
        self,
        product,
        old_product=None,
        current_product=None,
        refresh_remote_images: bool = False,
    ):
        image_url = str(getattr(product, "image_url", "") or "").strip()
        if not image_url:
            return product

        current_product = current_product or old_product
        if old_product is None:
            old_product = current_product
        review_enabled = (
            self.review_service is not None
            and self.image_downloader is not None
        )

        # When SQLite has an active path, inspect that exact file before looking
        # for any legacy/sibling image. A lexicographic directory fallback could
        # otherwise resurrect an obsolete version of the product image.
        db_path = str(self._get(current_product, "image_path") or "").strip()
        path_finder = getattr(self.image_repository, "find_path", None)
        if db_path and callable(path_finder):
            existing = self._as_image_record(path_finder(db_path))
        elif db_path:
            existing = self._as_image_record(
                self.image_repository.find(product.code)
            )
        else:
            existing = self._as_image_record(
                self.image_repository.find(product.code)
                if review_enabled
                else self.image_repository.find(product.code, image_url)
            )

        candidates = self._normalized_image_candidates(product, image_url)

        if existing and not review_enabled:
            current_url = str(self._get(current_product, "image_url") or "").strip()
            current_hash = str(self._get(current_product, "image_hash") or "").strip()
            same_source = not current_url or self._urls_equivalent(
                current_url, image_url
            )
            hash_matches = (
                not current_hash
                or str(existing.get("image_hash", "") or "") == current_hash
            )
            if same_source and hash_matches:
                product.image_url = image_url
                product.image_path = str(existing.get("image_path", "") or "")
                product.image_hash = str(existing.get("image_hash", "") or "")
                product.image_etag = str(
                    self._get(current_product, "image_etag") or ""
                )
                product.image_last_modified = str(
                    self._get(current_product, "image_last_modified") or ""
                )
                product.image_checked_at = str(
                    self._get(current_product, "image_checked_at") or ""
                )
                return product

        if existing and review_enabled:
            if self._has_authoritative_candidate(candidates, image_url):
                image_data = self._process_image(
                    product.code, image_url, force=True
                )
                if image_data.get("image_path") and image_data.get("image_hash"):
                    return self._apply_image_data(product, image_url, image_data)

            current_url = str(self._get(current_product, "image_url") or "").strip()
            current_is_generic = (
                ProductImageExtractor.is_generic_asset(current_url)
                or ProductImageExtractor.is_generic_asset(
                    str(existing.get("image_path", "") or ""),
                )
            )
            same_source = bool(
                current_url and self._urls_equivalent(current_url, image_url)
            )
            if same_source and not current_is_generic:
                if (
                    not refresh_remote_images
                    and self._cache_is_fresh(current_product)
                    and str(existing.get("image_hash", "") or "")
                    == str(self._get(current_product, "image_hash") or "")
                ):
                    return self._preserve_current_image(
                        product, current_product, existing, image_url
                    )

                revalidate = getattr(self.image_downloader, "revalidate_primary", None)
                if callable(revalidate):
                    try:
                        result = self._as_image_record(revalidate(
                            str(product.code),
                            image_url,
                            current_path=str(existing.get("image_path", "") or ""),
                            current_hash=str(self._get(current_product, "image_hash") or ""),
                            etag=str(self._get(current_product, "image_etag") or ""),
                            last_modified=str(
                                self._get(current_product, "image_last_modified") or ""
                            ),
                        ))
                    except (OSError, ValueError, RuntimeError, requests.exceptions.RequestException):
                        return self._preserve_current_image(
                            product, current_product, existing, current_url
                        )
                    if result and result.get("image_path") and result.get("image_hash"):
                        return self._apply_image_data(product, image_url, result)
                    return self._preserve_current_image(
                        product, current_product, existing, current_url
                    )

                # Lightweight test doubles/legacy integrations without HTTP
                # revalidation keep the currently accepted image unchanged.
                return self._preserve_current_image(
                    product, current_product, existing, current_url
                )

            return self._stage_changed_image(
                product,
                image_url,
                existing,
                current_product,
            )

        if not existing:
            valid_candidates = [
                candidate for candidate in candidates
                if not candidate.get("generic")
            ]
            preferred = valid_candidates[0] if valid_candidates else None
            if ProductImageExtractor.is_generic_asset(image_url) and preferred:
                image_url = str(preferred.get("url", "") or "").strip()
                product.image_url = image_url

        old_url = str(self._get(old_product, "image_url") or "").strip()
        url_changed = bool(
            old_url and not self._urls_equivalent(old_url, image_url)
        )

        # On a new local object or a changed accepted/authoritative source, force
        # a real download. The downloader publishes new bytes to a versioned file
        # rather than overwriting whatever SQLite may still reference.
        current_hash = str(self._get(current_product, "image_hash") or "").strip()
        local_hash = str((existing or {}).get("image_hash", "") or "").strip()
        local_hash_mismatch = bool(current_hash and local_hash and current_hash != local_hash)
        should_download = not existing or url_changed or local_hash_mismatch
        image_data = self._process_image(
            product.code, image_url, force=should_download
        )
        if image_data.get("image_path") and image_data.get("image_hash"):
            return self._apply_image_data(product, image_url, image_data)

        if existing and current_product is not None:
            return self._preserve_current_image(
                product,
                current_product,
                existing,
                str(self._get(current_product, "image_url") or ""),
            )

        product.image_path = ""
        product.image_hash = ""
        return product

    def _process_image(
        self, code: str, url: str, *, force: bool
    ) -> dict[str, Any]:
        """Keep compatibility with injected legacy managers lacking force=... ."""
        if not force:
            return cast(dict[str, Any], self.image_manager.process(code, url))
        try:
            return cast(
                dict[str, Any], self.image_manager.process(code, url, force=True)
            )
        except TypeError as error:
            if "force" not in str(error) or "keyword" not in str(error):
                raise
            return cast(dict[str, Any], self.image_manager.process(code, url))

    @staticmethod
    def _cache_is_fresh(current_product, *, max_age_seconds: int = 86400) -> bool:
        value = str(ImageSync._get(current_product, "image_checked_at") or "").strip()
        if not value:
            return False
        try:
            checked_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if checked_at.tzinfo is None:
                checked_at = checked_at.replace(tzinfo=timezone.utc)
        except ValueError:
            return False
        age = (datetime.now(timezone.utc) - checked_at.astimezone(timezone.utc)).total_seconds()
        return 0 <= age < max_age_seconds

    @staticmethod
    def _apply_image_data(
        product, image_url: str, image_data: dict[str, Any]
    ):
        product.image_url = image_url
        product.image_path = str(image_data.get("image_path", "") or "")
        product.image_hash = str(image_data.get("image_hash", "") or "")
        product.image_etag = str(image_data.get("image_etag", "") or "")
        product.image_last_modified = str(
            image_data.get("image_last_modified", "") or ""
        )
        product.image_checked_at = str(
            image_data.get("image_checked_at", "") or ""
        )
        return product

    @staticmethod
    def _preserve_current_image(product, current_product, existing, source_url: str):
        product.image_url = source_url
        # The repository validates the actual bytes; use their hash rather than
        # preserving a stale DB hash after an interrupted/older write.
        product.image_path = str(
            existing.get("image_path", "")
            or ImageSync._get(current_product, "image_path")
            or ""
        )
        product.image_hash = str(
            existing.get("image_hash", "")
            or ImageSync._get(current_product, "image_hash")
            or ""
        )
        product.image_etag = str(ImageSync._get(current_product, "image_etag") or "")
        product.image_last_modified = str(
            ImageSync._get(current_product, "image_last_modified") or ""
        )
        product.image_checked_at = str(
            ImageSync._get(current_product, "image_checked_at") or ""
        )
        return product

    def _stage_changed_image(  # noqa: PLR0912
        self,
        product,
        image_url,
        existing,
        current_product=None,
    ):
        try:
            current_url = str(
                getattr(current_product, "image_url", "") or ""
            ).strip()
            current_is_generic = (
                ProductImageExtractor.is_generic_asset(current_url)
                or ProductImageExtractor.is_generic_asset(
                    str(existing.get("image_path", "") or ""),
                )
            )
            candidates = self._normalized_image_candidates(product, image_url)

            if current_url and current_url == image_url and not current_is_generic:
                product.image_url = current_url
                product.image_path = existing["image_path"]
                product.image_hash = existing.get("image_hash", "")
                return product

            review_candidates = [
                candidate
                for candidate in candidates
                if not candidate.get("generic")
            ]
            if not review_candidates:
                review_candidates = candidates

            stage_candidates = getattr(
                self.review_service,
                "stage_candidates",
                None,
            )
            if callable(stage_candidates):
                staged_options = cast(
                    list[dict[str, Any]],
                    stage_candidates(
                        self.image_downloader,
                        str(product.code),
                        review_candidates,
                        max_candidates=6,
                    ),
                )
            else:
                staged_options = []
                for candidate in review_candidates[:6]:
                    url = str(candidate.get("url", "") or "").strip()
                    if not url:
                        continue
                    staged = cast(
                        dict[str, Any],
                        self.review_service.stage_candidate(
                            self.image_downloader,
                            str(product.code),
                            url,
                        ),
                    )
                    staged_options.append(
                        {
                            "url": url,
                            "path": str(staged.get("image_path", "") or ""),
                            "hash": str(staged.get("image_hash", "") or ""),
                            "score": int(candidate.get("score", 0) or 0),
                            "exact_code": bool(candidate.get("exact_code", False)),
                            "generic": bool(candidate.get("generic", False))
                    or ProductImageExtractor.is_generic_asset(url),
                            "source": str(candidate.get("source", "") or ""),
                        }
                    )

            existing_hash = str(existing.get("image_hash", "") or "")
            if current_is_generic:
                observed_options = staged_options
            else:
                observed_options = [
                    option
                    for option in staged_options
                    if str(option.get("hash", "") or "")
                    and str(option.get("hash", "")) != existing_hash
                ]
                discarded = [
                    option
                    for option in staged_options
                    if option not in observed_options
                ]
                self._discard_staged_options(discarded)

            if not observed_options:
                if current_is_generic:
                    review = self.review_service.register_candidate(
                        code=str(product.code),
                        product_name=str(getattr(product, "name", "") or ""),
                        current_path=str(existing.get("image_path", "") or ""),
                        current_hash=existing_hash,
                        current_url=current_url,
                        candidate_path="",
                        candidate_hash="",
                        candidate_url="",
                        candidate_options=[],
                        allow_manual_only=True,
                    )
                    if review is not None:
                        product.image_url = current_url
                        product.image_path = existing["image_path"]
                        product.image_hash = existing_hash
                    else:
                        product.image_url = current_url
                        product.image_path = existing["image_path"]
                        product.image_hash = existing_hash
                    return product

                product.image_url = current_url
                product.image_path = existing["image_path"]
                product.image_hash = existing_hash
                return product

            primary = observed_options[0]
            review = self.review_service.register_candidate(
                code=str(product.code),
                product_name=str(getattr(product, "name", "") or ""),
                current_path=str(existing.get("image_path", "") or ""),
                current_hash=existing_hash,
                current_url=current_url,
                candidate_path=str(primary.get("path", "") or ""),
                candidate_hash=str(primary.get("hash", "") or ""),
                candidate_url=str(primary.get("url", "") or ""),
                candidate_options=observed_options,
                allow_manual_only=False,
            )
            if review is None:
                self._discard_staged_options(observed_options)

            product.image_url = current_url
            product.image_path = existing["image_path"]
            product.image_hash = existing_hash
        except (OSError, ValueError, RuntimeError):
            product.image_url = str(
                getattr(current_product, "image_url", "") or ""
            )
            product.image_path = existing["image_path"]
            product.image_hash = existing.get("image_hash", "")
        return product

    @staticmethod
    def _normalized_image_candidates(product, image_url):
        candidates = []
        for candidate in list(getattr(product, "image_candidates", []) or []):
            url = str(candidate.get("url", "") or "").strip()
            if not url:
                continue
            candidates.append(
                {
                    "url": url,
                    "score": int(candidate.get("score", 0) or 0),
                    "exact_code": bool(candidate.get("exact_code", False)),
                    "generic": bool(candidate.get("generic", False))
                    or ProductImageExtractor.is_generic_asset(url),
                    "source": str(candidate.get("source", "") or ""),
                    "authoritative": bool(candidate.get("authoritative", False)),
                }
            )
        if candidates:
            return candidates
        return [
            {
                "url": str(image_url or "").strip(),
                "score": 0,
                "exact_code": False,
                "generic": ProductImageExtractor.is_generic_asset(
                    str(image_url or "").strip()
                ),
                "source": "",
                "authoritative": False,
            }
        ]

    @staticmethod
    def _urls_equivalent(left: str, right: str) -> bool:
        """Compare URL identity without case-folding a case-sensitive path/query."""
        try:
            first = urlsplit(str(left or "").strip())
            second = urlsplit(str(right or "").strip())
            if (
                first.scheme.lower() != second.scheme.lower()
                or (first.hostname or "").casefold()
                != (second.hostname or "").casefold()
                or first.path != second.path
                or first.query != second.query
                or first.username != second.username
                or first.password != second.password
            ):
                return False

            def effective_port(parsed):
                if parsed.port is not None:
                    return parsed.port
                return 443 if parsed.scheme.lower() == "https" else 80

            return effective_port(first) == effective_port(second)
        except ValueError:
            return str(left or "").strip() == str(right or "").strip()

    @staticmethod
    def _has_authoritative_candidate(candidates, image_url: str) -> bool:
        normalized_url = str(image_url or "").strip()
        if not normalized_url:
            return False
        return any(
            bool(candidate.get("authoritative"))
            and not bool(candidate.get("generic"))
            and ImageSync._urls_equivalent(
                str(candidate.get("url", "") or "").strip(),
                normalized_url,
            )
            for candidate in candidates
        )

    def _discard_staged_options(self, options) -> None:
        for option in list(options or []):
            self.review_service.discard_staged(
                str(option.get("path", "") or "")
            )


    def _load_current_products(self, products) -> dict[str, Any]:
        if self.review_service is None:
            return {}

        repository = getattr(self.review_service, "repository", None)
        if repository is None:
            return {}

        codes = [
            str(getattr(product, "code", "") or "").strip()
            for product in products
            if str(getattr(product, "code", "") or "").strip()
        ]
        getter = getattr(repository, "get_by_codes", None)
        if callable(getter):
            loaded = getter(codes) or {}
            if not isinstance(loaded, dict):
                return {}
            return {
                str(code).strip().casefold(): product
                for code, product in loaded.items()
                if str(code).strip()
            }

        return {
            code.casefold(): repository.get_by_code(code)
            for code in codes
        }

    @staticmethod
    def _as_image_record(value: object) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        return cast(dict[str, Any], value)

    @staticmethod
    def _get(product, field):
        if isinstance(product, dict):
            return product.get(field, "")
        return getattr(product, field, "") if product is not None else ""
