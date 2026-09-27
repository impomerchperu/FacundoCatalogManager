from __future__ import annotations

import re
from pathlib import Path

from config.runtime_paths import get_bundle_root


VERSION_FILENAME = "VERSION"
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def load_app_version(version_file: str | Path | None = None) -> str:
    """Carga y valida la versión central de la aplicación."""
    path = (
        Path(version_file)
        if version_file is not None
        else get_bundle_root() / VERSION_FILENAME
    )

    try:
        version = path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise RuntimeError(
            f"No se pudo leer la versión de la aplicación: {path}"
        ) from error

    if not VERSION_PATTERN.fullmatch(version):
        raise RuntimeError(
            "La versión de la aplicación debe usar el formato "
            f"MAJOR.MINOR.PATCH: {version!r}"
        )

    return version


APP_VERSION = load_app_version()
