from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from models.scraping.sync_result import SyncResult

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULT_PATH = PROJECT_ROOT / "data" / "scraping_result.json"
TIMING_LOG = PROJECT_ROOT / "data" / "scraping_timing.log"


class ScrapingResultWriter:
    """Persiste el único resultado estructurado de la última ejecución."""

    def write(self, result: SyncResult, codes: set[str]) -> None:
        payload = result.to_dict()
        payload.update(
            {
                "schema_version": 2,
                "scraped_at": result.finished_at.isoformat()
                if result.finished_at
                else None,
                "codes": sorted(codes),
                "scraped_unique_products": len(codes),
            }
        )
        RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=RESULT_PATH.parent,
            prefix="scraping_result_",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            json.dump(payload, temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
            temporary_path = Path(temporary.name)
        temporary_path.replace(RESULT_PATH)
        self._append_timing_anchor(result)

    @staticmethod
    def _append_timing_anchor(result: SyncResult) -> None:
        TIMING_LOG.parent.mkdir(parents=True, exist_ok=True)
        with TIMING_LOG.open("a", encoding="utf-8") as file:
            file.write(
                "SCRAPING TIMING | stage=result_artifact | "
                "run_id=%s | scraped_at=%s | coverage_complete=%s | "
                "products_found=%d | products_unique=%d\n"
                % (
                    result.run_id,
                    result.finished_at.isoformat() if result.finished_at else "",
                    result.coverage_complete,
                    result.products_found,
                    result.products_unique,
                )
            )
