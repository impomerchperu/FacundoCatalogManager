from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(slots=True)
class SyncResult:
    """
    Resultado consolidado de una sincronización de catálogo.

    Este modelo representa el resultado del proceso completo
    de scraping y sincronización.

    Mantiene compatibilidad con el flujo incremental anterior
    y permite ser utilizado por GUI, reportes y servicios.
    """

    success: bool = False

    started_at: datetime | None = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    finished_at: datetime | None = None

    # Compatibilidad con sincronización incremental
    processed: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0

    changes: list[dict] = field(default_factory=list)
    failures: list = field(default_factory=list)

    # Métricas del catálogo completo
    categories_processed: int = 0

    products_found: int = 0
    products_created: int = 0
    products_updated: int = 0
    products_unchanged: int = 0

    # Métricas de imágenes
    images_processed: int = 0
    images_downloaded: int = 0
    images_failed: int = 0

    errors: list[str] = field(default_factory=list)

    def increment_processed(self) -> None:
        """Incrementa la cantidad de productos procesados."""
        self.processed += 1

    def finish(self) -> None:
        """Marca la finalización del proceso."""
        self.finished_at = datetime.now(timezone.utc)
        self.success = not self.has_errors

    @property
    def duration_seconds(self) -> float:
        """Duración total del proceso de sincronización."""
        if not self.started_at or not self.finished_at:
            return 0.0

        return (
            self.finished_at - self.started_at
        ).total_seconds()

    @property
    def has_errors(self) -> bool:
        """Indica si la sincronización tuvo errores."""
        return bool(self.errors) or bool(self.failures)

    def add_error(self, message: str) -> None:
        """Registra un error durante la sincronización."""
        self.errors.append(message)

    def to_dict(self) -> dict:
        """Convierte el resultado a un diccionario serializable."""
        return {
            "success": self.success,
            "processed": self.processed,
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "categories_processed": self.categories_processed,
            "products_found": self.products_found,
            "products_created": self.products_created,
            "products_updated": self.products_updated,
            "products_unchanged": self.products_unchanged,
            "images_processed": self.images_processed,
            "images_downloaded": self.images_downloaded,
            "images_failed": self.images_failed,
            "errors": self.errors,
            "changes": self.changes,
            "failures": self.failures,
            "started_at": (
                self.started_at.isoformat()
                if self.started_at
                else None
            ),
            "finished_at": (
                self.finished_at.isoformat()
                if self.finished_at
                else None
            ),
            "duration_seconds": self.duration_seconds,
        }

    def summary(self) -> dict:
        """Genera un resumen legible del resultado."""
        return {
            "Procesados": self.processed,
            "Nuevos": self.created,
            "Actualizados": self.updated,
            "Sin cambios": self.unchanged,
            "Errores": len(self.errors),
            "Duración": self.duration_seconds,
        }
