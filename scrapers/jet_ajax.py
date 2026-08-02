import requests


class JetSmartAjax:
    """
    Cliente AJAX para JetSmartFilters + Bricks Query Loop
    """

    def __init__(self, ajax_url):
        self.ajax_url = ajax_url

        self.session = requests.Session()

        self.session.headers.update(
            {"User-Agent": ("Mozilla/5.0 Chrome/120 Safari/537.36")}
        )

    def get_page(self, query_id, settings, page=1):
        """
        Obtiene una página de productos mediante AJAX.
        """

        payload = {
            "action": "jet_smart_filters",
            "provider": "bricks-query-loop",
            "queryId": query_id,
            "jet_paged": page,
            "props": settings["props"],
            "settings": settings["settings"],
            "defaults": settings["defaults"],
            "query": settings["query"],
        }

        response = self.session.post(self.ajax_url, data=payload, timeout=30)

        response.raise_for_status()

        return response.text
