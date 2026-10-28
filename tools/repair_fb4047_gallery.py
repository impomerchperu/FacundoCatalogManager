from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from config.runtime_paths import DATABASE_PATH, resolve_data_path
from database.db_manager import DBManager
from models.scraping.detail_description_policy import (
    has_technical_detail,
    is_complete_detail,
    normalize_detail_text,
)
from models.scraping.scraped_product import ScrapedProduct
from repositories.product_repository import ProductRepository
from scrapers.browser import Browser
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.collectors.resilient_category_scraper import ResilientCategoryScraper
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.product_card_extractor import ProductCardExtractor
from scrapers.extractors.product_extractor import ProductExtractor
from scrapers.images.image_downloader import ImageDownloader
from scrapers.images.image_paths import IMAGE_PRODUCTS_DIR
from services.scraping.product_gallery_sync_service import (
    ProductGallerySyncService,
)

PRODUCT_CODE = "FB-4047"
PRODUCT_NAME = "Foco Antiestrés"
PRODUCT_URL = "https://stock.importacionesfacundo.com/producto/foco-antiestres/"
CATEGORY_URL = (
    "https://stock.importacionesfacundo.com/categoria-producto/"
    "articulos-de-antiestres/"
)
CATEGORY_NAME = "Artículos Antiestrés"


class _CapturedDetailBrowser:
    """Replay the live HTML already fetched for the isolated product run."""

    def __init__(self, url: str, html: str) -> None:
        self.url = url.rstrip("/").casefold()
        self.html = html

    def get_uncached(self, url: str) -> str:
        if str(url or "").rstrip("/").casefold() != self.url:
            raise RuntimeError(f"URL fuera del alcance de FB-4047: {url}")
        return self.html

    def get(self, url: str, *, force_revalidate: bool = False) -> str:
        return self.get_uncached(url)


def _unique_gallery_candidates(product: Any) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in list(getattr(product, "image_candidates", []) or []):
        if not isinstance(candidate, dict):
            continue
        if not candidate.get("gallery_container") or candidate.get("generic"):
            continue
        url = str(candidate.get("url") or "").strip()
        if not url or url.casefold() in seen:
            continue
        seen.add(url.casefold())
        selected.append(dict(candidate))
    return selected


def _gallery_urls(gallery: list[dict[str, Any]]) -> list[str]:
    return [
        url
        for item in gallery
        if (url := str(item.get("url") or "").strip())
    ]


