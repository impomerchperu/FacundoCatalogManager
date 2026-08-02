from pathlib import Path

from scrapers.images.image_downloader import ImageDownloader


URL = (
    "https://stock.importacionesfacundo.com/"
    "wp-content/uploads/2026/04/"
    "FB-1812.webp"
)


downloader = ImageDownloader()


print("=" * 80)
print("IMAGE DOWNLOADER REAL")
print("=" * 80)


path = downloader.download(
    "FB-1812",
    URL,
)


print(
    "PATH:",
    path
)


assert path


file = Path(
    path
)


assert file.exists()


assert file.stat().st_size > 0


print(
    "SIZE:",
    file.stat().st_size,
    "bytes"
)


print()
print("OK")