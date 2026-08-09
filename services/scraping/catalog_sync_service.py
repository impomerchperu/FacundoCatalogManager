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

        for product in products:
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
                field_changes = []
                for field in comparison["fields"]:
                    field_changes.append({
                        "field": field,
                        "label": self.FIELD_LABELS.get(field, field),
                        "old": self._value(existing, field),
                        "new": self._value(product, field),
                    })

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

    @staticmethod
    def _value(obj, field):
        if isinstance(obj, dict):
            return obj.get(field)
        try:
            return obj[field]
        except (KeyError, TypeError, IndexError):
            return getattr(obj, field, None)
