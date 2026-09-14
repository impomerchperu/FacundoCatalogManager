import threading
import time

import requests

from config.scraping_config import (
    DEFAULT_HEADERS,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    SCRAPING_HTTP_WORKERS,
)


class Browser:
    def __init__(
        self,
        session=None,
        request_timeout=None,
        max_retries=None,
        http_workers=None,
    ):
        self.session = session
        self._thread_local = threading.local()
        worker_count = (
            SCRAPING_HTTP_WORKERS
            if http_workers is None
            else int(http_workers)
        )
        if worker_count <= 0:
            raise ValueError("http_workers debe ser mayor que cero.")
        self._http_semaphore = threading.BoundedSemaphore(worker_count)

        if session is None:
            self.session = requests.Session()

        self.headers = DEFAULT_HEADERS
        self.timeout = (
            REQUEST_TIMEOUT if request_timeout is None else int(request_timeout)
        )
        self.max_retries = (
            MAX_RETRIES if max_retries is None else int(max_retries)
        )

        if self.timeout <= 0:
            raise ValueError("request_timeout debe ser mayor que cero.")
        if self.max_retries <= 0:
            raise ValueError("max_retries debe ser mayor que cero.")

        self._metrics_lock = threading.Lock()
        self._http_requests = 0
        self._http_successes = 0
        self._http_errors = 0
        self._http_terminal_errors = 0
        self._http_retries = 0
        self._http_total_seconds = 0.0
        self._http_max_seconds = 0.0
        self._http_in_flight = 0
        self._http_max_in_flight = 0
        self._detail_http_requests = 0
        self._category_http_requests = 0
        self._other_http_requests = 0
        self._latency_buckets = {
            "lt_0_5": 0,
            "0_5_1": 0,
            "1_2": 0,
            "2_5": 0,
            "5_10": 0,
            "gte_10": 0,
        }
        self._slowest_requests: list[tuple[float, str]] = []

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
            self._http_semaphore.acquire()
            started = time.perf_counter()
            self._begin_request(url)
            retry_after_release = False

            try:
                response = session.get(
                    url,
                    headers=self.headers,
                    timeout=self.timeout,
                )

                if hasattr(response, "raise_for_status"):
                    response.raise_for_status()
            except requests.exceptions.RequestException as error:
                elapsed = time.perf_counter() - started
                self._finish_request(elapsed, success=False, url=url)
                last_error = error

                if not self._is_retryable_error(error):
                    self._record_terminal_error()
                    raise

                if attempt < self.max_retries - 1:
                    self._record_retry()
                    retry_after_release = True
                else:
                    self._record_terminal_error()
            else:
                elapsed = time.perf_counter() - started
                self._finish_request(elapsed, success=True, url=url)

                if attempt:
                    self._record_retry()

                if hasattr(response, "text"):
                    return response.text
                return response
            finally:
                self._http_semaphore.release()

            if retry_after_release:
                time.sleep(attempt + 1)

        if last_error:
            raise last_error

    def post(self, url, data=None, headers=None):
        """POST using the same concurrency, retry and metrics pipeline as GET."""
        last_error = None
        session = self._get_session()
        request_headers = headers or self.headers

        for attempt in range(self.max_retries):
            self._http_semaphore.acquire()
            started = time.perf_counter()
            self._begin_request(url)
            retry_after_release = False

            try:
                response = session.post(
                    url,
                    data=data,
                    headers=request_headers,
                    timeout=self.timeout,
                )
                if hasattr(response, "raise_for_status"):
                    response.raise_for_status()
            except requests.exceptions.RequestException as error:
                elapsed = time.perf_counter() - started
                self._finish_request(elapsed, success=False, url=url)
                last_error = error

                if not self._is_retryable_error(error):
                    self._record_terminal_error()
                    raise

                if attempt < self.max_retries - 1:
                    self._record_retry()
                    retry_after_release = True
                else:
                    self._record_terminal_error()
            else:
                elapsed = time.perf_counter() - started
                self._finish_request(elapsed, success=True, url=url)
                if attempt:
                    self._record_retry()
                if hasattr(response, "text"):
                    return response.text
                return response
            finally:
                self._http_semaphore.release()

            if retry_after_release:
                time.sleep(attempt + 1)
