from dataclasses import dataclass
from datetime import datetime


@dataclass
class SyncHistory:

    id: int | None = None

    started_at: datetime | None = None

    finished_at: datetime | None = None

    processed: int = 0

    created: int = 0

    updated: int = 0

    unchanged: int = 0

    errors: int = 0

    status: str = "COMPLETED"
