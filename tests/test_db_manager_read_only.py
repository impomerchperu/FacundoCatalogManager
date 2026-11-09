import hashlib
import sqlite3

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
