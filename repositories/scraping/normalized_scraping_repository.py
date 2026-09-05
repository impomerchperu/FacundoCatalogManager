from __future__ import annotations

from datetime import datetime, timezone

from database.db_manager import DBManager


class NormalizedScrapingRepository:
    """Persiste la observación del scraper en el modelo normalizado."""

    def __init__(self, db: DBManager | None = None) -> None:
        self.db = db or DBManager()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _canonical_url(url: str) -> str:
        value = str(url or "").strip()
        if not value:
            return ""
        return value.split("#", 1)[0].split("?", 1)[0].rstrip("/").casefold()

    def upsert_category(self, name: str, url: str, expected_count: int = 0) -> int:
        canonical_url = self._canonical_url(url)
        if not canonical_url:
            raise ValueError("La categoría requiere una URL canónica.")
        now = self._now()
        self.db.execute_query(
            """
            INSERT INTO categories
                (name, canonical_url, expected_count, last_scraped_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(canonical_url) DO UPDATE SET
                name=excluded.name,
                expected_count=excluded.expected_count,
                last_scraped_at=excluded.last_scraped_at,
                updated_at=excluded.updated_at
            """,
            (str(name or "").strip(), canonical_url, max(int(expected_count or 0), 0), now, now),
        )
        row = self.db.fetch_one(
            "SELECT id FROM categories WHERE canonical_url=?",
            (canonical_url,),
        )
        if row is None:
            raise RuntimeError("No se pudo obtener la categoría normalizada.")
        return int(row["id"])

    def start_run(
        self,
        *,
        mode: str,
        categories_requested: int,
        expected_category_occurrences: int,
    ) -> int:
        cursor = self.db.execute_query(
            """
            INSERT INTO scraping_runs
                (started_at, mode, status, categories_requested,
                 expected_category_occurrences)
            VALUES (?, ?, 'RUNNING', ?, ?)
            """,
            (
                self._now(),
                str(mode or "directed"),
                max(int(categories_requested or 0), 0),
                max(int(expected_category_occurrences or 0), 0),
            ),
        )
        return int(cursor.lastrowid)

    def finish_run(
        self,
        run_id: int,
        *,
        result,
        actual_category_occurrences: int,
        message: str = "",
    ) -> None:
        expected = max(int(getattr(result, "expected_category_occurrences", 0) or 0), 0)
        actual = max(int(actual_category_occurrences or 0), 0)
        gap = max(expected - actual, 0)
        errors = len(getattr(result, "errors", []) or [])
        coverage_complete = bool(expected <= 0 or (actual >= expected and errors == 0))
        status = "SUCCESS" if not errors else "ERROR"
        self.db.execute_query(
            """
            UPDATE scraping_runs
            SET finished_at=?,
                status=?,
                actual_category_occurrences=?,
                products_found=?,
                products_unique=?,
                products_multiple_categories=?,
                duplicate_occurrences=?,
                coverage_complete=?,
                coverage_gap=?,
                error_count=?,
                message=?
            WHERE id=?
            """,
            (
                self._now(),
                status,
                actual,
                int(getattr(result, "products_found", 0) or 0),
                int(getattr(result, "products_unique", 0) or 0),
                int(getattr(result, "products_multiple_categories", 0) or 0),
                int(getattr(result, "duplicate_occurrences", 0) or 0),
                int(coverage_complete),
                gap,
                errors,
                str(message or ""),
                run_id,
            ),
        )

    def persist_occurrences(self, run_id: int, categories, products, product_repository) -> int:
        category_ids = {
            str(getattr(category, "name", "")).strip().casefold(): self.upsert_category(
                getattr(category, "name", ""),
                getattr(category, "url", ""),
                getattr(category, "expected_count", 0),
            )
            for category in categories
        }
        now = self._now()
        occurrences = 0
        seen = set()
        for product in products:
            code = str(getattr(product, "code", "")).strip().upper()
            if not code:
                continue
            product_record = product_repository.get(code)
            product_id = getattr(product_record, "product_id", None)
            product_categories = {
                item.strip().casefold()
                for item in str(getattr(product, "category", "")).split(",")
                if item.strip()
            }
            for category_name, category_id in category_ids.items():
                if category_name not in product_categories:
                    continue
                key = (run_id, category_id, code.casefold())
                if key in seen:
                    continue
                seen.add(key)
                self.db.execute_query(
                    """
                    INSERT INTO product_categories
                        (product_id, category_id, first_seen_at, last_seen_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(product_id, category_id) DO UPDATE SET
                        last_seen_at=excluded.last_seen_at
                    """,
                    (product_id, category_id, now, now),
                )
                self.db.execute_query(
                    """
                    INSERT INTO scraping_product_occurrences
                        (run_id, category_id, product_id, code, product_url,
                         page_number, position, name, discovered_at)
                    VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?)
                    ON CONFLICT(run_id, category_id, code) DO UPDATE SET
                        product_id=excluded.product_id,
                        product_url=excluded.product_url,
                        name=excluded.name,
                        discovered_at=excluded.discovered_at
                    """,
                    (
                        run_id,
                        category_id,
                        product_id,
                        code,
                        str(getattr(product, "url", "") or ""),
                        str(getattr(product, "name", "") or ""),
                        now,
                    ),
                )
                occurrences += 1
        return occurrences
