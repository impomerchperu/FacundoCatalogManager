from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from config.runtime_paths import resolve_data_path
from scrapers.extractors.product_image_extractor import ProductImageExtractor
from scrapers.images.image_downloader import ImageDownloader
from scrapers.images.image_paths import IMAGE_GALLERY_DIR


class ProductGallerySyncService:
    """Obtiene y descarga galerías de producto en segundo plano del pipeline."""

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

    def _sync_product(self, product, existing=None):
        existing = existing or self._existing_product(product)
        candidates = self._candidate_source(product, existing)
        if not candidates:
            product.gallery_images = list(
                getattr(existing, "gallery_images", []) or []
            )
            return product

        normalized = self._normalize_candidates(candidates)
        if not normalized:
            product.gallery_images = list(
                getattr(existing, "gallery_images", []) or []
            )
            return product

        existing_gallery = list(
            getattr(existing, "gallery_images", []) or []
        )
        existing_by_url = {
            str(item.get("url", "") or "").strip().casefold(): item
            for item in existing_gallery
            if isinstance(item, dict)
        }
        gallery_dir = resolve_data_path(IMAGE_GALLERY_DIR)
        product_dir = gallery_dir
        current_urls = {
            str(item.get("url", "") or "").strip().casefold()
            for item in normalized
        }

        new_options: list[dict[str, object]] = []
        gallery_images: list[dict[str, object]] = []
        for position, candidate in enumerate(normalized, start=1):
            url = str(candidate["url"])
            existing_item = existing_by_url.get(url.casefold())
            existing_path = (
                str(
                    existing_item.get("image_path", existing_item.get("path", ""))
                    or ""
                ).strip()
                if isinstance(existing_item, dict)
                else ""
            )
            path = resolve_data_path(existing_path) if existing_path else None

            if path is None or not path.is_file():
                try:
                    stored_path = self.image_downloader.download_gallery(
                        str(product.code),
                        url,
                        position,
                        product_dir / ImageDownloader._safe_code(str(product.code)),
                    )
                except Exception:  # noqa: BLE001
                    continue
                path = resolve_data_path(stored_path)
            image_hash = ImageDownloader.hash_file(path)

            item = {
                "url": url,
                "image_path": str(
                    path.relative_to(resolve_data_path("."))
                ).replace("\\", "/"),
                "image_hash": image_hash,
                "position": position,
                "source": "woocommerce-gallery",
            }
            gallery_images.append(item)

            if url.casefold() not in existing_by_url:
                new_options.append(
                    {
                        "url": url,
                        "path": item["image_path"],
                        "hash": image_hash,
                        "score": int(candidate.get("score", 0) or 0),
                        "exact_code": bool(candidate.get("exact_code", False)),
                        "generic": False,
                        "source": "woocommerce-gallery",
                        "gallery": True,
                    }
                )

        if gallery_images:
            product.gallery_images = gallery_images
            self._remove_obsolete_gallery_files(
                str(product.code),
                existing_gallery,
                current_urls,
            )
            self._register_gallery_review(product, new_options)
        else:
            product.gallery_images = existing_gallery
        return product

    def _candidate_source(self, product, existing):
        candidates = list(
            getattr(product, "image_candidates", []) or []
        )
        gallery_candidates = [
            candidate
            for candidate in candidates
            if bool(candidate.get("gallery"))
            and not bool(candidate.get("generic"))
        ]
        if gallery_candidates:
            return gallery_candidates[: self.max_candidates]

        existing_gallery = list(
            getattr(existing, "gallery_images", []) or []
        )
        primary_changed = (
            str(getattr(product, "image_url", "") or "").strip().casefold()
            != str(getattr(existing, "image_url", "") or "").strip().casefold()
        )
        needs_detail = (
            self.refresh_existing
            or not existing_gallery
            or primary_changed
            or ProductImageExtractor.is_generic_asset(
                getattr(product, "image_url", ""),
            )
        )
        if not needs_detail:
            return []

        detail_url = str(getattr(product, "url", "") or "").strip()
        if "/producto/" not in detail_url:
            return []

        try:
            html = self.browser.get(detail_url)
        except Exception:  # noqa: BLE001
            return []

        soup = BeautifulSoup(html, "lxml")
        detailed = self.product_extractor.extract(
            soup,
            url=detail_url,
            category=str(getattr(product, "category", "") or ""),
        )
        return [
            candidate
            for candidate in list(
                getattr(detailed, "image_candidates", []) or []
            )
            if not bool(candidate.get("generic"))
        ][: self.max_candidates]

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
            return {
                str(code).strip().casefold(): product
                for code, product in loaded.items()
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

    def _existing_product(self, product):
        if self.review_service is None:
            return None
        repository = getattr(self.review_service, "repository", None)
        getter = getattr(repository, "get_by_code", None)
        if not callable(getter):
            return None
        try:
            return getter(str(getattr(product, "code", "") or ""))
        except Exception:  # noqa: BLE001
            return None

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
            candidate_options=new_options,
            kind="gallery",
        )

    @staticmethod
    def _remove_obsolete_gallery_files(
        code: str,
        existing_gallery,
        current_urls: set[str],
    ) -> None:
        del code
        for item in list(existing_gallery or []):
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", "") or "").strip().casefold()
            if not url or url in current_urls:
                continue
            raw_path = str(
                item.get("image_path", item.get("path", "")) or ""
            ).strip()
            if not raw_path:
                continue
            path = resolve_data_path(raw_path)
            gallery_root = resolve_data_path(IMAGE_GALLERY_DIR).resolve()
            try:
                path.resolve().relative_to(gallery_root)
            except ValueError:
                continue
            try:
                path.unlink(missing_ok=True)
            except OSError:
                continue
