import os
import sqlite3


class DBManager:
    """Gestiona SQLite con una inicialización ligera y persistente."""

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
        schema_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "schema.sql",
        )
        if os.path.exists(schema_path):
            with open(schema_path, "r", encoding="utf-8") as file:
                self.connection.executescript(file.read())

        self._run_migrations()
        self.connection.commit()

    def _run_migrations(self):
        """Completa tablas necesarias en bases SQLite ya existentes."""
        self._add_column_if_missing("products", "colors", "TEXT DEFAULT '[]'")
        self._add_column_if_missing(
            "products",
            "color_stock",
            "TEXT DEFAULT '{}'",
        )
        self._add_column_if_missing(
            "scraped_products",
            "colors",
            "TEXT DEFAULT '[]'",
        )
        self._add_column_if_missing(
            "scraped_products",
            "color_stock",
            "TEXT DEFAULT '{}'",
        )

        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS download_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                history_id INTEGER NOT NULL,
                change_type TEXT NOT NULL,
                code TEXT NOT NULL,
                product_name TEXT NOT NULL,
                field_name TEXT,
                field_label TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                FOREIGN KEY (history_id)
                    REFERENCES scraping_history(id)
                    ON DELETE CASCADE
            )
            """,
        )
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_download_changes_history_id
            ON download_changes(history_id)
            """,
        )
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_scraping_history_finished_at
            ON scraping_history(finished_at)
            """,
        )

    def _add_column_if_missing(
        self,
        table_name: str,
        column_name: str,
        column_definition: str,
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
