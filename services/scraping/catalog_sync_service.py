import hashlib
import re
from typing import ClassVar
from urllib.parse import urlparse

from models.scraping.sync_result import SyncResult


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

    def sync(
        self,
        products,
        prune_missing: bool = False,
        cleanup_generated: bool = True,
        expected_products: int = 0,
    ):
        """Sincroniza productos y opcionalmente reconcilia códigos ausentes."""
        result = SyncResult()
        prepared = self._prepare_products(products)
        consolidated = self.consolidate_products(prepared)
        result.products_expected = max(int(expected_products or 0), 0)
        result.products_found = len(prepared)
        result.products_unique = len(consolidated)
        result.duplicate_occurrences = max(
            result.products_found - result.products_unique,
            0,
        )
        result.products_multiple_categories = self._count_multi_category_products(
            prepared,
        )

        scraped_codes = {
            str(product.code).strip().casefold()
            for product in consolidated
            if str(getattr(product, "code", "")).strip()
            and not getattr(product, "_generated_code", False)
        }

        for product in consolidated:
            if getattr(product, "_generated_code", False):
                result.generated += 1
                result.changes.append({
                    "type": "CODE_GENERATED",
                    "code": product.code,
                    "name": product.name,
                    "changes": [
                        {
                            "field": "code",
                            "label": "Código generado",
                            "old": "Sin código",
                            "new": product.code,
                        }
                    ],
                })
                continue

            result.increment_processed()
            existing = self.repository.get(product.code)

            if existing is None:
                result.created += 1
                result.changes.append({
                    "type": "NEW",
                    "code": product.code,
                    "name": product.name,
                    "changes": [],
                })
                self.repository.save(product)
                continue

            product.category = self._merge_categories(
                existing.category,
                product.category,
            )

            comparison = self.diff_service.compare(existing, product)
            if comparison["changed"]:
                result.updated += 1
                field_changes = [
                    {
                        "field": field,
                        "label": self.FIELD_LABELS.get(field, field),
                        "old": self._value(existing, field),
                        "new": self._value(product, field),
                    }
                    for field in comparison["fields"]
                ]
                result.changes.append({
                    "type": "UPDATED",
                    "code": product.code,
                    "name": product.name,
                    "changes": field_changes,
                })
                self.repository.save(product)
                continue

            result.unchanged += 1

        if cleanup_generated or prune_missing:
            self._remove_missing_products(
                scraped_codes,
                result,
                prune_real_codes=prune_missing,
            )

        result.finish()
        self.last_sync_result = result
        return result

    def sync_full_catalog(
        self,
        products,
        prune_missing: bool = True,
        expected_products: int = 0,
    ):
        """Sincroniza el catálogo y limpia códigos locales no presentes en origen."""
        return self.sync(
            products,
            prune_missing=prune_missing,
            cleanup_generated=True,
            expected_products=expected_products,
        )

    def synchronize(self, products, prune_missing: bool = False):
        return self.sync(products, prune_missing=prune_missing)

    def _prepare_products(self, products):
        """Garantiza que cada producto tenga un código único y auditable."""
        prepared = []
        used_codes: set[str] = set()
        generated_by_source: dict[str, str] = {}
        for product in products:
            code = str(getattr(product, "code", "")).strip()
            if not code:
                url = str(getattr(product, "url", "")).strip()
                name = str(getattr(product, "name", "")).strip()
                source_key = (url or name).casefold()
                code = generated_by_source.get(source_key, "")
                if not code:
                    code = self._generate_code(product, used_codes)
                    generated_by_source[source_key] = code
                product.code = code
                product._generated_code = True
            used_codes.add(code.casefold())
            prepared.append(product)
        return prepared

    @staticmethod
    def _generate_code(product, used_codes: set[str]) -> str:
        """Genera un código estable, legible y determinista para revisión manual."""
        url = str(getattr(product, "url", "")).strip()
        name = str(getattr(product, "name", "")).strip()
        parsed_path = urlparse(url).path.strip("/") if url else ""
        source = parsed_path.split("/")[-1] or name or "producto"
        slug = re.sub(r"[^A-Za-z0-9]+", "-", source).strip("-").upper()
        slug = slug[:48].strip("-") or "PRODUCTO"
        digest_source = url or name or source
        digest = hashlib.sha1(
            digest_source.casefold().encode("utf-8"),
        ).hexdigest()[:8].upper()
        base = f"AUTO-{slug}-{digest}"
        candidate = base
        suffix = 2
        while candidate.casefold() in used_codes:
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def _remove_missing_products(
        self,
        scraped_codes: set[str],
        result: SyncResult,
        prune_real_codes: bool,
    ) -> None:
        """Elimina AUTO siempre y códigos reales solo con extracción completa."""
        normalized_scraped_codes = {code.casefold() for code in scraped_codes}
        for existing in self.repository.get_all():
            code = str(getattr(existing, "code", "")).strip()
            if not code:
                continue
            normalized_code = code.casefold()
            is_generated = normalized_code.startswith("auto-")
            if normalized_code in normalized_scraped_codes:
                continue
            if not is_generated and not prune_real_codes:
                continue

            result.deleted += 1
            result.changes.append({
                "type": "DELETED",
                "code": code,
                "name": getattr(existing, "name", ""),
                "changes": [],
            })
            self.repository.delete_by_code(code)

    @classmethod
    def consolidate_products(cls, products):
        """Consolida por código antes de comparar o guardar el catálogo."""
        consolidated = {}

        for product in products:
            code = str(getattr(product, "code", "")).strip()
            if not code:
                continue

            existing = consolidated.get(code.casefold())
            if existing is None:
                consolidated[code.casefold()] = product
                continue

            existing.category = cls._merge_categories(
                existing.category,
                product.category,
            )

            colors = list(getattr(existing, "colors", []))
            colors.extend(getattr(product, "colors", []))
            existing.colors = list(
                dict.fromkeys(
                    str(color).strip()
                    for color in colors
                    if str(color).strip()
                )
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
                    color_stock.get(normalized_color, 0),
                    normalized_stock,
                )
            existing.color_stock = color_stock

            if not getattr(existing, "description", "") and getattr(
                product,
                "description",
                "",
            ):
                existing.description = product.description
            if not getattr(existing, "image_url", "") and getattr(
                product,
                "image_url",
                "",
            ):
                existing.image_url = product.image_url

        return list(consolidated.values())

    @classmethod
    def _count_multi_category_products(cls, products) -> int:
        """Cuenta códigos que aparecen en más de una categoría distinta."""
        categories_by_code: dict[str, set[str]] = {}
        for product in products:
            code = str(getattr(product, "code", "")).strip()
            if not code:
                continue
            categories = categories_by_code.setdefault(code.casefold(), set())
            raw_categories = str(getattr(product, "category", "") or "")
            for category in raw_categories.split(","):
                normalized = category.strip().casefold()
                if normalized:
                    categories.add(normalized)
        return sum(
            1
            for categories in categories_by_code.values()
            if len(categories) > 1
        )

    @staticmethod
    def _merge_categories(*categories) -> str:
        """Une categorías sin duplicarlas y conserva su orden de aparición."""
        merged: list[str] = []
        seen: set[str] = set()

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
