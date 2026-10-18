"""Adapt image synchronization to the scraping pipeline with stage timing."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from scrapers.sync.image_sync import ImageSync

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TIMING_LOG = PROJECT_ROOT / "data" / "scraping_timing.log"


def _log_timing(message: str, *args: Any) -> None:
    TIMING_LOG.parent.mkdir(parents=True, exist_ok=True)
    formatted = message % args if args else message
    with TIMING_LOG.open("a", encoding="utf-8") as file:
        file.write(f"{formatted}\n")


class ImageSyncAdapter:
    """Adaptador del flujo de scraping al motor de sincronización de imágenes."""

    def __init__(
        self,
        image_sync=None,
        gallery_sync=None,
    ):
        self.image_sync = image_sync or ImageSync()
        self.gallery_sync = gallery_sync

    @staticmethod
    def _http_metrics(browser) -> dict[str, Any]:
        getter = getattr(browser, "get_http_metrics", None)
        if not callable(getter):
            return {}
        try:
            result = getter() or {}
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return {}
        return result if isinstance(result, dict) else {}

    def sync_products(
        self,
        products,
        progress_callback=None,
        refresh_remote_images: bool = False,
    ):
        """Procesa imágenes principales y galerías, registrando cada etapa."""
        items = list(products or [])

        started = time.perf_counter()
        if refresh_remote_images:
            items = self.image_sync.process(
                items, refresh_remote_images=True
            )
        else:
            items = self.image_sync.process(items)
        _log_timing(
            "SCRAPING TIMING | stage=primary_image_sync | "
            "products=%d | workers=%d | seconds=%.3f",
            len(items),
            int(getattr(self.image_sync, "max_workers", 0) or 0),
            time.perf_counter() - started,
        )

        if self.gallery_sync is not None:
            browser = getattr(self.gallery_sync, "browser", None)
            before = self._http_metrics(browser)
            gallery_started = time.perf_counter()
            items = self.gallery_sync.sync_products(
                items,
                progress_callback=progress_callback,
            )
            elapsed = time.perf_counter() - gallery_started
            after = self._http_metrics(browser)
            detail_requests = max(
                int(after.get("detail_http_requests", 0) or 0)
                - int(before.get("detail_http_requests", 0) or 0),
                0,
            )
            detail_http_seconds = max(
                float(after.get("detail_http_total_seconds", 0.0) or 0.0)
                - float(before.get("detail_http_total_seconds", 0.0) or 0.0),
                0.0,
            )
            retries = max(
                int(after.get("http_retries", 0) or 0)
                - int(before.get("http_retries", 0) or 0),
                0,
            )
            _log_timing(
                "SCRAPING TIMING | stage=gallery_sync | products=%d | workers=%d "
                "| refresh_existing=%s | detail_http_requests=%d "
                "| detail_http_seconds=%.3f | retries=%d | seconds=%.3f",
                len(items),
                int(getattr(self.gallery_sync, "max_workers", 0) or 0),
                str(
                    bool(getattr(self.gallery_sync, "refresh_existing", False))
                ).lower(),
                detail_requests,
                detail_http_seconds,
                retries,
                elapsed,
            )
        return items
