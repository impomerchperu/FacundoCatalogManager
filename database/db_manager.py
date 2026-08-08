import os
import sqlite3


class DBManager:
    def __init__(self, db_path=None):

        base_dir = os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__),
            ),
        )

        if db_path is None:
            db_path = os.path.join(
                base_dir,
                "database",
                "catalog.db",
            )

        self.connection = sqlite3.connect(
            db_path,
            timeout=30,
        )

        self.connection.row_factory = sqlite3.Row

        self._configure_sqlite()

        self.initialize_database()

    def _configure_sqlite(self):
        """
        Configuración optimizada para cargas
        intensivas de scraping sobre SQLite.
        """

        cursor = self.connection.cursor()

        cursor.execute(
            "PRAGMA journal_mode=WAL;"
        )

        cursor.execute(
            "PRAGMA synchronous=NORMAL;"
        )

        cursor.execute(
            "PRAGMA foreign_keys=ON;"
        )

        self.connection.commit()

    def initialize_database(self):

        cursor = self.connection.cursor()

        schema_path = os.path.join(
            os.path.dirname(
                os.path.abspath(__file__),
            ),
            "schema.sql",
        )

        if os.path.exists(schema_path):

            with open(
                schema_path,
                "r",
                encoding="utf-8",
            ) as file:

                schema = file.read()

                cursor.executescript(
                    schema,
                )

        self.connection.commit()

    def execute_query(
        self,
        query,
        params=(),
    ):

        cursor = self.connection.cursor()

        cursor.execute(
            query,
            params,
        )

        self.connection.commit()

        return cursor

    def fetch_all(
        self,
        query,
        params=(),
    ):

        cursor = self.connection.cursor()

        cursor.execute(
            query,
            params,
        )

        return cursor.fetchall()

    def fetch_one(
        self,
        query,
        params=(),
    ):

        cursor = self.connection.cursor()

        cursor.execute(
            query,
            params,
        )

        return cursor.fetchone()

    def close(self):

        if self.connection:

            self.connection.close()
