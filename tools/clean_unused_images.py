from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from scrapers.images.image_validation import is_identifiable_image_file

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


def _gallery_image_paths(
    raw_gallery: object,
    project_root: Path,
) -> set[Path]:
    if raw_gallery in (None, ""):
        return set()
    try:
        gallery_images = json.loads(raw_gallery)
    except (TypeError, json.JSONDecodeError) as error:
        # A broken gallery record may hide an active file reference. Fail closed.
        raise RuntimeError(
            "No se puede limpiar imágenes: gallery_images no es JSON válido."
        ) from error
    if not isinstance(gallery_images, list):
        raise TypeError(
            "No se puede limpiar imágenes: gallery_images no es una lista."
        )

    paths: set[Path] = set()
    for image in gallery_images:
        if not isinstance(image, dict):
            raise TypeError(
                "No se puede limpiar imágenes: hay una entrada de galería inválida."
            )
        gallery_path = str(
            image.get("image_path", image.get("path", "")) or ""
        ).strip()
        if gallery_path:
            paths.add(
                _resolve_project_path(
                    gallery_path.replace("\\", "/"),
                    project_root,
                )
            )
    return paths


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

        gallery_column = "gallery_images" if "gallery_images" in columns else None
        selected_columns = ["image_path"]
        if gallery_column:
            selected_columns.append(gallery_column)
        rows = connection.execute(
            "SELECT " + ", ".join(selected_columns) + " FROM products"
        ).fetchall()
    finally:
        connection.close()

    paths: set[Path] = set()
    for row in rows:
        value = str(row[0] or "").strip()
        if value:
            paths.add(
                _resolve_project_path(value.replace("\\", "/"), project_root)
            )
        if gallery_column and len(row) > 1:
            paths.update(_gallery_image_paths(row[1], project_root))
    return paths


def _load_stable_active_paths(
    connection: sqlite3.Connection,
    db_path: Path,
    project_root: Path,
) -> tuple[set[Path], int]:
    """Refresh the full whitelist only when SQLite reports a concurrent commit."""
    for _attempt in range(3):
        before = int(
            connection.execute("PRAGMA data_version").fetchone()[0]
        )
        active_paths = _active_image_paths(db_path, project_root)
        after = int(
            connection.execute("PRAGMA data_version").fetchone()[0]
        )
        if before == after:
            return active_paths, after

    raise RuntimeError(
        "No se pueden limpiar imágenes mientras cambia la base de datos."
    )


def _iter_image_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []

    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        parts = {part.casefold() for part in path.parts}
        name = path.name.casefold()
        if (
            ".staging" in parts
            or name.endswith((".tmp", ".review-tmp", ".review-backup", ".review-delete-backup"))
        ):
            continue

        # Product/gallery directories are dedicated to catalog image assets:
        # include unknown/corrupt suffixes too, so an unidentifiable legacy
        # object is removed after its DB reference has been retired. The DB
        # allowlist below still protects every path referenced by the catalog.
        catalog_storage_path = bool({"products", "gallery"} & parts)
        # The root itself may still contain pre-directory legacy files named
        # by product code. It is also dedicated to catalog images, unlike
        # resources/images, so an unidentifiable orphan there is cleanable too.
        flat_legacy_catalog_file = (
            root.name.casefold() == "images"
            and root.parent.name.casefold() == "data"
            and path.parent.resolve() == root.resolve()
        )
        if (
            catalog_storage_path
            or flat_legacy_catalog_file
            or path.suffix.lower() in IMAGE_EXTENSIONS
            or is_identifiable_image_file(path)
        ):
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

    # Take a fresh whitelist before deletion and refresh it whenever another
    # SQLite connection commits. This protects concurrent updates without
    # reparsing every product/gallery row for each orphan file.
    project_root = project_root.resolve()
    resolved_db_path = db_path.resolve()
    resolved_roots = [
        _resolve_project_path(root, project_root) for root in roots
    ]
    deleted: list[dict[str, Any]] = []
    connection = sqlite3.connect(resolved_db_path)
    try:
        active_paths, data_version = _load_stable_active_paths(
            connection,
            resolved_db_path,
            project_root,
        )
        for candidate in candidates:
            path = Path(candidate["path"]).resolve()
            if not any(_is_within(path, root) for root in resolved_roots):
                continue
            if not path.is_file():
                continue

            current_version = int(
                connection.execute("PRAGMA data_version").fetchone()[0]
            )
            if current_version != data_version:
                active_paths, data_version = _load_stable_active_paths(
                    connection,
                    resolved_db_path,
                    project_root,
                )
            if path in active_paths:
                continue

            path.unlink()
            deleted.append(candidate)
    finally:
        connection.close()

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
        "--data-root",
        type=Path,
        default=None,
        help=(
            "Raíz donde se resuelven las rutas relativas guardadas en SQLite. "
            "Por defecto usa los dos niveles superiores de la ruta de la base."
        ),
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

    database_path = _resolve_project_path(args.db, project_root)
    data_root = (
        _resolve_project_path(args.data_root, project_root)
        if args.data_root is not None
        else database_path.parent.parent
    )
    candidates = clean_unused_images(
        project_root=data_root,
        db_path=database_path,
        roots=args.roots,
        delete=args.delete,
    )
    _print_result(candidates, deleted=args.delete)


if __name__ == "__main__":
    main()
