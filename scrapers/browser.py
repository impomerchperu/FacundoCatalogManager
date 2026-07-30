import requests


class Browser:

    def __init__(self, timeout=10):

        self.timeout = timeout


    def fetch(self, url):

        try:

            response = requests.get(
                url,
                timeout=self.timeout,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 "
                        "(Windows NT 10.0; Win64; x64)"
                    )
                }
            )

            response.raise_for_status()

            return response.text


        except requests.RequestException as error:

            raise Exception(
                f"Error al acceder a {url}: {error}"
            )