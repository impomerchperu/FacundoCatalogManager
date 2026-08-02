from pathlib import Path

from scrapers.images.image_manager import ImageManager


manager = ImageManager()


print("=" * 80)
print("IMAGE MANAGER REAL")
print("=" * 80)


result = manager.process(
    "FB-1812",
    "https://stock.importacionesfacundo.com/wp-content/uploads/2026/04/FB-1812.webp",
)


print(
    "PATH:",
    result["image_path"]
)


print(
    "HASH:",
    result["image_hash"]
)


assert result["image_path"]


assert Path(
    result["image_path"]
).exists()


assert result["image_hash"]


print()
print("OK")