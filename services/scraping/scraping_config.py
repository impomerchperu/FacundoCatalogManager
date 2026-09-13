from dataclasses import dataclass, field

from config.scraping_config import MAX_RETRIES, REQUEST_TIMEOUT, STORE_URL


@dataclass
class ScrapingConfig:
    """
    Configuración de ejecución del motor de scraping.

    Los parámetros de transporte compartidos se toman de la configuración
    canónica de bajo nivel para evitar que existan valores divergentes.
    """

    catalog_url: str = STORE_URL

    source_name: str = "importacionesfacundo"

    images_folder: str = "data/images"

    download_images: bool = True

    incremental_sync: bool = True

    save_scraped_products: bool = True

    max_retries: int = MAX_RETRIES

    request_timeout: int = REQUEST_TIMEOUT

    enabled_categories: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.request_timeout <= 0:
            raise ValueError("request_timeout debe ser mayor que cero.")
        if self.max_retries <= 0:
            raise ValueError("max_retries debe ser mayor que cero.")

    def is_category_enabled(self, category: str) -> bool:
        """Determina si una categoría debe procesarse."""
        if not self.enabled_categories:
            return True
        return category in self.enabled_categories

    def enable_category(self, category: str) -> None:
        """Agrega una categoría al filtro."""
        if category not in self.enabled_categories:
            self.enabled_categories.append(category)

    def disable_category(self, category: str) -> None:
        """Elimina una categoría del filtro."""
        if category in self.enabled_categories:
            self.enabled_categories.remove(category)
