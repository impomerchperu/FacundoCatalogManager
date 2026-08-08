from services.scraping.scraping_factory import ScrapingFactory
from services.scraping.scraping_session import ScrapingSession


class ScrapingController:
    """
    Controlador encargado de ejecutar
    procesos completos de scraping.

    Coordina:

    GUI
      |
      v
    Controller
      |
      v
    ScrapingSession
      |
      v
    ScrapingRunner
    """

    def __init__(self):
        runner = ScrapingFactory.create_runner()

        history_repository = getattr(
            runner,
            "history_repository",
            None,
        )

        self.session = ScrapingSession(
            runner,
            history_repository,
        )

    def run_scraping(
        self,
        categories=None,
        progress_callback=None,
    ):
        """
        Ejecuta scraping manual
        sobre categorías recibidas.
        """

        return self.session.execute(
            categories=categories,
            progress_callback=progress_callback,
        )

    def run_full_scraping(
        self,
        progress_callback=None,
    ):
        """
        Ejecuta scraping completo.

        Obtiene categorías automáticamente
        mediante CategoryService.
        """

        return self.session.execute_all(
            progress_callback=progress_callback,
        )
