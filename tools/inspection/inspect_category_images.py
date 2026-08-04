import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.extractors.product_block_extractor import ProductBlockExtractor


URL = (
    "https://stock.importacionesfacundo.com/"
    "categoria-producto/jarros-mug/"
)


scraper = CategoryScraper(
    "https://stock.importacionesfacundo.com",
    extractor=ProductBlockExtractor(),
)


blocks = scraper.get_product_blocks(URL)


print("PRODUCTOS:", len(blocks))
print("=" * 80)


for block in blocks[:5]:

    print()
    print("PRODUCTO")
    print("-" * 80)

    print(
        block.get_text(
            " ",
            strip=True,
        )[:100]
    )

    print()
    print("IMÁGENES")

    for img in block.find_all("img"):

        print(
            "src:",
            img.get("src"),
        )

        print(
            "data-src:",
            img.get("data-src"),
        )

        print(
            "data-lazy:",
            img.get("data-lazy-src"),
        )

        print("-" * 40)