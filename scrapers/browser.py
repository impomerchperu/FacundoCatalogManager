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

        self._metrics_lock = threading.Lock()
        self._http_requests = 0
        self._http_successes = 0
        self._http_errors = 0
        self._http_retries = 0
        self._http_total_seconds = 0.0
        self._http_max_seconds = 0.0
        self._http_in_flight = 0
        self._http_max_in_flight = 0
        self._detail_http_requests = 0
        self._category_http_requests = 0
        self._other_http_requests = 0

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
            started = time.perf_counter()
            self._begin_request(url)

            try:
                response = session.get(
                    url,
                    headers=self.headers,
                    timeout=self.timeout,
                )

                if hasattr(response, "raise_for_status"):
                    response.raise_for_status()

                elapsed = time.perf_counter() - started
                self._finish_request(elapsed, success=True)

                if attempt:
                    self._record_retry()

                if hasattr(response, "text"):
                    return response.text
                else:
                    return response

            except requests.exceptions.RequestException as error:
                elapsed = time.perf_counter() - started
                self._finish_request(elapsed, success=False)
                last_error = error

                if attempt < self.max_retries - 1:
                    self._record_retry()
                    time.sleep(attempt + 1)

        if last_error:
            raise last_error

    def _begin_request(self, url):
        with self._metrics_lock:
            self._http_requests += 1
            self._http_in_flight += 1
            self._http_max_in_flight = max(
                self._http_max_in_flight,
                self._http_in_flight,
            )

            url_text = str(url)
            if "/producto/" in url_text:
                self._detail_http_requests += 1
            elif "/categoria-producto/" in url_text or "/tienda/" in url_text:
                self._category_http_requests += 1
            else:
                self._other_http_requests += 1

    def _finish_request(self, elapsed, success):
        with self._metrics_lock:
            self._http_in_flight = max(0, self._http_in_flight - 1)
            self._http_total_seconds += elapsed
            self._http_max_seconds = max(
                self._http_max_seconds,
                elapsed,
            )

            if success:
                self._http_successes += 1
            else:
                self._http_errors += 1

    def _record_retry(self):
        with self._metrics_lock:
            self._http_retries += 1

    def get_http_metrics(self):
        """Return accumulated HTTP timing and concurrency metrics."""
        with self._metrics_lock:
            return {
                "http_requests": self._http_requests,
                "http_successes": self._http_successes,
                "http_errors": self._http_errors,
                "http_retries": self._http_retries,
                "http_total_seconds": self._http_total_seconds,
                "http_max_seconds": self._http_max_seconds,
                "http_in_flight": self._http_in_flight,
                "http_max_in_flight": self._http_max_in_flight,
                "detail_http_requests": self._detail_http_requests,
                "category_http_requests": self._category_http_requests,
                "other_http_requests": self._other_http_requests,
            }

    def reset_http_metrics(self):
        """Reset HTTP metrics before a new full scraping run."""
        with self._metrics_lock:
            self._http_requests = 0
            self._http_successes = 0
            self._http_errors = 0
            self._http_retries = 0
            self._http_total_seconds = 0.0
            self._http_max_seconds = 0.0
            self._http_in_flight = 0
            self._http_max_in_flight = 0
            self._detail_http_requests = 0
            self._category_http_requests = 0
            self._other_http_requests = 0
