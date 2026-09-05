from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(slots=True)
class SyncResult:
    """Resultado consolidado de una sincronización de catálogo."""

    success: bool = False
    started_at: datetime | None = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    finished_at: datetime | None = None
    run_id: str = field(default_factory=lambda: uuid4().hex)
    processed: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0
    generated: int = 0
    missing_code: int = 0
    changes: list[dict] = field(default_factory=list)
    failures: list = field(default_factory=list)
    categories_processed: int = 0
    products_expected: int = 0
    expected_category_occurrences: int = 0
    products_found: int = 0
    products_unique: int = 0
    products_multiple_categories: int = 0
    duplicate_occurrences: int = 0
    category_summary: list[dict] = field(default_factory=list)
    multiple_category_products: list[dict] = field(default_factory=list)
    images_processed: int = 0
    images_downloaded: int = 0
    images_failed: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def products_created(self) -> int:
        """Alias compatible con el contador canónico ``created``."""
        return self.created

    @products_created.setter
    def products_created(self, value: int) -> None:
        self.created = int(value)

    @property
    def products_updated(self) -> int:
        """Alias compatible con el contador canónico ``updated``."""
        return self.updated

    @products_updated.setter
    def products_updated(self, value: int) -> None
        self.updated = int(value)

    @property
    def products_unchanged(self) -> int:
        """Alias compatible con el contador canónico ``unchanged``."""
        return self.unchanged

    @products_unchanged.setter
    def products_unchanged(self, value: int) -> None:
        self.unchanged = int(value)

    @property
    def products_deleted(self) -> int:
        """Alias compatible con el contador canónico ``deleted``."""
        return self.deleted

    @products_deleted.setter
    def products_deleted(self, value: int) -> None:
        self.deleted = int(value)

    def increment_processed(self) -> None:
        self.processed += 1

    @property
    def classified_total(self) -> int:
        return self.created + self.updated + self.unchanged

    @property
    def counts_are_consistent(self) -> bool:
        return self.classified_total == self.products_unique

    @property
    def coverage_gap(self) -> int:
        """Brecha respecto de las ocurrencias publicadas por categorías."""
        return self.category_occurrence_gap

    @property
    def coverage_complete(self) -> bool:
        """True when every expected category is covered and codes are valid."""
        if self.missing_code != 0:
            return False
        if self.expected_category_occurrences > 0:
            if self.products_found < self.expected_category_occurrences:
                return False
        elif self.products_found <= 0:
            return False
        return not any(
            max(int(row.get("gap", 0) or 0), 0) > 0
            for row in self.category_summary
        )

    @property
    def category_occurrence_gap(self) -> int:
        return max(self.expected_category_occurrences - self.products_found, 0)

    def finish(self) -> None:
        self.finished_at = datetime.now(timezone.utc)
        self.success = self.coverage_complete and not self.has_errors

    @property
    def duration_seconds(self) -> float:
        if not self.started_at or not self.finished_at:
            return 0.0
        return (self.finished_at - self.started_at).total_seconds()

    @property
    def has_errors(self) -> bool:
        return bool(self.errors) or bool(self.failures)

    def add_error(self, message: str) -> None:
        self.errors.append(message)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "success": self.success,
            "processed": self.processed,
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "deleted": self.deleted,
            "generated": self.generated,
            "missing_code": self.missing_code,
            "classified_total": self.classified_total,
            "counts_are_consistent": self.counts_are_consistent,
            "categories_processed": self.categories_processed,
            "products_expected": self.products_expected,
            "expected_category_occurrences": self.expected_category_occurrences,
            "products_found": self.products_found,
            "products_unique": self.products_unique,
            "products_multiple_categories": self.products_multiple_categories,
            "duplicate_occurrences": self.duplicate_occurrences,
            "category_summary": self.category_summary,
            "multiple_category_products": self.multiple_category_products,
            "coverage_gap": self.coverage_gap,
            "category_occurrence_gap": self.category_occurrence_gap,
            "reference_category_occurrences": self.expected_category_occurrences,
            "actual_category_occurrences": self.products_found,
            "unique_products": self.products_unique,
            "multi_category_products": self.products_multiple_categories,
            "coverage_complete": self.coverage_complete,
            "products_created": self.products_created,
            "products_updated": self.products_updated,
            "products_unchanged": self.products_unchanged,
            "products_deleted": self.products_deleted,
            "images_processed": self.images_processed,
            "images_downloaded": self.images_downloaded,
            "images_failed": self.images_failed,
            "errors": self.errors,
            "changes": self.changes,
            "failures": self.failures,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": self.duration_seconds,
        }

    def summary(self) -> dict:
        return {
            "Procesados": self.processed,
            "Nuevos": self.created,
            "Actualizados": self.updated,
            "Sin cambios": self.unchanged,
            "Eliminados": self.deleted,
            "Códigos generados": self.generated,
            "Sin código": self.missing_code,
            "Categorías": self.categories_processed,
            "Esperados únicos": self.products_expected,
            "Esperados por categorías": self.expected_category_occurrences,
            "Encontrados": self.products_found,
            "Únicos": self.products_unique,
            "Múltiples categorías": self.products_multiple_categories,
            "Apariciones duplicadas": self.duplicate_occurrences,
            "Brecha cobertura": self.coverage_gap,
            "Brecha por categorías": self.category_occurrence_gap,
            "Cobertura completa": self.coverage_complete,
            "Total clasificado": self.classified_total,
            "Conteos consistentes": self.counts_are_consistent,
            "Errores": len(self.errors),
            "Duración": self.duration_seconds,
        }
