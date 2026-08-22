import json
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar

from models.scraping.sync_result import SyncResult

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRAPING_CODE_SNAPSHOT = PROJECT_ROOT / "data" / "last_scraping_codes.json"


class CatalogSyncService:
    """Compara productos obtenidos contra el catálogo persistido."""

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

    def __init__(self, repository, diff_service):
        self.repository = repository
        self.diff_service = diff_service
        self.last_sync_result = SyncResult()

    @staticmethod
    def _normalize_code(value) -> str:
        """Normaliza mayúsculas y espacios exteriores.

        Conserva el cuerpo exacto del código.
        """
        return str(value or "").strip().upper()

    def sync(
        self,
        products,
        prune_missing: bool = False,
        cleanup_generated: bool = True,
        expected_products: int | None = 0,
        expected_category_occurrences: int = 0,
    ):
        """Sincroniza el catálogo usando códigos reales como identidad."""
        del cleanup_generated
        result = SyncResult()
        raw_products = list(products)
        missing_code_products = [
            p for p in raw_products if not self._normalize_code(getattr(p, "code", ""))
        ]
        for product in missing_code_products:
            result.missing_code += 1
            result.changes.append(
                {
                    "type": "MISSING_CODE",
                    "code": "",
                    "name": str(getattr(product, "name", "")).strip(),
                    "changes": [
                        {
                            "field": "code",
                            "label": "Código no encontrado",
                            "old": "Sin código",
                            "new": "Ignorado",
                        }
                    ],
                }
            )
        prepared = []
        for product in raw_products:
            code = self._normalize_code(getattr(product, "code", ""))
            if not code:
                continue
            product.code = code
            prepared.append(product)
        consolidated = self.consolidate_products(prepared)
        result.products_expected = max(int(expected_products or 0), 0)
        result.expected_category_occurrences = max(
            int(expected_category_occurrences or 0), 0
        )
        result.products_found = len(raw_products)
        result.products_unique = len(consolidated)
        result.processed = result.products_found
        result.duplicate_occurrences = max(
            result.products_found - result.products_unique, 0
        )
        result.products_multiple_categories = self._count_multi_category_products(
            prepared
        )
        scraped_codes = {self._normalize_code(p.code).casefold() for p in consolidated}

        for product in consolidated:
            existing = self.repository.get(product.code)
            if existing is None:
                result.created += 1
                result.changes.append(
                    {
                        "type": "NEW",
                        "code": product.code,
                        "name": product.name,
                        "changes": [],
                    }
                )
                self.repository.save(product)
                continue

            product.category = self._merge_categories(
                self._value(existing, "category"),
                getattr(product, "category", ""),
            )
            comparison = self.diff_service.compare(existing, product)
            if comparison["changed"]:
                result.updated += 1
                result.changes.append(
                    {
                        "type": "UPDATED",
                        "code": product.code,
                        "name": product.name,
                        "changes": [
                            {
                                "field": field,
                                "label": self.FIELD_LABELS.get(field, field),
                                "old": self._value(existing, field),
                                "new": self._value(product, field),
                            }
                            for field in comparison["fields"]
                        ],
                    }
                )
                self.repository.save(product)
            else:
                result.unchanged += 1

        prune_allowed = (
            result.coverage_complete
            and not result.has_errors
            and (prune_missing or result.products_expected > 0)
        )
        if prune_allowed:
            self._remove_missing_products(scraped_codes, result)
        result.finish()
        self.last_sync_result = result

        snapshot_eligible = (
            result.products_expected > 0
            and result.expected_category_occurrences > 0
            and result.coverage_complete
            and result.products_found >= result.expected_category_occurrences
            and not result.has_errors
        )
        if snapshot_eligible:
            self._write_code_snapshot(scraped_codes, result)
        return result

    @staticmethod
    def _write_code_snapshot(scraped_codes: set[str], result: SyncResult) -> None:
        """Persiste los códigos del scraping completo para auditoría y limpieza."""
        SCRAPING_CODE_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "codes": sorted(scraped_codes),
            "scraped_unique_products": len(scraped_codes),
            "expected_unique_products": result.products_unique,
            "expected_catalog_products": result.products_expected,
            "expected_category_occurrences": result.expected_category_occurrences,
            "products_found": result.products_found,
            "coverage_complete": result.coverage_complete,
            "errors": list(result.errors),
            "failures": list(result.failures),
        }
        SCRAPING_CODE_SNAPSHOT.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def sync_full_catalog(
        self,
        products,
        prune_missing: bool = True,
        expected_products: int | None = 0,
        expected_category_occurrences: int = 0,
    ):
        return self.sync(
            products,
            prune_missing=prune_missing,
            expected_products=expected_products,
            expected_category_occurrences=expected_category_occurrences,
        )

    def synchronize(self, products, prune_missing: bool = False):
        return self.sync(products, prune_missing=prune_missing)

    def _remove_missing_products(
        self, scraped_codes: set[str], result: SyncResult
    ) -> None:
        for existing in self.repository.get_all():
            code = self._normalize_code(self._value(existing, "code"))
            if not code or code.casefold() in scraped_codes:
                continue
            result.deleted += 1
            result.changes.append(
                {
                    "type": "DELETED",
                    "code": code,
                    "name": self._value(existing, "name"),
                    "changes": [
                        {
                            "field": "code",
                            "label": "Código ausente en origen",
                            "old": code,
                            "new": "Eliminado",
                        }
                    ],
                }
            )
            self.repository.delete_by_code(code)

    @classmethod
    def consolidate_products(cls, products):
        consolidated = {}
        for product in products:
            code = cls._normalize_code(getattr(product, "code", ""))
            if not code:
                continue
            product.code = code
            existing = consolidated.get(code.casefold())
            if existing is None:
                consolidated[code.casefold()] = product
                continue
            existing.category = cls._merge_categories(
                existing.category, product.category
            )
            colors = list(getattr(existing, "colors", [])) + list(
                getattr(product, "colors", [])
            )
            existing.colors = list(
                dict.fromkeys(str(c).strip() for c in colors if str(c).strip())
            )
            color_stock = dict(getattr(existing, "color_stock", {}))
            for color, stock in getattr(product, "color_stock", {}).items():
                normalized_color = str(color).strip()
                if not normalized_color:
                    continue
                try:
                    normalized_stock = max(int(stock), 0)
                except (TypeError, ValueError):
                    continue
                color_stock[normalized_color] = max(
                    color_stock.get(normalized_color, 0), normalized_stock
                )
            existing.color_stock = color_stock
            if not getattr(existing, "description", "") and getattr(
                product, "description", ""
            ):
                existing.description = product.description
            if not getattr(existing, "image_url", "") and getattr(
                product, "image_url", ""
            ):
                existing.image_url = product.image_url
        return list(consolidated.values())

    @classmethod
    def _count_multi_category_products(cls, products) -> int:
        categories_by_code: dict[str, set[str]] = {}
        for product in products:
            code = cls._normalize_code(getattr(product, "code", ""))
            if not code:
                continue
            categories = categories_by_code.setdefault(code.casefold(), set())
            for category in str(getattr(product, "category", "") or "").split(","):
                normalized = category.strip().casefold()
                if normalized:
                    categories.add(normalized)
        return sum(
            1 for categories in categories_by_code.values() if len(categories) > 1
        )

    @staticmethod
    def _merge_categories(*categories) -> str:
        merged, seen = [], set()
        for value in categories:
            for category in str(value or "").split(","):
                normalized = category.strip()
                key = normalized.casefold()
                if normalized and key not in seen:
                    seen.add(key)
                    merged.append(normalized)
        return ", ".join(merged)

    @staticmethod
    def _value(obj, field):
        if isinstance(obj, dict):
            return obj.get(field)
        try:
            return obj[field]
        except (KeyError, TypeError, IndexError):
            return getattr(obj, field, None)
