import hashlib
import sqlite3
from pathlib import Path

import pytest

from database.db_manager import DBManager


def test_read_only_connection_does_not_initialize_or_modify_database(tmp_path):
    database_path = tmp_path / "catalog.db"
    connection = sqlite3.connect(database_path)
    connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
    connection.execute("INSERT INTO sample (value) VALUES ('original')")
    connection.commit()
    connection.close()

    before_hash = hashlib.sha256(database_path.read_bytes()).hexdigest()
    manager = DBManager(database_path, read_only=True)
    try:
        assert manager.read_only is True
        assert manager.connection.execute("PRAGMA query_only").fetchone()[0] == 1
        assert manager.fetch_one(
            "SELECT value FROM sample"
        )["value"] == "original"
        assert manager.fetch_one(
            "SELECT name FROM sqlite_master WHERE name='schema_migrations'"
        ) is None
        assert not Path(f"{database_path}-wal").exists()
        assert not Path(f"{database_path}-shm").exists()

        with pytest.raises(sqlite3.OperationalError):
            manager.execute_query(
                "UPDATE sample SET value='changed'"
            )
        with pytest.raises(sqlite3.OperationalError):
            manager.connection.execute(
                "CREATE TABLE forbidden (value TEXT)"
            )
    finally:
        manager.close()

    after_hash = hashlib.sha256(database_path.read_bytes()).hexdigest()
    assert after_hash == before_hash


def test_read_only_connection_does_not_create_missing_database(tmp_path):
    database_path = tmp_path / "missing.db"

    with pytest.raises(FileNotFoundError):
        DBManager(database_path, read_only=True)

    assert not database_path.exists()


def test_read_only_connection_rejects_existing_wal_sidecars_without_touching_them(tmp_path):
    database_path = tmp_path / "catalog.db"
    writer = sqlite3.connect(database_path)
    try:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0].casefold() == "wal"
        writer.execute("CREATE TABLE sample (value TEXT NOT NULL)")
        writer.execute("INSERT INTO sample (value) VALUES ('base')")
        writer.commit()
        writer.execute("INSERT INTO sample (value) VALUES ('pending')")
        writer.commit()

        wal_path = Path(f"{database_path}-wal")
        shm_path = Path(f"{database_path}-shm")
        assert wal_path.is_file()
        assert shm_path.is_file()

        before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (database_path, wal_path, shm_path)
        }
        with pytest.raises(sqlite3.OperationalError, match="WAL/SHM"):
            DBManager(database_path, read_only=True)

        after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (database_path, wal_path, shm_path)
        }
        assert after == before
    finally:
        writer.close()
