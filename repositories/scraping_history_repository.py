from models.scraping.scraping_history import ScrapingHistory


class ScrapingHistoryRepository:

    def __init__(self, db):

        self.db = db


    def save(
        self,
        history: ScrapingHistory,
    ):

        cursor = self.db.execute_query(
            """
            INSERT INTO scraping_history
            (
                started_at,
                finished_at,
                processed,
                created,
                updated,
                unchanged,
                errors,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                history.started_at.isoformat(),
                history.finished_at.isoformat(),
                history.processed,
                history.created,
                history.updated,
                history.unchanged,
                history.errors,
                history.status,
            ),
        )

        history.history_id = cursor.lastrowid

        return history


    def get_all(self):

        return self.db.fetch_all(
            """
            SELECT *
            FROM scraping_history
            ORDER BY id DESC
            """
        )
