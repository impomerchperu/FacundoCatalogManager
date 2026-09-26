from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "FacundoCatalogManager"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    """Indica si la aplicación se está ejecutando desde un bundle congelado."""
    return bool(getattr(sys, "frozen", False))


def get_bundle_root(
    *,
    frozen: bool | None = None,
    bundle_root: str | Path | None = None,
) -> Path:
    """Obtiene la raíz de recursos de solo lectura del bundle."""
    if frozen is None:
        frozen = is_frozen()

    if bundle_root is not None:
        return Path(bundle_root)

    if frozen:
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)

    return PROJECT_ROOT


def get_data_dir(
    *,
    frozen: bool | None = None,
    local_app_data: str | Path | None = None,
) -> Path:
    """Obtiene el directorio persistente de datos de la aplicación."""
    if frozen is None:
        frozen = is_frozen()

    if not frozen:
        return PROJECT_ROOT

    if local_app_data is None:
        local_app_data_value = os.environ.get("LOCALAPPDATA")
        local_app_data = (
            Path(local_app_data_value)
            if local_app_data_value
            else None
        )

    if local_app_data is None:
        return Path.home() / f".{APP_NAME}"

    return Path(local_app_data) / APP_NAME


DATA_DIR = get_data_dir()
DATABASE_DIR = DATA_DIR / "database"
DATABASE_PATH = DATABASE_DIR / "catalog.db"
SCHEMA_PATH = get_bundle_root() / "database" / "schema.sql"
LOG_PATH = DATA_DIR / "logs" / "fcm.log"


def resolve_data_path(path: str | Path) -> Path:
    """Resuelve una ruta relativa al directorio persistente de datos."""
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return DATA_DIR / candidate


def to_data_relative_path(path: str | Path) -> str:
    """Convierte rutas bajo DATA_DIR al formato relativo almacenado en SQLite."""
    candidate = Path(path)
    if not candidate.is_absolute():
        return candidate.as_posix()

    try:
        return candidate.resolve().relative_to(DATA_DIR.resolve()).as_posix()
    except ValueError:
        return candidate.as_posix()
