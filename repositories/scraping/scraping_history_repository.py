from datetime import datetime

from models.scraping.scraping_history import ScrapingHistory


class ScrapingHistoryRepository:
    """
    Repositorio SQLite para historial
    de sincronizaciones de scraping.
    """

    def __init__(
        self,
        db,
    ):
        self.db = db

    def save(
        self,
        history: ScrapingHistory,
    ) -> int:
        cursor = self.db.execute_query(
            """
            INSERT INTO scraping_history (
                load_id,
                started_at,
                finished_at,
                processed,
                created,
                updated,
                unchanged,
                errors,
                status,
                message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                history.load_id,
                history.started_at.isoformat(),
                history.finished_at.isoformat(),
                history.processed,
                history.created,
                history.updated,
                history.unchanged,
                history.errors,
                history.status,
                history.message,
            ),
        )

        history.history_id = cursor.lastrowid

        return int(cursor.lastrowid)

    def get_all(self):
        rows = self.db.fetch_all(
            """
            SELECT
                id,
                load_id,
                started_at,
                finished_at,
                processed,
                created,
                updated,
                unchanged,
                errors,
                status,
                message
            FROM scraping_history
            ORDER BY id DESC
            """
        )

        return [
            self._map_row(row)
            for row in rows
        ]

    def get_latest(
        self,
        limit: int = 10,
    ):
        rows = self.db.fetch_all(
            """
            SELECT
                id,
                load_id,
                started_at,
                finished_at,
                processed,
                created,
                updated,
                unchanged,
                errors,
                status,
                message
            FROM scraping_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                limit,
            ),
        )

        return [
            self._map_row(row)
            for row in rows
        ]

    def get_by_id(
        self,
        history_id: int,
    ):
        row = self.db.fetch_one(
            """
            SELECT
                id,
                load_id,
                started_at,
                finished_at,
                processed,
                created,
                updated,
                unchanged,
                errors,
                status,
                message
            FROM scraping_history
            WHERE id = ?
            """,
            (history_id,),
        )

        if row is None:
            return None

        return self._map_row(row)

    def _map_row(
        self,
        row,
    ) -> ScrapingHistory:
        return ScrapingHistory(
            history_id=row["id"],
            load_id=row["load_id"],
            started_at=datetime.fromisoformat(
                row["started_at"],
            ),
            finished_at=datetime.fromisoformat(
                row["finished_at"],
            ),
            processed=row["processed"],
            created=row["created"],
            updated=row["updated"],
            unchanged=row["unchanged"],
            errors=row["errors"],
            status=row["status"],
            message=row["message"],
        )
