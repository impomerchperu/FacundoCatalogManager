from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from config.runtime_paths import DATABASE_PATH, DATA_DIR, PROJECT_ROOT, is_frozen


class CatalogSeedService:
    """Provisiona el catálogo inicial de una distribución congelada."""

    SEED_ROOT = PROJECT_ROOT / "seed"
    SEED_DATABASE_PATH = SEED_ROOT / "database" / "catalog.db"
    SEED_IMAGES_PATH = SEED_ROOT / "data" / "images"

    @classmethod
    def seed_if_needed(cls) -> bool:
        """Instala la semilla solo cuando no existe un catálogo útil del usuario."""
        if not is_frozen():
            return False

        if not cls.SEED_DATABASE_PATH.is_file():
            raise RuntimeError(
                f"No se encontró la base semilla del bundle: {cls.SEED_DATABASE_PATH}"
            )
        if not cls.SEED_IMAGES_PATH.is_dir():
            raise RuntimeError(
                f"No se encontró el directorio de imágenes semilla: {cls.SEED_IMAGES_PATH}"
            )

        if not cls._needs_seed(DATABASE_PATH):
            return False

        cls._seed_database(cls.SEED_DATABASE_PATH, DATABASE_PATH)
        cls._seed_images(cls.SEED_IMAGES_PATH, DATA_DIR / "data" / "images")
        return True

    @staticmethod
    def _needs_seed(destination: Path) -> bool:
        if not destination.is_file():
            return True

        try:
            with sqlite3.connect(destination) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                if "products" not in tables or "scraping_history" not in tables:
                    return True

                products = connection.execute(
                    "SELECT COUNT(*) FROM products"
                ).fetchone()[0]
                history = connection.execute(
                    "SELECT COUNT(*) FROM scraping_history"
                ).fetchone()[0]
                return products == 0 and history == 0
        except sqlite3.Error as error:
            raise RuntimeError(
                f"No se pudo inspeccionar la base de datos persistente: {destination}"
            ) from error

    @classmethod
    def _seed_database(cls, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".seed.tmp")
        temporary.unlink(missing_ok=True)

        try:
            with (
                sqlite3.connect(source) as source_connection,
                sqlite3.connect(temporary) as destination_connection,
            ):
                source_connection.backup(destination_connection)
                destination_connection.commit()

            cls._integrity_check(temporary)
            temporary.replace(destination)
            Path(str(destination) + "-wal").unlink(missing_ok=True)
            Path(str(destination) + "-shm").unlink(missing_ok=True)
            cls._integrity_check(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    @staticmethod
    def _seed_images(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination, dirs_exist_ok=True)

    @staticmethod
    def _integrity_check(path: Path) -> None:
        with sqlite3.connect(path) as connection:
            row = connection.execute("PRAGMA integrity_check").fetchone()

        result = str(row[0]).strip().lower() if row else ""
        if result != "ok":
            raise RuntimeError(
                f"La base semilla no supera PRAGMA integrity_check: {result or 'sin resultado'}"
            )
