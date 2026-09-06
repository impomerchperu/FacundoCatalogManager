from dataclasses import dataclass, field


@dataclass
class ScrapingConfig:
    """
    Configuración central del motor scraping.

    Contiene parámetros generales utilizados
    por los servicios de extracción,
    sincronización e imágenes.
    """

    catalog_url: str = (
        "https://stock.importacionesfacundo.com/tienda/"
    )

    source_name: str = (
        "importacionesfacundo"
    )

    images_folder: str = (
        "data/images"
    )

    download_images: bool = True

    incremental_sync: bool = True

    save_scraped_products: bool = True

    # Keep defaults aligned with the effective transport defaults so wiring the
    # high-level configuration does not change existing runtime behavior.
    max_retries: int = 2

    request_timeout: int = 10

    enabled_categories: list[str] = field(
        default_factory=list,
    )

    def __post_init__(self) -> None:
        if self.request_timeout <= 0:
            raise ValueError("request_timeout debe ser mayor que cero.")
        if self.max_retries <= 0:
            raise ValueError("max_retries debe ser mayor que cero.")

    def is_category_enabled(
        self,
        category: str,
    ) -> bool:
        """
        Determina si una categoría debe procesarse.

        Si no hay categorías configuradas,
        procesa todas.
        """

        if not self.enabled_categories:
            return True

        return category in self.enabled_categories

    def enable_category(
        self,
        category: str,
    ):
        """
        Agrega una categoría al filtro.
        """

        if category not in self.enabled_categories:
            self.enabled_categories.append(
                category
            )

    def disable_category(
        self,
        category: str,
    ):
        """
        Elimina una categoría del filtro.
        """

        if category in self.enabled_categories:
            self.enabled_categories.remove(
                category
            )
