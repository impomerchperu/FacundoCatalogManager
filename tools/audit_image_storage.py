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


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    rows = connection.execute(
        f"PRAGMA table_info({_quote_identifier(table)})"
    ).fetchall()
    return {str(row[1]) for row in rows}


def _image_reference_tables(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name"
    ).fetchall()
    return [
        str(row[0])
        for row in rows
        if "image_path" in _table_columns(connection, str(row[0]))
    ]


def _gallery_image_entries(
    raw: Any,
    *,
    reference_errors: list[dict[str, Any]] | None = None,
    table: str = "products",
    rowid: Any = None,
    code: str = "",
) -> list[dict[str, Any]]:
    """Parse gallery references and report malformed entries instead of hiding them."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return []

    def record_error(message: str, *, position: int | None = None) -> None:
        if reference_errors is None:
            return
        error: dict[str, Any] = {
            "table": table,
            "rowid": rowid,
            "code": code,
            "source": "gallery_images",
            "error": message,
        }
        if position is not None:
            error["position"] = position
        reference_errors.append(error)

    try:
        payload = (
            json.loads(raw)
            if isinstance(raw, (str, bytes, bytearray))
            else raw
        )
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        record_error(f"JSON inválido: {type(error).__name__}")
        return []

    if not isinstance(payload, list):
        record_error("El valor gallery_images no es una lista.")
        return []

    entries: list[dict[str, Any]] = []
    for position, entry in enumerate(payload, start=1):
        if not isinstance(entry, dict):
            record_error("Entrada de galería inválida.", position=position)
            continue
        entries.append(entry)
    return entries


def _product_source_page_urls_by_code(
    connection: sqlite3.Connection,
) -> dict[str, list[str]]:
    """Resolve the product pages from which each product was extracted."""
    table_rows = connection.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    tables = {str(row[0]) for row in table_rows}
    urls_by_code: dict[str, set[str]] = defaultdict(set)

    source_tables = (
        ("scraping_product_occurrences", "product_url", False),
        ("scraped_products", "url", True),
    )

    for table, url_column, fallback in source_tables:
        if table not in tables:
            continue

        columns = _table_columns(connection, table)
        if not {"code", url_column}.issubset(columns):
            continue

        query = (
            f"SELECT {_quote_identifier('code')}, "
            f"{_quote_identifier(url_column)} "
            f"FROM {_quote_identifier(table)}"
        )

        for raw_code, raw_url in connection.execute(query).fetchall():
            code = str(raw_code or "").strip()
            url = str(raw_url or "").strip()

            if not code or not url:
                continue
            if fallback and code in urls_by_code:
                continue

            urls_by_code[code].add(url)

    return {
        code: sorted(urls)
        for code, urls in urls_by_code.items()
    }


def _add_image_reference(
    references: list[dict[str, Any]],
    row_references: dict[Path, dict[str, Any]],
    raw_path: Any,
    details: dict[str, Any],
    project_root: Path,
) -> None:
    """Add one image reference, deduplicating paths within the same DB row."""
    normalized = _normalized_db_path(raw_path, project_root)
    if normalized is None:
        return

    image_hash = str(details.get("image_hash") or "")
    image_url = str(details.get("image_url") or "")
    source_page_urls = list(details.get("source_page_urls") or [])
    existing = row_references.get(normalized)

    if existing is not None:
        if not existing["image_hash"] and image_hash:
            existing["image_hash"] = image_hash
        if not existing["image_url"] and image_url:
            existing["image_url"] = image_url
        if not existing["source_page_urls"] and source_page_urls:
            existing["source_page_urls"] = source_page_urls
        return

    reference = {
        "table": details["table"],
        "rowid": details["rowid"],
        "code": details["code"],
        "image_path": str(raw_path or ""),
        "resolved_path": normalized,
        "image_hash": image_hash,
        "image_url": image_url,
        "source": str(details.get("source") or ""),
        "source_page_urls": source_page_urls,
    }
    references.append(reference)
    row_references[normalized] = reference


def _collect_row_image_references(
    table: str,
    values: dict[str, Any],
    project_root: Path,
    reference_errors: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Collect primary and gallery images, preserving extraction provenance."""
    references: list[dict[str, Any]] = []
    row_references: dict[Path, dict[str, Any]] = {}

    base_details = {
        "table": table,
        "rowid": values.get("rowid"),
        "code": str(values.get("code") or ""),
        "image_hash": str(values.get("image_hash") or ""),
        "image_url": str(values.get("image_url") or ""),
        "source": "primary" if table == "products" else "",
        "source_page_urls": list(values.get("source_page_urls") or []),
    }

    _add_image_reference(
        references,
        row_references,
        values.get("image_path"),
        base_details,
        project_root,
    )

    for entry in _gallery_image_entries(
        values.get("gallery_images"),
        reference_errors=reference_errors,
        table=table,
        rowid=values.get("rowid"),
        code=str(values.get("code") or ""),
    ):
        gallery_details = {
            **base_details,
            "image_hash": str(entry.get("image_hash") or ""),
            "image_url": str(
                entry.get("url") or entry.get("image_url") or ""
            ),
            "source": str(entry.get("source") or ""),
        }
        _add_image_reference(
            references,
            row_references,
            entry.get("image_path") or entry.get("path"),
            gallery_details,
            project_root,
        )

    return references


