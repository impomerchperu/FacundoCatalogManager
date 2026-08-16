from typing import ClassVar

from models.scraping.sync_result import SyncResult


class CatalogSyncService:
    """Compara productos obtenidos contra el catálogo persistido."""

    FIELD_LABELS: ClassVar[dict[str, str]] = {
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

    def sync(self, products, prune_missing: bool = False):
        """Sincroniza productos y opcionalmente elimina los ausentes del origen."""
        result = SyncResult()
        consolidated = self.consolidate_products(products)
        scraped_codes = {
            str(product.code).strip()
            for product in consolidated
            if str(getattr(product, "code", "")).strip()
        }

        for product in consolidated:
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

        if prune_missing:
            self._remove_missing_products(scraped_codes, result)

        result.finish()
        return result

    def sync_full_catalog(self, products):
        """Sincroniza el catálogo completo y elimina productos ausentes del origen."""
        return self.sync(products, prune_missing=True)

    def synchronize(self, products, prune_missing: bool = False):
        return self.sync(products, prune_missing=prune_missing)

    def _remove_missing_products(
        self,
        scraped_codes: set[str],
        result: SyncResult,
    ) -> None:
        """Elimina del catálogo los productos que ya no aparecen en el origen."""
        for existing in self.repository.get_all():
            code = str(getattr(existing, "code", "")).strip()
            if not code or code in scraped_codes:
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

            existing = consolidated.get(code)
            if existing is None:
                consolidated[code] = product
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
