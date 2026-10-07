from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, cast

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

    def process(self, products):
        items = list(products or [])
        if not items:
            return []

        current_products = self._load_current_products(items)
        if len(items) == 1 or self.max_workers == 1:
            return [
                self.sync_product(
                    product,
                    current_product=current_products.get(
                        str(product.code).casefold(),
                    ),
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
                            str(product.code).casefold(),
                        ),
                    ),
                    product,
                )
                for product in items
            ]
            return [future.result() for future in futures]

    def sync_product(
        self,
        product,
        old_product=None,
        current_product=None,
    ):
        image_url = str(getattr(product, "image_url", "") or "").strip()
        if not image_url:
            return product

        review_enabled = (
            self.review_service is not None
            and self.image_downloader is not None
        )
        existing = (
            self.image_repository.find(product.code)
            if review_enabled
            else self.image_repository.find(product.code, image_url)
        )

        if existing and review_enabled:
            return self._stage_changed_image(
                product,
                image_url,
                existing,
                current_product,
            )

        if not existing:
            candidates = self._normalized_image_candidates(
                product,
                image_url,
            )
            valid_candidates = [
                candidate
                for candidate in candidates
                if not candidate.get("generic")
            ]
            preferred = valid_candidates[0] if valid_candidates else None
            if (
                ProductImageExtractor.is_generic_asset(image_url)
                and preferred is not None
            ):
                image_url = str(preferred.get("url", "") or "").strip()
                product.image_url = image_url

        old_url = self._get(old_product, "image_url")
        url_changed = bool(old_product and old_url and old_url != image_url)

        if existing and not url_changed:
            product.image_path = existing["image_path"]
            product.image_hash = existing.get("image_hash", "")
            return product

        if url_changed:
            image_data = self.image_manager.process(
                product.code,
                image_url,
                force=True,
            )
        else:
            image_data = self.image_manager.process(
                product.code,
                image_url,
            )

        product.image_path = image_data.get("image_path", "")
        product.image_hash = image_data.get("image_hash", "")
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

            if not current_is_generic:
                trusted = next(
                    (
                        candidate
                        for candidate in candidates
                        if candidate.get("exact_code")
                        and not candidate.get("generic")
                    ),
                    None,
                )
                if trusted is not None:
                    trusted_url = str(trusted.get("url", "") or "").strip()
                    if current_url and trusted_url == current_url:
                        product.image_url = current_url
                        product.image_path = existing["image_path"]
                        product.image_hash = existing.get("image_hash", "")
                        return product
                    image_data = self.image_manager.process(
                        product.code,
                        trusted_url,
                        force=True,
                    )
                    product.image_url = trusted_url
                    product.image_path = image_data.get("image_path", "")
                    product.image_hash = image_data.get("image_hash", "")
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
                            "generic": bool(candidate.get("generic", False)),
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
                    "generic": bool(candidate.get("generic", False)),
                    "source": str(candidate.get("source", "") or ""),
                }
            )
        if candidates:
            return candidates
        return [
            {
                "url": str(image_url or "").strip(),
                "score": 0,
                "exact_code": False,
                "generic": False,
                "source": "",
            }
        ]

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
    def _get(product, field):
        if isinstance(product, dict):
            return product.get(field, "")
        return getattr(product, field, "") if product is not None else ""
