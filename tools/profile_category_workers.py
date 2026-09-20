from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.scraping.scraping_config import ScrapingConfig
from tools import profile_scraping_categories as profiler


class _ExperimentScrapingConfig(ScrapingConfig):
    def __init__(self, *args, **kwargs):
        raw_workers = os.getenv("FCM_PROFILE_CATEGORY_WORKERS", "").strip()
        if raw_workers:
            workers = int(raw_workers)
            if workers <= 0:
                raise ValueError("FCM_PROFILE_CATEGORY_WORKERS debe ser mayor que cero.")
            kwargs["category_workers"] = workers
        super().__init__(*args, **kwargs)


def main() -> int:
    profiler.ScrapingConfig = _ExperimentScrapingConfig
    return profiler.main()


if __name__ == "__main__":
    raise SystemExit(main())