def _collect_db_references(
    db_path: Path,
    project_root: Path,
    reference_errors: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    if not db_path.is_file():
        return references

    connection = sqlite3.connect(db_path)
    try:
        source_urls_by_code = _product_source_page_urls_by_code(connection)

        for table in _image_reference_tables(connection):
            columns = _table_columns(connection, table)
            if "image_path" not in columns:
                continue

            selected = ["rowid", "image_path"]
            for optional in (
                "code",
                "image_hash",
                "image_url",
                "gallery_images",
            ):
                if optional in columns:
                    selected.append(optional)

            quoted_table = _quote_identifier(table)
            selected_sql = ", ".join(
                _quote_identifier(column) for column in selected
            )
            rows = connection.execute(
                f"SELECT {selected_sql} FROM {quoted_table}"
            ).fetchall()

            for row in rows:
                values = dict(zip(selected, row, strict=True))

                if table == "products":
                    code = str(values.get("code") or "").strip()
                    values["source_page_urls"] = source_urls_by_code.get(
                        code,
                        [],
                    )
                else:
                    values["source_page_urls"] = []

                references.extend(
                    _collect_row_image_references(
                        table,
                        values,
                        project_root,
                        reference_errors,
                    )
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

            parts = {part.casefold() for part in path.parts}
            name = path.name.casefold()
            if (
                ".staging" in parts
                or name.endswith(
                    (".tmp", ".review-tmp", ".review-backup", ".review-delete-backup")
                )
            ):
                continue

            # Product/gallery directories and flat data/images legacy files are
            # dedicated catalog storage. Scan unknown extensions there too so
            # corrupt/legacy assets are visible, while leaving resources/images
            # and unrelated resource trees extension-filtered.
            catalog_storage_path = bool({"products", "gallery"} & parts)
            flat_legacy_catalog_file = (
                root.name.casefold() == "images"
                and root.parent.name.casefold() == "data"
                and path.parent.resolve() == root.resolve()
            )
            if (
                path.suffix.lower() not in IMAGE_EXTENSIONS
                and not catalog_storage_path
                and not flat_legacy_catalog_file
            ):
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


def _annotate_source_provenance(
    files: list[dict[str, Any]],
    references: list[dict[str, Any]],
) -> None:
    """Attach product-page URL, image URL and extraction method to each file."""
    identities_by_path: dict[
        Path, set[tuple[str, str, str]]
    ] = defaultdict(set)
    incomplete_paths: set[Path] = set()
    page_urls_by_path: dict[Path, set[str]] = defaultdict(set)
    image_urls_by_path: dict[Path, set[str]] = defaultdict(set)
    methods_by_path: dict[Path, set[str]] = defaultdict(set)

    for reference in references:
        if reference["table"] != "products":
            continue

        image_path = reference["resolved_path"]
        page_urls = {
            str(url).strip()
            for url in (reference.get("source_page_urls") or [])
            if str(url).strip()
        }
        image_url = str(reference.get("image_url") or "").strip()
        method = str(reference.get("source") or "").strip()

        page_urls_by_path[image_path].update(page_urls)
        if image_url:
            image_urls_by_path[image_path].add(image_url)
        if method:
            methods_by_path[image_path].add(method)

        if len(page_urls) == 1 and image_url and method:
            identities_by_path[image_path].add(
                (next(iter(page_urls)), image_url, method)
            )
        else:
            incomplete_paths.add(image_path)

    for record in files:
        image_path = record["path"]
        identities = sorted(identities_by_path.get(image_path, set()))
        page_urls = sorted(page_urls_by_path.get(image_path, set()))
        image_urls = sorted(image_urls_by_path.get(image_path, set()))
        methods = sorted(methods_by_path.get(image_path, set()))

        record["source_page_urls"] = page_urls
        record["image_urls"] = image_urls
        record["source_urls"] = image_urls
        record["extraction_sources"] = methods

        if len(identities) == 1 and image_path not in incomplete_paths:
            (
                record["source_page_url"],
                record["source_url"],
                record["extraction_source"],
            ) = identities[0]
            record["source_provenance"] = "known"
        elif identities:
            record["source_page_url"] = (
                page_urls[0] if len(page_urls) == 1 else ""
            )
            record["source_url"] = (
                image_urls[0] if len(image_urls) == 1 else ""
            )
            record["extraction_source"] = (
                methods[0] if len(methods) == 1 else ""
            )
            record["source_provenance"] = "ambiguous"
        else:
            record["source_page_url"] = (
                page_urls[0] if len(page_urls) == 1 else ""
            )
            record["source_url"] = (
                image_urls[0] if len(image_urls) == 1 else ""
            )
            record["extraction_source"] = (
                methods[0] if len(methods) == 1 else ""
            )
            record["source_provenance"] = "unknown"


def _collect_image_group_maps(
    files: list[dict[str, Any]],
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
    dict[tuple[str, str, str, str], list[dict[str, Any]]],
]:
    """Build hash, filename, code-variant and fully source-aware groups."""
    hash_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    filename_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    code_variant_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_hash_groups: dict[
        tuple[str, str, str, str], list[dict[str, Any]]
    ] = defaultdict(list)

    for record in files:
        hash_groups[record["sha256"]].append(record)
        filename_groups[record["path"].name.casefold()].append(record)
        code_variant_groups[record["path"].stem.casefold()].append(record)

        if record["source_provenance"] == "known":
            source_hash_groups[
                (
                    str(record["sha256"]),
                    str(record["source_page_url"]),
                    str(record["source_url"]),
                    str(record["extraction_source"]),
                )
            ].append(record)

    return (
        hash_groups,
        filename_groups,
        code_variant_groups,
        source_hash_groups,
    )


def _groups_with_multiple_records(
    groups: dict[Any, list[dict[str, Any]]],
) -> list[list[dict[str, Any]]]:
    return [group for group in groups.values() if len(group) > 1]


def _groups_with_different_sources(
    groups: list[list[dict[str, Any]]],
) -> list[list[dict[str, Any]]]:
    result = []
    for group in groups:
        sources = {
            (
                record["source_page_url"],
                record["source_url"],
                record["extraction_source"],
            )
            for record in group
            if record["source_provenance"] == "known"
        }
        if len(sources) > 1:
            result.append(group)
    return result


def _groups_with_unknown_sources(
    groups: list[list[dict[str, Any]]],
) -> list[list[dict[str, Any]]]:
    return [
        group
        for group in groups
        if any(
            record["source_provenance"] != "known"
            for record in group
        )
    ]


def _groups_across_roots(
    groups: list[list[dict[str, Any]]],
) -> list[list[dict[str, Any]]]:
    return [
        group
        for group in groups
        if len({record["root"] for record in group}) > 1
    ]


def _classify_image_groups(
    files: list[dict[str, Any]],
    references: list[dict[str, Any]],
) -> dict[str, Any]:
    """Separate exact extraction sources from content-only coincidences."""
    _annotate_source_provenance(files, references)

    (
        hash_groups,
        filename_groups,
        code_variant_groups,
        source_hash_groups,
    ) = _collect_image_group_maps(files)

    content_duplicates = _groups_with_multiple_records(hash_groups)
    confirmed_duplicates = _groups_with_multiple_records(source_hash_groups)

    return {
        "duplicate_groups": confirmed_duplicates,
        "content_duplicate_groups": content_duplicates,
        "same_content_different_source_groups": (
            _groups_with_different_sources(content_duplicates)
        ),
        "same_content_unknown_source_groups": (
            _groups_with_unknown_sources(content_duplicates)
        ),
        "cross_root_duplicate_groups": (
            _groups_across_roots(confirmed_duplicates)
        ),
        "same_filename_groups": _groups_with_multiple_records(filename_groups),
        "same_code_variant_groups": (
            _groups_with_multiple_records(code_variant_groups)
        ),
    }




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
    reference_errors: list[dict[str, Any]] = []
    references = _collect_db_references(
        db_path,
        project_root,
        reference_errors,
    )

    file_by_path = {record["path"]: record for record in files}
    references_by_path: dict[Path, list[dict[str, Any]]] = defaultdict(list)
    for reference in references:
        references_by_path[reference["resolved_path"]].append(reference)

    image_groups = _classify_image_groups(files, references)

    active_references = [
        reference
        for reference in references
        if reference["table"] == "products"
    ]
    legacy_references = [
        reference
        for reference in references
        if reference["table"] != "products"
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
        "reference_audit_complete": not reference_errors,
        "reference_errors": reference_errors,
        "db_references_by_table": {
            table: sum(reference["table"] == table for reference in references)
            for table in sorted({reference["table"] for reference in references})
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
        **image_groups,
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


def _print_report_overview(report: dict[str, Any]) -> None:
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
    print(
        "Auditoría de referencias completa: "
        f"{report.get('reference_audit_complete', True)}"
    )


def _print_reference_errors(
    report: dict[str, Any],
    max_details: int,
) -> None:
    errors = report.get("reference_errors", [])
    if not errors:
        return

    print(
        "ADVERTENCIA: existen referencias de galería no interpretables; "
        "los conteos de huérfanos no son definitivos."
    )
    for error in errors[:max_details]:
        print(
            f"  - [{error.get('table')}#{error.get('rowid')}] "
            f"{error.get('code')}: {error.get('error')}"
        )


def _print_report_summary_counts(report: dict[str, Any]) -> None:
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
    print(
        "Grupos duplicados por hash y fuente: "
        f"{len(report['duplicate_groups'])}"
    )
    print(
        "Grupos con contenido idéntico de fuentes distintas: "
        f"{len(report['same_content_different_source_groups'])}"
    )
    print(
        "Grupos con procedencia desconocida o ambigua: "
        f"{len(report['same_content_unknown_source_groups'])}"
    )
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


def _print_missing_references(report: dict[str, Any], max_details: int) -> None:
    references = report["missing_reference_details"]
    if not references:
        return
    print("\nREFERENCIAS INEXISTENTES:")
    for reference in references[:max_details]:
        print(
            f"  - [{reference['table']}#{reference['rowid']}] "
            f"{reference['code']}: {reference['image_path']}"
        )


def _print_hash_mismatches(report: dict[str, Any], max_details: int) -> None:
    references = report["hash_mismatch_details"]
    if not references:
        return
    print("\nHASHES DISTINTOS:")
    for reference in references[:max_details]:
        print(
            f"  - [{reference['table']}#{reference['rowid']}] "
            f"{reference['code']}: {reference['image_path']}"
        )


def _print_cross_root_duplicates(
    report: dict[str, Any],
    max_details: int,
) -> None:
    groups = report["cross_root_duplicate_groups"]
    if not groups:
        return
    print("\nDUPLICADOS ENTRE ROOTS:")
    for group in groups[:max_details]:
        _print_group(group)


def _print_orphan_files(report: dict[str, Any], max_details: int) -> None:
    records = report["orphan_file_details"]
    if not records:
        return
    print("\nARCHIVOS SIN REFERENCIA DB:")
    for record in records[:max_details]:
        print(
            f"  - {record['path']} "
            f"({record['size']} bytes, sha256={record['sha256']})"
        )
    if len(records) > max_details:
        print(
            f"  ... {len(records) - max_details} "
            "más; use --json para el reporte completo."
        )


def print_report(report: dict[str, Any], max_details: int = 100) -> None:
    _print_report_overview(report)
    _print_reference_errors(report, max_details)
    _print_report_summary_counts(report)
    _print_missing_references(report, max_details)
    _print_hash_mismatches(report, max_details)
    _print_cross_root_duplicates(report, max_details)
    _print_orphan_files(report, max_details)

def _json_safe(value: Any) -> Any:
    """Recursively convert nested report values into JSON-safe data."""
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(
            (_json_safe(item) for item in value),
            key=repr,
        )
    return value




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
        "--data-root",
        type=Path,
        default=None,
        help=(
            "Raíz de datos para resolver rutas relativas de imágenes. "
            "Por defecto usa los dos niveles superiores de la ruta de la base."
        ),
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

    database_path = _resolve_project_path(args.db, project_root)
    data_root = (
        _resolve_project_path(args.data_root, project_root)
        if args.data_root is not None
        else database_path.parent.parent
    )
    report = audit(
        project_root=data_root,
        db_path=database_path,
        roots=args.roots,
    )
    if args.json:
        print(json.dumps(_json_safe(report), ensure_ascii=False, indent=2))
        return

    print_report(report, max_details=max(args.max_details, 0))


if __name__ == "__main__":
    main()
