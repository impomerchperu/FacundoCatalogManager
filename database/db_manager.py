import os
import sqlite3
from datetime import datetime, timedelta, timezone


class DBManager:
    def __init__(self, db_path=None):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        if db_path is None:
            db_path = os.path.join(base_dir, "database", "catalog.db")

        self.connection = sqlite3.connect(db_path, timeout=30)
        self.connection.row_factory = sqlite3.Row
        self._configure_sqlite()
        self.initialize_database()

    def _configure_sqlite(self):
        cursor = self.connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        self.connection.commit()

    def initialize_database(self):
        cursor = self.connection.cursor()
        schema_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "schema.sql"
        )

        if os.path.exists(schema_path):
            with open(schema_path, "r", encoding="utf-8") as file:
                cursor.executescript(file.read())

        self._run_migrations()
        self._create_migration_dependent_indexes()
        self._cleanup_expired_catalog_history()
        self.connection.commit()

    def _run_migrations(self):
        """Ejecuta migraciones idempotentes para bases existentes."""
        self._add_column_if_missing("scraping_history", "load_id", "INTEGER")
        self._add_column_if_missing("catalog_loads", "applied_at", "TEXT")
        self._add_column_if_missing("products", "colors", "TEXT DEFAULT '[]'")
        self._add_column_if_missing("products", "color_stock", "TEXT DEFAULT '{}'")
        self._add_column_if_missing("scraped_products", "colors", "TEXT DEFAULT '[]'")
        self._add_column_if_missing(
            "scraped_products", "color_stock", "TEXT DEFAULT '{}'"
        )
        self._add_column_if_missing(
            "catalog_load_products", "colors", "TEXT DEFAULT '[]'"
        )
        self._add_column_if_missing(
            "catalog_load_products", "color_stock", "TEXT DEFAULT '{}'"
        )

        self.connection.execute(
            """
            UPDATE catalog_loads
            SET applied_at = created_at
            WHERE applied = 1 AND applied_at IS NULL
            """,
        )

    def _create_migration_dependent_indexes(self):
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_scraping_history_load_id
            ON scraping_history(load_id)
            """,
        )
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_catalog_loads_applied_at
            ON catalog_loads(applied_at)
            """,
        )

    def _cleanup_expired_catalog_history(self, retention_days: int = 7) -> None:
        """Elimina historiales antiguos sin eliminar la última carga aplicada."""
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=retention_days)
        ).isoformat()
        latest_applied = self.fetch_one(
            """
            SELECT id
            FROM catalog_loads
            WHERE applied = 1 OR applied_at IS NOT NULL
            ORDER BY applied_at DESC, id DESC
            LIMIT 1
            """,
        )
        protected_load_id = (
            int(latest_applied["id"]) if latest_applied is not None else None
        )

        if protected_load_id is None:
            self.connection.execute(
                """
                DELETE FROM scraping_history
                WHERE started_at < ?
                """,
                (cutoff,),
            )
            self.connection.execute(
                """
                DELETE FROM catalog_loads
                WHERE created_at < ?
                """,
                (cutoff,),
            )
            return

        self.connection.execute(
            """
            DELETE FROM scraping_history
            WHERE started_at < ?
              AND (load_id IS NULL OR load_id != ?)
            """,
            (cutoff, protected_load_id),
        )
        self.connection.execute(
            """
            DELETE FROM catalog_loads
            WHERE created_at < ?
              AND id != ?
            """,
            (cutoff, protected_load_id),
        )

    def _add_column_if_missing(
        self, table_name: str, column_name: str, column_definition: str
    ) -> None:
        columns = self.fetch_all(f"PRAGMA table_info({table_name})")
        if column_name in {row["name"] for row in columns}:
            return
        self.connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}",
        )

    def execute_query(self, query, params=()):
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        self.connection.commit()
        return cursor

    def fetch_all(self, query, params=()):
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

    def fetch_one(self, query, params=()):
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()

    def close(self):
        if self.connection:
            self.connection.close()
