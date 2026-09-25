from config.runtime_paths import DATA_DIR

# Rutas canónicas del almacenamiento persistente de imágenes del catálogo.
# Se mantienen bajo DATA_DIR para que una instalación Windows no escriba
# dentro del bundle interno de PyInstaller.
IMAGE_ROOT = DATA_DIR / "data/images"
IMAGE_PRODUCTS_DIR = IMAGE_ROOT / "products"
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})
