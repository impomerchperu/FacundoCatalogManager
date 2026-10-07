from __future__ import annotations

import contextlib
import copy
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import cast

import requests

from config.runtime_paths import DATA_DIR, resolve_data_path, to_data_relative_path
from models.product import Product
from repositories.product_repository import ProductRepository
from scrapers.images.image_downloader import ImageDownloader
from scrapers.images.image_paths import (
    IMAGE_EXTENSIONS,
    IMAGE_GALLERY_DIR,
    IMAGE_PRODUCTS_DIR,
)

QUEUE_PATH = DATA_DIR / "image_review_queue.json"
STAGING_DIR = DATA_DIR / "image_review_staging"


class ImageReviewService:
    """Gestiona candidatos de imagen sin sobrescribir la imagen vigente."""

    def __init__(self, repository: ProductRepository | None = None) -> None:
        self.repository = repository or ProductRepository()
        self._lock = Lock()
        self._active_batch: str | None = None

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
                }
            )
        return staged

    def register_candidate(
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
        normalized_kind = "gallery" if str(kind or "").strip().casefold() == "gallery" else "replacement"
        if not candidate_hash and not allow_manual_only:
            if normalized_kind == "gallery":
                self._remove_gallery_file(candidate_path)
            else:
                self._remove_staged_file(candidate_path)
            return None

        with self._lock:
            records = self._read()
            for record in records:
                if (
                    str(record.get("code", "")).casefold() == str(code).casefold()
                    and str(record.get("candidate_hash", "")) == candidate_hash
                    and record.get("status") in {"pending", "resolved", "staged"}
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
                        "generic": bool(option.get("generic", False)),
                        "source": str(option.get("source", "") or ""),
                        "gallery": bool(option.get("gallery", normalized_kind == "gallery")),
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
                        "generic": False,
                        "source": "",
                    }
                ]

            primary = (
                next(
                    (
                        option
                        for option in options
                        if option["path"] == str(candidate_path or "")
                    ),
                    options[0],
                )
                if options
                else {
                    "url": "",
                    "path": "",
                    "hash": "",
                    "score": 0,
                    "exact_code": False,
                    "generic": False,
                    "source": "",
                }
            )

            normalized_code = str(code).casefold()
            for existing_record in records:
                if (
                    str(existing_record.get("code", "")).casefold()
                    == normalized_code
                    and existing_record.get("status") in {"pending", "staged"}
                ):
                    if str(existing_record.get("kind", "replacement")) != "gallery":
                        self._remove_all_staged_candidates(existing_record)
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
                "kind": normalized_kind,
                "manual_only": bool(allow_manual_only and not options),
            }
            records.append(record)
            self._write(records)
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

    def apply_selection(
        self,
        review_id: str,
        action: str,
        manual_path: str | Path | None = None,
    ) -> dict:
        """Registra una selección sin modificar todavía el catálogo."""
        action = str(action).strip().casefold()
        if action not in {
            "keep",
            "replace",
            "candidate",
            "manual",
            "accept_gallery",
            "dismiss_gallery",
        }:
            raise ValueError("Acción de revisión no válida.")

        with self._lock:
            records = self._read()
            record = self._find_available_record(records, review_id)

            if record.get("status") == "staged":
                self._store_deferred_selection(record, action, manual_path)
                self._write(records)
                return {
                    "code": str(record.get("code", "")),
                    "action": action,
                    "changed": False,
                    "selected": True,
                }

            if record.get("kind") == "gallery":
                result = self._apply_gallery_resolution(record, action)
                record["status"] = "resolved"
                record["resolution"] = action
                record["updated_at"] = self._now()
                self._write(records)
                return result

            if action in {"keep", "replace"}:
                product = self.repository.get_by_code(
                    str(record.get("code", "")),
                )
                if product is None:
                    raise ValueError(
                        "No existe el producto "
                        f"{record.get('code', '')} en la base de datos."
                    )
                result: dict[str, object] = (
                    self._keep_current(record, product)
                    if action == "keep"
                    else cast(
                        dict[str, object],
                        self._apply_selected_image(
                            record,
                            product,
                            action,
                            manual_path,
                        ),
                    )
                )
                record["status"] = "resolved"
                record["resolution"] = action
                record["updated_at"] = self._now()
                self._write(records)
                return result

            previous_action = str(
                record.get("selected_action", "") or ""
            ).casefold()
            previous_path = str(
                record.get("selected_path", "") or ""
            )

            selected_path = ""
            selected_url = ""
            if action == "candidate":
                selected_path = self._resolve_staged_selection(
                    record,
                    str(manual_path or ""),
                )
                selected_url = self._candidate_url_for_path(
                    record,
                    selected_path,
                )
                if not selected_path:
                    raise ValueError("La imagen seleccionada no existe.")
            elif action == "replace":
                selected_path = self._resolve_staged_selection(
                    record,
                    str(record.get("candidate_path", "") or ""),
                )
                selected_url = str(
                    record.get("candidate_url", "") or ""
                ).strip()
                if not selected_path:
                    raise ValueError("La imagen detectada no existe.")
            elif action == "manual":
                selected_path = self._stage_manual_image(
                    record,
                    manual_path,
                )
            elif action == "keep":
                selected_path = ""
                selected_url = str(
                    record.get("current_url", "") or ""
                )

            if (
                previous_action == "manual"
                and previous_path
                and previous_path != selected_path
            ):
                self._remove_staged_file(previous_path)

            record["selected_action"] = action
            record["selected_path"] = selected_path
            record["selected_url"] = selected_url
            record["updated_at"] = self._now()
            self._write(records)
            return {
                "code": str(record.get("code", "")),
                "action": action,
                "changed": False,
                "selected": True,
            }

    def _store_deferred_selection(
        self,
        record: dict,
        action: str,
        manual_path: str | Path | None,
    ) -> None:
        normalized = str(action or "").strip().casefold()
        if str(record.get("kind", "replacement")) == "gallery":
            if normalized not in {"accept_gallery", "dismiss_gallery"}:
                raise ValueError("Acción de galería no válida.")
            record["selected_action"] = normalized
            record["selected_path"] = ""
            record["selected_url"] = ""
            record["updated_at"] = self._now()
            return

        if normalized not in {"keep", "replace", "candidate", "manual"}:
            raise ValueError("Acción de revisión no válida.")

        selected_path = ""
        selected_url = ""
        if normalized == "candidate":
            selected_path = self._resolve_staged_selection(
                record,
                str(manual_path or ""),
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
            self.repository.update(product)
            for option in options:
                self._remove_gallery_file(
                    str(option.get("path", "") or "")
                )

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
                            self._keep_current(product, record)
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
                    results.append(result)
                except (OSError, ValueError, RuntimeError):
                    continue

            if results:
                self._write(records)
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
            ]
            if len(selected_records) != len(ids):
                raise ValueError(
                    "Hay revisiones seleccionadas que ya no están disponibles."
                )
            if any(
                not str(record.get("selected_action", "") or "").strip()
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
                result, file_state, product = self._prepare_selected_record(record)
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
            raise

        # El catálogo y la cola ya están confirmados. La limpieza es posterior
        # para evitar perder candidatos antes de un commit exitoso.
        try:
            self._cleanup_selected_records(selected_records)
            self._cleanup_file_states(prepared)
        except OSError:
            pass

        return results

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
            self._remove_all_staged_candidates(record)
            selected_path = str(
                record.get("selected_path", "") or ""
            )
            if selected_path:
                self._remove_staged_file(selected_path)

    @staticmethod
    def _find_pending_record(records: list[dict], review_id: str) -> dict:
        for record in records:
            if record.get("id") == review_id and record.get("status") == "pending":
                return record
        raise ValueError("La revisión de imagen ya no está disponible.")

    def _keep_current(self, record: dict, product) -> dict:
        product.image_path = str(record.get("current_path", "") or "")
        product.image_hash = str(record.get("current_hash", "") or "")
        product.image_url = str(record.get("current_url", "") or "")
        self.repository.update(product)
        self._remove_all_staged_candidates(record)
        return {
            "code": product.code,
            "action": "keep",
            "changed": False,
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

        source = self._resolve_selected_source(record, action, manual_path)
        if source is None or not source.is_file():
            raise ValueError("La imagen seleccionada no existe.")
        if source.suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValueError(
                "El archivo seleccionado no es una imagen compatible."
            )

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

    def _apply_keep_selection(
        self,
        record: dict,
        product,
        persist: bool,
    ) -> tuple[dict, dict] | dict:
        product.image_path = str(record.get("current_path", "") or "")
        product.image_hash = str(record.get("current_hash", "") or "")
        product.image_url = str(record.get("current_url", "") or "")
        result = {
            "code": product.code,
            "action": "keep",
            "changed": False,
        }
        if persist:
            self.repository.update(product)
            self._remove_all_staged_candidates(record)
            return result
        return result, {
            "destination": None,
            "backup": None,
            "destination_existed": False,
        }

    def _resolve_selected_source(
        self,
        record: dict,
        action: str,
        manual_path: str | Path | None,
    ) -> Path | None:
        if action == "candidate":
            selected = self._resolve_staged_selection(
                record,
                str(manual_path or ""),
            )
            return self._resolve_staged_path(selected) if selected else None
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
        image_products_dir = resolve_data_path(IMAGE_PRODUCTS_DIR)
        image_products_dir.mkdir(parents=True, exist_ok=True)
        destination = image_products_dir / (
            f"{ImageDownloader._safe_code(str(product.code))}"
            f"{source.suffix.lower()}"
        )
        destination_existed = destination.is_file()
        backup = self._create_image_backup(destination, destination_existed)
        temporary = destination.with_name(
            f"{destination.name}.{uuid.uuid4().hex}.review-tmp"
        )
        try:
            shutil.copy2(source, temporary)
            temporary.replace(destination)
            self._set_product_image(
                record,
                product,
                action,
                manual_path,
                destination,
            )
            if persist:
                self.repository.update(product)
        except (OSError, ValueError, RuntimeError):
            temporary.unlink(missing_ok=True)
            self._restore_image_backup(
                destination,
                backup,
                destination_existed,
            )
            raise

        if persist and cleanup:
            self._cleanup_persisted_image_selection(record, manual_path, backup)

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
                "backup": backup,
                "destination_existed": destination_existed,
            },
        )

    @staticmethod
    def _create_image_backup(
        destination: Path,
        destination_existed: bool,
    ) -> Path | None:
        if not destination_existed:
            return None
        backup = destination.with_name(
            f"{destination.name}.{uuid.uuid4().hex}.review-backup"
        )
        shutil.copy2(destination, backup)
        return backup

    def _set_product_image(
        self,
        record: dict,
        product,
        action: str,
        manual_path: str | Path | None,
        destination: Path,
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
        else:
            product.image_url = str(record.get("current_url", "") or "")

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
    def _restore_image_backup(
        destination: Path,
        backup: Path | None,
        destination_existed: bool,
    ) -> None:
        if backup is not None and backup.is_file():
            backup.replace(destination)
        elif not destination_existed and destination.is_file():
            destination.unlink()

    @staticmethod
    def _rollback_file_state(state: dict) -> None:
        destination = state.get("destination")
        backup = state.get("backup")
        existed = bool(state.get("destination_existed", False))
        if not isinstance(destination, Path):
            return
        try:
            ImageReviewService._restore_image_backup(
                destination,
                backup if isinstance(backup, Path) else None,
                existed,
            )
        except OSError:
            pass
        finally:
            if backup is not None and isinstance(backup, Path):
                backup.unlink(missing_ok=True)

    def _stage_manual_image(
        self,
        record: dict,
        manual_path: str | Path | None,
    ) -> str:
        source = self._resolve_manual_path(manual_path)
        if source is None or not source.is_file():
            raise ValueError("La imagen seleccionada no existe.")
        if source.suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValueError(
                "El archivo seleccionado no es una imagen compatible."
            )
        STAGING_DIR.mkdir(parents=True, exist_ok=True)
        safe_code = ImageDownloader._safe_code(
            str(record.get("code", "image"))
        )
        destination = STAGING_DIR / (
            f"{safe_code}-{uuid.uuid4().hex}{source.suffix.lower()}"
        )
        shutil.copy2(source, destination)
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
    def _candidate_url_for_path(record: dict, path: str) -> str:
        for option in list(record.get("candidate_options", []) or []):
            if str(option.get("path", "")) == path:
                return str(option.get("url", "") or "")
        return str(record.get("candidate_url", "") or "")

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
        try:
            candidate.resolve().relative_to(
                resolve_data_path(IMAGE_GALLERY_DIR).resolve()
            )
        except ValueError:
            return None
        return candidate

    @staticmethod
    def _remove_gallery_file(value: str) -> None:
        candidate = ImageReviewService._resolve_gallery_path(value)
        if candidate is not None:
            candidate.unlink(missing_ok=True)

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
