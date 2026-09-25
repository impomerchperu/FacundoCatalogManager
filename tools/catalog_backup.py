from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from config.runtime_paths import DATABASE_PATH

SQLITE_OK = "ok"


def _integrity_check(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        row = connection.execute("PRAGMA integrity_check").fetchone()
    finally:
        connection.close()

    result = str(row[0]).strip().lower() if row else ""
    if result != SQLITE_OK:
        raise RuntimeError(
            f"La base de datos no supera PRAGMA integrity_check: {result or 'sin resultado'}"
        )


def _backup_to_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    if temporary.exists():
        temporary.unlink()

    source_connection = sqlite3.connect(source)
    destination_connection = sqlite3.connect(temporary)
    try:
        source_connection.backup(destination_connection)
        destination_connection.commit()
    finally:
        destination_connection.close()
        source_connection.close()

    try:
        _integrity_check(temporary)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def create_backup(
    source: str | Path = DATABASE_PATH,
    destination: str | Path | None = None,
) -> Path:
    source_path = Path(source)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    _integrity_check(source_path)

    if destination is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        destination_path = source_path.with_name(
            f"{source_path.stem}-{timestamp}.bak"
        )
    else:
        destination_path = Path(destination)

    _backup_to_file(source_path, destination_path)
    return destination_path


def restore_backup(
    backup: str | Path,
    destination: str | Path = DATABASE_PATH,
) -> Path | None:
    backup_path = Path(backup)
    destination_path = Path(destination)

    if not backup_path.is_file():
        raise FileNotFoundError(backup_path)

    _integrity_check(backup_path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    safety_backup: Path | None = None
    if destination_path.is_file():
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safety_backup = destination_path.with_name(
            f"{destination_path.stem}-pre-restore-{timestamp}.bak"
        )
        _backup_to_file(destination_path, safety_backup)

    temporary = destination_path.with_name(destination_path.name + ".restore.tmp")
    temporary.unlink(missing_ok=True)

    shutil.copy2(backup_path, temporary)

    try:
        _integrity_check(temporary)
        temporary.replace(destination_path)
        Path(str(destination_path) + "-wal").unlink(missing_ok=True)
        Path(str(destination_path) + "-shm").unlink(missing_ok=True)
        _integrity_check(destination_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    return safety_backup


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backup y restauración segura de catalog.db."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup = subparsers.add_parser("backup")
    backup.add_argument("--database", type=Path, default=DATABASE_PATH)
    backup.add_argument("--output", type=Path)

    restore = subparsers.add_parser("restore")
    restore.add_argument("backup", type=Path)
    restore.add_argument("--database", type=Path, default=DATABASE_PATH)

    return parser


def main() -> None:
    args = _build_parser().parse_args()

    if args.command == "backup":
        result = create_backup(args.database, args.output)
        print(f"Backup creado: {result}")
        return

    safety_backup = restore_backup(args.backup, args.database)
    print(f"Restauración completada: {args.database}")
    if safety_backup is not None:
        print(f"Backup previo conservado: {safety_backup}")


if __name__ == "__main__":
    main()
