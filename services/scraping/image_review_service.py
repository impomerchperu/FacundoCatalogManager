from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from config.runtime_paths import DATA_DIR, resolve_data_path, to_data_relative_path
from repositories.product_repository import ProductRepository
from scrapers.images.image_downloader import ImageDownloader
from scrapers.images.image_paths import IMAGE_EXTENSIONS, IMAGE_PRODUCTS_DIR

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
                if record.get("batch_id") == batch_id and record.get("status") == "staged":
                    self._remove_staged_file(record.get("candidate_path", ""))
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
    ) -> dict | None:
        if not candidate_hash:
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
                    self._remove_staged_file(candidate_path)
                    return None

            normalized_code = str(code).casefold()
            for existing_record in records:
                if (
                    str(existing_record.get("code", "")).casefold()
                    == normalized_code
                    and existing_record.get("status") in {"pending", "staged"}
                ):
                    self._remove_staged_file(
                        existing_record.get("candidate_path", "")
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
                "candidate_path": str(candidate_path or ""),
                "candidate_hash": str(candidate_hash or ""),
                "candidate_url": str(candidate_url or ""),
            }
            records.append(record)
            self._write(records)
            return dict(record)

    def pending(self) -> list[dict]:
        with self._lock:
            records = self._read()
            changed = False
            pending: list[dict] = []
            for record in records:
                if record.get("status") != "pending":
                    continue
                candidate = self._resolve_staged_path(record.get("candidate_path", ""))
                if candidate is None or not candidate.is_file():
                    record["status"] = "resolved"
                    record["resolution"] = "missing_candidate"
                    record["updated_at"] = self._now()
                    changed = True
                    continue
                pending.append(dict(record))
            if changed:
                self._write(records)
            return pending

    def discard_staged(self, path: str) -> None:
        self._remove_staged_file(path)

    def apply_selection(
        self,
        review_id: str,
        action: str,
        manual_path: str | Path | None = None,
    ) -> dict:
        action = str(action).strip().casefold()
        if action not in {"keep", "replace", "manual"}:
            raise ValueError("Acción de revisión no válida.")

        with self._lock:
            records = self._read()
            record = self._find_pending_record(records, review_id)
            product = self.repository.get_by_code(str(record.get("code", "")))
            if product is None:
                raise ValueError(
                    "No existe el producto "
                    f"{record.get('code', '')} en la base de datos."
                )

            if action == "keep":
                result = self._keep_current(record, product)
            else:
                result = self._apply_selected_image(
                    record,
                    product,
                    action,
                    manual_path,
                )

            record["status"] = "resolved"
            record["resolution"] = action
            record["updated_at"] = self._now()
            self._write(records)
            return result

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
        self._remove_staged_file(record.get("candidate_path", ""))
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
    ) -> dict:
        source = (
            self._resolve_staged_path(record.get("candidate_path", ""))
            if action == "replace"
            else self._resolve_manual_path(manual_path)
        )
        if source is None or not source.is_file():
            raise ValueError("La imagen seleccionada no existe.")
        if source.suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValueError(
                "El archivo seleccionado no es una imagen compatible."
            )

        image_products_dir = resolve_data_path(IMAGE_PRODUCTS_DIR)
        image_products_dir.mkdir(parents=True, exist_ok=True)
        destination = image_products_dir / (
            f"{ImageDownloader._safe_code(str(product.code))}"
            f"{source.suffix.lower()}"
        )
        old_path = resolve_data_path(
            str(record.get("current_path", "") or "")
        )
        backup = None
        if old_path == destination and destination.is_file():
            backup = destination.with_name(destination.name + ".review-backup")
            shutil.copy2(destination, backup)

        temporary = destination.with_name(destination.name + ".review-tmp")
        try:
            shutil.copy2(source, temporary)
            temporary.replace(destination)
            image_hash = ImageDownloader.hash_file(destination)
            product.image_path = to_data_relative_path(destination)
            product.image_hash = image_hash
            product.image_url = (
                str(record.get("candidate_url", "") or "")
                if action == "replace"
                else str(record.get("current_url", "") or "")
            )
            self.repository.update(product)
        except (OSError, ValueError, RuntimeError):
            temporary.unlink(missing_ok=True)
            if backup is not None and backup.is_file():
                backup.replace(destination)
            elif old_path != destination and destination.is_file():
                destination.unlink()
            raise
        finally:
            if backup is not None:
                backup.unlink(missing_ok=True)

        self._remove_staged_file(record.get("candidate_path", ""))
        return {
            "code": product.code,
            "action": action,
            "changed": True,
            "image_path": product.image_path,
            "image_hash": product.image_hash,
            "image_url": product.image_url,
        }

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