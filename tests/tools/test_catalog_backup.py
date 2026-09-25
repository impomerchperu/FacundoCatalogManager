from __future__ import annotations

import sqlite3
from pathlib import Path

from tools.catalog_backup import create_backup, restore_backup


def _create_database(path: Path, value: str) -> None:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE products (code TEXT PRIMARY KEY, name TEXT)")
    connection.execute("INSERT INTO products (code, name) VALUES (?, ?)", ("P001", value))
    connection.commit()
    connection.close()


def _read_name(path: Path) -> str:
    connection = sqlite3.connect(path)
    try:
        return str(
            connection.execute(
                "SELECT name FROM products WHERE code='P001'"
            ).fetchone()[0]
        )
    finally:
        connection.close()


def test_create_backup_produces_integrity_checked_copy(tmp_path: Path):
    source = tmp_path / "catalog.db"
    backup = tmp_path / "backups" / "catalog.bak"
    _create_database(source, "original")

    result = create_backup(source, backup)

    assert result == backup
    assert backup.is_file()
    assert _read_name(backup) == "original"


def test_restore_backup_preserves_safety_copy_and_replaces_database(
    tmp_path: Path,
):
    source = tmp_path / "catalog.db"
    backup = tmp_path / "catalog-backup.bak"
    _create_database(source, "original")
    create_backup(source, backup)

    connection = sqlite3.connect(source)
    connection.execute("UPDATE products SET name='modified'")
    connection.commit()
    connection.close()

    safety_backup = restore_backup(backup, source)

    assert safety_backup is not None
    assert safety_backup.is_file()
    assert _read_name(safety_backup) == "modified"
    assert _read_name(source) == "original"


def test_restore_backup_does_not_require_existing_destination(
    tmp_path: Path,
):
    backup = tmp_path / "catalog-backup.bak"
    source = tmp_path / "source.db"
    destination = tmp_path / "restored" / "catalog.db"
    _create_database(source, "original")
    create_backup(source, backup)

    assert restore_backup(backup, destination) is None
    assert _read_name(destination) == "original"
