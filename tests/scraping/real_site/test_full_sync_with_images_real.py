from models.scraping.scraped_product import ScrapedProduct
from scrapers.sync.sync_engine import SyncEngine

print("=" * 80)
print("FULL SYNC WITH IMAGES")
print("=" * 80)


product = ScrapedProduct(
    source="importacionesfacundo",
    code="FB-1812",
    name="Taza de Plástico",
    image_url=(
        "https://stock.importacionesfacundo.com/wp-content/uploads/2026/04/FB-1812.webp"
    ),
)


engine = SyncEngine()


result = engine.synchronize([product])


print()
print("RESULTADO")
print("=" * 80)


print("Nuevos:", len(result.new))

print("Actualizados:", len(result.updated))

print("Sin cambios:", len(result.unchanged))


saved = engine.storage.load()


print()
print("PRODUCTO GUARDADO")
print("=" * 80)


print(saved[0])


assert saved[0]["image_path"] != ""

assert hasattr(saved[0], "image_hash")


print()
print("OK")
