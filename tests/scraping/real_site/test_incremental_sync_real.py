import os

from models.scraping.scraped_product import ScrapedProduct
from scrapers.sync.sync_engine import SyncEngine

TEST_STORAGE = "data/scraping/products.json"


if os.path.exists(TEST_STORAGE):
    os.remove(TEST_STORAGE)


engine = SyncEngine()


products = [
    ScrapedProduct(
        source="test",
        code="TEST-001",
        name="Producto prueba",
        category="Testing",
        description="Producto inicial",
        stock=10,
        price_sample=5,
        price_hundred=100,
        price_thousand=900,
        image_url="imagen-v1.jpg",
    )
]


print("=" * 80)
print("PRIMERA SINCRONIZACION")
print("=" * 80)


result = engine.synchronize(products)


print("Nuevos:", len(result.new))

print("Actualizados:", len(result.updated))

print("Sin cambios:", len(result.unchanged))


print()


print("=" * 80)
print("SEGUNDA SINCRONIZACION")
print("=" * 80)


result = engine.synchronize(products)


print("Nuevos:", len(result.new))

print("Actualizados:", len(result.updated))

print("Sin cambios:", len(result.unchanged))


products_changed = [
    ScrapedProduct(
        source="test",
        code="TEST-001",
        name="Producto prueba",
        category="Testing",
        description="Producto inicial",
        stock=25,
        price_sample=5,
        price_hundred=100,
        price_thousand=900,
        image_url="imagen-v1.jpg",
    )
]


print()


print("=" * 80)
print("TERCERA SINCRONIZACION (CAMBIO STOCK)")
print("=" * 80)


result = engine.synchronize(products_changed)


print("Nuevos:", len(result.new))

print("Actualizados:", len(result.updated))

print("Sin cambios:", len(result.unchanged))
