import json
from datetime import datetime

from models.scraping.scraping_history import ScrapingHistory


class ScrapingHistoryRepository:
    """Persistencia ligera del historial de cambios del catálogo."""

    def __init__(self, db):
        self.db = db

    def save(self, history: ScrapingHistory, changes: list[dict] | None = None) -> int:
        cursor = self.db.execute_query(
            """
            INSERT INTO download_history (
                created_at, finished_at, processed, new_products,
                updated_products, unchanged_products, errors, status, message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                history.message,
            ),
        )
        history.history_id = int(cursor.lastrowid)

        for item in changes or []:
            item_changes = item.get("changes") or []
            if item.get("type") == "NEW":
                self.db.execute_query(
                    """
                    INSERT INTO download_changes (
                        history_id, change_type, code, product_name,
                        field_name, field_label, old_value, new_value
                    ) VALUES (?, ?, ?, ?, NULL, ?, ?, ?)
                    """,
                    (
                        history.history_id,
                        "NEW",
                        str(item.get("code", "")),
                        str(item.get("name", "")),
                        "Producto nuevo",
                        None,
                        "Alta",
                    ),
                )
                continue

            for change in item_changes:
                self.db.execute_query(
                    """
                    INSERT INTO download_changes (
                        history_id, change_type, code, product_name,
                        field_name, field_label, old_value, new_value
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        history.history_id,
                        "UPDATED",
                        str(item.get("code", "")),
                        str(item.get("name", "")),
                        str(change.get("field", "")),
                        str(change.get("label", change.get("field", ""))),
                        self._serialize(change.get("old")),
                        self._serialize(change.get("new")),
                    ),
                )

        return history.history_id

    def get_all(self):
        return self.get_latest(limit=1000)

    def get_latest(self, limit: int = 100):
        rows = self.db.fetch_all(
            """
            SELECT id, created_at, finished_at, processed,
                   new_products, updated_products, unchanged_products,
                   errors, status, message
            FROM download_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [self._map_row(row) for row in rows]

    def get_changes(self, history_id: int) -> list[dict]:
        rows = self.db.fetch_all(
            """
            SELECT change_type, code, product_name, field_name,
                   field_label, old_value, new_value
            FROM download_changes
            WHERE history_id = ?
            ORDER BY id
            """,
            (history_id,),
        )
        return [
            {
                "type": row["change_type"],
                "code": row["code"],
                "name": row["product_name"],
                "field": row["field_name"],
                "label": row["field_label"],
                "old": self._deserialize(row["old_value"]),
                "new": self._deserialize(row["new_value"]),
            }
            for row in rows
        ]

    @staticmethod
    def _serialize(value) -> str | None:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value)

    @staticmethod
    def _deserialize(value):
        if value is None:
            return None
        if not isinstance(value, str):
            return value

        stripped = value.strip()
        if not stripped or stripped[0] not in "[{":
            return value

        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    @staticmethod
    def _map_row(row) -> ScrapingHistory:
        return ScrapingHistory(
            history_id=row["id"],
            started_at=datetime.fromisoformat(row["created_at"]),
            finished_at=datetime.fromisoformat(row["finished_at"]),
            processed=row["processed"],
            created=row["new_products"],
            updated=row["updated_products"],
            unchanged=row["unchanged_products"],
            errors=row["errors"],
            status=row["status"],
            message=row["message"],
        )
