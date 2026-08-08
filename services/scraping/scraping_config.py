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

    max_retries: int = 3

    request_timeout: int = 20

    enabled_categories: list[str] = field(
        default_factory=list,
    )

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
