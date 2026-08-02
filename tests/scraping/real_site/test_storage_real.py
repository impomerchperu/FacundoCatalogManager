from scrapers.storage.product_storage import ProductStorage
from scrapers.storage.product_comparator import ProductComparator


storage = ProductStorage()


old = storage.load()


print("="*80)
print("PRODUCTOS GUARDADOS")
print("="*80)

print(
    len(old)
)


storage.save([])


print(
    "Storage OK"
)