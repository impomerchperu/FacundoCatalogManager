from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress
from typing import Any, ClassVar, cast

from bs4 import BeautifulSoup

from config.runtime_paths import resolve_data_path
from scrapers.extractors.product_image_extractor import ProductImageExtractor
from scrapers.images.image_downloader import ImageDownloader
from scrapers.images.image_paths import IMAGE_PRODUCTS_DIR
from scrapers.images.product_image_storage import store_image_in_product_group
from scrapers.images.visual_duplicate_detector import (
    VisualImageFingerprint,
    build_visual_fingerprint,
    is_generated_resolution_duplicate,
)


class ProductGallerySyncService:
    """Obtiene y descarga galerías de producto en segundo plano del pipeline."""

    # FB-4047 had a gallery reference removed because its remote filename
    # looked suspicious. A direct, decoded download proved it is a light-bulb
    # image (SHA-256 176a9b93...); the earlier product-page HTML also listed it.
    # Keep the narrow recovery explicit until the gallery is fully reconciled.
    FORCE_LIVE_GALLERY_REVALIDATION_CODES = frozenset({"FB-4047"})
    VERIFIED_GALLERY_RECOVERY_URLS: ClassVar[dict[str, tuple[str, ...]]] = {
        "FB-4047": (
            "https://stock.importacionesfacundo.com/wp-content/uploads/2025/08/"
            "MEZCLADOR-CAMION-copia.webp",
        )
    }
    VERIFIED_GALLERY_RECOVERY_SHA256_BY_URL: ClassVar[dict[str, str]] = {
        (
            "https://stock.importacionesfacundo.com/wp-content/uploads/2025/08/"
            "mezclador-camion-copia.webp"
        ): "176a9b93be51c07a3b062e72a4a2a2062f11de56d9256c1b4e8f1ba100270f83"
    }

    def __init__(
        self,
        *,
        browser,
        product_extractor,
        image_downloader,
        review_service=None,
        max_workers=4,
        max_candidates=6,
        refresh_existing=True,
    ) -> None:
        self.browser = browser
        self.product_extractor = product_extractor
        self.image_downloader = image_downloader
        self.review_service = review_service
        self.max_workers = max(1, int(max_workers))
        self.max_candidates = max(1, int(max_candidates))
        self.refresh_existing = bool(refresh_existing)

    def sync_products(
        self,
        products: list[Any],
        progress_callback=None,
    ) -> list[Any]:
        items = list(products or [])
        if not items:
            return items

        existing_by_code = self._load_existing_products(items)
        worker_count = min(self.max_workers, len(items))
        completed = 0
        results = list(items)
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    self._sync_product,
                    product,
                    existing_by_code.get(
                        str(getattr(product, "code", "") or "").strip().casefold()
                    ),
                ): index
                for index, product in enumerate(items)
            }
            for future in as_completed(futures):
                index = futures[future]
                product = items[index]
                try:
                    results[index] = future.result()
                except Exception:  # noqa: BLE001
                    results[index] = product
                completed += 1
                if callable(progress_callback):
                    progress_callback(completed, len(items))
        return results

    def _sync_product(self, product, existing=None):  # noqa: PLR0912
        initial_image_state = {
            field: str(getattr(product, field, "") or "")
            for field in ("image_url", "image_path", "image_hash")
        }
        existing_gallery = [
            dict(image)
            for image in list(getattr(existing, "gallery_images", []) or [])
            if isinstance(image, dict)
        ]
        products_root = resolve_data_path(IMAGE_PRODUCTS_DIR)
        product_code = ImageDownloader._safe_code(str(product.code))
        product_dir = products_root / product_code
        product_dir.mkdir(parents=True, exist_ok=True)
        primary_url_before_gallery_sync = str(
            getattr(product, "image_url", "") or ""
        ).strip()
        primary_path = self._canonicalize_primary(
            product,
            existing_gallery,
            products_root,
        )

        candidates = self._candidate_source(product, existing)
        primary_url_after_gallery_sync = str(
            getattr(product, "image_url", "") or ""
        ).strip()
        if (
            primary_url_after_gallery_sync.casefold()
            != primary_url_before_gallery_sync.casefold()
        ):
            # The detail page can correct a category-card image. Do not reuse
            # that card's bytes for the newly selected gallery primary.
            product.image_path = ""
            product.image_hash = ""
            primary_path = self._canonicalize_primary(
                product,
                existing_gallery,
                products_root,
            )
        if not candidates:
            product.gallery_images = self._canonicalize_existing_gallery(
                product,
                existing_gallery,
                primary_path,
                products_root,
            )
            return product

        normalized = self._normalize_candidates(candidates)
        primary_url = str(getattr(product, "image_url", "") or "").strip()
        if primary_url:
            primary_key = primary_url.casefold()
            primary_candidate = next(
                (
                    candidate
                    for candidate in normalized
                    if str(candidate.get("url", "") or "").strip().casefold()
                    == primary_key
                ),
                {
                    "url": primary_url,
                    "score": 0,
                    "exact_code": False,
                    "generic": False,
                    "gallery": True,
                    "source": "primary",
                },
            )
            normalized = [primary_candidate] + [
                candidate
                for candidate in normalized
                if str(candidate.get("url", "") or "").strip().casefold()
                != primary_key
            ]

        if not normalized:
            product.gallery_images = self._canonicalize_existing_gallery(
                product,
                existing_gallery,
                primary_path,
                products_root,
            )
            return product

        existing_by_url = {
            str(item.get("url", "") or "").strip().casefold(): item
            for item in existing_gallery
            if str(item.get("url", "") or "").strip()
        }
        seen_urls: set[str] = set()
        seen_hashes: set[str] = set()
        gallery_images: list[dict[str, Any]] = []
        visual_fingerprints: list[VisualImageFingerprint | None] = []
        new_options: list[dict[str, object]] = []
        gallery_complete = True
        candidate_by_url = {
            str(candidate.get("url", "") or "").strip().casefold(): candidate
            for candidate in normalized
            if str(candidate.get("url", "") or "").strip()
        }
        staging_dir = product_dir / ".staging"
        staging_dir.mkdir(parents=True, exist_ok=True)

        try:
            for candidate in normalized:
                url = str(candidate.get("url", "") or "").strip()
                key = url.casefold()
                if not url or key in seen_urls:
                    continue

                is_primary = bool(primary_url and key == primary_url.casefold())
                existing_item = existing_by_url.get(key)
                recovery_hash = self._verified_gallery_recovery_hash(
                    product.code,
                    url,
                )
                path = None
                if is_primary and primary_path is not None and primary_path.is_file():
                    path = primary_path
                elif isinstance(existing_item, dict) and not recovery_hash:
                    raw_path = str(
                        existing_item.get(
                            "image_path",
                            existing_item.get("path", ""),
                        )
                        or ""
                    ).strip()
                    if raw_path:
                        candidate_path = resolve_data_path(raw_path)
                        if candidate_path.is_file():
                            stored_path, _ = store_image_in_product_group(
                                product.code,
                                candidate_path,
                                len(gallery_images) + 1,
                                root=products_root,
                            )
                            if stored_path:
                                path = resolve_data_path(stored_path)

                downloaded_path = None
                if path is None:
                    try:
                        staged_path = self.image_downloader.download_gallery(
                            str(product.code),
                            url,
                            len(gallery_images) + 1,
                            staging_dir,
                        )
                        downloaded_path = resolve_data_path(staged_path)
                        if downloaded_path.is_file():
                            if (
                                recovery_hash
                                and ImageDownloader.hash_file(downloaded_path).casefold()
                                != recovery_hash
                            ):
                                # A URL whose bytes changed is not the asset that
                                # was visually approved. Preserve the prior gallery.
                                gallery_complete = False
                                continue
                            staged_fingerprint = build_visual_fingerprint(
                                downloaded_path,
                                url,
                            )
                            duplicate_index = next(
                                (
                                    index
                                    for index, accepted in enumerate(visual_fingerprints)
                                    if is_generated_resolution_duplicate(
                                        accepted,
                                        staged_fingerprint,
                                    )
                                ),
                                None,
                            )
                            if duplicate_index is not None:
                                accepted_fingerprint = visual_fingerprints[duplicate_index]
                                if (
                                    staged_fingerprint is not None
                                    and accepted_fingerprint is not None
                                    and staged_fingerprint.area
                                    <= accepted_fingerprint.area
                                ):
                                    # Do not even publish a redundant generated size
                                    # into canonical storage; the staging file is
                                    # removed by the finally block below.
                                    continue

                            stored_path, _ = store_image_in_product_group(
                                product.code,
                                downloaded_path,
                                len(gallery_images) + 1,
                                root=products_root,
                            )
                            if stored_path:
                                path = resolve_data_path(stored_path)
                    except Exception:  # noqa: BLE001
                        gallery_complete = False
                        continue
                    finally:
                        if downloaded_path is not None:
                            with suppress(OSError):
                                downloaded_path.unlink(missing_ok=True)

                if path is None or not path.is_file():
                    gallery_complete = False
                    continue

                image_hash = ImageDownloader.hash_file(path)
                if image_hash and image_hash in seen_hashes:
                    continue

                item = {
                    "url": url,
                    "image_path": str(path.relative_to(resolve_data_path(".")))
                    .replace("\\", "/")
                    if path.is_relative_to(resolve_data_path("."))
                    else str(path).replace("\\", "/"),
                    "image_hash": image_hash,
                    "position": len(gallery_images) + 1,
                    "source": (
                        str(existing_item.get("source", "woocommerce-gallery") or "woocommerce-gallery")
                        if isinstance(existing_item, dict)
                        else str(candidate.get("source", "woocommerce-gallery") or "woocommerce-gallery")
                    ),
                }
                fingerprint = build_visual_fingerprint(path, url)
                duplicate_index = next(
                    (
                        index
                        for index, accepted in enumerate(visual_fingerprints)
                        if is_generated_resolution_duplicate(accepted, fingerprint)
                    ),
                    None,
                )
                if duplicate_index is not None:
                    accepted_fingerprint = visual_fingerprints[duplicate_index]
                    if (
                        fingerprint is not None
                        and accepted_fingerprint is not None
                        and fingerprint.area > accepted_fingerprint.area
                    ):
                        previous = gallery_images[duplicate_index]
                        item["position"] = int(previous.get("position", duplicate_index + 1))
                        gallery_images[duplicate_index] = item
                        visual_fingerprints[duplicate_index] = fingerprint
                        previous_url = str(previous.get("url", "") or "").strip().casefold()
                        previous_hash = str(previous.get("image_hash", "") or "").strip()
                        seen_urls.discard(previous_url)
                        seen_urls.add(key)
                        if previous_hash:
                            seen_hashes.discard(previous_hash)
                        if image_hash:
                            seen_hashes.add(image_hash)
                    # The same image at a different CMS-generated resolution is
                    # not another product view. Keep one reference only.
                    continue

                seen_urls.add(key)
                if image_hash:
                    seen_hashes.add(image_hash)
                gallery_images.append(item)
                visual_fingerprints.append(fingerprint)
        finally:
            with suppress(OSError):
                staging_dir.rmdir()

        if not gallery_complete:
            # A successful refresh must account for every valid source-gallery
            # candidate. If any image fails, preserve the complete last-known
            # gallery instead of committing a partial list and pruning good files.
            fallback_state = (
                {
                    field: str(getattr(existing, field, "") or "")
                    for field in (
                        "image_url",
                        "image_path",
                        "image_hash",
                        "image_etag",
                        "image_last_modified",
                        "image_checked_at",
                    )
                }
                if existing is not None
                else initial_image_state
            )
            for field, value in fallback_state.items():
                if hasattr(product, field) or field in initial_image_state:
                    setattr(product, field, value)
            fallback_path_value = str(fallback_state.get("image_path", "") or "").strip()
            fallback_primary_path = (
                resolve_data_path(fallback_path_value)
                if fallback_path_value
                else None
            )
            if (
                fallback_primary_path is not None
                and not fallback_primary_path.is_file()
            ):
                fallback_primary_path = None
            if existing is not None:
                # An incomplete refresh must not rewrite the last-known-good
                # gallery paths. Preserve the persisted references verbatim;
                # canonicalizing them here can turn relative DB paths into
                # absolute temporary/test paths and mutate otherwise valid state.
                product.gallery_images = [
                    dict(image) for image in existing_gallery
                ]
            else:
                product.gallery_images = self._canonicalize_existing_gallery(
                    product,
                    existing_gallery,
                    fallback_primary_path,
                    products_root,
                )
            return product

        if not gallery_images:
            gallery_images = self._canonicalize_existing_gallery(
                product,
                existing_gallery,
                primary_path,
                products_root,
            )

        for position, image in enumerate(gallery_images, start=1):
            image["position"] = position

        # Offer only retained images to the human-review queue. The storage
        # gallery itself is not capped: every valid source-gallery image stays.
        retained_primary_url = (
            str(gallery_images[0].get("url", "") or primary_url).strip().casefold()
            if gallery_images
            else primary_url.casefold()
        )
        for image in gallery_images:
            url = str(image.get("url", "") or "").strip()
            key = url.casefold()
            if not url or key == retained_primary_url or key in existing_by_url:
                continue
            candidate = candidate_by_url.get(key, {})
            new_options.append(
                {
                    "url": url,
                    "path": str(image.get("image_path", "") or ""),
                    "hash": str(image.get("image_hash", "") or ""),
                    "score": int(candidate.get("score", 0) or 0),
                    "exact_code": bool(candidate.get("exact_code", False)),
                    "generic": False,
                    "source": "woocommerce-gallery",
                    "gallery": True,
                }
            )

        product.gallery_images = gallery_images
        if gallery_images:
            primary = gallery_images[0]
            product.image_path = str(primary.get("image_path", "") or "")
            product.image_url = str(primary.get("url", "") or "") or primary_url
            product.image_hash = str(primary.get("image_hash", "") or "")
        if existing is not None:
            self._register_gallery_review(product, new_options)
        return product

    @staticmethod
    def _canonicalize_primary(product, existing_gallery, products_root):
        raw_path = str(getattr(product, "image_path", "") or "").strip()
        primary_url = str(getattr(product, "image_url", "") or "").strip()
        candidate_paths = []
        if raw_path:
            candidate_paths.append(raw_path)
        if primary_url:
            candidate_paths.extend(
                str(item.get("image_path", item.get("path", "")) or "")
                for item in existing_gallery
                if isinstance(item, dict)
                and str(item.get("url", "") or "").strip().casefold()
                == primary_url.casefold()
            )

        for value in candidate_paths:
            if not value.strip():
                continue
            source = resolve_data_path(value)
            if not source.is_file():
                continue
            stored_path, image_hash = store_image_in_product_group(
                getattr(product, "code", ""),
                source,
                1,
                root=products_root,
            )
            if stored_path:
                product.image_path = stored_path
                if image_hash:
                    product.image_hash = image_hash
                return resolve_data_path(stored_path)
        return None

    @staticmethod
    def _canonicalize_existing_gallery(
        product,
        existing_gallery,
        primary_path,
        products_root,
    ):
        results: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        seen_paths: set[str] = set()
        seen_hashes: set[str] = set()
        primary_url = str(getattr(product, "image_url", "") or "").strip()
        source_items = [dict(item) for item in existing_gallery]
        if primary_path is not None and primary_path.is_file():
            source_items.insert(
                0,
                {
                    "url": primary_url,
                    "image_path": str(primary_path),
                    "image_hash": ImageDownloader.hash_file(primary_path),
                    "position": 1,
                    "source": "primary",
                },
            )

        for image in source_items:
            raw_path = str(image.get("image_path", image.get("path", "")) or "").strip()
            if not raw_path:
                continue
            path = resolve_data_path(raw_path)
            if not path.is_file():
                continue
            stored_path, computed_hash = store_image_in_product_group(
                getattr(product, "code", ""),
                path,
                len(results) + 1,
                root=products_root,
            )
            if not stored_path:
                continue
            canonical_path = resolve_data_path(stored_path)
            url = str(image.get("url", "") or "").strip()
            image_hash = computed_hash or str(
                image.get("image_hash", image.get("hash", "")) or ""
            ).strip()
            path_key = str(canonical_path).replace("\\", "/").casefold()
            if (
                path_key in seen_paths
                or (url and url.casefold() in seen_urls)
                or (image_hash and image_hash.casefold() in seen_hashes)
            ):
                continue
            results.append(
                {
                    **image,
                    "url": url,
                    "image_path": stored_path,
                    "image_hash": image_hash,
                    "position": len(results) + 1,
                }
            )
            seen_paths.add(path_key)
            if url:
                seen_urls.add(url.casefold())
            if image_hash:
                seen_hashes.add(image_hash.casefold())

        if results:
            first = results[0]
            product.image_path = str(first.get("image_path", "") or "")
            product.image_url = str(first.get("url", "") or "") or primary_url
            product.image_hash = str(first.get("image_hash", "") or "")
        return results

    @classmethod
    def _verified_gallery_recovery_hash(cls, product_code, url):
        """Return a pinned SHA-256 only for the explicitly verified recovery asset."""
        if str(product_code or "").strip().upper() != "FB-4047":
            return ""
        return cls.VERIFIED_GALLERY_RECOVERY_SHA256_BY_URL.get(
            str(url or "").strip().casefold(),
            "",
        )

    def _known_fb4047_gallery_recovery_candidates(
        self,
        product,
        existing_gallery,
    ) -> list[dict[str, Any]]:
        """Rebuild the previously verified FB-4047 gallery when the page is gated."""
        code = str(getattr(product, "code", "") or "").strip().upper()
        recovery_urls = self.VERIFIED_GALLERY_RECOVERY_URLS.get(code, ())
        if not recovery_urls:
            return []

        candidates: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for image in existing_gallery:
            url = str(image.get("url", "") or "").strip()
            key = url.casefold()
            if not url or key in seen_urls:
                continue
            seen_urls.add(key)
            candidates.append(
                {
                    "url": url,
                    "score": 300,
                    "exact_code": False,
                    "generic": False,
                    "gallery": True,
                    "gallery_container": True,
                    "source": str(
                        image.get("source", "") or "woocommerce-gallery"
                    ),
                    "sequence": len(candidates),
                }
            )

        for url in recovery_urls:
            key = url.casefold()
            if key in seen_urls:
                continue
            seen_urls.add(key)
            candidates.append(
                {
                    "url": url,
                    "score": 300,
                    "exact_code": False,
                    "generic": False,
                    "gallery": True,
                    "gallery_container": True,
                    "source": "verified-historical-gallery-recovery",
                    "sequence": len(candidates),
                }
            )
        return candidates

    def _candidate_source(self, product, existing):  # noqa: PLR0912
        candidates = list(getattr(product, "image_candidates", []) or [])
        existing_gallery = [
            dict(image)
            for image in list(getattr(existing, "gallery_images", []) or [])
            if isinstance(image, dict)
        ]
        detail_candidates = [
            candidate
            for candidate in candidates
            if isinstance(candidate, dict)
            and bool(candidate.get("gallery_container"))
            and not bool(candidate.get("generic"))
        ]
        candidate_gallery = [
            candidate
            for candidate in candidates
            if isinstance(candidate, dict)
            and bool(candidate.get("gallery"))
            and not bool(candidate.get("generic"))
        ]

        # The collection scraper marks images obtained from a product detail
        # page. This is already the authoritative ordered gallery; do not go
        # back to category-card thumbnails or apply a candidate-count limit.
        image_candidate_source = str(
            getattr(product, "image_candidates_source", "") or ""
        ).casefold()
        product_code = str(getattr(product, "code", "") or "").strip().upper()
        force_live_revalidation = (
            product_code in self.FORCE_LIVE_GALLERY_REVALIDATION_CODES
        )
        if image_candidate_source == "detail" and not force_live_revalidation:
            return detail_candidates

        if not self.refresh_existing and candidate_gallery:
            return candidate_gallery

        primary_changed = (
            str(getattr(product, "image_url", "") or "").strip().casefold()
            != str(getattr(existing, "image_url", "") or "").strip().casefold()
        )
        needs_detail = (
            self.refresh_existing
            or not existing_gallery
            or not candidate_gallery
            or primary_changed
            or ProductImageExtractor.is_generic_asset(
                getattr(product, "image_url", ""),
            )
        )

        detail_url = str(getattr(product, "url", "") or "").strip()
        if needs_detail and "/producto/" in detail_url:
            try:
                if force_live_revalidation:
                    live_getter = getattr(self.browser, "get_uncached", None)
                    if callable(live_getter):
                        # Never cache a login/gateway page as the product's source HTML.
                        html = live_getter(detail_url)
                    else:
                        html = self.browser.get(
                            detail_url,
                            force_revalidate=True,
                        )
                else:
                    html = self.browser.get(detail_url)
            except Exception:  # noqa: BLE001
                # Do not treat a failed live validation as proof that a gallery
                # image is absent. FB-4047 has a narrowly verified recovery URL.
                if force_live_revalidation:
                    return self._known_fb4047_gallery_recovery_candidates(
                        product,
                        existing_gallery,
                    )
                return [] if existing_gallery else candidate_gallery

            if not isinstance(html, str) or not html.strip():
                if force_live_revalidation:
                    return self._known_fb4047_gallery_recovery_candidates(
                        product,
                        existing_gallery,
                    )
                return [] if existing_gallery else candidate_gallery

            soup = BeautifulSoup(html, "lxml")
            detailed = self.product_extractor.extract(
                soup,
                url=detail_url,
                category=str(getattr(product, "category", "") or ""),
            )
            page_candidates = list(
                getattr(detailed, "image_candidates", []) or []
            )
            page_gallery = [
                candidate
                for candidate in page_candidates
                if isinstance(candidate, dict)
                and bool(candidate.get("gallery_container"))
                and not bool(candidate.get("generic"))
            ]
            if force_live_revalidation:
                detail_code = str(
                    getattr(detailed, "code", "") or ""
                ).strip().upper()
                detail_name = str(getattr(detailed, "name", "") or "").casefold()
                if detail_code != product_code or "foco" not in detail_name:
                    return self._known_fb4047_gallery_recovery_candidates(
                        product,
                        existing_gallery,
                    )

                # Once the live response is identified as the actual product
                # page, its extracted gallery is authoritative. Do not append
                # a historical URL that the current gallery no longer lists.

            if page_gallery:
                product.image_candidates = page_gallery
                product.image_candidates_source = "detail"
                page_primary_url = str(
                    page_gallery[0].get("url", "") or ""
                ).strip()
                if page_primary_url:
                    product.image_url = page_primary_url
                return page_gallery

            # A successful HTTP response without a recognized product-gallery
            # container is not proof that the gallery is empty. Keep FB-4047's
            # verified historic source instead of accepting a login template.
            if force_live_revalidation:
                return self._known_fb4047_gallery_recovery_candidates(
                    product,
                    existing_gallery,
                )
            return [] if existing_gallery else candidate_gallery

        if force_live_revalidation:
            return self._known_fb4047_gallery_recovery_candidates(
                product,
                existing_gallery,
            )
        if candidate_gallery:
            return candidate_gallery
        return []

    @staticmethod
    def _normalize_candidates(candidates):
        seen: set[str] = set()
        normalized = []
        for candidate in list(candidates or []):
            if not isinstance(candidate, dict):
                continue
            url = str(candidate.get("url", "") or "").strip()
            if not url or url.casefold() in seen:
                continue
            seen.add(url.casefold())
            normalized.append(candidate)
        return normalized

    def _load_existing_products(self, products) -> dict[str, Any]:
        if self.review_service is None:
            return {}
        repository = getattr(self.review_service, "repository", None)
        getter = getattr(repository, "get_by_codes", None)
        if callable(getter):
            codes = [
                str(getattr(product, "code", "") or "").strip()
                for product in products
                if str(getattr(product, "code", "") or "").strip()
            ]
            try:
                loaded = getter(codes) or {}
            except (OSError, RuntimeError, TypeError, ValueError):
                return {}
            if not isinstance(loaded, dict):
                return {}
            loaded_dict = cast(dict[object, Any], loaded)
            return {
                str(code).strip().casefold(): product
                for code, product in loaded_dict.items()
                if str(code).strip()
            }
        getter = getattr(repository, "get_by_code", None)
        if not callable(getter):
            return {}
        result: dict[str, Any] = {}
        for product in products:
            code = str(getattr(product, "code", "") or "").strip()
            if not code:
                continue
            try:
                result[code.casefold()] = getter(code)
            except (OSError, RuntimeError, TypeError, ValueError):
                continue
        return result

    def _register_gallery_review(self, product, new_options):
        if self.review_service is None or not new_options:
            return
        first = new_options[0]
        self.review_service.register_candidate(
            code=str(product.code),
            product_name=str(getattr(product, "name", "") or ""),
            current_path=str(getattr(product, "image_path", "") or ""),
            current_hash=str(getattr(product, "image_hash", "") or ""),
            current_url=str(getattr(product, "image_url", "") or ""),
            candidate_path=str(first["path"]),
            candidate_hash=str(first["hash"]),
            candidate_url=str(first["url"]),
            candidate_options=new_options[: self.max_candidates],
            kind="gallery",
        )
