from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import logging
import os
import re
import shutil
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

import requests

from config.runtime_paths import DATA_DIR, resolve_data_path, to_data_relative_path
from models.product import Product
from models.product_image_gallery import normalize_product_gallery
from repositories.product_repository import ProductRepository
from scrapers.images.image_downloader import ImageDownloader
from scrapers.images.image_paths import (
    IMAGE_GALLERY_DIR,
    IMAGE_PRODUCTS_DIR,
    product_image_directory,
)
from scrapers.images.image_validation import (
    file_extension_matches,
    identify_image_file,
)
from scrapers.images.product_image_storage import store_image_in_product_group

QUEUE_PATH = DATA_DIR / "image_review_queue.json"
STAGING_DIR = DATA_DIR / "image_review_staging"
_QUEUE_LOCK = Lock()
LOGGER = logging.getLogger(__name__)


class ImageReviewService:
    """Gestiona candidatos de imagen sin sobrescribir la imagen vigente."""

    def __init__(
        self,
        repository: ProductRepository | None = None,
        image_cleanup: Callable[[], list[dict[str, object]]] | None = None,
    ) -> None:
        self._owns_repository = repository is None
        self.repository = repository or ProductRepository()
        self.image_cleanup = image_cleanup
        self._lock = _QUEUE_LOCK
        self._active_batch: str | None = None

    def _cleanup_unused_images(self) -> None:
        """Remove files made unreferenced only after the catalog has persisted."""
        if not callable(self.image_cleanup):
            return
        try:
            self.image_cleanup()
        except Exception:
            LOGGER.exception("No se pudo completar la limpieza post-commit de imágenes.")

    def close(self) -> None:
        if not self._owns_repository:
            return
        close_db = getattr(getattr(self.repository, "db", None), "close", None)
        if callable(close_db):
            close_db()

    def begin_batch(self) -> str:
        with self._lock:
            self._active_batch = uuid.uuid4().hex
            return self._active_batch

    def finalize_batch(self, batch_id: str | None) -> None:
        if not batch_id:
            return
        with self._lock:
            records = self._read()
            changed = False
            for record in records:
                if (
                    record.get("batch_id") == batch_id
                    and record.get("status") == "staged"
                ):
                    record["status"] = "pending"
                    record["updated_at"] = self._now()
                    changed = True
            if changed:
                self._write(records)
            if self._active_batch == batch_id:
                self._active_batch = None

    def discard_batch(self, batch_id: str | None) -> None:
        if not batch_id:
            return
        with self._lock:
            records = self._read()
            retained: list[dict] = []
            changed = False
            for record in records:
                if (
                    record.get("batch_id") == batch_id
                    and record.get("status") == "staged"
                ):
                    if str(record.get("kind", "replacement")) != "gallery":
                        self._remove_all_staged_candidates(record)
                    changed = True
                    continue
                retained.append(record)
            if changed:
                self._write(retained)
            if self._active_batch == batch_id:
                self._active_batch = None

    def stage_candidate(
        self,
        downloader: ImageDownloader,
        code: str,
        url: str,
    ) -> dict:
        STAGING_DIR.mkdir(parents=True, exist_ok=True)
        path = downloader.download_staged(code, url, STAGING_DIR)
        image_path = resolve_data_path(path)
        return {
            "image_path": path,
            "image_hash": ImageDownloader.hash_file(image_path),
        }

    def stage_candidates(
        self,
        downloader: ImageDownloader,
        code: str,
        candidates: list[dict],
        *,
        max_candidates: int | None = None,
    ) -> list[dict]:
        """Descarga candidatos únicos para revisión, sin descartar tipos genéricos."""
        staged: list[dict] = []
        seen_urls: set[str] = set()
        candidate_items = list(candidates or [])
        if max_candidates is not None:
            candidate_items = candidate_items[: max(int(max_candidates), 1)]
        for candidate in candidate_items:
            url = str(candidate.get("url", "") or "").strip()
            if not url or url.casefold() in seen_urls:
                continue
            seen_urls.add(url.casefold())
            try:
                downloaded = self.stage_candidate(downloader, code, url)
            except (
                OSError,
                ValueError,
                RuntimeError,
                requests.exceptions.RequestException,
            ):
                continue
            staged.append(
                {
                    "url": url,
                    "path": str(downloaded.get("image_path", "") or ""),
                    "hash": str(downloaded.get("image_hash", "") or ""),
                    "score": int(candidate.get("score", 0) or 0),
                    "exact_code": bool(candidate.get("exact_code", False)),
                    "generic": bool(candidate.get("generic", False)),
                    "source": str(candidate.get("source", "") or ""),
                    "source_page_url": str(
                        candidate.get(
                            "source_page_url",
                            candidate.get("page_url", candidate.get("product_url", "")),
                        ) or ""
                    ),
                    "extraction_source": str(
                        candidate.get("extraction_source", "") or ""
                    ),
                }
            )
        return staged


    @staticmethod
    def _observation_ledger_path() -> Path:
        return QUEUE_PATH.with_name("image_review_observations.json")

    @staticmethod
    def _observation_archive_root() -> Path:
        return QUEUE_PATH.parent / "image_review_observed"

    @staticmethod
    def _is_generic_observation_url(url: str) -> bool:
        filename = str(url or "").split("#", 1)[0].split("?", 1)[0]
        filename = filename.rsplit("/", 1)[-1]
        filename = re.sub(
            r"-(?:\d+x\d+|scaled)(?=\.[^.]+$)",
            "",
            filename,
            flags=re.IGNORECASE,
        ).casefold()
        return filename in {
            "placeholder-img.webp",
            "woocommerce-placeholder.png",
            "nuevo-producto.png",
            "nuevo-producto.webp",
        }

    @staticmethod
    def _read_observations() -> list[dict]:
        path = ImageReviewService._observation_ledger_path()
        if not path.is_file():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ValueError(
                f"Could not read image observation history: {path}"
            ) from error
        if not isinstance(payload, list):
            raise TypeError(
                f"Invalid image observation history format: {path}"
            )
        return [item for item in payload if isinstance(item, dict)]

    @staticmethod
    def _write_observations(records: list[dict]) -> None:
        path = ImageReviewService._observation_ledger_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def _observation_key(
        *,
        code: str,
        kind: str,
        current_hash: str,
        image_hash: str,
        image_url: str,
        source_page_url: str,
        extraction_source: str,
    ) -> str:
        # A changed local primary image creates a new review identity.
        identity = {
            "code": str(code or "").strip().casefold(),
            "kind": str(kind or "replacement").strip().casefold(),
            "current_hash": str(current_hash or "").strip().casefold(),
            "image_hash": str(image_hash or "").strip().casefold(),
            "image_url": str(image_url or "").strip(),
            "source_page_url": str(source_page_url or "").strip(),
            "extraction_source": str(extraction_source or "").strip().casefold(),
        }
        payload = json.dumps(
            identity,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _observation_source_path(
        self,
        value: str,
        kind: str,
        *,
        current_image: bool = False,
    ) -> Path | None:
        raw = str(value or "").strip()
        if not raw:
            return None

        if current_image:
            try:
                candidate = self._resolve_product_image_path(raw)
            except (OSError, ValueError):
                return None
            return candidate if candidate is not None and candidate.is_file() else None

        candidate = self._resolve_staged_path(raw)
        if candidate is not None and candidate.is_file():
            return candidate

        if str(kind or "").strip().casefold() == "gallery":
            candidate = self._resolve_gallery_path(raw)
            if candidate is not None and candidate.is_file():
                return candidate
        return None

    def _archive_observation_image(
        self,
        *,
        code: str,
        observation_key: str,
        source_path: Path | None,
    ) -> str:
        """Preserve a copy outside the temporary review staging directory."""
        if source_path is None or not source_path.is_file():
            return ""

        try:
            content = source_path.read_bytes()
        except OSError:
            LOGGER.exception("Could not read observed image: %s", source_path)
            return ""

        actual_hash = hashlib.sha256(content).hexdigest()
        safe_code = re.sub(
            r"[^A-Za-z0-9._-]+",
            "_",
            str(code or "").strip(),
        ).strip("._-")[:80] or "unknown"

        extension = source_path.suffix.casefold()
        if extension not in {
            ".jpg", ".jpeg", ".png", ".webp", ".gif",
            ".bmp", ".tif", ".tiff",
        }:
            extension = ".img"

        relative = (
            Path("image_review_observed")
            / safe_code
            / f"{observation_key[:24]}-{actual_hash[:12]}{extension}"
        )
        destination = QUEUE_PATH.parent / relative

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.is_file():
                destination.write_bytes(content)
        except OSError:
            LOGGER.exception("Could not archive observed image for %s", code)
            return ""

        return relative.as_posix()

    @staticmethod
    def _legacy_observation_resolution(  # noqa: PLR0912
        existing_records: list[dict],
        *,
        code: str,
        kind: str,
        current_hash: str,
        image_hash: str,
        image_url: str,
        source_page_url: str,
        extraction_source: str,
        manual_only: bool,
    ) -> str:
        """Migrate older decisions only when their known identity matches."""
        allowed = {
            "keep", "replace", "candidate", "manual", "delete",
            "accept_gallery", "dismiss_gallery",
        }

        for record in existing_records:
            if str(record.get("status", "")).casefold() != "resolved":
                continue
            resolution = str(record.get("resolution", "") or "").casefold()
            if resolution not in allowed:
                continue
            if str(record.get("code", "")).casefold() != code.casefold():
                continue
            if str(record.get("current_hash", "") or "").casefold() != (
                str(current_hash or "").casefold()
            ):
                continue

            old_kind = str(
                record.get("kind", "replacement") or "replacement"
            ).casefold()
            if old_kind != str(kind).casefold():
                continue

            if manual_only:
                if (
                    bool(record.get("manual_only"))
                    and not str(record.get("candidate_hash", "") or "")
                    and not list(record.get("candidate_options", []) or [])
                ):
                    return resolution
                continue

            old_options = list(record.get("candidate_options", []) or [])
            if not old_options:
                old_options = [record]

            for option in old_options:
                old_hash = str(
                    option.get("hash", record.get("candidate_hash", "")) or ""
                ).strip().casefold()
                old_url = str(
                    option.get("url", record.get("candidate_url", "")) or ""
                ).strip()
                old_page = str(
                    option.get(
                        "source_page_url",
                        record.get("source_page_url", ""),
                    ) or ""
                ).strip()
                old_method = str(
                    option.get("extraction_source")
                    or record.get("extraction_source")
                    or ""
                ).strip().casefold()

                if old_hash != str(image_hash or "").strip().casefold():
                    continue
                if old_url != str(image_url or "").strip():
                    continue
                # Unknown legacy provenance cannot confirm that a candidate
                # came from the same source page and extraction method.
                requested_page = str(source_page_url or "").strip()
                if old_page != requested_page:
                    continue

                requested_method = str(extraction_source or "").strip().casefold()
                if old_method != requested_method:
                    continue
                return resolution

        return ""

    def _record_candidate_observations(  # noqa: PLR0912
        self,
        *,
        code: str,
        product_name: str,
        current_path: str,
        current_hash: str,
        current_url: str,
        kind: str,
        candidate_path: str,
        candidate_hash: str,
        candidate_url: str,
        candidate_options: list[dict],
        allow_manual_only: bool,
        existing_records: list[dict],
    ) -> tuple[list[str], list[str], bool, bool]:
        """Archive observations and identify candidates eligible for review."""
        current_is_generic = self._is_generic_observation_url(current_url)
        inputs = [dict(option) for option in candidate_options]

        if not inputs and candidate_hash:
            inputs = [{
                "path": candidate_path,
                "hash": candidate_hash,
                "url": candidate_url,
                "source_page_url": "",
                "extraction_source": (
                    "gallery" if kind == "gallery" else "primary"
                ),
                "gallery": kind == "gallery",
            }]
        elif not inputs and allow_manual_only:
            if current_is_generic and current_path:
                inputs = [{
                    "_current_image": True,
                    "path": current_path,
                    "hash": current_hash,
                    "url": current_url,
                    "source_page_url": "",
                    "extraction_source": "primary_current",
                    "generic": True,
                }]
            else:
                inputs = [{
                    "_manual_only": True,
                    "path": "",
                    "hash": "",
                    "url": "",
                    "source_page_url": "",
                    "extraction_source": "manual_only",
                }]

        if not inputs:
            return [], [], False, current_is_generic

        def option_is_generic(option: dict) -> bool:
            if option.get("_manual_only") or option.get("_current_image"):
                return True
            url = str(option.get("url", option.get("candidate_url", "")) or "")
            return bool(
                option.get("generic", False)
                or self._is_generic_observation_url(url)
            )

        generic_only = current_is_generic and all(
            option_is_generic(option) for option in inputs
        )

        observations = self._read_observations()
        by_key = {
            str(item.get("observation_key", "")): item
            for item in observations
            if str(item.get("observation_key", ""))
        }
        keys: list[str] = []
        queue_keys: list[str] = []
        all_reviewed = True
        changed = False
        now = self._now()

        for option in inputs:
            is_manual = bool(option.get("_manual_only"))
            is_current_image = bool(option.get("_current_image"))
            path_value = str(option.get("path", "") or "").strip()
            image_url = str(
                option.get("url", option.get("candidate_url", "")) or ""
            ).strip()
            source_page_url = str(
                option.get(
                    "source_page_url",
                    option.get("page_url", option.get("product_url", "")),
                ) or ""
            ).strip()

            extraction_source = str(
                option.get("extraction_source")
                or option.get("source")
                or (
                    "manual_only"
                    if is_manual
                    else (
                        "primary_current"
                        if is_current_image
                        else (
                            "gallery"
                            if bool(option.get("gallery", kind == "gallery"))
                            else "primary"
                        )
                    )
                )
            ).strip()

            source_path = (
                self._observation_source_path(
                    path_value,
                    kind,
                    current_image=is_current_image,
                )
                if path_value and not is_manual
                else None
            )
            image_hash = str(
                option.get("hash", option.get("image_hash", "")) or ""
            ).strip()

            if not image_hash and source_path is not None:
                try:
                    image_hash = hashlib.sha256(
                        source_path.read_bytes()
                    ).hexdigest()
                except OSError:
                    image_hash = ""

            if not image_hash and not is_manual:
                all_reviewed = False
                continue

            queue_eligible = (
                not option_is_generic(option)
                or (is_manual and not current_is_generic)
            )

            key = self._observation_key(
                code=code,
                kind=kind,
                current_hash=current_hash,
                image_hash=image_hash,
                image_url=image_url,
                source_page_url=source_page_url,
                extraction_source=extraction_source,
            )
            keys.append(key)
            if queue_eligible:
                queue_keys.append(key)
            entry = by_key.get(key)

            if entry is None:
                resolution = self._legacy_observation_resolution(
                    existing_records,
                    code=code,
                    kind=kind,
                    current_hash=current_hash,
                    image_hash=image_hash,
                    image_url=image_url,
                    source_page_url=source_page_url,
                    extraction_source=extraction_source,
                    manual_only=is_manual,
                )
                initial_state = (
                    "reviewed"
                    if resolution
                    else (
                        "observed_not_queued"
                        if generic_only or not queue_eligible
                        else "unreviewed"
                    )
                )
                entry = {
                    "observation_key": key,
                    "code": str(code),
                    "product_name": str(product_name or ""),
                    "kind": str(kind or "replacement"),
                    "current_hash": str(current_hash or ""),
                    "current_url": str(current_url or ""),
                    "image_hash": image_hash,
                    "image_url": image_url,
                    "source_page_url": source_page_url,
                    "extraction_source": extraction_source,
                    "source": str(option.get("source", "") or ""),
                    "generic": option_is_generic(option),
                    "stored_path": "",
                    "review_state": initial_state,
                    "resolution": resolution,
                    "first_seen_at": now,
                    "last_seen_at": now,
                    "last_reviewed_at": now if resolution else "",
                    "seen_count": 1,
                    "manual_only": is_manual,
                }
                observations.append(entry)
                by_key[key] = entry
                changed = True
            else:
                entry["last_seen_at"] = now
                entry["seen_count"] = int(entry.get("seen_count", 0) or 0) + 1
                entry["current_hash"] = str(current_hash or "")
                entry["current_url"] = str(current_url or "")
                if not entry.get("product_name") and product_name:
                    entry["product_name"] = str(product_name)
                changed = True

            if not is_manual:
                stored = str(entry.get("stored_path", "") or "")
                stored_file = QUEUE_PATH.parent / Path(stored) if stored else None
                if stored_file is None or not stored_file.is_file():
                    archived = self._archive_observation_image(
                        code=code,
                        observation_key=key,
                        source_path=source_path,
                    )
                    if archived:
                        entry["stored_path"] = archived
                        changed = True

            if not queue_eligible:
                if str(entry.get("review_state", "")) != "reviewed":
                    entry["review_state"] = "observed_not_queued"
                    entry["not_queued_reason"] = (
                        "manual_only_while_current_primary_is_generic"
                        if is_manual and current_is_generic
                        else "generic_candidate"
                    )
                    changed = True
            elif str(entry.get("review_state", "")) != "reviewed":
                all_reviewed = False

            if not is_manual:
                stored = str(entry.get("stored_path", "") or "")
                stored_file = QUEUE_PATH.parent / Path(stored) if stored else None
                if (
                    (stored_file is None or not stored_file.is_file())
                    and queue_eligible
                ):
                    all_reviewed = False

        if changed:
            self._write_observations(observations)

        unique_keys = list(dict.fromkeys(keys))
        unique_queue_keys = list(dict.fromkeys(queue_keys))
        return (
            unique_keys,
            unique_queue_keys,
            bool(unique_queue_keys) and all_reviewed,
            generic_only,
        )

    def _update_observation_states(
        self,
        observation_keys: set[str],
        *,
        state: str,
        resolution: str = "",
        reason: str = "",
        preserve_reviewed: bool = False,
    ) -> None:
        if not observation_keys:
            return
        try:
            observations = self._read_observations()
            changed = False
            now = self._now()
            for entry in observations:
                if str(entry.get("observation_key", "")) not in observation_keys:
                    continue
                if (
                    preserve_reviewed
                    and str(entry.get("review_state", "")) == "reviewed"
                ):
                    continue
                entry["review_state"] = state
                entry["last_seen_at"] = now
                if resolution:
                    entry["resolution"] = resolution
                if reason:
                    entry["not_queued_reason"] = reason
                changed = True
            if changed:
                self._write_observations(observations)
        except (OSError, ValueError, TypeError):
            LOGGER.exception("Could not update image observation status.")

    def _mark_observations_queued(self, record: dict) -> None:
        keys = {
            str(value).strip()
            for value in list(record.get("observation_keys", []) or [])
            if str(value).strip()
        }
        self._update_observation_states(
            keys,
            state="queued",
            preserve_reviewed=True,
        )

    def _mark_observations_not_queued(
        self,
        keys: list[str],
        *,
        reason: str = "generic_only_while_current_primary_is_generic",
    ) -> None:
        self._update_observation_states(
            set(keys),
            state="observed_not_queued",
            reason=reason,
            preserve_reviewed=True,
        )

    def _mark_observations_reviewed(
        self,
        record: dict,
        resolution: str,
    ) -> None:
        keys = {
            str(value).strip()
            for value in list(record.get("observation_keys", []) or [])
            if str(value).strip()
        }
        self._update_observation_states(
            keys,
            state="reviewed",
            resolution=str(resolution or "resolved"),
        )

    def register_candidate(  # noqa: PLR0912
        self,
        *,
        code: str,
        product_name: str,
        current_path: str,
        current_hash: str,
        current_url: str,
        candidate_path: str,
        candidate_hash: str,
        candidate_url: str,
        candidate_options: list[dict] | None = None,
        allow_manual_only: bool = False,
        kind: str = "replacement",
    ) -> dict | None:
        normalized_kind = (
            "gallery"
            if str(kind or "").strip().casefold() == "gallery"
            else "replacement"
        )
        if not candidate_hash and not allow_manual_only:
            # Do not delete a candidate directly: a legacy gallery path may
            # still be referenced by a catalog row. The post-commit cleaner
            # performs the whitelist check before physical deletion.
            if normalized_kind != "gallery":
                self._remove_staged_file(candidate_path)
            return None

        with self._lock:
            records = self._read()
            (
                observation_keys,
                queue_observation_keys,
                observations_already_reviewed,
                generic_only,
            ) = self._record_candidate_observations(
                    code=code,
                    product_name=product_name,
                    current_path=current_path,
                    current_hash=current_hash,
                    current_url=current_url,
                    kind=normalized_kind,
                    candidate_path=candidate_path,
                    candidate_hash=candidate_hash,
                    candidate_url=candidate_url,
                    candidate_options=list(candidate_options or []),
                    allow_manual_only=allow_manual_only,
                    existing_records=records,
                )
            for record in records:
                same_code = (
                    str(record.get("code", "")).casefold()
                    == str(code).casefold()
                )
                same_hash = (
                    str(record.get("candidate_hash", ""))
                    == candidate_hash
                )
                same_batch = (
                    str(record.get("batch_id", "") or "")
                    == str(self._active_batch or "")
                    and bool(self._active_batch)
                )
                if (
                    same_code
                    and same_hash
                    and record.get("status") in {"pending", "resolved", "staged"}
                    and same_batch
                ):
                    if normalized_kind != "gallery":
                        self._remove_staged_file(candidate_path)
                    return None

            options: list[dict] = []
            for option in list(candidate_options or []):
                path = str(option.get("path", "") or "").strip()
                url = str(option.get("url", "") or "").strip()
                if not path or not url:
                    continue
                options.append(
                    {
                        "url": url,
                        "path": path,
                        "hash": str(option.get("hash", "") or ""),
                        "score": int(option.get("score", 0) or 0),
                        "exact_code": bool(option.get("exact_code", False)),
                        "source": str(option.get("source", "") or ""),
                        "source_page_url": str(
                            option.get(
                                "source_page_url",
                                option.get("page_url", option.get("product_url", "")),
                            ) or ""
                        ),
                        "extraction_source": str(
                            option.get("extraction_source")
                            or option.get("source")
                            or (
                                "gallery"
                                if bool(
                                    option.get("gallery", normalized_kind == "gallery")
                                )
                                else "primary"
                            )
                        ),
                        "generic": bool(
                            option.get("generic", False)
                            or self._is_generic_observation_url(url)
                        ),
                        "gallery": bool(
                            option.get("gallery", normalized_kind == "gallery")
                        ),
                    }
                )
            if not options and not allow_manual_only:
                options = [
                    {
                        "url": str(candidate_url or ""),
                        "path": str(candidate_path or ""),
                        "hash": str(candidate_hash or ""),
                        "score": 0,
                        "exact_code": False,
                        "source": "",
                        "source_page_url": "",
                        "extraction_source": (
                            "gallery" if normalized_kind == "gallery" else "primary"
                        ),
                        "generic": self._is_generic_observation_url(
                            str(candidate_url or "")
                        ),
                        "gallery": normalized_kind == "gallery",
                    }
                ]

            if options:
                primary = next(
                    (
                        option
                        for option in options
                        if option["path"] == str(candidate_path or "")
                    ),
                    None,
                )
                if primary is None:
                    primary = options[0]
            else:
                primary = {
                    "url": "",
                    "path": "",
                    "hash": "",
                    "score": 0,
                    "exact_code": False,
                    "generic": False,
                    "source": "",
                }

            if generic_only:
                protected_paths: set[str] = set()
                queue_changed = False
                for existing_record in records:
                    if (
                        str(existing_record.get("code", "")).casefold()
                        != str(code).casefold()
                        or existing_record.get("status") not in {"pending", "staged"}
                    ):
                        continue

                    active_options = list(
                        existing_record.get("candidate_options", []) or []
                    )
                    active_urls = [
                        str(option.get("url", "") or "")
                        for option in active_options
                    ]
                    if not active_urls:
                        active_urls = [
                            str(existing_record.get("candidate_url", "") or "")
                        ]
                    active_has_valid_image = any(
                        not (
                            self._is_generic_observation_url(url)
                        )
                        for url in active_urls
                        if url
                    )
                    same_primary = (
                        str(existing_record.get("current_hash", "") or "").casefold()
                        == str(current_hash or "").casefold()
                    )
                    if active_has_valid_image and same_primary:
                        protected_paths.update(
                            str(option.get("path", "") or "")
                            for option in active_options
                            if str(option.get("path", "") or "").strip()
                        )
                        continue

                    if str(existing_record.get("kind", "replacement")) != "gallery":
                        self._remove_all_staged_candidates(existing_record)
                    existing_record["status"] = "resolved"
                    existing_record["resolution"] = "generic_only_waiting"
                    existing_record["updated_at"] = self._now()
                    queue_changed = True

                if queue_changed:
                    self._write(records)

                self._mark_observations_not_queued(observation_keys)
                self._remove_staged_candidates_except(
                    {
                        "candidate_options": options,
                        "candidate_path": candidate_path,
                    },
                    protected_paths,
                )
                return None

            all_options = options
            generic_options = [
                option for option in all_options if bool(option.get("generic", False))
            ]
            eligible_options = [
                option for option in all_options if not bool(option.get("generic", False))
            ]

            if generic_options:
                generic_keys = sorted(
                    set(observation_keys) - set(queue_observation_keys)
                )
                self._mark_observations_not_queued(
                    generic_keys,
                    reason="generic_candidate",
                )
                protected_paths = {
                    str(option.get("path", "") or "").strip()
                    for option in eligible_options
                    if str(option.get("path", "") or "").strip()
                }
                self._remove_staged_candidates_except(
                    {
                        "candidate_options": all_options,
                        "candidate_path": candidate_path,
                    },
                    protected_paths,
                )

            options = eligible_options
            # Manual-only reviews intentionally start without candidates.
            # Preserve that path; only suppress empty non-manual reviews.
            if not options and not allow_manual_only:
                return None

            observation_keys = queue_observation_keys

            if observations_already_reviewed and observation_keys:
                self._remove_all_staged_candidates(
                    {
                        "candidate_options": options,
                        "candidate_path": candidate_path,
                    }
                )
                return None

            normalized_code = str(code).casefold()
            protected_paths = {
                str(option.get("path", "") or "")
                for option in options
                if str(option.get("path", "") or "").strip()
            }
            if str(candidate_path or "").strip():
                protected_paths.add(str(candidate_path))

            for existing_record in records:
                if (
                    str(existing_record.get("code", "")).casefold()
                    == normalized_code
                    and existing_record.get("status") in {"pending", "staged"}
                ):
                    if str(existing_record.get("kind", "replacement")) != "gallery":
                        self._remove_staged_candidates_except(
                            existing_record,
                            protected_paths,
                        )
                    existing_record["status"] = "resolved"
                    existing_record["resolution"] = "superseded"
                    existing_record["updated_at"] = self._now()

            now = self._now()
            record = {
                "id": uuid.uuid4().hex,
                "batch_id": self._active_batch,
                "status": "staged" if self._active_batch else "pending",
                "created_at": now,
                "updated_at": now,
                "code": str(code),
                "product_name": str(product_name or ""),
                "current_path": str(current_path or ""),
                "current_hash": str(current_hash or ""),
                "current_url": str(current_url or ""),
                "candidate_path": primary["path"],
                "candidate_hash": primary["hash"],
                "candidate_url": primary["url"],
                "candidate_options": options,
                "observation_keys": observation_keys,
                "source_page_url": str(primary.get("source_page_url", "") or ""),
                "extraction_source": str(primary.get("extraction_source", "") or ""),
                "excluded_options": [],
                "kind": normalized_kind,
                "manual_only": bool(allow_manual_only and not options),
            }
            records.append(record)
            self._write(records)
            self._mark_observations_queued(record)
            return dict(record)

    def pending(self) -> list[dict]:
        return self._available({"pending"})

    def available(self) -> list[dict]:
        """Incluye revisiones que están listas aunque el lote siga ejecutándose."""
        return self._available({"pending", "staged"})

    def _available(self, statuses: set[str]) -> list[dict]:
        with self._lock:
            records = self._read()
            changed = False
            available: list[dict] = []
            for record in records:
                if record.get("status") not in statuses:
                    continue
                options = list(record.get("candidate_options", []) or [])
                if options:
                    valid_options = [
                        option
                        for option in options
                        if self._candidate_path_exists(
                            record,
                            str(option.get("path", "") or ""),
                        )
                    ]
                    if not valid_options:
                        record["status"] = "resolved"
                        record["resolution"] = "missing_candidate"
                        record["updated_at"] = self._now()
                        changed = True
                        continue
                    view_record = dict(record)
                    view_record["candidate_options"] = valid_options
                    view_record["candidate_path"] = str(valid_options[0].get("path", "") or "")
                    view_record["candidate_url"] = str(valid_options[0].get("url", "") or "")
                    view_record["candidate_hash"] = str(valid_options[0].get("hash", "") or "")
                    available.append(view_record)
                    continue

                candidate_path = str(record.get("candidate_path", "") or "").strip()
                if not candidate_path and bool(record.get("manual_only")):
                    available.append(dict(record))
                    continue
                if not self._candidate_path_exists(record, candidate_path):
                    record["status"] = "resolved"
                    record["resolution"] = "missing_candidate"
                    record["updated_at"] = self._now()
                    changed = True
                    continue
                available.append(dict(record))
            if changed:
                self._write(records)
            return available

    @staticmethod
    def _candidate_path_exists(record: dict, value: str) -> bool:
        if str(record.get("kind", "replacement")) == "gallery":
            candidate = ImageReviewService._resolve_gallery_path(value)
        else:
            candidate = ImageReviewService._resolve_staged_path(value)
        return candidate is not None and candidate.is_file()

    def discard_staged(self, path: str) -> None:
        self._remove_staged_file(path)

    def remove_candidate(self, review_id: str, option_path: str) -> None:
        """Elimina una alternativa de la cola; las galerías se marcan como excluidas."""
        value = str(option_path or "").strip()
        if not value:
            raise ValueError("La alternativa seleccionada no es válida.")
        with self._lock:
            records = self._read()
            record = self._find_available_record(records, review_id)
            options = list(record.get("candidate_options", []) or [])
            matched = next(
                (
                    option
                    for option in options
                    if str(option.get("path", "") or "").strip() == value
                ),
                None,
            )
            if matched is None:
                raise ValueError("La alternativa seleccionada no existe.")

            if str(record.get("kind", "replacement")).strip().casefold() == "gallery":
                self._exclude_candidate_locked(record, value)
            else:
                record["candidate_options"] = [
                    option
                    for option in options
                    if str(option.get("path", "") or "").strip() != value
                ]
                if str(record.get("selected_path", "") or "").strip() == value:
                    record["selected_action"] = ""
                    record["selected_path"] = ""
                    record["selected_url"] = ""
                self._remove_staged_file(value)
                remaining = record["candidate_options"]
                if remaining:
                    primary = remaining[0]
                    record["candidate_path"] = str(primary.get("path", "") or "")
                    record["candidate_hash"] = str(primary.get("hash", "") or "")
                    record["candidate_url"] = str(primary.get("url", "") or "")
                else:
                    record["candidate_path"] = ""
                    record["candidate_hash"] = ""
                    record["candidate_url"] = ""
                    record["manual_only"] = True
            record["updated_at"] = self._now()
            self._write(records)

    def apply_selection(
        self,
        review_id: str,
        action: str,
        manual_path: str | Path | None = None,
    ) -> dict:
        """Registra una selección pendiente; no modifica todavía el catálogo."""
        action = str(action).strip().casefold()
        if action not in {
            "keep",
            "replace",
            "candidate",
            "manual",
            "delete",
            "accept_gallery",
            "dismiss_gallery",
        }:
            raise ValueError("Acción de revisión no válida.")

        with self._lock:
            records = self._read()
            record = self._find_available_record(records, review_id)
            previous_path = str(record.get("selected_path", "") or "").strip()
            self._store_deferred_selection(record, action, manual_path)
            selected_path = str(record.get("selected_path", "") or "").strip()
            if (
                previous_path
                and previous_path != selected_path
                and not self._is_record_option_path(record, previous_path)
            ):
                self._remove_staged_file(previous_path)

            self._write(records)
            return {
                "code": str(record.get("code", "")),
                "action": action,
                "changed": False,
                "selected": True,
            }

    def exclude_candidate(self, review_id: str, option_path: str) -> None:
        """Marca una alternativa como excluida sin modificar el catálogo."""
        value = str(option_path or "").strip()
        if not value:
            raise ValueError("La alternativa seleccionada no es válida.")
        with self._lock:
            records = self._read()
            record = self._find_available_record(records, review_id)
            options = list(record.get("candidate_options", []) or [])
            if value not in {
                str(option.get("path", "") or "")
                for option in options
            }:
                raise ValueError("La alternativa seleccionada no existe.")
            self._exclude_candidate_locked(record, value)
            record["updated_at"] = self._now()
            self._write(records)

    def discard_selections(self, review_ids: list[str] | None = None) -> None:
        """Descarta selecciones pendientes sin tocar el catálogo."""
        ids = (
            {
                str(review_id).strip()
                for review_id in review_ids
                if str(review_id).strip()
            }
            if review_ids is not None
            else None
        )
        with self._lock:
            records = self._read()
            changed = False
            for record in records:
                if record.get("status") not in {"pending", "staged"}:
                    continue
                if ids is not None and str(record.get("id", "")) not in ids:
                    continue
                if str(record.get("selected_action", "") or "").strip():
                    selected_path = str(
                        record.get("selected_path", "") or ""
                    ).strip()
                    if selected_path and not self._is_record_option_path(
                        record,
                        selected_path,
                    ):
                        self._remove_staged_file(selected_path)
                    record.pop("selected_action", None)
                    record.pop("selected_path", None)
                    record.pop("selected_url", None)
                    record["updated_at"] = self._now()
                    changed = True
            if changed:
                self._write(records)

    @staticmethod
    def _is_record_option_path(record: dict, value: str) -> bool:
        return str(value or "") in {
            str(option.get("path", "") or "")
            for option in list(record.get("candidate_options", []) or [])
        }

    def _exclude_candidate_locked(self, record: dict, value: str) -> None:
        excluded = [
            str(item).strip()
            for item in list(record.get("excluded_options", []) or [])
            if str(item).strip()
        ]
        if value not in excluded:
            excluded.append(value)
        record["excluded_options"] = excluded
        if str(record.get("selected_path", "") or "").strip() == value:
            record["selected_action"] = ""
            record["selected_path"] = ""
            record["selected_url"] = ""

    def _store_deferred_selection(
        self,
        record: dict,
        action: str,
        manual_path: str | Path | None,
    ) -> None:
        normalized = str(action or "").strip().casefold()
        if str(record.get("kind", "replacement")) == "gallery" and normalized in {
            "accept_gallery",
            "dismiss_gallery",
        }:
            record["selected_action"] = normalized
            record["selected_path"] = ""
            record["selected_url"] = ""
            record["updated_at"] = self._now()
            return

        if normalized not in {"keep", "replace", "candidate", "manual", "delete"}:
            raise ValueError("Acción de revisión no válida.")

        selected_path = ""
        selected_url = ""
        if normalized == "candidate":
            selected_value = str(manual_path or "")
            selected_path = (
                self._resolve_gallery_selection(record, selected_value)
                if str(record.get("kind", "replacement")) == "gallery"
                else self._resolve_staged_selection(record, selected_value)
            )
            selected_url = self._candidate_url_for_path(record, selected_path)
            if not selected_path:
                raise ValueError("La imagen seleccionada no existe.")
        elif normalized == "replace":
            selected_path = str(record.get("candidate_path", "") or "")
            selected_url = str(record.get("candidate_url", "") or "")
        elif normalized == "manual":
            selected_path = self._stage_manual_image(record, manual_path)

        record["selected_action"] = normalized
        record["selected_path"] = selected_path
        record["selected_url"] = selected_url
        record["updated_at"] = self._now()

    def _apply_gallery_resolution(self, record: dict, action: str) -> dict:
        normalized = str(action or "").strip().casefold()
        if normalized not in {"accept_gallery", "dismiss_gallery"}:
            raise ValueError("Acción de galería no válida.")

        product = self.repository.get_by_code(str(record.get("code", "")))
        if product is None:
            raise ValueError(
                "No existe el producto "
                f"{record.get('code', '')} en la base de datos."
            )

        options = list(record.get("candidate_options", []) or [])
        if normalized == "dismiss_gallery":
            dismissed_urls = {
                str(option.get("url", "") or "").strip().casefold()
                for option in options
            }
            product.gallery_images = [
                image
                for image in list(getattr(product, "gallery_images", []) or [])
                if str(image.get("url", "") or "").strip().casefold()
                not in dismissed_urls
            ]
            product.gallery_images = self._normalize_identifiable_gallery(product)
            self.repository.update(product)

        return {
            "code": product.code,
            "action": normalized,
            "changed": normalized == "dismiss_gallery",
        }

    def apply_approved(self, batch_id: str | None = None) -> list[dict]:
        """Aplica decisiones tomadas durante el scraping después de confirmar el catálogo."""
        with self._lock:
            records = self._read()
            selected = [
                record
                for record in records
                if record.get("status") == "pending"
                and str(record.get("selected_action", "") or "").strip()
                and (
                    batch_id is None
                    or str(record.get("batch_id", "")) == str(batch_id)
                )
            ]
            results: list[dict] = []
            for record in selected:
                action = str(record.get("selected_action", "") or "")
                try:
                    if record.get("kind") == "gallery":
                        result = self._apply_gallery_resolution(record, action)
                    else:
                        product = self.repository.get_by_code(
                            str(record.get("code", "")),
                        )
                        if product is None:
                            continue
                        result = (
                            self._keep_current(record, product)
                            if action == "keep"
                            else self._apply_selected_image(
                                record,
                                product,
                                action,
                                str(record.get("selected_path", "") or ""),
                            )
                        )
                    record["status"] = "resolved"
                    record["resolution"] = action
                    record["updated_at"] = self._now()
                    if isinstance(result, tuple):
                        result = result[0]
                    results.append(result)
                except (OSError, ValueError, RuntimeError):
                    continue

            if results:
                self._write(records)
                for resolved_record in selected:
                    if resolved_record.get("status") == "resolved":
                        self._mark_observations_reviewed(
                            resolved_record,
                            str(resolved_record.get("resolution", "") or ""),
                        )
                if any(
                    str(record.get("kind", "replacement")) == "gallery"
                    for record in selected
                ):
                    self._cleanup_unused_images()
            return results

    def finalize_selected(self, review_ids: list[str]) -> list[dict]:
        """Aplica en bloque las decisiones seleccionadas de una revisión."""
        ids = {
            str(review_id).strip()
            for review_id in review_ids
            if str(review_id).strip()
        }
        if not ids:
            return []

        with self._lock:
            records = self._read()
            selected_records = [
                record
                for record in records
                if str(record.get("id", "")) in ids
                and record.get("status") == "pending"
                and (
                    str(record.get("selected_action", "") or "").strip()
                    or list(record.get("excluded_options", []) or [])
                )
            ]
            if len(selected_records) != len(ids):
                raise ValueError(
                    "Hay revisiones seleccionadas que ya no están disponibles."
                )
            if any(
                not str(record.get("selected_action", "") or "").strip()
                and not list(record.get("excluded_options", []) or [])
                for record in selected_records
            ):
                raise ValueError("La revisión total aún no está completa.")

            return self._commit_selected_records(records, selected_records)

    def _commit_selected_records(
        self,
        records: list[dict],
        selected_records: list[dict],
    ) -> list[dict]:
        prepared: list[dict] = []
        results: list[dict] = []
        original_records = copy.deepcopy(records)
        db = getattr(self.repository, "db", None)
        transaction_started = False
        try:
            if db is not None and hasattr(db, "begin"):
                db.begin()
                transaction_started = True

            for record in selected_records:
                if str(record.get("kind", "replacement")) == "gallery":
                    result, file_state, product = self._prepare_gallery_record(
                        record,
                    )
                else:
                    result, file_state, product = self._prepare_selected_record(
                        record,
                    )
                prepared.append(file_state)
                self.repository.update(product)
                record["status"] = "resolved"
                record["resolution"] = str(
                    record.get("selected_action", "")
                )
                record["updated_at"] = self._now()
                results.append(result)

            # La cola se persiste mientras la transacción de catálogo sigue
            # abierta. Si falla la escritura, la base aún puede hacer rollback.
            self._write(records)

            if transaction_started and db is not None:
                db.commit()
                transaction_started = False
        except Exception:
            if transaction_started and db is not None:
                db.rollback()
            for file_state in reversed(prepared):
                self._rollback_file_state(file_state)
            with contextlib.suppress(OSError):
                self._write(original_records)
            if transaction_started and not bool(
                getattr(db, "_transaction_active", False)
            ):
                self._cleanup_unused_images()
            raise

        # El catálogo y la cola ya están confirmados. La limpieza es posterior
        # para evitar perder candidatos antes de un commit exitoso.
        try:
            for resolved_record in selected_records:
                self._mark_observations_reviewed(
                    resolved_record,
                    str(resolved_record.get("resolution", "") or ""),
                )
            self._cleanup_selected_records(selected_records)
            self._cleanup_file_states(prepared)
        except OSError:
            LOGGER.exception("No se pudieron limpiar todos los archivos temporales de revisión.")
        self._cleanup_unused_images()

        return results

    def _prepare_gallery_record(
        self,
        record: dict,
    ) -> tuple[dict, dict, Product]:
        product = self.repository.get_by_code(
            str(record.get("code", "")),
        )
        if product is None:
            raise ValueError(
                "No existe el producto "
                f"{record.get('code', '')} en la base de datos."
            )

        excluded = {
            str(value).strip().casefold()
            for value in list(record.get("excluded_options", []) or [])
            if str(value).strip()
        }
        product.gallery_images = [
            image
            for image in list(getattr(product, "gallery_images", []) or [])
            if (
                str(image.get("image_path", "") or "").strip().casefold()
                not in excluded
                and str(image.get("url", "") or "").strip().casefold()
                not in excluded
            )
        ]

        action = str(
            record.get("selected_action", "") or ""
        ).strip().casefold()
        if action in {"candidate", "manual"}:
            applied = self._apply_selected_image(
                record,
                product,
                action,
                str(record.get("selected_path", "") or ""),
                persist=False,
                cleanup=False,
            )
            result, file_state = (
                applied
                if isinstance(applied, tuple)
                else (
                    applied,
                    {
                        "destination": None,
                        "backup": None,
                        "destination_existed": False,
                    },
                )
            )
        else:
            result = {
                "code": product.code,
                "action": action or "gallery",
                "changed": bool(excluded),
            }
            file_state = {
                "destination": None,
                "backup": None,
                "destination_existed": False,
            }

        created_gallery_paths: list[Path] = []
        product.gallery_images = self._normalize_identifiable_gallery(
            product,
            created_gallery_paths,
        )
        file_state.setdefault("created_paths", []).extend(created_gallery_paths)
        for position, image in enumerate(product.gallery_images, start=1):
            image["position"] = position

        return result, file_state, product

    def _prepare_selected_record(
        self,
        record: dict,
    ) -> tuple[dict, dict, Product]:
        product = self.repository.get_by_code(
            str(record.get("code", "")),
        )
        if product is None:
            raise ValueError(
                "No existe el producto "
                f"{record.get('code', '')} en la base de datos."
            )

        applied = self._apply_selected_image(
            record,
            product,
            str(record.get("selected_action", "")),
            str(record.get("selected_path", "") or ""),
            persist=False,
            cleanup=False,
        )
        result, file_state = (
            applied
            if isinstance(applied, tuple)
            else (
                applied,
                {
                    "destination": None,
                    "backup": None,
                    "destination_existed": False,
                },
            )
        )
        return result, file_state, product

    def _cleanup_selected_records(self, records: list[dict]) -> None:
        for record in records:
            if str(record.get("kind", "replacement")) == "gallery":
                # Excluded gallery paths are cleaned by the centralized
                # post-commit sweep after all catalog references are re-read.
                continue

            self._remove_all_staged_candidates(record)
            selected_path = str(
                record.get("selected_path", "") or ""
            ).strip()
            if (
                selected_path
                and not self._is_record_option_path(record, selected_path)
            ):
                self._remove_staged_file(selected_path)

    @staticmethod
    def _find_available_record(records: list[dict], review_id: str) -> dict:
        for record in records:
            if (
                record.get("id") == review_id
                and record.get("status") in {"pending", "staged"}
            ):
                return record
        raise ValueError("La revisión de imagen ya no está disponible.")

    def _keep_current(self, record: dict, product) -> dict:
        before = (
            str(getattr(product, "image_path", "") or ""),
            str(getattr(product, "image_hash", "") or ""),
            str(getattr(product, "image_url", "") or ""),
        )
        created_paths: list[Path] = []
        self._apply_kept_image_state(record, product, created_paths)
        after = (
            str(getattr(product, "image_path", "") or ""),
            str(getattr(product, "image_hash", "") or ""),
            str(getattr(product, "image_url", "") or ""),
        )
        changed = before != after
        try:
            self.repository.update(product)
        except Exception:
            # Any new canonical copies are cleaned only after re-reading the
            # committed catalog references; never unlink them by guessed path.
            self._cleanup_unused_images()
            raise
        self._remove_all_staged_candidates(record)
        if changed:
            self._cleanup_unused_images()
        return {
            "code": product.code,
            "action": "keep",
            "changed": changed,
        }

    def _apply_kept_image_state(
        self,
        record: dict,
        product,
        created_paths: list[Path] | None = None,
    ) -> None:
        """Keep only decoded image bytes and migrate valid legacy suffixes."""
        source_url = str(record.get("current_url", "") or "")
        raw_path = str(record.get("current_path", "") or "").strip()
        record_hash = str(record.get("current_hash", "") or "").strip()
        product.image_url = source_url
        product.image_path = ""
        product.image_hash = ""
        product.image_etag = ""
        product.image_last_modified = ""
        product.image_checked_at = ""

        source = self._resolve_gallery_path(raw_path) if raw_path else None
        if source is not None and source.is_file():
            try:
                identify_image_file(source)
                stored_path, stored_hash = self._store_identifiable_image(
                    str(getattr(product, "code", "") or ""),
                    source,
                    1,
                    created_paths,
                )
            except (OSError, ValueError, RuntimeError):
                stored_path, stored_hash = "", ""

            if stored_path and stored_hash:
                product.image_path = stored_path
                product.image_hash = stored_hash
                # HTTP validators are usable only when the local bytes still
                # match the image version stored with the review record.
                if record_hash and record_hash == stored_hash:
                    product.image_etag = str(record.get("image_etag", "") or "")
                    product.image_last_modified = str(
                        record.get("image_last_modified", "") or ""
                    )
                    product.image_checked_at = str(
                        record.get("image_checked_at", "") or ""
                    )

        product.gallery_images = self._normalize_identifiable_gallery(
            product,
            created_paths,
        )

    def _store_identifiable_image(
        self,
        code: str,
        source: Path,
        position: int,
        created_paths: list[Path] | None = None,
    ) -> tuple[str, str]:
        if not code:
            return "", ""
        product_dir = resolve_data_path(
            product_image_directory(code, root=IMAGE_PRODUCTS_DIR)
        )
        before = {
            path.resolve()
            for path in product_dir.iterdir()
            if product_dir.is_dir() and path.is_file()
        } if product_dir.is_dir() else set()

        try:
            stored_path, stored_hash = store_image_in_product_group(
                code,
                source,
                position,
                root=IMAGE_PRODUCTS_DIR,
            )
        except (OSError, ValueError, RuntimeError):
            return "", ""
        if not stored_path or not stored_hash:
            return "", ""
        destination = Path(resolve_data_path(stored_path)).resolve()
        try:
            source_resolved = Path(source).resolve()
        except OSError:
            source_resolved = source
        if (
            created_paths is not None
            and destination != source_resolved
            and destination not in before
        ):
            created_paths.append(destination)
        return stored_path, stored_hash

    def _normalize_identifiable_gallery(
        self,
        product,
        created_paths: list[Path] | None = None,
    ) -> list[dict]:
        """Keep only decoded, canonically named images and exact unique bytes."""
        code = str(getattr(product, "code", "") or "")
        old_primary_hash = str(getattr(product, "image_hash", "") or "").casefold()
        primary_url = str(getattr(product, "image_url", "") or "").strip()
        _primary_path, primary_hash, primary_is_valid = self._normalize_review_primary(
            product,
            code,
            old_primary_hash,
            created_paths,
        )
        valid = self._normalize_review_gallery_entries(
            product,
            code,
            primary_hash=primary_hash if primary_is_valid else "",
            primary_url=primary_url if primary_is_valid else "",
            created_paths=created_paths,
        )

        # normalize_product_gallery injects a primary entry; do that only when
        # the primary itself was successfully identified from its local bytes.
        if primary_is_valid:
            return normalize_product_gallery(product, valid)
        return valid

    def _normalize_review_primary(
        self,
        product,
        code: str,
        old_hash: str,
        created_paths: list[Path] | None,
    ) -> tuple[str, str, bool]:
        raw_path = str(getattr(product, "image_path", "") or "").strip()
        source = None
        if raw_path:
            try:
                source = self._resolve_product_image_path(raw_path)
            except (OSError, ValueError):
                source = None

        stored_path = ""
        stored_hash = ""
        if source is not None and source.is_file():
            stored_path, stored_hash = self._store_identifiable_image(
                code,
                source,
                1,
                created_paths,
            )

        if stored_path and stored_hash:
            product.image_path = stored_path
            product.image_hash = stored_hash
            if old_hash != stored_hash.casefold():
                product.image_etag = ""
                product.image_last_modified = ""
                product.image_checked_at = ""
            return stored_path, stored_hash, True

        # A stale DB path/hash is not evidence that the source bytes still
        # exist or can be decoded. Keep the remote URL for future recovery.
        product.image_path = ""
        product.image_hash = ""
        product.image_etag = ""
        product.image_last_modified = ""
        product.image_checked_at = ""
        return "", "", False

    def _normalize_review_gallery_entries(
        self,
        product,
        code: str,
        *,
        primary_hash: str,
        primary_url: str,
        created_paths: list[Path] | None,
    ) -> list[dict]:
        seen_hashes = {primary_hash.casefold()} if primary_hash else set()
        seen_urls = {primary_url.casefold()} if primary_url else set()
        valid: list[dict] = []

        for raw in list(getattr(product, "gallery_images", []) or []):
            entry = self._normalize_review_gallery_entry(
                raw,
                code,
                position=len(valid) + 1,
                seen_hashes=seen_hashes,
                seen_urls=seen_urls,
                created_paths=created_paths,
            )
            if entry is None:
                continue
            valid.append(entry)
            seen_hashes.add(str(entry["image_hash"]).casefold())
            url = str(entry.get("url", "") or "").strip()
            if url:
                seen_urls.add(url.casefold())

        return valid

    def _normalize_review_gallery_entry(
        self,
        raw: object,
        code: str,
        *,
        position: int,
        seen_hashes: set[str],
        seen_urls: set[str],
        created_paths: list[Path] | None,
    ) -> dict | None:
        if not isinstance(raw, dict):
            return None
        raw_path = str(raw.get("image_path", raw.get("path", "")) or "").strip()
        if not raw_path:
            return None
        source = self._resolve_gallery_path(raw_path)
        if source is None or not source.is_file():
            return None
        try:
            verified = identify_image_file(source)
        except (OSError, ValueError):
            return None

        url = str(raw.get("url", "") or "").strip()
        url_key = url.casefold()
        image_hash = verified["image_hash"].casefold()
        if image_hash in seen_hashes or (url_key and url_key in seen_urls):
            return None

        stored_path, stored_hash = self._store_identifiable_image(
            code,
            source,
            position,
            created_paths,
        )
        if not stored_path or not stored_hash:
            return None
        return {
            **raw,
            "url": url,
            "image_path": stored_path,
            "image_hash": stored_hash,
            "position": position,
        }

    def _apply_selected_image(
        self,
        record: dict,
        product,
        action: str,
        manual_path: str | Path | None,
        *,
        persist: bool = True,
        cleanup: bool = True,
    ) -> tuple[dict, dict] | dict:
        if action == "keep":
            return self._apply_keep_selection(record, product, persist)
        if action == "delete":
            return self._apply_delete_selection(record, product, persist)

        source = self._resolve_selected_source(record, action, manual_path)
        if source is None or not source.is_file():
            raise ValueError("La imagen seleccionada no existe.")
        try:
            identify_image_file(source)
        except (OSError, ValueError) as error:
            raise ValueError(
                "El archivo seleccionado no contiene una imagen compatible e identificable."
            ) from error

        result, file_state = self._copy_selected_image(
            record,
            product,
            action,
            manual_path,
            source,
            persist,
            cleanup,
        )
        if persist:
            return result
        return result, file_state

    def _apply_delete_selection(
        self,
        record: dict,
        product,
        persist: bool,
    ) -> tuple[dict, dict] | dict:
        # Do not unlink the active image while SQLite still references it.
        # Clear and persist first, then let the normal unused-image cleanup
        # re-read the catalog and decide whether the physical file is orphaned.
        product.image_path = ""
        product.image_hash = ""
        product.image_url = ""
        product.image_etag = ""
        product.image_last_modified = ""
        product.image_checked_at = ""
        created_paths: list[Path] = []
        product.gallery_images = self._normalize_identifiable_gallery(
            product,
            created_paths,
        )
        result = {
            "code": product.code,
            "action": "delete",
            "changed": True,
        }

        if persist:
            try:
                self.repository.update(product)
            except Exception:
                self._cleanup_unused_images()
                raise
            self._remove_all_staged_candidates(record)
            self._cleanup_unused_images()
            return result

        return result, {
            "destination": None,
            "backup": None,
            "destination_existed": False,
            "created_paths": created_paths,
        }

    def _apply_keep_selection(
        self,
        record: dict,
        product,
        persist: bool,
    ) -> tuple[dict, dict] | dict:
        before = (
            str(getattr(product, "image_path", "") or ""),
            str(getattr(product, "image_hash", "") or ""),
            str(getattr(product, "image_url", "") or ""),
            str(getattr(product, "image_etag", "") or ""),
            str(getattr(product, "image_last_modified", "") or ""),
            str(getattr(product, "image_checked_at", "") or ""),
            list(getattr(product, "gallery_images", []) or []),
        )
        created_paths: list[Path] = []
        self._apply_kept_image_state(record, product, created_paths)
        after = (
            str(getattr(product, "image_path", "") or ""),
            str(getattr(product, "image_hash", "") or ""),
            str(getattr(product, "image_url", "") or ""),
            str(getattr(product, "image_etag", "") or ""),
            str(getattr(product, "image_last_modified", "") or ""),
            str(getattr(product, "image_checked_at", "") or ""),
            list(getattr(product, "gallery_images", []) or []),
        )
        result = {
            "code": product.code,
            "action": "keep",
            "changed": before != after,
        }
        if persist:
            try:
                self.repository.update(product)
            except Exception:
                self._cleanup_unused_images()
                raise
            self._remove_all_staged_candidates(record)
            if result["changed"]:
                self._cleanup_unused_images()
            return result
        return result, {
            "destination": None,
            "backup": None,
            "destination_existed": False,
            "created_paths": created_paths,
        }

    def _resolve_selected_source(
        self,
        record: dict,
        action: str,
        manual_path: str | Path | None,
    ) -> Path | None:
        if action == "candidate":
            selected_value = str(manual_path or "")
            selected = (
                self._resolve_gallery_selection(record, selected_value)
                if str(record.get("kind", "replacement")) == "gallery"
                else self._resolve_staged_selection(record, selected_value)
            )
            if not selected:
                return None
            return (
                self._resolve_gallery_path(selected)
                if str(record.get("kind", "replacement")) == "gallery"
                else self._resolve_staged_path(selected)
            )
        if action == "replace":
            selected = self._resolve_staged_selection(
                record,
                str(record.get("candidate_path", "") or ""),
            )
            return self._resolve_staged_path(selected) if selected else None
        if action == "manual":
            return self._resolve_staged_path(str(manual_path or ""))
        return None

    def _copy_selected_image(
        self,
        record: dict,
        product,
        action: str,
        manual_path: str | Path | None,
        source: Path,
        persist: bool,
        cleanup: bool,
    ) -> tuple[dict, dict]:
        verified_source = identify_image_file(source)
        image_hash = verified_source["image_hash"]
        extension = verified_source["image_extension"]
        product_dir = product_image_directory(
            product.code,
            root=resolve_data_path(IMAGE_PRODUCTS_DIR),
        )
        product_dir.mkdir(parents=True, exist_ok=True)
        safe_code = ImageDownloader._safe_code(str(product.code))
        destination, destination_existed = self._select_review_destination(
            product_dir,
            safe_code,
            image_hash,
            extension,
        )
        if not destination_existed:
            destination = self._publish_review_image(
                source,
                destination,
                image_hash,
                extension,
            )

        created_gallery_paths: list[Path] = []
        try:
            self._set_product_image(
                record,
                product,
                action,
                manual_path,
                destination,
                created_paths=created_gallery_paths,
            )
            if persist:
                self.repository.update(product)
        except Exception:
            if persist:
                self._cleanup_unused_images()
            raise

        if persist:
            self._cleanup_persisted_image_selection(record, manual_path, None)
            if cleanup:
                self._cleanup_unused_images()

        return (
            {
                "code": product.code,
                "action": action,
                "changed": True,
                "image_path": product.image_path,
                "image_hash": product.image_hash,
                "image_url": product.image_url,
            },
            {
                "destination": destination,
                "backup": None,
                "destination_existed": destination_existed,
                "created_paths": created_gallery_paths,
            },
        )

    @staticmethod
    def _image_matches(
        path: Path,
        image_hash: str,
        extension: str,
    ) -> bool:
        try:
            verified = identify_image_file(path)
        except (OSError, ValueError):
            return False
        return (
            file_extension_matches(path, verified["image_extension"])
            and verified["image_extension"] == extension
            and verified["image_hash"] == image_hash
        )

    @classmethod
    def _select_review_destination(
        cls,
        product_dir: Path,
        safe_code: str,
        image_hash: str,
        extension: str,
    ) -> tuple[Path, bool]:
        destination = product_dir / f"{safe_code}-01{extension}"
        if destination.is_file():
            if cls._image_matches(destination, image_hash, extension):
                return destination, True
            destination = product_dir / f"{safe_code}-01-{image_hash[:16]}{extension}"

        if destination.is_file():
            if cls._image_matches(destination, image_hash, extension):
                return destination, True
            destination = product_dir / (
                f"{safe_code}-01-{image_hash[:16]}-{uuid.uuid4().hex[:8]}{extension}"
            )

        return destination, False

    @classmethod
    def _publish_review_image(
        cls,
        source: Path,
        destination: Path,
        image_hash: str,
        extension: str,
    ) -> Path:
        """Verify a private temporary and publish without replacing existing bytes."""
        temporary = destination.with_name(
            f".{destination.name}.{uuid.uuid4().hex}.tmp"
        )
        temporary_created = False
        try:
            with source.open("rb") as source_stream, temporary.open("xb") as target:
                temporary_created = True
                shutil.copyfileobj(source_stream, target)
            verified = identify_image_file(temporary)

            is_valid = (
                verified["image_hash"] == image_hash
                and verified["image_extension"] == extension
            )
            if not is_valid:
                raise ValueError("La imagen copiada no pasó la verificación de contenido.")

            for _attempt in range(8):
                try:
                    os.link(temporary, destination)
                except FileExistsError:
                    if cls._image_matches(destination, image_hash, extension):
                        return destination
                    destination = destination.with_name(
                        f"{destination.stem}-{uuid.uuid4().hex[:8]}{destination.suffix}"
                    )
                else:
                    return destination
            raise RuntimeError(
                "No se pudo publicar la imagen sin sobrescribir otro archivo."
            )
        finally:
            if temporary_created:
                temporary.unlink(missing_ok=True)

    def _set_product_image(
        self,
        record: dict,
        product,
        action: str,
        manual_path: str | Path | None,
        destination: Path,
        *,
        created_paths: list[Path] | None = None,
    ) -> None:
        image_hash = ImageDownloader.hash_file(destination)
        product.image_path = to_data_relative_path(destination)
        product.image_hash = image_hash
        if action == "replace":
            product.image_url = str(
                record.get("candidate_url", "") or ""
            )
        elif action == "candidate":
            product.image_url = self._candidate_url_for_path(
                record,
                str(manual_path or ""),
            )
        elif action == "manual":
            # A local file has no trustworthy remote representation to revalidate.
            # Leaving the old source URL would let the next full sync overwrite it.
            product.image_url = ""
        else:
            product.image_url = str(record.get("current_url", "") or "")

        # Validators are bound to the exact source representation. A reviewed
        # alternate image must not inherit the old URL's ETag/Last-Modified.
        if (
            image_hash != str(record.get("current_hash", "") or "")
            or product.image_url != str(record.get("current_url", "") or "")
        ):
            product.image_etag = ""
            product.image_last_modified = ""
            product.image_checked_at = ""

        product.gallery_images = self._normalize_identifiable_gallery(
            product,
            created_paths,
        )

    def _cleanup_persisted_image_selection(
        self,
        record: dict,
        manual_path: str | Path | None,
        backup: Path | None,
    ) -> None:
        self._remove_all_staged_candidates(record)
        self._remove_staged_file(str(manual_path or ""))
        if backup is not None:
            backup.unlink(missing_ok=True)

    @staticmethod
    def _cleanup_file_states(states: list[dict]) -> None:
        for state in states:
            backup = state.get("backup")
            if isinstance(backup, Path):
                backup.unlink(missing_ok=True)

    @staticmethod
    def _rollback_file_state(state: dict) -> None:
        # Do not unlink a newly-created canonical image by filename during a
        # rollback: another catalog row/process may already reference it.
        # The caller runs the whitelist-based cleaner only after DB rollback.
        backup = state.get("backup")
        if isinstance(backup, Path):
            try:
                backup.unlink(missing_ok=True)
            except OSError:
                LOGGER.exception("No se pudo eliminar un backup temporal de revisión.")

    def _stage_manual_image(
        self,
        record: dict,
        manual_path: str | Path | None,
    ) -> str:
        source = self._resolve_manual_path(manual_path)
        if source is None or not source.is_file():
            raise ValueError("La imagen seleccionada no existe.")
        try:
            verified = identify_image_file(source)
        except (OSError, ValueError) as error:
            raise ValueError(
                "El archivo seleccionado no contiene una imagen compatible e identificable."
            ) from error

        STAGING_DIR.mkdir(parents=True, exist_ok=True)
        safe_code = ImageDownloader._safe_code(
            str(record.get("code", "image"))
        )
        destination = STAGING_DIR / (
            f"{safe_code}-{uuid.uuid4().hex}{verified['image_extension']}"
        )
        temporary = destination.with_name(
            f"{destination.name}.{uuid.uuid4().hex}.tmp"
        )
        temporary_created = False
        try:
            with source.open("rb") as source_stream, temporary.open("xb") as target:
                temporary_created = True
                shutil.copyfileobj(source_stream, target)
            staged = identify_image_file(temporary)
        except Exception:
            if temporary_created:
                temporary.unlink(missing_ok=True)
            raise

        matches_source = (
            staged["image_hash"] == verified["image_hash"]
            and staged["image_extension"] == verified["image_extension"]
        )
        if not matches_source:
            if temporary_created:
                temporary.unlink(missing_ok=True)
            raise ValueError("La imagen temporal no pasó la verificación.")

        try:
            os.link(temporary, destination)
        except FileExistsError as error:
            raise RuntimeError("Ya existe el archivo temporal de revisión.") from error
        finally:
            if temporary_created:
                temporary.unlink(missing_ok=True)
        return to_data_relative_path(destination)

    @staticmethod
    def _resolve_staged_selection(record: dict, value: str) -> str:
        candidate = ImageReviewService._resolve_staged_path(value)
        if candidate is None or not candidate.is_file():
            return ""
        allowed = {
            str(option.get("path", "") or "")
            for option in list(record.get("candidate_options", []) or [])
        }
        if str(value) not in allowed:
            return ""
        return str(value)


    @staticmethod
    def _resolve_gallery_selection(record: dict, value: str) -> str:
        candidate = ImageReviewService._resolve_gallery_path(value)
        if candidate is None or not candidate.is_file():
            return ""
        allowed = {
            str(option.get("path", "") or "")
            for option in list(record.get("candidate_options", []) or [])
        }
        return value if value in allowed else ""

    @staticmethod
    def _candidate_url_for_path(record: dict, path: str) -> str:
        for option in list(record.get("candidate_options", []) or []):
            if str(option.get("path", "")) == path:
                return str(option.get("url", "") or "")
        return str(record.get("candidate_url", "") or "")

    @staticmethod
    def _remove_staged_candidates_except(
        record: dict,
        protected_paths: set[str],
    ) -> None:
        options = list(record.get("candidate_options", []) or [])
        if options:
            for option in options:
                path = str(option.get("path", "") or "")
                if path not in protected_paths:
                    ImageReviewService._remove_staged_file(path)
            return
        path = str(record.get("candidate_path", "") or "")
        if path not in protected_paths:
            ImageReviewService._remove_staged_file(path)

    @staticmethod
    def _remove_all_staged_candidates(record: dict) -> None:
        options = list(record.get("candidate_options", []) or [])
        if options:
            for option in options:
                ImageReviewService._remove_staged_file(
                    str(option.get("path", "") or "")
                )
            return
        ImageReviewService._remove_staged_file(
            str(record.get("candidate_path", "") or "")
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _read() -> list[dict]:
        if not QUEUE_PATH.is_file():
            return []
        try:
            payload = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)]

    @staticmethod
    def _write(records: list[dict]) -> None:
        QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = QUEUE_PATH.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(records[-2000:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(QUEUE_PATH)

    @staticmethod
    def _resolve_gallery_path(value: str) -> Path | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        candidate = resolve_data_path(raw)
        candidate_resolved = candidate.resolve()
        allowed_roots = (
            resolve_data_path(IMAGE_GALLERY_DIR).resolve(),
            resolve_data_path(IMAGE_PRODUCTS_DIR).resolve(),
        )
        for root in allowed_roots:
            try:
                candidate_resolved.relative_to(root)
            except ValueError:
                continue
            return candidate
        return None

    @staticmethod
    def _resolve_product_image_path(value: str) -> Path | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        candidate = resolve_data_path(raw)
        try:
            candidate.resolve().relative_to(
                resolve_data_path(IMAGE_PRODUCTS_DIR).resolve()
            )
        except ValueError as error:
            raise ValueError(
                "La imagen actual no pertenece al directorio de imágenes del catálogo."
            ) from error
        return candidate

    @staticmethod
    def _resolve_staged_path(value: str) -> Path | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        candidate = resolve_data_path(raw)
        try:
            candidate.resolve().relative_to(STAGING_DIR.resolve())
        except ValueError:
            return None
        return candidate

    @staticmethod
    def _resolve_manual_path(value: str | Path | None) -> Path | None:
        if value is None:
            return None
        candidate = Path(value).expanduser()
        if not candidate.is_absolute() or not candidate.exists():
            return None
        return candidate.resolve()

    @staticmethod
    def _remove_staged_file(value: str) -> None:
        candidate = ImageReviewService._resolve_staged_path(value)
        if candidate is not None:
            candidate.unlink(missing_ok=True)
