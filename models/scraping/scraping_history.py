from dataclasses import dataclass
from datetime import datetime


@dataclass
class ScrapingHistory:
    """Registro persistente de una descarga aplicada."""

    started_at: datetime
    finished_at: datetime
    processed: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0
    generated: int = 0
    products_found: int = 0
    products_unique: int = 0
    products_multiple_categories: int = 0
    duplicate_occurrences: int = 0
    errors: int = 0
    status: str = "SUCCESS"
    message: str = ""
    history_id: int | None = None
