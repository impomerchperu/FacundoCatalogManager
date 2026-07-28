import requests


class Browser:
    def __init__(self):

        self.session = requests.Session()

        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def get(self, url):

        response = self.session.get(url, timeout=30)

        response.raise_for_status()

        return response.text
