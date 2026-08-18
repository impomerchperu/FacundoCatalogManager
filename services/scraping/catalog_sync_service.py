from typing import ClassVar

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
        """Sincroniza el catálogo exclusivamente mediante códigos reales."""
        del cleanup_generated
        result = SyncResult()
        raw_products = list(products)
        missing_code_products = [
            product
            for product in raw_products
            if not str(getattr(product, "code", "")).strip()
        ]
        for product in missing_code_products:
            result.missing_code += 1
            result.changes.append({
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
            })

        # Nunca se genera ni se asigna un código local para un producto
        # scrapeado sin código. Sin código no existe identidad confiable
        # para crear, actualizar o eliminar por coincidencia.
        prepared = [
            product
            for product in raw_products
            if str(getattr(product, "code", "")).strip()
        ]
        consolidated = self.consolidate_products(prepared)
        result.products_expected = max(int(expected_products or 0), 0)
        result.products_found = len(raw_products)
        result.products_unique = len(consolidated)
        result.processed = result.products_found
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
        }

        for product in consolidated:
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

        # La eliminación solo ocurre en un full sync autorizado por el
        # orquestador. Ese orquestador ya valida categorías, cobertura,
        # códigos y errores HTTP antes de llamar con prune_missing=True.
        coverage_complete = (
            expected_products > 0 and len(raw_products) == expected_products
        )
        prune_allowed = bool(prune_missing and coverage_complete)
        if prune_allowed:
            self._remove_missing_products(scraped_codes, result)

        result.finish()
        self.last_sync_result = result
        return result

    def sync_full_catalog(
        self,
        products,
        prune_missing: bool = True,
        expected_products: int = 0,
    ):
        """Sincroniza y elimina códigos locales ausentes en el scraping completo."""
        return self.sync(
            products,
            prune_missing=prune_missing,
            expected_products=expected_products,
        )

    def synchronize(self, products, prune_missing: bool = False):
        return self.sync(products, prune_missing=prune_missing)

    def _remove_missing_products(
        self,
        scraped_codes: set[str],
        result: SyncResult,
    ) -> None:
        """Elimina códigos locales que no aparezcan en el scraping completo."""
        normalized_scraped_codes = {code.casefold() for code in scraped_codes}
        for existing in self.repository.get_all():
            code = str(getattr(existing, "code", "")).strip()
            if not code or code.casefold() in normalized_scraped_codes:
                continue
            result.deleted += 1
            result.changes.append({
                "type": "DELETED",
                "code": code,
                "name": getattr(existing, "name", ""),
                "changes": [
                    {
                        "field": "code",
                        "label": "Código ausente en origen",
                        "old": code,
                        "new": "Eliminado",
                    }
                ],
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
