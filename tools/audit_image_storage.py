from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_db_path(raw: Any, project_root: Path) -> Path | None:
    value = str(raw or "").strip()
    if not value:
        return None
    return _resolve_project_path(value.replace("\\", "/"), project_root)


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row[1]) for row in rows}


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        is not None
    )


def _collect_db_references(
    db_path: Path,
    project_root: Path,
) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    if not db_path.is_file():
        return references

    connection = sqlite3.connect(db_path)
    try:
        for table in ("products", "scraped_products", "sync_records"):
            if not _table_exists(connection, table):
                continue
            columns = _table_columns(connection, table)
            if "image_path" not in columns:
                continue

            selected = ["rowid", "image_path"]
            for optional in ("code", "image_hash", "image_url"):
                if optional in columns:
                    selected.append(optional)

            rows = connection.execute(
                f"SELECT {', '.join(selected)} FROM {table}"
            ).fetchall()
            for row in rows:
                values = dict(zip(selected, row, strict=True))
                normalized = _normalized_db_path(
                    values.get("image_path"),
                    project_root,
                )
                if normalized is None:
                    continue
                references.append(
                    {
                        "table": table,
                        "rowid": values.get("rowid"),
                        "code": str(values.get("code") or ""),
                        "image_path": str(values.get("image_path") or ""),
                        "resolved_path": normalized,
                        "image_hash": str(values.get("image_hash") or ""),
                        "image_url": str(values.get("image_url") or ""),
                    }
                )
    finally:
        connection.close()
    return references


def _root_label(root: Path, project_root: Path) -> str:
    try:
        return root.relative_to(project_root).as_posix() or "."
    except ValueError:
        return root.as_posix()


