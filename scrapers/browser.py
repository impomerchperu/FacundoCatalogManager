import time

import requests

from config.scraping_config import (
    DEFAULT_HEADERS,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
)


class Browser:

    def __init__(
        self,
        session=None
    ):

        self.session = session or requests.Session()

        self.headers = DEFAULT_HEADERS

        self.timeout = REQUEST_TIMEOUT

        self.max_retries = MAX_RETRIES


    def fetch(
        self,
        url
    ):

        return self.get(url)


    def get(
        self,
        url
    ):

        last_error = None


        for attempt in range(
            self.max_retries
        ):

            try:

                response = self.session.get(
                    url,
                    headers=self.headers,
                    timeout=self.timeout
                )


                if hasattr(
                    response,
                    "raise_for_status"
                ):
                    response.raise_for_status()


                if hasattr(
                    response,
                    "text"
                ):
                    return response.text


                return response


            except Exception as error:

                last_error = error


                if attempt < self.max_retries - 1:

                    time.sleep(
                        attempt + 1
                    )


        raise last_error