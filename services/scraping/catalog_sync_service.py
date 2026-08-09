from typing import ClassVar

from models.scraping.sync_result import SyncResult


class CatalogSyncService:
    """Compara productos obtenidos durante el scraping contra sync_records."""

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

    def sync(self, products):
        result = SyncResult()
        consolidated = self._consolidate_products(products)

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

        result.finish()
        return result

    def synchronize(self, products):
        return self.sync(products)

    @classmethod
    def _consolidate_products(cls, products):
        consolidated = {}
        for product in products:
            code = str(getattr(product, "code", "")).strip()
            if not code:
                continue
            existing = consolidated.get(code)
            if existing is None:
                consolidated[code] = product
                continue

            categories = [
                item.strip()
                for item in str(getattr(existing, "category", "")).split(",")
                if item.strip()
            ]
            incoming = [
                item.strip()
                for item in str(getattr(product, "category", "")).split(",")
                if item.strip()
            ]
            existing.category = ", ".join(dict.fromkeys(categories + incoming))

            colors = list(getattr(existing, "colors", []))
            colors.extend(getattr(product, "colors", []))
            existing.colors = list(dict.fromkeys(
                str(color).strip() for color in colors if str(color).strip()
            ))

            color_stock = dict(getattr(existing, "color_stock", {}))
            for color, stock in getattr(product, "color_stock", {}).items():
                color_stock[color] = max(color_stock.get(color, 0), int(stock))
            existing.color_stock = color_stock

        return list(consolidated.values())

    @staticmethod
    def _value(obj, field):
        if isinstance(obj, dict):
            return obj.get(field)
        try:
            return obj[field]
        except (KeyError, TypeError, IndexError):
            return getattr(obj, field, None)
