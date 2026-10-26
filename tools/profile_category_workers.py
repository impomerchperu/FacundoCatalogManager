from __future__ import annotations

import importlib
import os
import sqlite3
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


def _configure_isolated_database() -> Path:
    """Redirect profiling to a verified temporary DB copy, never the live catalogs."""
    raw_path = os.getenv("FCM_PROFILE_DB_PATH", "").strip()
    if not raw_path:
        raise ValueError(
            "FCM_PROFILE_DB_PATH es obligatorio; usa una copia temporal "
            "de database/catalog.db para no perfilar sobre la base real."
        )

    database_path = Path(raw_path).expanduser().resolve()
    if not database_path.is_file():
        raise FileNotFoundError(
            f"FCM_PROFILE_DB_PATH no existe o no es un archivo: {database_path}"
        )

    runtime_paths = importlib.import_module("config.runtime_paths")
    protected_paths = {Path(runtime_paths.DATABASE_PATH).resolve()}
    local_app_data = os.getenv("LOCALAPPDATA", "").strip()
    if local_app_data:
        protected_paths.add(
            (
                Path(local_app_data)
                / "FacundoCatalogManager"
                / "database"
                / "catalog.db"
            ).resolve()
        )
    if database_path in protected_paths:
        raise ValueError(
            "FCM_PROFILE_DB_PATH apunta a una base canónica. "
            "Usa una copia temporal aislada."
        )

    with sqlite3.connect(database_path.as_uri() + "?mode=ro", uri=True) as connection:
        integrity = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if integrity != "ok":
            raise RuntimeError(
                f"La copia temporal no supera PRAGMA quick_check: {integrity}"
            )
        if not {"products", "schema_migrations"}.issubset(tables):
            raise ValueError(
                "FCM_PROFILE_DB_PATH no contiene una base de catálogo FCM reconocible."
            )
        row = connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()
        schema_version = int(row[0] or 0) if row else 0
        if schema_version != 6:
            raise ValueError(
                f"La copia temporal debe usar esquema 6; se encontró {schema_version}."
            )

    db_manager_module = importlib.import_module("database.db_manager")
    scraping_factory_module = importlib.import_module("services.scraping.scraping_factory")
    db_manager_module.DATABASE_PATH = database_path
    scraping_factory_module.DATABASE_PATH = database_path
    return database_path


def main() -> int:
    database_path = _configure_isolated_database()
    profiler.ScrapingConfig = _ExperimentScrapingConfig
    print(f"profile_database={database_path}")
    return profiler.main()


if __name__ == "__main__":
    raise SystemExit(main())
