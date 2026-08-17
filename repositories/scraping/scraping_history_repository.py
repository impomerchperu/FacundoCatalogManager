import json
from datetime import datetime
from typing import ClassVar

from models.scraping.scraping_history import ScrapingHistory


class ScrapingHistoryRepository:
    """Persistencia del historial de descargas y sus cambios."""

    PRODUCT_FIELDS = (
        "name",
        "category",
        "description",
        "price",
        "price_sample",
        "price_hundred",
        "price_thousand",
        "stock",
        "colors",
        "color_stock",
        "image_url",
        "image_path",
        "image_hash",
        "content_hash",
    )

    FIELD_LABELS: ClassVar[dict[str, str]] = {
        "code": "Código",
        "name": "Nombre",
        "category": "Categoría",
        "description": "Detalle",
        "price": "Precio",
        "price_sample": "Precio muestra",
        "price_hundred": "Precio ciento",
        "price_thousand": "Precio millar",
        "stock": "Stock",
        "colors": "Colores",
        "color_stock": "Stock por color",
        "image_url": "URL imagen",
        "image_path": "Ruta imagen",
        "image_hash": "Hash imagen",
        "content_hash": "Hash contenido",
    }

    def __init__(self, db):
        self.db = db

    def save(
        self,
        history: ScrapingHistory,
        changes: list[dict] | None = None,
        products: list | None = None,
    ) -> int:
        """Guarda una descarga ya aplicada y únicamente sus cambios."""
        cursor = self.db.execute_query(
            """
            INSERT INTO scraping_history (
                started_at, finished_at, processed, created, updated,
                unchanged, deleted, errors, status, message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                history.started_at.isoformat(),
                history.finished_at.isoformat(),
                history.processed,
                history.created,
                history.updated,
                history.unchanged,
                history.deleted,
                history.errors,
                history.status,
                history.message,
            ),
        )
        history.history_id = int(cursor.lastrowid)

        product_map = {
            str(getattr(product, "code", "")): product
            for product in (products or [])
        }

        for item in changes or []:
            code = str(item.get("code", ""))
            name = str(item.get("name", ""))
            item_type = item.get("type")

            if item_type == "CODE_GENERATED":
                self._insert_change(
                    history.history_id,
                    "CODE_GENERATED",
                    code,
                    name,
                    "code",
                    "Código generado",
                    "Sin código",
                    code,
                )
                continue

            if item_type == "NEW":
                product = product_map.get(code)
                if product is None:
                    self._insert_change(
                        history.history_id,
                        "NEW",
                        code,
                        name,
                        None,
                        "Producto nuevo",
                        None,
                        "Alta",
                    )
                    continue
                for field in self.PRODUCT_FIELDS:
                    self._insert_change(
                        history.history_id,
                        "NEW",
                        code,
                        name,
                        field,
                        self.FIELD_LABELS[field],
                        None,
                        self._serialize(self._value(product, field)),
                    )
                continue

            if item_type == "DELETED":
                self._insert_change(
                    history.history_id,
                    "DELETED",
                    code,
                    name,
                    None,
                    "Producto eliminado",
                    "Presente en catálogo",
                    "Ausente en origen",
                )
                continue

            for change in item.get("changes") or []:
                field = str(change.get("field", ""))
                self._insert_change(
                    history.history_id,
                    "UPDATED",
                    code,
                    name,
                    field,
                    str(change.get("label", self.FIELD_LABELS.get(field, field))),
                    self._serialize(change.get("old")),
                    self._serialize(change.get("new")),
                )

        return history.history_id

    def _insert_change(
        self,
        history_id: int,
        change_type: str,
        code: str,
        name: str,
        field: str | None,
        label: str,
        old_value,
        new_value,
    ) -> None:
        self.db.execute_query(
            """
            INSERT INTO download_changes (
                history_id, change_type, code, product_name,
                field_name, field_label, old_value, new_value
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                history_id,
                change_type,
                code,
                name,
                field,
                label,
                old_value,
                new_value,
            ),
        )

    def get_all(self):
        return self.get_latest(limit=1000)

    def get_latest(self, limit: int = 100):
        rows = self.db.fetch_all(
            """
            SELECT id, started_at, finished_at, processed, created,
                   updated, unchanged, deleted, errors, status, message
            FROM scraping_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [self._map_row(row) for row in rows]

    def get_by_id(self, history_id: int):
        row = self.db.fetch_one(
            """
            SELECT id, started_at, finished_at, processed, created,
                   updated, unchanged, deleted, errors, status, message
            FROM scraping_history
            WHERE id = ?
            """,
            (history_id,),
        )
        return None if row is None else self._map_row(row)

    def get_changes(self, history_id: int) -> list[dict]:
        rows = self.db.fetch_all(
            """
            SELECT change_type, code, product_name, field_name,
                   field_label, old_value, new_value
            FROM download_changes
            WHERE history_id = ?
            ORDER BY code COLLATE NOCASE ASC, id ASC
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
    def _value(product, field):
        if isinstance(product, dict):
            return product.get(field)
        return getattr(product, field, None)

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
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return value

    @staticmethod
    def _map_row(row) -> ScrapingHistory:
        return ScrapingHistory(
            history_id=row["id"],
            started_at=datetime.fromisoformat(row["started_at"]),
            finished_at=datetime.fromisoformat(row["finished_at"]),
            processed=row["processed"],
            created=row["created"],
            updated=row["updated"],
            unchanged=row["unchanged"],
            deleted=row["deleted"],
            errors=row["errors"],
            status=row["status"],
            message=row["message"],
        )
