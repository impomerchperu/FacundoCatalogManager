import threading
import time

import requests

from config.scraping_config import (
    DEFAULT_HEADERS,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
)


class Browser:
    def __init__(self, session=None):
        self.session = session
        self._thread_local = threading.local()

        if session is None:
            self.session = requests.Session()

        self.headers = DEFAULT_HEADERS
        self.timeout = REQUEST_TIMEOUT
        self.max_retries = MAX_RETRIES

    def _get_session(self):
        """Return a session safe for the current scraping worker."""
        if self.session is not None and not getattr(
            self,
            "_use_thread_sessions",
            False,
        ):
            return self.session

        session = getattr(self._thread_local, "session", None)
        if session is None:
            session = requests.Session()
            self._thread_local.session = session
        return session

    def enable_thread_sessions(self):
        """Use one requests session per worker thread for concurrent scraping."""
        self._use_thread_sessions = True

    def fetch(self, url):
        return self.get(url)

    def get(self, url):
        last_error = None
        session = self._get_session()

        for attempt in range(self.max_retries):
            try:
                response = session.get(
                    url,
                    headers=self.headers,
                    timeout=self.timeout,
                )

                if hasattr(response, "raise_for_status"):
                    response.raise_for_status()

                if hasattr(response, "text"):
                    return response.text
                else:
                    return response

            except requests.exceptions.RequestException as error:
                last_error = error

                if attempt < self.max_retries - 1:
                    time.sleep(attempt + 1)

        if last_error:
            raise last_error
