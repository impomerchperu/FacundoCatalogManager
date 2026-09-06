from __future__ import annotations

from services.scraping.scraping_factory import (
    ScrapingFactory as CanonicalScrapingFactory,
)


class ScrapingFactory:
    """Fachada de compatibilidad para la fábrica canónica de scraping."""

    @staticmethod
    def create():
        """Mantiene la API histórica y devuelve el runner canónico."""
        return CanonicalScrapingFactory.create_runner()
