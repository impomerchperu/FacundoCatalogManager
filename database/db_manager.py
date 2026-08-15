import os
import sqlite3


class DBManager:
    """Gestiona SQLite con inicialización, migraciones y persistencia segura."""

    def __init__(self, db_path=None):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if db_path is None:
            db_path = os.path.join(base_dir, "database", "catalog.db")

        self.connection = sqlite3.connect(db_path, timeout=30)
        self.connection.row_factory = sqlite3.Row
        self._transaction_active = False
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
        """Completa y corrige estructuras necesarias en bases existentes."""
        self._add_column_if_missing(
            "products",
            "color_stock",
            "TEXT DEFAULT '{}'",
        )
        self._add_column_if_missing(
            "scraped_products",
            "color_stock",
            "TEXT DEFAULT '{}'",
        )
        self._remove_legacy_colors_column("products")
        self._remove_legacy_colors_column("scraped_products")

        self._migrate_download_changes()

        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_scraping_history_finished_at
            ON scraping_history(finished_at)
            """
        )

    def _remove_legacy_colors_column(self, table_name: str) -> None:
        """Elimina la columna antigua colors de bases existentes."""
        columns = self.fetch_all(f"PRAGMA table_info({table_name})")
        if "colors" not in {row["name"] for row in columns}:
            return
        self.connection.execute(f"ALTER TABLE {table_name} DROP COLUMN colors")

    def _migrate_download_changes(self):
        """Garantiza la FK de download_changes hacia scraping_history."""
        if not self._table_exists("download_changes"):
            self._create_download_changes_table()
            self._create_download_changes_indexes()
            return

        foreign_keys = self.fetch_all(
            "PRAGMA foreign_key_list(download_changes)"
        )

        references_scraping_history = any(
            row["table"] == "scraping_history"
            and row["from"] == "history_id"
            and row["to"] == "id"
            for row in foreign_keys
        )

        if references_scraping_history:
            self._create_download_changes_indexes()
            return

        self._backup_legacy_download_changes()
        self._create_download_changes_table()
        self._create_download_changes_indexes()

    def _backup_legacy_download_changes(self):
        """Conserva la tabla antigua antes de reconstruir su FK."""
        legacy_table = "download_changes_legacy"

        if self._table_exists(legacy_table):
            return

        self.connection.execute(
            "DROP INDEX IF EXISTS idx_download_changes_history_id"
        )
        self.connection.execute("DROP INDEX IF EXISTS idx_download_changes_code")
        self.connection.execute(
            "ALTER TABLE download_changes RENAME TO download_changes_legacy"
        )

    def _create_download_changes_table(self):
        """Crea la tabla de detalles con la FK correcta."""
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
            """
        )

    def _create_download_changes_indexes(self):
        """Crea índices para las consultas del historial."""
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_download_changes_history_id
            ON download_changes(history_id)
            """
        )
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_download_changes_code
            ON download_changes(code)
            """
        )

    def _table_exists(self, table_name: str) -> bool:
        row = self.connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            """,
            (table_name,),
        ).fetchone()
        return row is not None

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
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )

    def begin(self):
        """Inicia una transacción explícita."""
        if self._transaction_active:
            raise RuntimeError("Ya existe una transacción activa.")
        self.connection.execute("BEGIN")
        self._transaction_active = True

    def commit(self):
        """Confirma la transacción activa."""
        if not self._transaction_active:
            return
        self.connection.commit()
        self._transaction_active = False

    def rollback(self):
        """Revierte la transacción activa."""
        if not self._transaction_active:
            return
        self.connection.rollback()
        self._transaction_active = False

    def execute_query(self, query, params=()):
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        if not self._transaction_active:
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
            if self._transaction_active:
                self.rollback()
            self.connection.close()
