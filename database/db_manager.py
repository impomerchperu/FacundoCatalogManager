import sqlite3
import os


class DBManager:

    def __init__(self, db_path=None):

        if db_path is None:

            base_dir = os.path.dirname(
                os.path.dirname(
                    os.path.abspath(__file__)
                )
            )

            database_dir = os.path.join(
                base_dir,
                "database"
            )

            os.makedirs(
                database_dir,
                exist_ok=True
            )

            db_path = os.path.join(
                database_dir,
                "catalog.db"
            )

        self.connection = sqlite3.connect(
            db_path
        )

        self.connection.row_factory = sqlite3.Row



    def initialize_database(self):

        base_dir = os.path.dirname(
            os.path.abspath(__file__)
        )

        schema_path = os.path.join(
            base_dir,
            "schema.sql"
        )

        with open(
            schema_path,
            "r",
            encoding="utf-8"
        ) as file:

            schema = file.read()


        self.connection.executescript(
            schema
        )

        self.connection.commit()



    def execute_query(
        self,
        query,
        params=()
    ):

        cursor = self.connection.cursor()

        cursor.execute(
            query,
            params
        )

        self.connection.commit()

        return cursor



    def fetch_all(
        self,
        query,
        params=()
    ):

        cursor = self.connection.cursor()

        cursor.execute(
            query,
            params
        )

        return cursor.fetchall()



    def fetch_one(
        self,
        query,
        params=()
    ):

        cursor = self.connection.cursor()

        cursor.execute(
            query,
            params
        )

        return cursor.fetchone()



    def close(self):

        if self.connection:

            self.connection.close()