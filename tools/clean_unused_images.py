from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Any

IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})
DEFAULT_ROOTS = ("data/images", "resources/images")


def _resolve_project_path(value: str | Path, project_root: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _active_image_paths(db_path: Path, project_root: Path) -> set[Path]:
    if not db_path.is_file():
        raise FileNotFoundError(f"Base de datos no encontrada: {db_path}")

    connection = sqlite3.connect(db_path)
    try:
        columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(products)")
        }
        if "image_path" not in columns:
            raise RuntimeError(
                "La tabla products no contiene la columna image_path."
            )

        rows = connection.execute(
            "SELECT image_path FROM products "
            "WHERE image_path IS NOT NULL AND TRIM(image_path) <> ''"
        ).fetchall()
    finally:
        connection.close()

    paths: set[Path] = set()
    for (raw_path,) in rows:
        value = str(raw_path or "").strip()
        if value:
            paths.add(
                _resolve_project_path(
                    value.replace("\\", "/"),
                    project_root,
                )
            )
    return paths


def _iter_image_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []

    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            files.append(path.resolve())
    return files


def find_unused_images(
    *,
    project_root: Path,
    db_path: Path,
    roots: list[Path],
) -> list[dict[str, Any]]:
    project_root = project_root.resolve()
    active_paths = _active_image_paths(db_path.resolve(), project_root)

    candidates: dict[Path, dict[str, Any]] = {}
    resolved_roots = [
        _resolve_project_path(root, project_root)
        for root in roots
    ]

    for root in resolved_roots:
        for path in _iter_image_files(root):
            if path in active_paths or path in candidates:
                continue
            if not _is_within(path, root):
                continue

            candidates[path] = {
                "path": path,
                "relative": path.relative_to(project_root).as_posix(),
                "bytes": path.stat().st_size,
            }

    return [
        candidates[path]
        for path in sorted(candidates)
    ]


def clean_unused_images(
    *,
    project_root: Path,
    db_path: Path,
    roots: list[Path],
    delete: bool = False,
) -> list[dict[str, Any]]:
    candidates = find_unused_images(
        project_root=project_root,
        db_path=db_path,
        roots=roots,
    )

    if not delete:
        return candidates

    # Re-read the whitelist immediately before deletion so files referenced by
    # a newly persisted product are never removed by a stale candidate list.
    project_root = project_root.resolve()
    active_paths = _active_image_paths(db_path.resolve(), project_root)
    deleted: list[dict[str, Any]] = []

    for candidate in candidates:
        path = Path(candidate["path"]).resolve()
        if path in active_paths:
            continue
        if not path.is_file():
            continue
        path.unlink()
        deleted.append(candidate)

    return deleted


def _print_result(items: list[dict[str, Any]], deleted: bool) -> None:
    total_bytes = sum(int(item["bytes"]) for item in items)
    action = "Eliminadas" if deleted else "Candidatas"

    print(f"{action}: {len(items)}")
    print(f"Bytes: {total_bytes}")

    for item in items:
        print(f"  - {item['relative']} ({item['bytes']} bytes)")


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]

    parser = argparse.ArgumentParser(
        description=(
            "Elimina imágenes que no estén referenciadas por "
            "products.image_path. Por defecto solo informa candidatas."
        )
    )
    parser.add_argument(
        "--db",
        default="database/catalog.db",
        help="Ruta a la SQLite del catálogo.",
    )
    parser.add_argument(
        "--root",
        action="append",
        dest="roots",
        default=list(DEFAULT_ROOTS),
        help=(
            "Root de imágenes a limpiar. Puede repetirse. "
            "Por defecto incluye data/images y resources/images."
        ),
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Elimina físicamente las imágenes no referenciadas.",
    )
    args = parser.parse_args()

    candidates = clean_unused_images(
        project_root=project_root,
        db_path=_resolve_project_path(args.db, project_root),
        roots=args.roots,
        delete=args.delete,
    )
    _print_result(candidates, deleted=args.delete)


if __name__ == "__main__":
    main()
