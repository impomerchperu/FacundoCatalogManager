from pathlib import Path

from config.runtime_paths import DATA_DIR

# Fuente canónica: todas las imágenes de cada producto viven juntas en
# data/images/products/<CODIGO>/. IMAGE_GALLERY_DIR queda solo para migrar
# instalaciones antiguas; el scraper ya no escribe imágenes ahí.
IMAGE_ROOT = DATA_DIR / "data/images"
IMAGE_PRODUCTS_DIR = IMAGE_ROOT / "products"
IMAGE_GALLERY_DIR = IMAGE_ROOT / "gallery"
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})


def safe_image_code(code: object) -> str:
    """Return a filesystem-safe product code."""
    value = str(code or "").strip()
    return "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in value
    )


def product_image_directory(
    code: object,
    *,
    root: str | Path = IMAGE_PRODUCTS_DIR,
) -> Path:
    """Return the canonical folder containing all images for one product."""
    return Path(root) / safe_image_code(code)