def _candidate_coverage(
    candidate_urls: list[str],
    gallery: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized_candidates = list(
        dict.fromkeys(url.strip().casefold() for url in candidate_urls if url.strip())
    )
    normalized_gallery = {
        url.casefold() for url in _gallery_urls(gallery) if url.strip()
    }
    return {
        "candidate_count": len(normalized_candidates),
        "stored_gallery_count": len(normalized_gallery),
        "missing_urls": [
            url for url in candidate_urls if url.strip().casefold() not in normalized_gallery
        ],
        "all_candidates_stored": bool(normalized_candidates)
        and set(normalized_candidates).issubset(normalized_gallery),
    }



def _gallery_signature(gallery: list[dict[str, Any]]) -> tuple[tuple[str, str, str, int], ...]:
    return tuple(
        (
            str(item.get("url") or "").strip().casefold(),
            str(item.get("image_path") or "").strip().replace("\\\\", "/").casefold(),
            str(item.get("image_hash") or "").strip().casefold(),
            int(item.get("position", 0) or 0),
        )
        for item in gallery
        if isinstance(item, dict)
    )

def _verify_gallery_files(
    gallery: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    checked: list[dict[str, Any]] = []
    for position, item in enumerate(gallery, start=1):
        raw_path = str(item.get("image_path", item.get("path", "")) or "").strip()
        if not raw_path:
            raise RuntimeError(f"La imagen de galería #{position} no tiene ruta local.")
        path = resolve_data_path(raw_path)
        if not path.is_file():
            raise RuntimeError(f"No existe el archivo local de la imagen #{position}: {path}")
        verified = ImageDownloader.verify_image_file(path)
        actual_hash = str(verified["image_hash"])
        expected_hash = str(item.get("image_hash") or "").strip()
        if expected_hash and actual_hash.casefold() != expected_hash.casefold():
            raise RuntimeError(
                f"SHA-256 no coincide para {path}: DB={expected_hash}, archivo={actual_hash}"
            )
        checked.append({
            "position": int(item.get("position", position) or position),
            "url": str(item.get("url") or ""),
            "image_path": str(path),
            "format": verified["image_extension"].lstrip(".").upper(),
            "bytes": path.stat().st_size,
            "sha256": actual_hash,
            "hash_matches_record": not expected_hash
            or actual_hash.casefold() == expected_hash.casefold(),
        })
    if not checked:
        raise RuntimeError("La galería resultante está vacía.")
    return checked


def _backup_database(db_path: Path) -> Path:
    if not db_path.is_file():
        raise FileNotFoundError(f"No existe la base de datos del catálogo: {db_path}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = Path(tempfile.gettempdir()) / f"FCM_catalog_before_FB4047_{stamp}.db"
    if backup_path.exists():
        raise FileExistsError(f"El backup ya existe y no se sobrescribirá: {backup_path}")
    source = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True, timeout=30)
    destination = sqlite3.connect(backup_path, timeout=30)
    try:
        source.backup(destination)
        check = destination.execute("PRAGMA integrity_check").fetchone()
        if not check or str(check[0]).casefold() != "ok":
            raise RuntimeError(f"El backup SQLite no pasó integrity_check: {check}")
        destination.commit()
    finally:
        destination.close()
        source.close()
    return backup_path


def _snapshot_files(directory: Path) -> set[Path]:
    if not directory.is_dir():
        return set()
    return {path.resolve() for path in directory.rglob("*") if path.is_file()}


def _remove_new_files(directory: Path, before: set[Path]) -> None:
    if not directory.exists():
        return
    for path in sorted(
        (item for item in directory.rglob("*") if item.is_file()),
        reverse=True,
    ):
        if path.resolve() not in before:
            path.unlink(missing_ok=True)
    for path in sorted(
        (item for item in directory.rglob("*") if item.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        with suppress(OSError):
            path.rmdir()


def _collect_category_target() -> tuple[str, Any]:
    browser = Browser(request_timeout=30, max_retries=2, http_workers=2)
    collector: ProductCollectionScraper | None = None
    try:
        category_scraper = ResilientCategoryScraper(browser=browser)
        collector = ProductCollectionScraper(
            category_scraper,
            ProductCardExtractor(),
            CategoryProductExtractor(),
            ProductExtractor(),
            max_workers=1,
            category_page_workers=1,
        )
        items = collector.collect_category(CATEGORY_URL)
        for card, page_url, product in items:
            code = str(getattr(product, "code", "") or "").strip().upper()
            if code != PRODUCT_CODE:
                continue
            name = str(getattr(product, "name", "") or "").strip()
            if "foco" not in name.casefold():
                raise RuntimeError(
                    f"La categoría identificó {PRODUCT_CODE}, pero el nombre fue {name!r}."
                )
            detail_url = collector._card_detail_url(card, page_url, product) or PRODUCT_URL
            if detail_url.rstrip("/").casefold() != PRODUCT_URL.rstrip("/").casefold():
                raise RuntimeError(
                    f"URL inesperada para {PRODUCT_CODE}; se rechaza el destino: {detail_url}"
                )
            return detail_url, product
        raise RuntimeError(
            f"La categoría no identificó {PRODUCT_CODE} por código de producto."
        )
    finally:
        if collector is not None:
            collector.close()
        else:
            browser.close()


def _fetch_live_detail(url: str) -> tuple[str, Any, list[dict[str, Any]]]:
    browser = Browser(request_timeout=30, max_retries=2, http_workers=2)
    try:
        html = browser.get_uncached(url)
    finally:
        browser.close()
    if not isinstance(html, str) or not html.strip():
        raise RuntimeError("La ficha live devolvió HTML vacío.")
    extracted = ProductExtractor().extract(
        BeautifulSoup(html, "lxml"),
        url=url,
        category=CATEGORY_NAME,
    )
    code = str(getattr(extracted, "code", "") or "").strip().upper()
    if code != PRODUCT_CODE:
        raise RuntimeError(
            f"La ficha live devolvió el código {code!r}, no {PRODUCT_CODE!r}."
        )
    detail = normalize_detail_text(getattr(extracted, "description", ""))
    if not has_technical_detail(detail) or not is_complete_detail(detail):
        raise RuntimeError(
            "El detalle live no supera la validación de contenido técnico completo."
        )
    candidates = _unique_gallery_candidates(extracted)
    if not candidates:
        raise RuntimeError(
            "El HTML live no expone imágenes válidas dentro del contenedor de galería."
        )
    return html, extracted, candidates


def repair(*, apply: bool) -> dict[str, Any]:  # noqa: PLR0912
    if not apply:
        raise ValueError("La actualización requiere el argumento explícito --apply.")

    db_path = Path(DATABASE_PATH).resolve()
    backup_path = _backup_database(db_path)
    db = DBManager(db_path)
    repository = ProductRepository(db)
    existing = repository.get_by_code(PRODUCT_CODE)
    if existing is None:
        db.close()
        raise RuntimeError(f"No existe {PRODUCT_CODE} en {db_path}.")
    if "foco" not in str(existing.name or "").casefold():
        db.close()
        raise RuntimeError(
            f"El registro existente {PRODUCT_CODE} no tiene el nombre esperado: {existing.name!r}"
        )

    product_dir = resolve_data_path(IMAGE_PRODUCTS_DIR) / PRODUCT_CODE
    files_before = _snapshot_files(product_dir)
    report: dict[str, Any] = {
        "product_code": PRODUCT_CODE,
        "product_name": existing.name,
        "database": str(db_path),
        "backup": str(backup_path),
        "database_write_scope": [PRODUCT_CODE],
        "database_writes": False,
        "catalog_full_sync": False,
        "live_url": PRODUCT_URL,
        "status": "started",
        "errors": [],
    }
    committed = False

    try:
        detail_url, category_product = _collect_category_target()
        category_name = str(getattr(category_product, "name", "") or "").strip()
        category_detail = str(
            getattr(category_product, "description", "") or ""
        ).strip()
        category_image_url = str(
            getattr(category_product, "image_url", "") or ""
        ).strip()
        report["category"] = {
            "name": category_name,
            "detail": category_detail,
            "detail_complete": is_complete_detail(category_detail),
            "primary_image_url": category_image_url,
            "identity_matched_by_code": True,
        }

        html, live_product, source_candidates = _fetch_live_detail(detail_url)
        source_urls = [str(item["url"]).strip() for item in source_candidates]
        report["live_extraction"] = {
            "name": str(getattr(live_product, "name", "") or ""),
            "page_title_identity_valid": (
                "foco" in str(getattr(live_product, "name", "") or "").casefold()
            ),
            "code": str(getattr(live_product, "code", "") or ""),
            "detail": normalize_detail_text(getattr(live_product, "description", "")),
            "gallery_candidates": [
                {
                    "position": position,
                    "url": str(item["url"]),
                    "source": str(item.get("source") or ""),
                }
                for position, item in enumerate(source_candidates, start=1)
            ],
        }

        # Preserve the previously stored Detail when it is already complete.
        # If it is incomplete, repair it from the complete, code-matched source page.
        current_detail = str(existing.description or "").strip()
        live_detail = normalize_detail_text(
            getattr(live_product, "description", ""),
            preserve_boundaries=True,
        )
        detail_to_store = current_detail
        if not has_technical_detail(current_detail) or not is_complete_detail(current_detail):
            detail_to_store = live_detail
        if not has_technical_detail(detail_to_store) or not is_complete_detail(detail_to_store):
            raise RuntimeError("No hay un Detail técnico completo y seguro para persistir.")  # noqa: TRY301

        scraped = ScrapedProduct(
            source="importacionesfacundo",
            url=detail_url,
            code=PRODUCT_CODE,
            name=existing.name,
            category=existing.category or CATEGORY_NAME,
            description=detail_to_store,
            stock=existing.stock,
            price=existing.price,
            price_sample=existing.price_sample,
            price_hundred=existing.price_hundred,
            price_thousand=existing.price_thousand,
            color_stock=dict(existing.color_stock),
            image_url=existing.image_url,
            image_path=existing.image_path,
            image_hash=existing.image_hash,
            gallery_images=[dict(item) for item in existing.gallery_images],
        )
        # The sync service reparses the live HTML with the project's production
        # extractor, then downloads and validates every explicit gallery candidate.
        service = ProductGallerySyncService(
            browser=_CapturedDetailBrowser(detail_url, html),
            product_extractor=ProductExtractor(),
            image_downloader=ImageDownloader(),
            refresh_existing=True,
        )

        synced = service._sync_product(scraped, existing)
        synced_gallery = [
            dict(item)
            for item in list(getattr(synced, "gallery_images", []) or [])
            if isinstance(item, dict)
        ]
        coverage = _candidate_coverage(source_urls, synced_gallery)
        verified_files = _verify_gallery_files(synced_gallery)
        report["download_verification"] = {
            **coverage,
            "verified_file_count": len(verified_files),
            "verified_files": verified_files,
        }
        if not coverage["all_candidates_stored"] or coverage["missing_urls"]:
            missing = coverage["missing_urls"]
            raise RuntimeError(  # noqa: TRY301
                "No se guardaron todas las imágenes fuente de FB-4047. "
                f"URLs pendientes: {missing!r}. No se modificará SQLite."
            )
        if len(verified_files) != len(source_urls):
            raise RuntimeError(  # noqa: TRY301
                "La cantidad de imágenes verificadas no coincide con las candidatas "
                f"de la página: {len(verified_files)} != {len(source_urls)}."
            )

        # Begin a short transaction and avoid overwriting unrelated product fields.
        original_image_state = (
            str(existing.image_url or ""),
            str(existing.image_path or ""),
            str(existing.image_hash or ""),
            _gallery_signature(existing.gallery_images),
            str(existing.description or ""),
        )
        clean_gallery = repository._clean_gallery_images(synced_gallery)
        db.begin()
        try:
            current = repository.get_by_code(PRODUCT_CODE)
            if current is None or current.product_id != existing.product_id:
                raise RuntimeError("FB-4047 cambió durante el scraping; no se escribirá.")  # noqa: TRY301
            current_image_state = (
                str(current.image_url or ""),
                str(current.image_path or ""),
                str(current.image_hash or ""),
                _gallery_signature(current.gallery_images),
                str(current.description or ""),
            )
            if current_image_state != original_image_state:
                raise RuntimeError(  # noqa: TRY301
                    "La imagen/galería/Detalle guardado cambió durante el scraping; "
                    "se cancela para no sobrescribir cambios concurrentes."
                )
            cursor = db.execute_query(
                """
                UPDATE products
                SET description=?, image_url=?, image_path=?, image_hash=?, gallery_images=?
                WHERE id=? AND code=? COLLATE NOCASE
                """,
                (
                    detail_to_store,
                    str(synced.image_url or existing.image_url),
                    str(synced.image_path or existing.image_path),
                    str(synced.image_hash or existing.image_hash),
                    json.dumps(clean_gallery, ensure_ascii=False),
                    existing.product_id,
                    PRODUCT_CODE,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("No se actualizó exactamente un registro de FB-4047.")  # noqa: TRY301
            reread = repository.get_by_code(PRODUCT_CODE)
            if reread is None:
                raise RuntimeError("FB-4047 desapareció al verificar la escritura.")  # noqa: TRY301
            persisted_urls = _gallery_urls(reread.gallery_images)
            persisted_coverage = _candidate_coverage(source_urls, reread.gallery_images)
            persisted_files = _verify_gallery_files(reread.gallery_images)
            if not persisted_coverage["all_candidates_stored"]:
                raise RuntimeError(  # noqa: TRY301
                    "La lectura de comprobación no contiene todas las imágenes fuente."
                )
            if len(persisted_files) != len(source_urls):
                raise RuntimeError(  # noqa: TRY301
                    "La cantidad de imágenes verificadas tras escribir no coincide."
                )
            if normalize_detail_text(
                reread.description, preserve_boundaries=True
            ) != normalize_detail_text(detail_to_store, preserve_boundaries=True):
                raise RuntimeError("El Detail persistido no coincide con el validado.")  # noqa: TRY301
            db.commit()
            committed = True
            report["database_writes"] = True
            report["status"] = "success"
            report["persisted_gallery_urls"] = persisted_urls
            report["persisted_gallery_count"] = len(persisted_urls)
            report["persisted_detail"] = reread.description
            report["post_write_verified_files"] = persisted_files
        except Exception:
            db.rollback()
            raise
    except Exception as error:
        report["errors"].append(f"{type(error).__name__}: {error}")
        report["status"] = "failed"
        _remove_new_files(product_dir, files_before)
        raise
    finally:
        db.close()

    report_path = Path(tempfile.gettempdir()) / (
        "FCM_FB4047_repair_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + ".json"
    )
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nInforme: {report_path}")
    print(f"Backup previo: {backup_path}")
    print("FB-4047 actualizado y sus imágenes verificadas." if committed else "No se aplicaron cambios.")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Refresca solo FB-4047 desde la categoría y la página live, "
            "descarga toda su galería y verifica archivos/hash antes de persistir."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplicar la actualización verificada de FB-4047 en SQLite.",
    )
    args = parser.parse_args()
    try:
        repair(apply=bool(args.apply))
    except Exception as error:  # noqa: BLE001
        print(f"ERROR: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
