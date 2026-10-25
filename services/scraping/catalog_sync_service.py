from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, ClassVar

from config.runtime_paths import resolve_data_path
from models.scraping.detail_description_policy import (
    has_technical_detail,
    is_complete_detail,
    normalize_detail_text,
)
from models.scraping.sync_result import SyncResult
from scrapers.images.image_downloader import ImageDownloader
from scrapers.images.image_paths import IMAGE_PRODUCTS_DIR
from scrapers.images.image_validation import (
    file_extension_matches,
    identify_image_file,
)
from scrapers.images.product_image_storage import store_image_in_product_group
from services.scraping.category_name_normalizer import (
    merge_category_names,
    split_category_names,
)
from services.scraping.product_hash_service import ProductHashService

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TIMING_LOG = PROJECT_ROOT / "data" / "scraping_timing.log"


def _log_timing(message, *args):
    TIMING_LOG.parent.mkdir(parents=True, exist_ok=True)
    formatted = message % args if args else message
    with TIMING_LOG.open("a", encoding="utf-8") as file:
        file.write(f"{formatted}\n")


if TYPE_CHECKING:
    from services.scraping.scraping_result_writer import ScrapingResultWriter


class CatalogSyncService:
    """Compara productos obtenidos contra el catálogo persistido."""

    guarantees_product_masters = True

    FIELD_LABELS: ClassVar[dict[str, str]] = {
        "code": "Código",
        "name": "Nombre",
        "category": "Categoría",
        "description": "Detalle",
        "price": "Precio",
        "price_sample": "Precio muestra",
        "price_hundred": "Precio ciento",
        "price_thousand": "Precio millar",
        "stock": "Stock",
        "colors": "Colores",
        "color_stock": "Stock por color",
        "image_url": "URL imagen",
        "image_path": "Ruta imagen",
        "image_hash": "Hash imagen",
        "gallery_images": "Galería de imágenes",
        "content_hash": "Hash contenido",
    }

    def __init__(
        self,
        repository,
        diff_service,
        image_cleanup: Callable[[], list[dict[str, Any]]] | None = None,
    ):
        self.repository = repository
        self.diff_service = diff_service
        self.image_cleanup = image_cleanup
        self.last_sync_result = SyncResult()
        self.hash_service = ProductHashService()
        self.result_writer: ScrapingResultWriter | None = None
        self._deferred_image_cleanup = False
        self._full_sync_in_progress = False
        self._image_state_repaired = False

    @staticmethod
    def _normalize_code(value) -> str:
        """Normaliza mayúsculas y espacios exteriores."""
        return str(value or "").strip().upper()

    def sync(
        self,
        products,
        prune_missing: bool = True,
        cleanup_generated: bool = True,
        expected_products: int | None = 0,
        expected_category_occurrences: int = 0,
    ):
        """Sincroniza el catálogo usando códigos reales como identidad."""
        del cleanup_generated
        result = SyncResult()
        self._image_state_repaired = False
        raw_products = list(products)
        missing_code_products = [
            p
            for p in raw_products
            if not self._normalize_code(getattr(p, "code", ""))
        ]
        result.missing_code = len(missing_code_products)
        prepared = []
        for product in raw_products:
            code = self._normalize_code(getattr(product, "code", ""))
            if not code:
                continue
            product.code = code
            product.category = self._merge_categories(
                getattr(product, "category", "")
            )
            product.description = normalize_detail_text(
                getattr(product, "description", "")
            )
            prepared.append(product)
        consolidated = self.consolidate_products(prepared)
        result.products_expected = max(int(expected_products or 0), 0)
        result.expected_category_occurrences = max(
            int(expected_category_occurrences or 0), 0
        )
        result.products_found = len(raw_products)
        result.products_unique = len(consolidated)
        result.processed = result.products_found
        result.duplicate_occurrences = max(
            result.products_found - result.products_unique, 0
        )
        result.products_multiple_categories = self._count_multi_category_products(
            prepared
        )
        scraped_codes = {
            self._normalize_code(p.code).casefold() for p in consolidated
        }
        existing_by_code = self._load_existing_products(consolidated)
        # Replacing category memberships is safe only when this call carries
        # a known, complete unique-product target. The scraping orchestrator
        # additionally validates all category occurrences before calling FULL.
        replace_category_memberships = (
            prune_missing
            and result.products_expected > 0
            and result.products_unique >= result.products_expected
            and result.coverage_complete
            and result.missing_code == 0
            and not result.has_errors
        )
        transaction_started = self._begin_repository_transaction()

        try:
            self._synchronize_products(
                consolidated,
                existing_by_code,
                result,
                replace_category_memberships=replace_category_memberships,
                preserve_existing_categories=(
                    prune_missing and not replace_category_memberships
                ),
            )

            expected_unique = result.products_expected
            actual_unique = len(scraped_codes)
            expected_complete = (
                expected_unique <= 0 or actual_unique >= expected_unique
            )
            prune_allowed = (
                prune_missing
                and result.coverage_complete
                and expected_complete
                and not result.has_errors
            )
            if prune_allowed:
                self._remove_missing_products(scraped_codes, result)
            if transaction_started:
                self._commit_repository_transaction()
        except Exception:
            if transaction_started:
                self._rollback_repository_transaction()
                if not self._transaction_is_active():
                    # Any canonical files created by the failed attempt are
                    # retired through the DB-reference whitelist, never by path.
                    self._cleanup_unused_images()
            raise

        image_path_changed = self._image_state_repaired or any(
            any(
                str(field.get("field", "")) in {"image_path", "gallery_images"}
                for field in list(change.get("changes", []) or [])
                if isinstance(field, dict)
            )
            for change in result.changes
            if isinstance(change, dict)
        )
        if not image_path_changed:
            new_codes = {
                self._normalize_code(change.get("code", "")).casefold()
                for change in result.changes
                if isinstance(change, dict) and change.get("type") == "NEW"
            }
            image_path_changed = any(
                self._normalize_code(getattr(product, "code", "")).casefold()
                in new_codes
                and (
                    str(getattr(product, "image_path", "") or "").strip()
                    or list(getattr(product, "gallery_images", []) or [])
                )
                for product in consolidated
            )
        if image_path_changed:
            self._deferred_image_cleanup = True
            if (
                not self._full_sync_in_progress
                and not self._transaction_is_active()
            ):
                self._deferred_image_cleanup = False
                self._cleanup_unused_images()

        result.finish()
        self.last_sync_result = result
        return result

    def _synchronize_products(
        self,
        products,
        existing_by_code,
        result: SyncResult,
        *,
        replace_category_memberships: bool,
        preserve_existing_categories: bool,
    ) -> None:
        """Persiste campos de productos sin perder categorías ante FULL incompleto."""
        for product in products:
            existing = existing_by_code.get(
                self._normalize_code(product.code).casefold()
            )
            if existing is None:
                description = getattr(product, "description", "")
                if not self._description_is_complete(description):
                    product.description = ""
                self._image_state_repaired = (
                    self._normalize_product_image_state(product)
                    or self._image_state_repaired
                )
                product.content_hash = self.hash_service.generate(product)
                result.created += 1
                result.changes.append(
                    {
                        "type": "NEW",
                        "code": product.code,
                        "name": product.name,
                        "changes": [],
                    }
                )
                self._save_catalog_product(product)
                continue

            incoming_categories = self._merge_categories(
                getattr(product, "category", "")
            )
            if replace_category_memberships:
                # A validated FULL sync is authoritative for category membership.
                product.category = incoming_categories
            elif preserve_existing_categories:
                # An incomplete FULL sync cannot alter any stored membership,
                # including legacy category display names.
                product.category = self._value(existing, "category")
            else:
                # Directed syncs observe one category at a time; merge the new
                # occurrence without dropping previously confirmed memberships.
                product.category = self._merge_categories(
                    self._value(existing, "category"),
                    incoming_categories,
                )

            self._preserve_existing_prices(existing, product)
            self._preserve_existing_description(existing, product)
            self._preserve_existing_image_state(existing, product)
            self._image_state_repaired = (
                self._normalize_product_image_state(product)
                or self._image_state_repaired
            )
            product.content_hash = self.hash_service.generate(product)
            comparison = self.diff_service.compare(existing, product)
            if comparison["changed"]:
                result.updated += 1
                result.changes.append(
                    {
                        "type": "UPDATED",
                        "code": product.code,
                        "name": product.name,
                        "changes": [
                            {
                                "field": field,
                                "label": self.FIELD_LABELS.get(field, field),
                                "old": self._value(existing, field),
                                "new": self._value(product, field),
                            }
                            for field in comparison["fields"]
                        ],
                    }
                )
                self._save_catalog_product(product, existing)
            else:
                # Internal HTTP cache metadata is persisted without emitting a
                # user-facing catalog change for a 304/unchanged image response.
                if self._image_sync_metadata_changed(existing, product):
                    self._save_catalog_product(product, existing)
                result.unchanged += 1


    @classmethod
    def _normalize_product_image_state(cls, product) -> bool:
        """Persist only decodable image bytes, with a suffix matching real format."""
        before_path = str(getattr(product, "image_path", "") or "")
        before_hash = str(getattr(product, "image_hash", "") or "")
        before_validators = (
            str(getattr(product, "image_etag", "") or ""),
            str(getattr(product, "image_last_modified", "") or ""),
            str(getattr(product, "image_checked_at", "") or ""),
        )
        before_gallery = list(getattr(product, "gallery_images", []) or [])
        code = cls._normalize_code(getattr(product, "code", ""))
        raw_path = str(getattr(product, "image_path", "") or "").strip()
        if raw_path and code:
            try:
                source = resolve_data_path(raw_path)
                stored_path, stored_hash = store_image_in_product_group(
                    code,
                    source,
                    1,
                    root=IMAGE_PRODUCTS_DIR,
                    deduplicate_in_group=False,
                )
            except (OSError, ValueError, RuntimeError):
                stored_path, stored_hash = "", ""
            if stored_path and stored_hash:
                product.image_path = stored_path
                product.image_hash = stored_hash
            else:
                product.image_path = ""
                product.image_hash = ""
                product.image_etag = ""
                product.image_last_modified = ""
                product.image_checked_at = ""
        else:
            # A validator/hash without a decodable local file is not a valid
            # cache entry. Keep the source URL so a later sync can retry.
            product.image_path = ""
            product.image_hash = ""
            product.image_etag = ""
            product.image_last_modified = ""
            product.image_checked_at = ""

        gallery_items = list(getattr(product, "gallery_images", []) or [])
        if gallery_items:
            product.gallery_images = cls._normalize_existing_gallery(
                code=code,
                gallery=gallery_items,
                primary_url=str(getattr(product, "image_url", "") or ""),
                primary_path=str(getattr(product, "image_path", "") or ""),
                primary_hash=str(getattr(product, "image_hash", "") or ""),
            )
        else:
            product.gallery_images = []

        # If the previous primary was unidentifiable but a valid gallery image
        # remains, promote the best matching source image instead of leaving an
        # empty primary reference. A second pass removes its duplicate gallery row.
        if not str(getattr(product, "image_path", "") or "").strip() and product.gallery_images:
            primary = product.gallery_images[0]
            product.image_path = str(primary.get("image_path", "") or "")
            product.image_hash = str(primary.get("image_hash", "") or "")
            primary_url = str(primary.get("url", "") or "").strip()
            if primary_url:
                product.image_url = primary_url
            product.gallery_images = cls._normalize_existing_gallery(
                code=code,
                gallery=product.gallery_images,
                primary_url=str(getattr(product, "image_url", "") or ""),
                primary_path=product.image_path,
                primary_hash=product.image_hash,
            )

        after_path = str(getattr(product, "image_path", "") or "")
        after_hash = str(getattr(product, "image_hash", "") or "")
        after_validators = (
            str(getattr(product, "image_etag", "") or ""),
            str(getattr(product, "image_last_modified", "") or ""),
            str(getattr(product, "image_checked_at", "") or ""),
        )
        after_gallery = list(getattr(product, "gallery_images", []) or [])
        return (
            before_path != after_path
            or before_hash != after_hash
            or before_validators != after_validators
            or before_gallery != after_gallery
        )

    @classmethod
    def _preserve_existing_image_state(cls, existing, product) -> None:  # noqa: PLR0912
        incoming_path = str(getattr(product, "image_path", "") or "").strip()
        incoming_hash = str(getattr(product, "image_hash", "") or "").strip()
        current_path = str(cls._value(existing, "image_path") or "").strip()
        current_hash = str(cls._value(existing, "image_hash") or "").strip()
        if not incoming_path and not incoming_hash and (current_path or current_hash):
            # Re-identify local bytes by decoding them. Valid legacy files with a
            # misleading suffix are copied to a correctly suffixed path; corrupt
            # or unsupported bytes must not be retained as the current image.
            current_url = str(cls._value(existing, "image_url") or "")
            stored_path = ""
            stored_hash = ""
            code = str(getattr(product, "code", "") or cls._value(existing, "code") or "")
            source_path = resolve_data_path(current_path) if current_path else None

            if source_path is not None and source_path.is_file():
                try:
                    verified = ImageDownloader.verify_image_file(source_path)
                except (OSError, ValueError, RuntimeError):
                    try:
                        detected = identify_image_file(source_path)
                    except (OSError, ValueError, RuntimeError):
                        detected = {}
                    if (
                        detected
                        and code
                        and not file_extension_matches(
                            source_path,
                            detected["image_extension"],
                        )
                    ):
                        try:
                            stored_path, stored_hash = store_image_in_product_group(
                                code,
                                source_path,
                                1,
                                root=IMAGE_PRODUCTS_DIR,
                            )
                        except (OSError, ValueError, RuntimeError):
                            stored_path, stored_hash = "", ""
                    else:
                        detected = {}
                else:
                    stored_path = current_path
                    stored_hash = verified["image_hash"]

            if stored_path and stored_hash:
                product.image_url = current_url
                product.image_path = stored_path
                product.image_hash = stored_hash
                for field in ("image_etag", "image_last_modified", "image_checked_at"):
                    setattr(product, field, cls._value(existing, field) or "")
            else:
                # Keep the source URL for a future retry, but clear every
                # validator/hash/path tied to bytes that cannot be identified.
                if not str(getattr(product, "image_url", "") or "").strip():
                    product.image_url = current_url
                product.image_path = ""
                product.image_hash = ""
                product.image_etag = ""
                product.image_last_modified = ""
                product.image_checked_at = ""

            # Defer gallery decoding/canonicalization to
            # _normalize_product_image_state so a gallery is walked once.
            product.gallery_images = list(cls._value(existing, "gallery_images") or [])
            return

        if str(getattr(product, "image_url", "") or "").strip() == str(
            cls._value(existing, "image_url") or ""
        ).strip() and not str(getattr(product, "image_checked_at", "") or "").strip():
            for field in ("image_etag", "image_last_modified", "image_checked_at"):
                if not str(getattr(product, field, "") or "").strip():
                    setattr(product, field, cls._value(existing, field) or "")

    @staticmethod
    def _normalize_existing_gallery(  # noqa: PLR0912
        *,
        code: str,
        gallery,
        primary_url: str = "",
        primary_path: str = "",
        primary_hash: str = "",
    ) -> list[dict[str, Any]]:
        """Keep only decodable images and collapse exact byte duplicates."""
        if not code:
            return []

        normalized: list[dict[str, Any]] = []
        seen_hashes: set[str] = set()
        seen_urls: set[str] = set()
        seen_paths: set[str] = set()

        if primary_path and primary_hash:
            normalized.append(
                {
                    "url": primary_url,
                    "image_path": primary_path,
                    "image_hash": primary_hash,
                    "position": 1,
                    "source": "primary",
                }
            )
            seen_hashes.add(primary_hash.casefold())
            primary_path_key = str(
                resolve_data_path(primary_path).resolve()
            ).replace("\\", "/").casefold()
            seen_paths.add(primary_path_key)
            if primary_url:
                seen_urls.add(primary_url.strip().casefold())

        gallery_items = [
            item for item in list(gallery or []) if isinstance(item, dict)
        ]
        if not primary_path and primary_url:
            primary_key = primary_url.strip().casefold()
            gallery_items.sort(
                key=lambda item: (
                    0
                    if str(item.get("url", "") or "").strip().casefold() == primary_key
                    else 1
                )
            )

        for item in gallery_items:
            raw_path = str(
                item.get("image_path", item.get("path", "")) or ""
            ).strip()
            if not raw_path:
                continue
            url = str(item.get("url", "") or "").strip()
            if url and url.casefold() in seen_urls:
                continue
            source_path = resolve_data_path(raw_path)
            source_path_key = str(source_path.resolve()).replace(
                "\\", "/"
            ).casefold()
            if source_path_key in seen_paths:
                continue

            try:
                stored_path, stored_hash = store_image_in_product_group(
                    code,
                    source_path,
                    len(normalized) + 1,
                    root=IMAGE_PRODUCTS_DIR,
                    deduplicate_in_group=False,
                )
            except (OSError, ValueError, RuntimeError):
                continue
            if not stored_path or not stored_hash:
                continue
            stored_path_key = str(
                resolve_data_path(stored_path).resolve()
            ).replace("\\", "/").casefold()
            if stored_path_key in seen_paths:
                seen_paths.add(source_path_key)
                continue
            seen_paths.add(source_path_key)
            seen_paths.add(stored_path_key)
            if stored_hash.casefold() in seen_hashes:
                continue

            normalized.append(
                {
                    **item,
                    "url": url,
                    "image_path": stored_path,
                    "image_hash": stored_hash,
                    "position": len(normalized) + 1,
                    "source": str(item.get("source", "gallery") or "gallery"),
                }
            )
            seen_hashes.add(stored_hash.casefold())
            if url:
                seen_urls.add(url.casefold())

        return normalized

    @staticmethod
    def _image_sync_metadata_changed(existing, product) -> bool:
        return any(
            str(getattr(existing, field, "") or "")
            != str(getattr(product, field, "") or "")
            for field in ("image_etag", "image_last_modified", "image_checked_at")
        )

    def sync_full_catalog(
        self,
        products,
        prune_missing: bool = True,
        expected_products: int | None = 0,
        expected_category_occurrences: int = 0,
    ):
        self._full_sync_in_progress = True
        try:
            result = self.sync(
                products,
                prune_missing=prune_missing,
                expected_products=expected_products,
                expected_category_occurrences=expected_category_occurrences,
            )
        finally:
            self._full_sync_in_progress = False

        if (
            prune_missing
            and result.coverage_complete
            and not result.has_errors
            and (
                result.products_expected <= 0
                or result.products_unique >= result.products_expected
            )
        ):
            if self._transaction_is_active():
                self._deferred_image_cleanup = True
            else:
                self._deferred_image_cleanup = False
                self._cleanup_unused_images()
        elif self._deferred_image_cleanup and not self._transaction_is_active():
            # Even an incomplete scrape may have committed safe per-product image
            # changes; clean only after the catalog transaction has finished.
            self._deferred_image_cleanup = False
            self._cleanup_unused_images()
        return result

    def finalize_post_commit(self) -> None:
        """Ejecuta la limpieza diferida cuando la transacción externa ya confirmó."""
        if not self._deferred_image_cleanup:
            return
        self._deferred_image_cleanup = False
        self._cleanup_unused_images()

    def _transaction_is_active(self) -> bool:
        """Indica si otra capa mantiene abierta la transacción del catálogo."""
        db = getattr(self.repository, "db", None)
        return bool(getattr(db, "_transaction_active", False))

    def synchronize(self, products, prune_missing: bool = False):
        return self.sync(products, prune_missing=prune_missing)

    def _cleanup_unused_images(self) -> None:
        """Limpia imágenes que ya no pertenecen a productos actuales."""
        cleanup = self.image_cleanup
        if not callable(cleanup):
            return
        started = time.perf_counter()
        _log_timing("SCRAPING TIMING | stage=image_cleanup_started")
        try:
            deleted = cleanup()
        except Exception as error:  # noqa: BLE001
            _log_timing(
                "SCRAPING TIMING | stage=image_cleanup_error | error_type=%s | error=%s",
                type(error).__name__,
                str(error),
            )
            return
        _log_timing(
            "SCRAPING TIMING | stage=image_cleanup | deleted=%d | seconds=%.3f",
            len(deleted),
            time.perf_counter() - started,
        )

    def _load_existing_products(self, products) -> dict[str, object]:
        """Carga los productos existentes evitando una consulta por producto."""
        codes = [
            self._normalize_code(getattr(product, "code", ""))
            for product in products
        ]
        codes = [code for code in codes if code]
        bulk_lookup = getattr(self.repository, "get_by_codes", None)
        if callable(bulk_lookup):
            loaded = bulk_lookup(codes) or {}
            if isinstance(loaded, dict):
                return {
                    self._normalize_code(code).casefold(): product
                    for code, product in loaded.items()
                    if self._normalize_code(code)
                }

        return {
            self._normalize_code(code).casefold(): self.repository.get(code)
            for code in codes
        }

    def _begin_repository_transaction(self) -> bool:
        db = getattr(self.repository, "db", None)
        begin = getattr(db, "begin", None)
        if not callable(begin):
            return False
        if getattr(db, "_transaction_active", False):
            return False
        begin()
        return True

    def _commit_repository_transaction(self) -> None:
        db = getattr(self.repository, "db", None)
        commit = getattr(db, "commit", None)
        if not callable(commit):
            raise TypeError("El repositorio no permite confirmar la transacción.")
        commit()

    def _rollback_repository_transaction(self) -> None:
        db = getattr(self.repository, "db", None)
        rollback = getattr(db, "rollback", None)
        if callable(rollback):
            rollback()

    def _save_catalog_product(self, product, existing=None):
        """Evita una segunda lectura cuando el repositorio conoce el registro actual."""
        save_with_existing = getattr(self.repository, "save_with_existing", None)
        if callable(save_with_existing):
            return save_with_existing(product, existing)
        return self.repository.save(product)

    def _remove_missing_products(
        self, scraped_codes: set[str], result: SyncResult
    ) -> None:
        for existing in self.repository.get_all():
            code = self._normalize_code(self._value(existing, "code"))
            if not code or code.casefold() in scraped_codes:
                continue
            result.deleted += 1
            result.changes.append(
                {
                    "type": "DELETED",
                    "code": code,
                    "name": self._value(existing, "name"),
                    "changes": [
                        {
                            "field": "code",
                            "label": "Código ausente en origen",
                            "old": code,
                            "new": "Eliminado",
                        }
                    ],
                }
            )
            self.repository.delete_by_code(code)

    @classmethod
    def consolidate_products(cls, products):
        consolidated = {}
        for product in products:
            code = cls._normalize_code(getattr(product, "code", ""))
            if not code:
                continue
            product.code = code
            product.category = cls._merge_categories(
                getattr(product, "category", "")
            )
            product.description = normalize_detail_text(
                getattr(product, "description", "")
            )
            existing = consolidated.get(code.casefold())
            if existing is None:
                consolidated[code.casefold()] = product
                continue
            existing.category = cls._merge_categories(
                existing.category, product.category
            )
            colors = list(getattr(existing, "colors", [])) + list(
                getattr(product, "colors", [])
            )
            existing.colors = list(
                dict.fromkeys(str(c).strip() for c in colors if str(c).strip())
            )
            color_stock = dict(getattr(existing, "color_stock", {}))
            for color, stock in getattr(product, "color_stock", {}).items():
                normalized_color = str(color).strip()
                if not normalized_color:
                    continue
                try:
                    normalized_stock = max(int(stock), 0)
                except (TypeError, ValueError):
                    continue
                color_stock[normalized_color] = max(
                    color_stock.get(normalized_color, 0), normalized_stock
                )
            existing.color_stock = color_stock
            cls._merge_gallery_images(existing, product)
            cls._merge_missing_scalar_fields(existing, product)
        return list(consolidated.values())

    @staticmethod
    def _merge_gallery_images(existing, product) -> None:
        current = [
            dict(image)
            for image in list(getattr(existing, "gallery_images", []) or [])
            if isinstance(image, dict)
        ]
        incoming = [
            dict(image)
            for image in list(getattr(product, "gallery_images", []) or [])
            if isinstance(image, dict)
        ]
        seen = {
            str(image.get("url", "") or "").strip().casefold()
            for image in current
            if str(image.get("url", "") or "").strip()
        }
        for image in incoming:
            url = str(image.get("url", "") or "").strip()
            if not url or url.casefold() in seen:
                continue
            current.append(image)
            seen.add(url.casefold())
        current.sort(
            key=lambda image: (
                int(image.get("position", 0) or 0),
                str(image.get("url", "") or ""),
            )
        )
        for position, image in enumerate(current, start=1):
            image["position"] = position
        existing.gallery_images = current

    @classmethod
    def _merge_missing_scalar_fields(cls, existing, product) -> None:
        """Completa campos vacíos y conserva el Detail íntegro como fuente."""
        text_fields = (
            "name",
            "image_url",
            "image_path",
            "image_hash",
        )
        for field in text_fields:
            current = getattr(existing, field, "")
            candidate = getattr(product, field, "")
            if not str(current or "").strip() and str(candidate or "").strip():
                setattr(existing, field, candidate)

        current_description = normalize_detail_text(
            getattr(existing, "description", "")
        )
        candidate_description = normalize_detail_text(
            getattr(product, "description", "")
        )
        existing.description = current_description
        product.description = candidate_description
        if cls._description_is_complete(candidate_description):
            # A complete Detail from the current scrape can refresh an older
            # complete value as well as repair an incomplete one.
            existing.description = candidate_description
        elif (
            not current_description
            and candidate_description
            and has_technical_detail(candidate_description)
        ):
            # Retain a technical excerpt only when no prior Detail exists.
            existing.description = candidate_description

        price_fields = (
            "price",
            "price_sample",
            "price_hundred",
            "price_thousand",
        )
        for field in price_fields:
            try:
                current = float(getattr(existing, field, 0.0) or 0.0)
                candidate = float(getattr(product, field, 0.0) or 0.0)
            except (TypeError, ValueError):
                continue
            if current <= 0.0 < candidate:
                setattr(existing, field, candidate)

    @classmethod
    def _description_is_complete(cls, value: object) -> bool:
        return has_technical_detail(value) and is_complete_detail(value)

    @classmethod
    def _preserve_existing_description(cls, existing, product) -> None:
        """Keep only complete technical Detail; never persist commercial prose."""
        incoming = normalize_detail_text(getattr(product, "description", ""))
        current = normalize_detail_text(cls._value(existing, "description"))

        if cls._description_is_complete(incoming):
            product.description = incoming
        elif cls._description_is_complete(current):
            # Do not replace useful stored Detail with a clipped or unrelated
            # section returned by the product page.
            product.description = current
        else:
            product.description = ""

    @staticmethod
    def _preserve_existing_prices(existing, product) -> None:
        """Evita borrar precios válidos cuando una extracción llega incompleta."""
        for field in (
            "price",
            "price_sample",
            "price_hundred",
            "price_thousand",
        ):
            try:
                current = float(CatalogSyncService._value(existing, field) or 0.0)
                incoming = float(getattr(product, field, 0.0) or 0.0)
            except (TypeError, ValueError):
                continue
            if incoming <= 0.0 < current:
                setattr(product, field, current)

    @classmethod
    def _count_multi_category_products(cls, products) -> int:
        categories_by_code: dict[str, set[str]] = {}
        for product in products:
            code = cls._normalize_code(getattr(product, "code", ""))
            if not code:
                continue
            categories = categories_by_code.setdefault(code.casefold(), set())
            for category in split_category_names(getattr(product, "category", "")):
                normalized = category.strip().casefold()
                if normalized:
                    categories.add(normalized)
        return sum(
            1 for categories in categories_by_code.values() if len(categories) > 1
        )

    @staticmethod
    def _merge_categories(*categories) -> str:
        return merge_category_names(*categories)

    @staticmethod
    def _value(obj, field):
        if isinstance(obj, dict):
            return obj.get(field)
        try:
            return obj[field]
        except (KeyError, TypeError, IndexError):
            return getattr(obj, field, None)
