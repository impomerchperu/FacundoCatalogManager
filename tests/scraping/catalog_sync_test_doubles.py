class InMemoryCatalogRepository:
    """Repositorio mínimo para probar CatalogSyncService sin la API legacy."""

    def __init__(self):
        self.records = {}

    def get(self, code):
        return self.records.get(str(code).strip().upper())

    def save(self, product):
        self.records[str(product.code).strip().upper()] = product
        return product

    def get_all(self):
        return list(self.records.values())

    def delete_by_code(self, code):
        self.records.pop(str(code).strip().upper(), None)
