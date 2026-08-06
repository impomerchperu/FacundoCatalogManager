from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class SyncResult:
    """
    Resultado consolidado de una sincronización de catálogo.

    Este modelo permite comunicar el resultado del motor
    de sincronización hacia otras capas como GUI o reportes.
    """

    success: bool = False

    started_at: datetime | None = None
    finished_at: datetime | None = None

    categories_processed: int = 0

    products_found: int = 0
    products_created: int = 0
    products_updated: int = 0
    products_unchanged: int = 0

    images_processed: int = 0
    images_downloaded: int = 0
    images_failed: int = 0

    errors: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        """
        Duración total del proceso de sincronización.
        """

        if not self.started_at or not self.finished_at:
            return 0.0

        return (
            self.finished_at - self.started_at
        ).total_seconds()

    @property
    def has_errors(self) -> bool:
        """
        Indica si la sincronización tuvo errores.
        """

        return bool(self.errors)

    def add_error(self, message: str) -> None:
        """
        Registra un error durante la sincronización.
        """

        self.errors.append(message)