def _scan_files(
    roots: list[Path],
    project_root: Path,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    existing_roots = [root for root in roots if root.is_dir()]
    seen: set[Path] = set()

    for root in existing_roots:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue

            resolved = path.resolve()
            if resolved in seen:
                continue

            matching_roots = [
                candidate
                for candidate in existing_roots
                if _is_within(resolved, candidate)
            ]
            owner_root = max(
                matching_roots,
                key=lambda candidate: len(candidate.parts),
            )
            seen.add(resolved)
            records.append(
                {
                    "path": resolved,
                    "root": _root_label(owner_root, project_root),
                    "relative": resolved.relative_to(owner_root).as_posix(),
                    "size": resolved.stat().st_size,
                    "sha256": _sha256(resolved),
                }
            )
    return records


def audit(
    *,
    project_root: Path,
    db_path: Path,
    roots: list[Path],
) -> dict[str, Any]:
    project_root = project_root.resolve()
    db_path = db_path.resolve()
    roots = [_resolve_project_path(root, project_root) for root in roots]

    files = _scan_files(roots, project_root)
    references = _collect_db_references(db_path, project_root)

    file_by_path = {record["path"]: record for record in files}
    references_by_path: dict[Path, list[dict[str, Any]]] = defaultdict(list)
    for reference in references:
        references_by_path[reference["resolved_path"]].append(reference)

    hash_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    filename_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    code_variant_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in files:
        hash_groups[record["sha256"]].append(record)
        filename_groups[record["path"].name.casefold()].append(record)
        code_variant_groups[record["path"].stem.casefold()].append(record)

    duplicate_groups = [
        group for group in hash_groups.values() if len(group) > 1
    ]
    cross_root_duplicate_groups = [
        group
        for group in duplicate_groups
        if len({record["root"] for record in group}) > 1
    ]

    active_references = [
        reference
        for reference in references
        if reference["table"] == "products"
    ]
    legacy_references = [
        reference
        for reference in references
        if reference["table"] in {"scraped_products", "sync_records"}
    ]
    active_referenced_paths = {
        reference["resolved_path"] for reference in active_references
    }
    legacy_referenced_paths = {
        reference["resolved_path"] for reference in legacy_references
    }

    missing_references = [
        reference
        for reference in references
        if reference["resolved_path"] not in file_by_path
    ]
    missing_active_references = [
        reference
        for reference in active_references
        if reference["resolved_path"] not in file_by_path
    ]
    orphan_files = [
        record
        for record in files
        if record["path"] not in references_by_path
    ]
    active_orphan_files = [
        record
        for record in files
        if record["path"] not in active_referenced_paths
    ]
    legacy_only_files = [
        record
        for record in files
        if record["path"] in legacy_referenced_paths
        and record["path"] not in active_referenced_paths
    ]

    hash_match = []
    hash_mismatch = []
    hash_missing = []
    for reference in references:
        stored_hash = reference["image_hash"].strip()
        file_record = file_by_path.get(reference["resolved_path"])
        if not stored_hash:
            if file_record is not None:
                hash_missing.append(reference)
            continue
        if file_record is None:
            continue
        if stored_hash.casefold() == file_record["sha256"].casefold():
            hash_match.append(reference)
        else:
            hash_mismatch.append(reference)

    db_path_counts: dict[str, int] = defaultdict(int)
    db_url_counts: dict[str, int] = defaultdict(int)
    for reference in references:
        db_path_counts[reference["image_path"]] += 1
        if reference["image_url"]:
            db_url_counts[reference["image_url"]] += 1

    return {
        "project_root": project_root.as_posix(),
        "db_path": db_path.as_posix(),
        "roots": [
            {
                "path": root.as_posix(),
                "label": _root_label(root, project_root),
                "exists": root.is_dir(),
            }
            for root in roots
        ],
        "files_total": len(files),
        "files_by_root": {
            label: sum(record["root"] == label for record in files)
            for label in sorted({record["root"] for record in files})
        },
        "db_references_total": len(references),
        "db_references_by_table": {
            table: sum(reference["table"] == table for reference in references)
            for table in ("products", "scraped_products", "sync_records")
        },
        "referenced_files": len(files) - len(orphan_files),
        "orphan_files": len(orphan_files),
        "active_referenced_files": len(files) - len(active_orphan_files),
        "active_orphan_files": len(active_orphan_files),
        "legacy_only_files": len(legacy_only_files),
        "missing_references": len(missing_references),
        "missing_active_references": len(missing_active_references),
        "hash_match_references": len(hash_match),
        "hash_mismatch_references": len(hash_mismatch),
        "hash_missing_references": len(hash_missing),
        "duplicate_groups": duplicate_groups,
        "cross_root_duplicate_groups": cross_root_duplicate_groups,
        "same_filename_groups": [
            group for group in filename_groups.values() if len(group) > 1
        ],
        "same_code_variant_groups": [
            group for group in code_variant_groups.values() if len(group) > 1
        ],
        "db_path_duplicates": sorted(
            (
                {"path": path, "references": count}
                for path, count in db_path_counts.items()
                if count > 1
            ),
            key=lambda item: (-item["references"], item["path"]),
        ),
        "db_url_duplicates": sorted(
            (
                {"url": url, "references": count}
                for url, count in db_url_counts.items()
                if count > 1
            ),
            key=lambda item: (-item["references"], item["url"]),
        ),
        "missing_reference_details": missing_references,
        "missing_active_reference_details": missing_active_references,
        "orphan_file_details": orphan_files,
        "active_orphan_file_details": active_orphan_files,
        "legacy_only_file_details": legacy_only_files,
        "hash_mismatch_details": hash_mismatch,
    }


def _print_group(group: list[dict[str, Any]]) -> None:
    for record in group:
        print(
            f"  - {record['path']} "
            f"({record['size']} bytes, sha256={record['sha256']})"
        )


def print_report(report: dict[str, Any], max_details: int = 100) -> None:
    print(f"Proyecto: {report['project_root']}")
    print(f"DB: {report['db_path']}")
    for root in report["roots"]:
        print(f"ROOT: {root['label']} | exists={root['exists']}")

    print(f"Archivos de imagen: {report['files_total']}")
    for root, count in report["files_by_root"].items():
        print(f"  {root}: {count}")

    print(f"Referencias DB: {report['db_references_total']}")
    for table, count in report["db_references_by_table"].items():
        print(f"  {table}: {count}")

    print(f"Archivos referenciados: {report['referenced_files']}")
    print(f"Archivos sin referencia DB: {report['orphan_files']}")
    print(
        "Archivos referenciados por products: "
        f"{report['active_referenced_files']}"
    )
    print(
        "Archivos no referenciados por products: "
        f"{report['active_orphan_files']}"
    )
    print(f"Archivos solo legacy: {report['legacy_only_files']}")
    print(f"Referencias a archivos inexistentes: {report['missing_references']}")
    print(
        "Referencias activas a archivos inexistentes: "
        f"{report['missing_active_references']}"
    )
    print(f"Hashes DB coincidentes: {report['hash_match_references']}")
    print(f"Hashes DB ausentes: {report['hash_missing_references']}")
    print(f"Hashes DB distintos: {report['hash_mismatch_references']}")
    print(f"Grupos duplicados por hash: {len(report['duplicate_groups'])}")
    print(
        "Grupos duplicados entre roots: "
        f"{len(report['cross_root_duplicate_groups'])}"
    )
    print(
        "Grupos con mismo nombre entre roots: "
        f"{len(report['same_filename_groups'])}"
    )
    print(
        "Códigos con múltiples archivos locales: "
        f"{len(report['same_code_variant_groups'])}"
    )
    print(f"Rutas DB repetidas: {len(report['db_path_duplicates'])}")
    print(f"URLs DB repetidas: {len(report['db_url_duplicates'])}")

    if report["missing_reference_details"]:
        print("\nREFERENCIAS INEXISTENTES:")
        for reference in report["missing_reference_details"][:max_details]:
            print(
                f"  - [{reference['table']}#{reference['rowid']}] "
                f"{reference['code']}: {reference['image_path']}"
            )

    if report["hash_mismatch_details"]:
        print("\nHASHES DISTINTOS:")
        for reference in report["hash_mismatch_details"][:max_details]:
            print(
                f"  - [{reference['table']}#{reference['rowid']}] "
                f"{reference['code']}: {reference['image_path']}"
            )

    if report["cross_root_duplicate_groups"]:
        print("\nDUPLICADOS ENTRE ROOTS:")
        for group in report["cross_root_duplicate_groups"][:max_details]:
            _print_group(group)

    if report["orphan_file_details"]:
        print("\nARCHIVOS SIN REFERENCIA DB:")
        for record in report["orphan_file_details"][:max_details]:
            print(
                f"  - {record['path']} "
                f"({record['size']} bytes, sha256={record['sha256']})"
            )
        if len(report["orphan_file_details"]) > max_details:
            print(
                f"  ... {len(report['orphan_file_details']) - max_details} "
                "más; use --json para el reporte completo."
            )


def _json_safe(report: dict[str, Any]) -> dict[str, Any]:
    serializable = dict(report)
    for key in (
        "duplicate_groups",
        "cross_root_duplicate_groups",
        "same_filename_groups",
        "same_code_variant_groups",
    ):
        serializable[key] = [
            [
                {**record, "path": str(record["path"])}
                for record in group
            ]
            for group in serializable[key]
        ]
    for key in (
        "missing_reference_details",
        "missing_active_reference_details",
        "hash_mismatch_details",
    ):
        serializable[key] = [
            {**reference, "resolved_path": str(reference["resolved_path"])}
            for reference in serializable[key]
        ]
    for key in (
        "orphan_file_details",
        "active_orphan_file_details",
        "legacy_only_file_details",
    ):
        serializable[key] = [
            {**record, "path": str(record["path"])}
            for record in serializable[key]
        ]
    return serializable


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]

    parser = argparse.ArgumentParser(
        description=(
            "Audita imágenes de forma no destructiva cruzando filesystem, "
            "SQLite, hashes y duplicados entre roots."
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
        default=[
            "data/images",
            "data/images/products",
        ],
        help=(
            "Root adicional de imágenes. Puede repetirse. "
            "Los dos roots de data/images se incluyen por defecto."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emite el reporte completo como JSON.",
    )
    parser.add_argument(
        "--max-details",
        type=int,
        default=100,
        help="Máximo de elementos detallados en modo humano.",
    )
    args = parser.parse_args()

    report = audit(
        project_root=project_root,
        db_path=_resolve_project_path(args.db, project_root),
        roots=args.roots,
    )
    if args.json:
        print(json.dumps(_json_safe(report), ensure_ascii=False, indent=2))
        return

    print_report(report, max_details=max(args.max_details, 0))


if __name__ == "__main__":
    main()
