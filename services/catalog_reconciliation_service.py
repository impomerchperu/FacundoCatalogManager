from typing import ClassVar

from database.db_manager import DBManager


class CatalogReconciliationService:
    """Reconstruye el catálogo desde la última ejecución FULL válida."""

    PRODUCT_COLUMNS: ClassVar[tuple[str, ...]] = (
        "code",
        "name",
        "category",
        "description",
        "price",
        "price_sample",
        "price_hundred",
        "price_thousand",
        "stock",
        "color_stock",
        "image_url",
        "image_path",
        "image_hash",
        "content_hash",
    )

    def __init__(self, db: DBManager) -> None:
        self.db = db

    def find_latest_successful_full_run(self):
        candidates = self.db.fetch_all(
            """
            SELECT id,
                   expected_category_occurrences,
                   actual_category_occurrences,
                   products_found,
                   products_unique,
                   coverage_gap,
                   error_count
            FROM scraping_runs
            WHERE mode='full'
              AND status='SUCCESS'
              AND coverage_complete=1
            ORDER BY id DESC
            """
        )
        for run in candidates:
            run_id = int(run["id"])
            occurrence_count = self.db.fetch_one(
                """
                SELECT COUNT(*) AS total,
                       COUNT(DISTINCT UPPER(TRIM(code))) AS unique_codes
                FROM scraping_product_occurrences
                WHERE run_id=?
                """,
                (run_id,),
            )
            total_occurrences = (
                int(occurrence_count["total"] or 0) if occurrence_count else 0
            )
            unique_codes = (
                int(occurrence_count["unique_codes"] or 0) if occurrence_count else 0
            )
            if self._run_metrics_are_consistent(
                run,
                total_occurrences=total_occurrences,
                unique_codes=unique_codes,
            ):
                return run
        return None

    def reconcile_latest_successful_run(self) -> int:
        """Reconstruye productos y relaciones exclusivamente desde el último FULL válido."""
        run = self.find_latest_successful_full_run()
        if run is None:
            return 0

        run_id = int(run["id"])
        occurrence_count = self.db.fetch_one(
            """
            SELECT COUNT(*) AS total
            FROM scraping_product_occurrences
            WHERE run_id=?
            """,
            (run_id,),
        )
        total_occurrences = (
            int(occurrence_count["total"] or 0) if occurrence_count else 0
        )
        if total_occurrences <= 0:
            return 0

        self.db.begin()
        try:
            self._restore_missing_products_from_legacy_sources(run_id)
            self.db.execute_query(
                """
                UPDATE scraping_product_occurrences
                SET product_id=(
                    SELECT p.id
                    FROM products p
                    WHERE UPPER(TRIM(p.code))=UPPER(TRIM(scraping_product_occurrences.code))
                    LIMIT 1
                )
                WHERE run_id=?
                """,
                (run_id,),
            )
            missing = self.db.fetch_one(
                """
                SELECT COUNT(*) AS total
                FROM scraping_product_occurrences
                WHERE run_id=? AND product_id IS NULL
                """,
                (run_id,),
            )
            if missing is None or int(missing["total"] or 0) != 0:
                self.db.rollback()
                return 0

            self.db.execute_query("DELETE FROM product_categories")
            self.db.execute_query(
                """
                DELETE FROM products
                WHERE id NOT IN (
                    SELECT DISTINCT product_id
                    FROM scraping_product_occurrences
                    WHERE run_id=?
                )
                """,
                (run_id,),
            )
            self.db.execute_query(
                """
                INSERT INTO product_categories
                    (product_id, category_id, first_seen_at, last_seen_at)
                SELECT product_id, category_id, MIN(discovered_at), MAX(discovered_at)
                FROM scraping_product_occurrences
                WHERE run_id=?
                GROUP BY product_id, category_id
                ON CONFLICT(product_id, category_id) DO UPDATE SET
                    last_seen_at=excluded.last_seen_at
                """,
                (run_id,),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        row = self.db.fetch_one("SELECT COUNT(*) AS total FROM products")
        return int(row["total"]) if row else 0

    @staticmethod
    def _run_metrics_are_consistent(
        run,
        *,
        total_occurrences: int,
        unique_codes: int,
    ) -> bool:
        expected_occurrences = int(run["expected_category_occurrences"] or 0)
        actual_occurrences = int(run["actual_category_occurrences"] or 0)
        products_found = int(run["products_found"] or 0)
        products_unique = int(run["products_unique"] or 0)
        coverage_gap = int(run["coverage_gap"] or 0)
        error_count = int(run["error_count"] or 0)

        if coverage_gap != 0 or error_count != 0:
            return False
        if total_occurrences <= 0:
            return False
        if expected_occurrences > 0 and total_occurrences != expected_occurrences:
            return False
        if actual_occurrences > 0 and total_occurrences != actual_occurrences:
            return False
        if products_found > 0 and total_occurrences != products_found:
            return False
        if products_unique > 0 and unique_codes != products_unique:
            return False
        return True

    def _restore_missing_products_from_legacy_sources(self, run_id: int) -> None:
        missing = self.db.fetch_all(
            """
            SELECT DISTINCT UPPER(TRIM(o.code)) AS code
            FROM scraping_product_occurrences o
            LEFT JOIN products p
              ON UPPER(TRIM(p.code))=UPPER(TRIM(o.code))
            WHERE o.run_id=? AND p.id IS NULL
            """,
            (run_id,),
        )
        for row in missing:
            code = self._normalize_code(row["code"])
            if not code:
                continue

            legacy = self.db.fetch_one(
                """
                SELECT code, name, category, description, price, price_sample,
                       price_hundred, price_thousand, stock, color_stock,
                       image_url, image_path, image_hash, content_hash
                FROM scraped_products
                WHERE UPPER(TRIM(code))=?
                ORDER BY id DESC
                LIMIT 1
                """,
                (code,),
            )
            if legacy is None:
                legacy = self.db.fetch_one(
                    """
                    SELECT code, name, category, description, price, price_sample,
                           price_hundred, price_thousand, stock, color_stock,
                           image_url, image_path, image_hash, content_hash
                    FROM sync_records
                    WHERE UPPER(TRIM(code))=?
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (code,),
                )
            if legacy is None:
                continue

            placeholders = ", ".join("?" for _ in self.PRODUCT_COLUMNS)
            self.db.execute_query(
                f"INSERT OR IGNORE INTO products ({', '.join(self.PRODUCT_COLUMNS)}) "
                f"VALUES ({placeholders})",
                tuple(legacy[column] for column in self.PRODUCT_COLUMNS),
            )

    @staticmethod
    def _normalize_code(value) -> str:
        return str(value or "").strip().upper()
