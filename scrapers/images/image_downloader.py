from __future__ import annotations

import hashlib
import ipaddress
import os
import time
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from threading import local
from typing import cast
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

import requests

from config.runtime_paths import resolve_data_path, to_data_relative_path
from scrapers.images.image_hash import ImageHash
from scrapers.images.image_paths import (
    IMAGE_EXTENSIONS,
    IMAGE_PRODUCTS_DIR,
    product_image_directory,
    safe_image_code,
)
from scrapers.images.image_validation import (
    file_extension_matches,
    identify_image_bytes,
    identify_image_file,
)

_MAX_IMAGE_BYTES = 20 * 1024 * 1024


class ImageDownloader:
    """Descarga y revalida imágenes sin sobrescribir bytes que sigan activos en BD."""

    def __init__(
        self,
        output_dir: str | Path = IMAGE_PRODUCTS_DIR,
        request_timeout: int = 30,
        max_retries: int = 2,
    ):
        self.output_dir = resolve_data_path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.request_timeout = int(request_timeout)
        self.max_retries = int(max_retries)
        self._thread_local = local()
        if self.request_timeout <= 0:
            raise ValueError("request_timeout debe ser mayor que cero.")
        if self.max_retries <= 0:
            raise ValueError("max_retries debe ser mayor que cero.")

    def _session(self) -> requests.Session:
        """Reutiliza conexiones HTTP dentro de cada hilo sin compartir Session."""
        session = getattr(self._thread_local, "session", None)
        if session is None:
            session = requests.Session()
            self._thread_local.session = session
        return session

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlsplit(str(url or "").strip())
        scheme = parsed.scheme.lower()
        hostname = (parsed.hostname or "").rstrip(".").casefold()
        if (
            scheme not in {"http", "https"}
            or not hostname
            or parsed.username is not None
            or parsed.password is not None
            or (parsed.port is not None and parsed.port != (443 if scheme == "https" else 80))
            or hostname == "localhost"
            or hostname.endswith(".localhost")
            or hostname.endswith(".local")
        ):
            raise ValueError("La URL de imagen no es válida o segura.")
        try:
            address = ipaddress.ip_address(hostname.strip("[]"))
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("La URL de imagen no puede apuntar a una IP privada o reservada.")

    def _request(self, url: str, headers: dict[str, str]) -> requests.Response:
        self._validate_url(url)
        return self._session().get(
            url,
            timeout=self.request_timeout,
            headers=headers,
            stream=True,
            allow_redirects=False,
        )

    @staticmethod
    def _validate_response_url(requested_url: str, response_url: str) -> None:
        ImageDownloader._validate_url(response_url)
        requested = urlsplit(requested_url)
        final = urlsplit(response_url)
        if requested.scheme.lower() == "https" and final.scheme.lower() != "https":
            raise ValueError("La descarga no puede degradarse de HTTPS a HTTP.")

    @staticmethod
    def _read_response_body(response: requests.Response) -> bytes:
        headers = getattr(response, "headers", {}) or {}
        length = str(headers.get("Content-Length", "") or "").strip()
        if length.isdigit() and int(length) > _MAX_IMAGE_BYTES:
            raise ValueError("La imagen supera el límite de 20 MiB.")

        iterator = getattr(response, "iter_content", None)
        if callable(iterator):
            chunks = []
            total = 0
            for chunk in cast(Iterable[bytes], iterator(chunk_size=64 * 1024)):
                if not chunk:
                    continue
                total += len(chunk)
                if total > _MAX_IMAGE_BYTES:
                    raise ValueError("La imagen supera el límite de 20 MiB.")
                chunks.append(chunk)
            return b"".join(chunks)

        body = bytes(getattr(response, "content", b"") or b"")
        if len(body) > _MAX_IMAGE_BYTES:
            raise ValueError("La imagen supera el límite de 20 MiB.")
        return body

    @staticmethod
    def _checked_at() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _sha256_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _verified_extension(data: bytes, content_type: str) -> str:
        """Decodifica la imagen y obtiene su extensión real, sin confiar en la URL."""
        return identify_image_bytes(data, content_type)["image_extension"]

    @staticmethod
    def _response_metadata(response: requests.Response, checked_at: str) -> dict[str, str]:
        headers = getattr(response, "headers", {}) or {}
        return {
            "image_etag": str(headers.get("ETag", "") or "").strip(),
            "image_last_modified": str(headers.get("Last-Modified", "") or "").strip(),
            "image_checked_at": checked_at,
        }

    def _get_with_retries(  # noqa: PLR0912
        self, url: str, headers: dict[str, str]
    ) -> requests.Response:
        last_error = None
        for attempt in range(self.max_retries):
            response = None
            try:
                current_url = url
                current_headers = dict(headers)
                for _ in range(6):
                    self._validate_url(current_url)
                    response = self._request(current_url, current_headers)
                    status_code = int(getattr(response, "status_code", 200) or 200)

                    if status_code in {301, 302, 303, 307, 308}:
                        location = str(
                            (getattr(response, "headers", {}) or {}).get("Location", "")
                            or ""
                        ).strip()
                        if not location:
                            raise requests.exceptions.HTTPError(
                                "Redirección HTTP sin encabezado Location.",
                                response=response,
                            )
                        next_url = urljoin(current_url, location)
                        # Close the streaming response before validating its target.
                        close = getattr(response, "close", None)
                        if callable(close):
                            close()
                        response = None
                        self._validate_response_url(current_url, next_url)
                        # Validators belong to the original resource. Never carry
                        # them to a redirected URL, or a 304 could preserve stale bytes.
                        current_headers.pop("If-None-Match", None)
                        current_headers.pop("If-Modified-Since", None)
                        current_url = next_url
                        continue

                    if status_code == 304:
                        return response
                    response.raise_for_status()
                    if status_code != 200:
                        raise requests.exceptions.HTTPError(
                            f"Estado HTTP inesperado: {status_code}",
                            response=response,
                        )
                    return response

                raise requests.exceptions.TooManyRedirects(
                    "La descarga superó el máximo de redirecciones."
                )
            except requests.exceptions.RequestException as error:
                if response is not None:
                    close = getattr(response, "close", None)
                    if callable(close):
                        close()
                last_error = error
                if not self._is_retryable_error(error):
                    raise
                if attempt < self.max_retries - 1:
                    time.sleep(attempt + 1)

        if last_error:
            raise last_error
        raise RuntimeError("No se pudo descargar la imagen.")

    def _store_verified_body(
        self,
        code: str,
        data: bytes,
        extension: str,
        image_hash: str,
        *,
        position: int | None = None,
    ) -> str:
        safe_code = self._safe_code(code)
        target_dir = (
            product_image_directory(safe_code, root=self.output_dir)
        )
        target_dir.mkdir(parents=True, exist_ok=True)

        if position is None:
            canonical = target_dir / f"{safe_code}-01{extension}"
        else:
            canonical = target_dir / f"{safe_code}-{int(position):02d}{extension}"

        if canonical.is_file():
            try:
                if self.hash_file(canonical) == image_hash:
                    return to_data_relative_path(canonical)
            except OSError:
                pass
            # Preserve the previous DB-referenced bytes until the catalog commit.
            target = target_dir / (
                f"{safe_code}-{int(position or 1):02d}-{image_hash[:16]}{extension}"
            )
        else:
            target = canonical

        if target.exists():
            try:
                if self.hash_file(target) == image_hash:
                    return to_data_relative_path(target)
            except OSError:
                pass
            target = target.with_name(
                f"{target.stem}-{uuid4().hex[:8]}{target.suffix}"
            )

        temporary = target.with_name(f"{target.name}.{uuid4().hex}.tmp")
        temporary_created = False
        try:
            with temporary.open("xb") as stream:
                temporary_created = True
                stream.write(data)
                stream.flush()
            if self.hash_file(temporary) != image_hash:
                raise RuntimeError("La verificación SHA-256 de la descarga falló.")
            target = self._publish_temporary_without_overwrite(
                temporary,
                target,
                image_hash,
                extension,
            )
        finally:
            if temporary_created:
                temporary.unlink(missing_ok=True)
        return to_data_relative_path(target)

    @classmethod
    def _publish_temporary_without_overwrite(
        cls,
        temporary: Path,
        target: Path,
        image_hash: str,
        extension: str,
    ) -> Path:
        """Atomically publish verified bytes without replacing an existing path."""
        for _attempt in range(8):
            try:
                # Same-directory hard link is atomic and fails rather than
                # replacing a path that another worker might already reference.
                os.link(temporary, target)
            except FileExistsError:
                try:
                    verified = cls.verify_image_file(target)
                except (OSError, ValueError):
                    verified = {}
                if (
                    verified.get("image_hash") == image_hash
                    and verified.get("image_extension") == extension
                ):
                    break
                target = target.with_name(
                    f"{target.stem}-{uuid4().hex[:8]}{target.suffix}"
                )
            else:
                return target
        else:
            raise RuntimeError(
                "No se pudo publicar la imagen sin sobrescribir otro archivo."
            )
        return target

    def download_result(self, code: str, url: str) -> dict[str, str]:
        """Descarga una imagen validada a una ruta versionada y devuelve sus metadatos."""
        response = self._get_with_retries(
            url,
            {"User-Agent": "FacundoCatalogManager/1.0"},
        )
        try:
            self._validate_response_url(
                url, str(getattr(response, "url", "") or url)
            )
            body = self._read_response_body(response)
            extension = self._verified_extension(
                body,
                (getattr(response, "headers", {}) or {}).get("Content-Type", ""),
            )
            image_hash = self._sha256_bytes(body)
            checked_at = self._checked_at()
            path = self._store_verified_body(code, body, extension, image_hash)
            return {
                "image_path": path,
                "image_hash": image_hash,
                **self._response_metadata(response, checked_at),
            }
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()

    def revalidate_primary(
        self,
        code: str,
        url: str,
        *,
        current_path: str = "",
        current_hash: str = "",
        etag: str = "",
        last_modified: str = "",
    ) -> dict[str, str | bool]:
        """Realiza GET condicional y repara solo si los bytes/metadata lo requieren."""
        self._validate_url(url)
        old_path = resolve_data_path(current_path) if current_path else None
        old_file_ok = False
        if old_path is not None and old_path.is_file() and current_hash:
            try:
                verified_old = self.verify_image_file(old_path)
                old_file_ok = verified_old["image_hash"] == current_hash
            except (OSError, ValueError):
                old_file_ok = False

        headers = {"User-Agent": "FacundoCatalogManager/1.0"}
        if old_file_ok:
            if etag:
                headers["If-None-Match"] = etag
            if last_modified:
                headers["If-Modified-Since"] = last_modified

        response = self._get_with_retries(url, headers)
        try:
            self._validate_response_url(
                url, str(getattr(response, "url", "") or url)
            )
            status = int(getattr(response, "status_code", 200) or 200)
            checked_at = self._checked_at()
            if status == 304 and old_file_ok and old_path is not None:
                metadata = self._response_metadata(response, checked_at)
                return {
                    "status": "not_modified",
                    "image_path": to_data_relative_path(old_path),
                    "image_hash": current_hash,
                    "image_etag": metadata["image_etag"] or etag,
                    "image_last_modified": metadata["image_last_modified"] or last_modified,
                    "image_checked_at": checked_at,
                }

            if status == 304:
                # A 304 cannot repair a missing/corrupt local object. Retry unconditionally.
                close = getattr(response, "close", None)
                if callable(close):
                    close()
                response = self._get_with_retries(
                    url,
                    {"User-Agent": "FacundoCatalogManager/1.0"},
                )
                status = int(getattr(response, "status_code", 200) or 200)
                if status == 304:
                    raise RuntimeError("El servidor devolvió 304 sin una copia local válida.")

            self._validate_response_url(
                url, str(getattr(response, "url", "") or url)
            )
            body = self._read_response_body(response)
            extension = self._verified_extension(
                body,
                (getattr(response, "headers", {}) or {}).get("Content-Type", ""),
            )
            image_hash = self._sha256_bytes(body)
            metadata = self._response_metadata(response, checked_at)

            if old_file_ok and image_hash == current_hash and old_path is not None:
                return {
                    "status": "unchanged",
                    "image_path": to_data_relative_path(old_path),
                    "image_hash": current_hash,
                    **metadata,
                }

            path = self._store_verified_body(code, body, extension, image_hash)
            return {
                "status": "downloaded",
                "image_path": path,
                "image_hash": image_hash,
                **metadata,
            }
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()

    def download(self, code: str, url: str) -> str:
        """Compatibilidad con consumidores anteriores: devuelve únicamente la ruta."""
        result = self.download_result(code, url)
        return result["image_path"]

    def download_staged(
        self,
        code: str,
        url: str,
        staging_dir: str | Path,
    ) -> str:
        """Descarga una opción de revisión sin sobrescribir la imagen vigente."""
        staging_path = resolve_data_path(staging_dir)
        staging_path.mkdir(parents=True, exist_ok=True)
        response = self._get_with_retries(
            url,
            {"User-Agent": "FacundoCatalogManager/1.0"},
        )
        try:
            self._validate_response_url(
                url, str(getattr(response, "url", "") or url)
            )
            body = self._read_response_body(response)
            extension = self._verified_extension(
                body,
                (getattr(response, "headers", {}) or {}).get("Content-Type", ""),
            )
            target = staging_path / (
                f"{self._safe_code(code)}-{uuid4().hex}{extension}"
            )
            temporary = target.with_name(f"{target.name}.tmp")
            temporary_created = False
            try:
                with temporary.open("xb") as stream:
                    temporary_created = True
                    stream.write(body)
                    stream.flush()
                image_hash = self._sha256_bytes(body)
                if self.hash_file(temporary) != image_hash:
                    raise RuntimeError("La verificación SHA-256 de la descarga falló.")
                target = self._publish_temporary_without_overwrite(
                    temporary,
                    target,
                    image_hash,
                    extension,
                )
            finally:
                if temporary_created:
                    temporary.unlink(missing_ok=True)
            return to_data_relative_path(target)
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()

    @staticmethod
    def _is_retryable_error(error):
        if isinstance(
            error,
            (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ),
        ):
            return True

        if isinstance(error, requests.exceptions.HTTPError):
            response = getattr(error, "response", None)
            status_code = getattr(response, "status_code", None)
            return status_code == 429 or (
                isinstance(status_code, int) and status_code >= 500
            )

        return False

    @staticmethod
    def _safe_code(code: str) -> str:
        return safe_image_code(code)

    @staticmethod
    def _extension(url: str, content_type: str) -> str:
        suffix = Path(url.split("?", 1)[0]).suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            return suffix

        mapping = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }
        return mapping.get(content_type.split(";", 1)[0].lower(), ".jpg")

    def download_gallery(
        self,
        code: str,
        url: str,
        position: int,
        output_dir: str | Path,
    ) -> str:
        """Descarga una imagen de galería manteniendo los bytes anteriores protegidos."""
        target_root = resolve_data_path(output_dir)
        response = self._get_with_retries(
            url,
            {"User-Agent": "FacundoCatalogManager/1.0"},
        )
        try:
            self._validate_response_url(
                url, str(getattr(response, "url", "") or url)
            )
            body = self._read_response_body(response)
            extension = self._verified_extension(
                body,
                (getattr(response, "headers", {}) or {}).get("Content-Type", ""),
            )
            image_hash = self._sha256_bytes(body)
            safe_code = self._safe_code(code)
            target_root.mkdir(parents=True, exist_ok=True)
            canonical = target_root / f"{safe_code}-{int(position):02d}{extension}"
            try:
                existing = self.verify_image_file(canonical)
            except (OSError, ValueError):
                existing = {}
            if (
                existing.get("image_hash") == image_hash
                and existing.get("image_extension") == extension
            ):
                return to_data_relative_path(canonical)

            if canonical.exists():
                canonical = target_root / (
                    f"{safe_code}-{int(position):02d}-{image_hash[:16]}{extension}"
                )
            if canonical.exists():
                try:
                    existing = self.verify_image_file(canonical)
                except (OSError, ValueError):
                    existing = {}
                if (
                    existing.get("image_hash") == image_hash
                    and existing.get("image_extension") == extension
                ):
                    return to_data_relative_path(canonical)
                canonical = canonical.with_name(
                    f"{canonical.stem}-{uuid4().hex[:8]}{canonical.suffix}"
                )

            temporary = canonical.with_name(f"{canonical.name}.{uuid4().hex}.tmp")
            temporary_created = False
            try:
                with temporary.open("xb") as stream:
                    temporary_created = True
                    stream.write(body)
                    stream.flush()
                if self.hash_file(temporary) != image_hash:
                    raise RuntimeError("La verificación SHA-256 de la galería falló.")
                canonical = self._publish_temporary_without_overwrite(
                    temporary,
                    canonical,
                    image_hash,
                    extension,
                )
            finally:
                if temporary_created:
                    temporary.unlink(missing_ok=True)
            return to_data_relative_path(canonical)
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()

    @classmethod
    def verify_image_file(cls, path: str | Path) -> dict[str, str]:
        """Decodifica la imagen local y confirma que su sufijo corresponda al formato."""
        image_path = Path(path)
        suffix = image_path.suffix.lower()
        if suffix not in IMAGE_EXTENSIONS:
            raise ValueError("La extensión local no es compatible.")
        verified = identify_image_file(image_path)
        detected = verified["image_extension"]
        if not file_extension_matches(image_path, detected):
            raise ValueError("La extensión local no coincide con el contenido de imagen.")
        return {
            "image_hash": verified["image_hash"],
            "image_extension": detected,
        }

    @staticmethod
    def hash_file(path: str | Path) -> str:
        image_path = Path(path)
        if not image_path.exists():
            raise FileNotFoundError(image_path)
        return ImageHash().calculate(image_path)
